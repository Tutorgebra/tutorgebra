import asyncio
import json
import logging
import uuid
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse

from app.security import (
    get_client_ip,
    check_rate_limit_memory,
    read_json_body,
    get_str_field,
    ALLOWED_GTTS_VOICES,
    ALLOWED_EDGE_VOICES,
    ALLOWED_MODELS,
    MAX_BODY_BYTES,
    MAX_IMAGE_B64_CHARS,
    MAX_PROMPT_CHARS,
    MAX_API_KEY_CHARS,
    MAX_SHORT_FIELD_CHARS,
)
from app.redis_rate_limit import check_rate_limit_redis
from app.agent import generate_geogebra_script, route_exercise, sanitize_geogebra_command
from app.lesson_token import sign_lesson, verify_lesson
from app.placeholders import placeholder_names, fill_placeholders, replace_unfilled_placeholders
from app.arithmetic_check import check_names
from app.provider import ProviderError, ERROR_DETAILS as PROVIDER_ERROR_DETAILS
from app.bot import (
    _generate_single_edge_audio,
    _generate_single_audio,
    global_tts_semaphore,
)

logger = logging.getLogger('TutorGebraExercises')

router = APIRouter(prefix="/api", tags=["exercises"])

# A lesson takes two requests: /api/run generates it and ends with an "evaluate" event; the browser runs
# its commands in GeoGebra (static/ggb_evaluate.js) and sends the real values to /api/voice, which fills
# the {name} placeholders of the speeches and synthesizes the audio.
MAX_FAILED_COMMANDS = 200
# Progress messages are English; static/i18n.js (translateProgress) translates them
REASONING_PROGRESS = "Reasoning exercise detected: it is solved with Claude Sonnet 5.5 and may take up to a minute..."


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def _with_checks(steps: list, checks: list) -> list:
    """The lesson's steps followed by the reviewer's check commands, as steps (only for evaluating them)."""
    return steps + [{"command": c, "speech": ""} for c in checks]


async def _check_client(req: Request, bucket: str = "") -> str:
    """Bot header and rate limit, shared by both endpoints. Returns the client IP."""
    # Get real user IP from the trusted proxy hop (see get_client_ip)
    client_ip = get_client_ip(req)

    # Bot Protection: Check for custom header to block simple curl/script bots
    client_header = req.headers.get("x-tutor-client")
    if client_header != "TutorGebraWeb":
        logger.warning(f"Bot blocked. Missing or invalid client header from IP: {client_ip}")
        raise HTTPException(status_code=403, detail="Forbidden. Please use the official web interface.")

    # Try to use Redis Global Rate Limiting first
    redis_handled = await check_rate_limit_redis(client_ip, limit=5, window=60, bucket=bucket)

    # If Redis is disconnected or fails, fallback to local memory limit
    if not redis_handled:
        check_rate_limit_memory(client_ip, bucket=bucket)
    return client_ip


@router.post("/run")
async def run_exercise(req: Request):
    client_ip = await _check_client(req)

    body = await read_json_body(req, MAX_BODY_BYTES)
    prompt = get_str_field(body, "prompt", MAX_PROMPT_CHARS, default="")
    api_key = get_str_field(body, "api_key", MAX_API_KEY_CHARS, default="")
    voice = get_str_field(body, "voice", MAX_SHORT_FIELD_CHARS, default="auto")
    edge_voice = get_str_field(body, "edge_voice", MAX_SHORT_FIELD_CHARS)
    image_b64 = get_str_field(body, "image", MAX_IMAGE_B64_CHARS)
    selected_model = get_str_field(body, "selected_model", MAX_SHORT_FIELD_CHARS) or "auto"

    if not prompt.strip() and not image_b64:
        raise HTTPException(status_code=400, detail="Debes ingresar un ejercicio o adjuntar una imagen.")

    # Fix #2: only allow known models (prevents arbitrary/expensive models on the server key)
    if not isinstance(selected_model, str) or selected_model not in ALLOWED_MODELS:
        logger.warning(f"Rejected unsupported model from IP {client_ip}: {selected_model!r:.100}")
        raise HTTPException(status_code=400, detail="Modelo no soportado.")

    # Fix #1: resolve gTTS (lang, tld) strictly from the allowlist (prevents SSRF via tld)
    gtts_override = None
    if voice and voice != "auto":
        if not isinstance(voice, str) or voice not in ALLOWED_GTTS_VOICES:
            logger.warning(f"Rejected unsupported voice from IP {client_ip}: {voice!r:.100}")
            raise HTTPException(status_code=400, detail="Voz no soportada.")
        gtts_override = ALLOWED_GTTS_VOICES[voice]

    # Fix #3: only allow the Edge TTS voices offered by the UI (prevents SSML injection)
    if edge_voice and edge_voice not in ALLOWED_EDGE_VOICES:
        logger.warning(f"Rejected unsupported edge voice from IP {client_ip}: {edge_voice!r:.100}")
        raise HTTPException(status_code=400, detail="Voz no soportada.")

    async def event_stream():
        try:
            yield _sse({'status': 'progress', 'message': 'Thinking about the mathematical solution...', 'percent': 10})

            # The generator is synchronous (OpenRouter calls), so it runs in a thread. The routing goes first so
            # the student is told, before the long wait, that a reasoning exercise goes to Claude Sonnet
            routing = await asyncio.to_thread(route_exercise, prompt, api_key, image_b64, selected_model)
            if routing["kind"] == "reasoning":
                yield _sse({'status': 'progress', 'message': REASONING_PROGRESS, 'percent': 15})
            data = await asyncio.to_thread(generate_geogebra_script, prompt, api_key, image_b64, selected_model, routing)
            raw_steps = data.get("steps", [])
            if isinstance(raw_steps, dict):
                raw_steps = [raw_steps]
            elif not isinstance(raw_steps, list):
                raw_steps = []

            steps = []
            for s in raw_steps:
                if isinstance(s, dict):
                    cmd = sanitize_geogebra_command(s.get("command", ""))
                    speech = s.get("speech", "")
                    steps.append({"command": cmd, "speech": speech if isinstance(speech, str) else ""})
                elif isinstance(s, str):
                    steps.append({"command": "", "speech": s})

            lang = data.get("language", "en")
            tld = "com"
            # lang/tld come only from the server-side allowlist, never from raw user text
            if gtts_override:
                lang, tld = gtts_override

            # The reviewer's checks (app/checker.py) are evaluated in GeoGebra with the lesson but never played
            checks = [c for c in data.get("_checks", []) if isinstance(c, str)]

            # Everything /api/voice needs travels signed, so it only ever synthesizes lessons generated here
            lesson = {
                "language": data.get("language", "en"),
                "steps": steps,
                "checks": checks,
                "meta": data.get("_meta", {}),
                "tts": {"lang": lang, "tld": tld, "edge_voice": edge_voice or None},
            }
            yield _sse({
                'status': 'evaluate',
                'token': sign_lesson(lesson),
                # after the lesson's commands come the reviewer's, which may use the lesson's values
                'commands': [s["command"] for s in steps] + checks,
                # the placeholders to fill, plus the checks, so the ones only GeoGebra can compute get logged
                'names': list(dict.fromkeys(placeholder_names(lesson) + check_names(_with_checks(steps, checks)))),
                'percent': 30,
            })
        except ProviderError as exc:
            # The model provider failed (no credit, rate limit, timeout, cut answer...): the UI explains the code
            logger.warning(f"Provider error for IP {client_ip}: {exc.code} ({exc})")
            if not await req.is_disconnected():
                yield _sse({'status': 'error', 'code': exc.code, 'detail': PROVIDER_ERROR_DETAILS[exc.code]})
        except Exception:
            # Log the real error (with traceback) server-side, return a generic message to the client
            logger.exception(f"Critical error in bot execution for IP {client_ip}")
            if not await req.is_disconnected():
                yield _sse({'status': 'error', 'detail': 'No se pudo generar la lección. Inténtalo de nuevo en unos minutos.'})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/voice")
async def synthesize_voice(req: Request):
    client_ip = await _check_client(req, bucket="voice")

    body = await read_json_body(req, MAX_BODY_BYTES)
    lesson = verify_lesson(body.get("token"))
    if lesson is None or not isinstance(lesson.get("steps"), list):
        raise HTTPException(status_code=400, detail="La lección caducó o no es válida. Genérala de nuevo.")
    steps = [s for s in lesson["steps"] if isinstance(s, dict)]
    lesson["steps"] = steps
    # Values GeoGebra computed in the browser: only numbers and [x, y] pairs are used (see app/placeholders.py)
    values = body.get("values") if isinstance(body.get("values"), dict) else {}
    failed = body.get("failed") if isinstance(body.get("failed"), list) else []
    failed = sorted({i for i in failed[:MAX_FAILED_COMMANDS]
                     if isinstance(i, int) and not isinstance(i, bool) and 0 <= i < len(steps)})

    async def event_stream():
        try:
            session_id = str(uuid.uuid4())

            # Commands GeoGebra rejected in the browser are only logged (otherwise they are invisible). They are
            # not removed: with error dialogs off a failed command shows nothing, while removing a false
            # positive would break the lesson (a ZoomIn or SetVisibleInView that did work)
            if failed:
                rejected = {i + 1: steps[i].get("command", "") for i in failed}
                logger.warning(f"GeoGebra rejected these lesson commands in the browser (step: command): {rejected}")

            # Checks the server could not evaluate (they use Root, Intersect...) as GeoGebra computed them: 0 is false.
            # Generation is over, so they are only logged
            checks = [c for c in lesson.get("checks") or [] if isinstance(c, str)]
            false_checks = [name for name in check_names(_with_checks(steps, checks)) if values.get(name) == 0]
            if false_checks:
                logger.warning(f"GeoGebra computed these lesson checks as false: {false_checks}")
            # The student is warned if any check is false, whether the server found it while generating (signed
            # in the lesson) or GeoGebra did in the browser. The browser can add warnings but not remove them.
            meta = dict(lesson.get("meta") or {})
            signed_failed = meta.get("failed_checks") if isinstance(meta.get("failed_checks"), list) else []
            meta["failed_checks"] = list(dict.fromkeys(signed_failed + false_checks))

            unfilled = fill_placeholders(lesson, values, keys=("speech",))
            if unfilled:
                logger.warning(f"Placeholders with no value from GeoGebra or the server: {unfilled}")
            replace_unfilled_placeholders(lesson, keys=("speech",))

            yield _sse({'status': 'progress', 'message': f'Lesson generated ({len(steps)} steps). Synthesizing teacher voice...', 'percent': 35})

            tts = lesson.get("tts") if isinstance(lesson.get("tts"), dict) else {}
            edge_voice = tts.get("edge_voice")
            tasks = []
            if edge_voice:
                edge_state = {}  # shared by this request's steps: stops calling Edge after a 403
                for i, step in enumerate(steps):
                    tasks.append(_generate_single_edge_audio(step, edge_voice, session_id, i, edge_state))
            else:
                lang, tld = tts.get("lang", "en"), tts.get("tld", "com")

                async def bounded_gtts_audio(s, idx):
                    async with global_tts_semaphore:
                        return await asyncio.to_thread(_generate_single_audio, s, lang, tld, session_id, idx)

                for i, step in enumerate(steps):
                    tasks.append(bounded_gtts_audio(step, i))

            completed = 0
            total = len(tasks)
            for coro in asyncio.as_completed(tasks):
                if await req.is_disconnected():
                    logger.info("Client disconnected. Aborting audio synthesis.")
                    break

                await coro
                completed += 1
                percent = 35 + int((completed / total) * 65)

                # Check disconnect again before yielding
                if await req.is_disconnected():
                    break

                yield _sse({'status': 'progress', 'message': f'Synthesizing audio step {completed}/{total}...', 'percent': percent})

            if not await req.is_disconnected():
                yield _sse({'status': 'done', 'steps': steps, 'session_id': session_id, 'meta': meta})
        except Exception:
            logger.exception(f"Critical error synthesizing the voice for IP {client_ip}")
            if not await req.is_disconnected():
                yield _sse({'status': 'error', 'detail': 'No se pudo generar la voz de la lección. Inténtalo de nuevo en unos minutos.'})

    return StreamingResponse(event_stream(), media_type="text/event-stream")
