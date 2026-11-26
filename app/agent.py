import os
import re
import copy
import json
import logging
import base64
from openrouter import OpenRouter

from app.geogebra_commands import (
    find_unknown_commands, build_retry_note, blank_unknown_commands, hide_restricted_function_sources,
    lesson_draws_something, build_drawing_retry_note,
)
from app.prompt_modules import build_system_prompt
from app.checker import write_checks
from app.provider import (
    ProviderError, classify_provider_error, completion_limits, is_provider_error, log_usage, response_problem,
)

LESSON_MAX_TOKENS = 2500  # output for the lesson itself; models that reason get their own budget on top
EXPLAIN_LESSON_MAX_TOKENS = 6000  # "Explain more" lessons: 3 to 5 sentences per step plus an opening and a closing step
# Sent with the exercise when "Explain more" is on. The module alone was not enough: in a 21-step lesson
# Claude Sonnet kept the one-sentence limit of core.md, which comes first in the system prompt
EXPLAIN_NOTE = (
    "(CRITICAL: EXPLAIN MORE MODE IS ON. Follow the section 'Explain More Mode' of the system prompt: the FIRST "
    "step is a plan with an empty command; every step that applies a formula or a decision has 3 to 5 sentences "
    "(what we do, why, what each term means, what the result means); the LAST step is a closing with an empty "
    "command. The one-sentence limit of SPEECH LENGTH does NOT apply, however many steps the lesson has.)"
)


class GenerationCancelled(Exception):
    """The student left (the browser disconnected): the remaining calls for this lesson are not worth paying for."""
from app.arithmetic_check import (
    find_unconfirmed_results, build_arithmetic_retry_note, format_value, find_failed_checks, build_checks_retry_note,
)
from app.placeholders import (
    find_invalid_placeholders, fill_placeholders, replace_unfilled_placeholders, build_placeholder_retry_note,
)

logger = logging.getLogger('TutorGebraAgent')

# A string argument in single quotes: right after "(" or "," and right before "," or ")". The apostrophe
# of a derivative (funcF'(x)) follows a name, so it never matches.
_SINGLE_QUOTED_ARG_RE = re.compile(r"(?<=[(,])(\s*)'([^'\"\n]*)'(?=\s*[,)])")
# "name = <something> = <something>": the first '=' of the right side is a lone one (not part of <=, >=, ==, !=)
_EQUATION_ASSIGNMENT_RE = re.compile(r'^([a-zA-Z][a-zA-Z0-9]*)\s*=\s*([^=]*?(?<![<>!=])=(?!=).*)$')


def sanitize_geogebra_command(cmd: str) -> str:
    """Fix syntax errors in GeoGebra commands, such as double equals in equation naming."""
    if not cmd or not isinstance(cmd, str):
        return ""
    cmd = cmd.strip()
    # GeoGebra strings need double quotes: Text('EOQ', P) opens an error popup, Text("EOQ", P) works
    cmd = _SINGLE_QUOTED_ARG_RE.sub(r'\1"\2"', cmd)
    # GeoGebra equation syntax: equations (lines, conics, curves) MUST use a colon ':' to assign a label,
    # NOT double equals like 'line1 = y = x - 1' or 'circ1 = x^2 + y^2 = 16'. Only a lone '=' counts: a check
    # such as 'checkStation1 = station1Time <= taktTime' (<=, >=, ==, !=) must stay an assignment.
    m = _EQUATION_ASSIGNMENT_RE.match(cmd)
    if m:
        return f"{m.group(1)}: {m.group(2)}"
    return cmd


# --- Routing: which model solves the exercise ---------------------------------------------------------
# Auto mode classifies the exercise with a cheap gpt-4o-mini call (which also reads the photo, if any):
# formula exercises go to gpt-4o; reasoning exercises, where gpt-4o kept choosing a wrong method (line
# balancing, optimization, scheduling...), go straight to Claude Sonnet 5.5, which reasons before answering.
# Each list is an OpenRouter fallback list: the second model answers if the first one's provider fails.
FORMULA_MODELS = ['openai/gpt-4o', 'anthropic/claude-sonnet-5.5']
REASONING_MODELS = ['anthropic/claude-sonnet-5.5', 'openai/gpt-4o']
CLASSIFIER_MODEL = 'openai/gpt-4o-mini'

CLASSIFIER_PROMPT = """You classify math exercises for a tutor. Read the user's request (and the image, if any).
1. If there is an image, copy all its text and math into "extracted_text"; otherwise leave it "".
2. Decide the kind of exercise:
- "formula": the answer comes from putting the given data into known formulas, step by step, with no decision to make. Examples: EOQ, OEE, break-even point, compound interest, standard time, productivity, learning curve, queue formulas, areas, perimeters and volumes, statistics of a data list (mean, median, deviation), derivatives and integrals of a given function, unit conversions, drawing a given figure or graph.
- "reasoning": the solution requires deciding, grouping, ordering, searching or optimizing, or it must satisfy conditions that have to be checked. Examples: line balancing (grouping tasks into stations), linear programming or any optimization with constraints, sequencing and scheduling (Johnson's rule), assignment, critical path (CPM/PERT), period-by-period calculations (forecasts, loan balances, inventory month by month), proofs, word problems with several conditions to combine.
When in doubt, choose "reasoning".
Return EXACTLY this JSON: {"extracted_text": "...", "kind": "formula" | "reasoning"}"""


def _openrouter_client(api_key: str = ""):
    final_api_key = api_key.strip() if api_key else os.environ.get("OPENROUTER_API_KEY")
    if not final_api_key:
        raise ValueError("OpenRouter API Key is missing. Please provide one in the UI or configure the server with OPENROUTER_API_KEY.")
    return OpenRouter(api_key=final_api_key)


def _user_content(prompt: str, image_b64: str = None) -> list:
    user_content = [{"type": "text", "text": prompt}]
    if image_b64:
        user_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}})
        logger.info("Included image in the prompt")
    return user_content


def _json_object(content: str) -> dict:
    match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    start, end = content.find('{'), content.rfind('}')
    return json.loads(content[start:end + 1] if start != -1 and end != -1 else content)


def route_exercise(prompt: str, api_key: str = "", image_b64: str = None, selected_model: str = "auto") -> dict:
    """Which models solve the exercise and with which content. 'kind' is "formula", "reasoning" (Auto mode)
    or "manual" (a model chosen by the user, used as it is). Separate from the generation so the router can
    tell the student, before the long wait, that a reasoning exercise goes to Claude Sonnet."""
    routing = {
        "kind": "manual",
        "target_models": [selected_model],
        "user_content": _user_content(prompt, image_b64),
        # Text used to pick the topic modules of the system prompt. A photo without extracted text has unknown
        # content, so None makes build_system_prompt include every module.
        "topic_text": None if image_b64 else prompt,
        "provider_issues": [],
    }
    if selected_model != "auto":
        logger.info(f"User manually selected model: {selected_model}. Bypassing Smart Routing.")
        return routing

    client = _openrouter_client(api_key)
    try:
        logger.info(f"Classifying the exercise (formula or reasoning) with {CLASSIFIER_MODEL}...")
        response = client.chat.send(
            models=[CLASSIFIER_MODEL],
            messages=[{"role": "system", "content": CLASSIFIER_PROMPT}, {"role": "user", "content": routing["user_content"]}],
            response_format={'type': 'json_object'},
            temperature=0.1,
            max_tokens=1000,
        )
        log_usage("Classifier", response)
        parsed = _json_object(response.choices[0].message.content or "")
        kind = str(parsed.get("kind", "reasoning")).strip().lower()
        kind = kind if kind in ("formula", "reasoning") else "reasoning"
        extracted = parsed.get("extracted_text") or ""
    except Exception as e:
        # Unsure about the kind: the reasoning route is the safe one
        logger.warning(f"Exercise classification failed, solving it as a reasoning exercise: {e}")
        if is_provider_error(e):
            routing["provider_issues"].append(classify_provider_error(e))
        kind, extracted = "reasoning", ""

    routing["kind"] = kind
    if extracted:
        routing["topic_text"] = f"{prompt}\n{extracted}"
    if kind == "formula":
        routing["target_models"] = list(FORMULA_MODELS)
        logger.info("Formula exercise: solving it with GPT-4o.")
    else:
        routing["target_models"] = list(REASONING_MODELS)
        logger.info("Reasoning exercise: solving it with Claude Sonnet 5.5.")
        if image_b64 and extracted:
            logger.info("Stripping image to save Vision costs and using extracted text.")
            routing["user_content"] = [{"type": "text", "text": (
                f"User Request: {prompt}\n\n[Extracted Mathematical Content from User's Image]:\n{extracted}\n\n"
                "(CRITICAL: Solve this problem step-by-step, but you MUST provide all 'speech' explanations in the "
                "EXACT SAME LANGUAGE as the User Request above).")}]
    return routing


def generate_geogebra_script(prompt: str, api_key: str = "", image_b64: str = None, selected_model: str = "auto",
                             routing: dict = None, explain: bool = False, should_stop=None) -> dict:
    """The lesson for an exercise. routing comes from route_exercise (the router computes it first so it can
    warn the student about slow reasoning exercises); it is computed here when not given. explain is the
    "Explain more" option of the UI: the lesson explains the why of every step (app/prompts/explain.md).
    should_stop() tells whether the student left; then GenerationCancelled is raised before the next paid call
    (a call already sent cannot be cancelled)."""

    def stop_if_gone(next_call: str) -> None:
        if should_stop is not None and should_stop():
            logger.info(f"The student disconnected: {next_call} skipped")
            raise GenerationCancelled()

    client = _openrouter_client(api_key)
    logger.info(f"Sending prompt to OpenRouter: {prompt}")
    if routing is None:
        routing = route_exercise(prompt, api_key, image_b64, selected_model)
    target_models = list(routing["target_models"])
    user_content = routing["user_content"]
    # The note goes only to the lesson calls; the reviewer gets the exercise alone
    lesson_content = user_content + ([{"type": "text", "text": EXPLAIN_NOTE}] if explain else [])
    topic_text = routing["topic_text"]
    difficulty = routing["kind"]
    # Problems the model provider had along the way (app/provider.py codes); the UI tells the user about them
    provider_issues = list(routing["provider_issues"])

    system_prompt, prompt_modules = build_system_prompt(topic_text, explain)
    lesson_max_tokens = EXPLAIN_LESSON_MAX_TOKENS if explain else LESSON_MAX_TOKENS
    logger.info(
        f"System prompt modules: {prompt_modules or 'all (no topic detected or image without extracted text)'}"
        f"{' + explain.md (Explain more)' if explain else ''} (~{len(system_prompt) // 4} tokens)"
    )

    max_retries = 3
    full_prompt_sent = not prompt_modules
    # Every validation note so far goes along with each retry: when one note replaced the previous one, fixing
    # one problem brought back another (a lesson rewritten for a false check dropped its diagram)
    notes, used_notes, candidates = [], set(), []
    for attempt in range(max_retries):
        stop_if_gone(f"generation attempt {attempt + 1}")
        if attempt >= 1 and not full_prompt_sent:
            # The first attempt may have failed because a topic module was left out: retry with all of them
            system_prompt, _ = build_system_prompt(None, explain)
            full_prompt_sent = True
            logger.info(f"Retrying with the full system prompt (~{len(system_prompt) // 4} tokens)")
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": lesson_content + [{"type": "text", "text": note} for note in notes]},
        ]
        try:
            logger.info(f"Generation attempt {attempt + 1} with target models: {target_models}")
            response = client.chat.send(
                models=target_models,
                messages=messages,
                temperature=0.3,  # lower variance: the prompt's rules and the arithmetic are followed more consistently
                # 2500 tokens for the lesson (6000 with "Explain more"), plus a reasoning budget for models that
                # reason (app/provider.py)
                **completion_limits(target_models, lesson_max_tokens),
            )
            #logs helper, to see which model was used in each response
            logger.info(f"OpenRouter successfully routed the request to model: {response.model}")
            log_usage(f"Attempt {attempt + 1}", response)

            # A cut or empty answer is a failed attempt, never an empty lesson for the student
            problem = response_problem(response)
            if problem:
                provider_issues.append(problem)
                logger.error(f"Attempt {attempt + 1}: the model's answer is {problem} (finish_reason "
                             f"{getattr(response.choices[0], 'finish_reason', None)})")
                if attempt < max_retries - 1:
                    continue
                if candidates:
                    break  # deliver the best earlier lesson
                raise ProviderError(problem)

            content = response.choices[0].message.content

            # Extract JSON block if surrounded by markdown
            match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if match:
                clean_content = match.group(1).strip()
            else:
                # Fallback to finding first { and last }
                start = content.find('{')
                end = content.rfind('}')
                if start != -1 and end != -1:
                    clean_content = content[start:end+1].strip()
                else:
                    if candidates:
                        logger.warning("No JSON object in this retry: delivering the best earlier lesson instead.")
                        break
                    # No JSON object found at all. This usually means a conversational refusal or explanation.
                    # Instead of failing and retrying, we return a synthetic valid response so the tutor just "speaks" it.
                    logger.warning("No JSON object detected in response. Treating as conversational fallback.")
                    return {
                        "steps": [
                            {
                                "command": "",
                                "speech": content.strip()
                            }
                        ],
                        "_meta": {
                            "difficulty": difficulty,
                            "model": response.model,
                            "provider_issues": list(dict.fromkeys(provider_issues)),
                        }
                    }

            data = json.loads(clean_content)
            # The model answers every question here before writing the steps; logged only for debugging
            logger.info(f"Lesson questions: {data.get('questions')}")
            if not ("steps" in data and isinstance(data["steps"], list)):
                data["_meta"] = {"difficulty": difficulty, "model": response.model, "failed_checks": [],
                                 "provider_issues": list(dict.fromkeys(provider_issues))}
                return data
            for step in data["steps"]:
                if isinstance(step, dict) and "command" in step:
                    step["command"] = sanitize_geogebra_command(step.get("command", ""))

            stop_if_gone("lesson review")
            candidate = _assess_lesson(data, attempt, response.model, client, target_models, user_content)
            candidates.append(candidate)
            if attempt < max_retries - 1:
                kind, note = _next_retry_note(candidate, used_notes)
                if note:
                    if kind != "unknown":  # nonexistent commands may be retried every time, the rest only once
                        used_notes.add(kind)
                    notes.append(note)
                    continue
            break

        except (ProviderError, GenerationCancelled):
            raise  # a provider error is already classified (the router shows its code); a cancel ends it all

        except json.JSONDecodeError as e:
            logger.error(f"JSON Parsing Error on attempt {attempt + 1}: {e}")
            # Retried with the same models: in Auto mode their list already falls back to the other model
            # when a provider fails, and gpt-4o-mini no longer writes lessons
            if attempt < max_retries - 1:
                logger.info(f"Attempt {attempt + 1} failed. Retrying with {target_models}...")
                continue
            if candidates:
                break  # deliver the best earlier lesson

            logger.error(f"Raw response: {content if 'content' in locals() else 'None'}")
            raise Exception(f"The model failed to generate a valid lesson. It may have refused the prompt due to safety filters. Last response: {content[:300] if 'content' in locals() and content else 'Empty/None'}")

        except Exception as e:
            logger.error(f"General Error: {e}")
            # Only failures of the OpenRouter call itself are the provider's; a bug in our code is not
            provider_code = classify_provider_error(e) if is_provider_error(e) else None
            if provider_code:
                provider_issues.append(provider_code)
                logger.error(f"Attempt {attempt + 1}: provider error '{provider_code}' ({type(e).__name__})")
            if attempt < max_retries - 1:
                continue
            if candidates:
                break  # deliver the best earlier lesson
            if provider_code:
                raise ProviderError(provider_code, str(e))
            raise Exception(f"AI Processing Error: {e}")

    if not candidates:
        if provider_issues:
            raise ProviderError(provider_issues[-1])
        raise Exception("AI Processing Error: no lesson could be generated.")
    # A retry can make a lesson worse (fix the numbers and drop the diagram): deliver the best one, not the last
    best = min(candidates, key=_candidate_rank)
    if best is not candidates[-1]:
        logger.info(f"Delivering attempt {best['attempt'] + 1} of {len(candidates)}: it is better than the last one")
    if not best["reviewed"]:
        stop_if_gone("lesson review")
    return _finalize_lesson(best, client, target_models, user_content, prompt_modules, difficulty, provider_issues)


# --- One generated lesson as a candidate ------------------------------------------------------------
# Every attempt is assessed in full and kept; retries get notes for the first problem found, and at the end
# the best candidate is delivered (a retry can make a lesson worse, e.g. fix the numbers and drop the diagram).

def _assess_lesson(data: dict, attempt: int, model: str, client, target_models: list, user_content: list) -> dict:
    """Everything that is wrong with one generated lesson, without changing it."""
    steps = data["steps"]
    candidate = {
        "attempt": attempt,
        "data": data,
        "model": model,
        "unknown": find_unknown_commands(steps),
        # {name} placeholders get their values later from GeoGebra (/api/voice); only those that can never
        # get one are a problem here
        "invalid": find_invalid_placeholders(data),
        "draws": lesson_draws_something(steps),
        "checks": [],
        "reviewed": False,
        "review_failed": False,
    }
    # The reviewer (app/checker.py) writes the conditions the solution must meet. It is only paid for lessons
    # that draw something: one that draws nothing is rewritten anyway, or reviewed at the end if it is chosen
    if candidate["draws"]:
        _review(candidate, client, target_models, user_content)
    _evaluate_checks(candidate)

    # Numbers the model typed itself are checked against what the commands compute. Placeholders count as
    # stated, so the check runs on a copy with the arithmetic ones filled by the server
    checked = copy.deepcopy({"language": data.get("language"), "steps": steps, "questions": data.get("questions")})
    fill_placeholders(checked)
    reviewer_steps = [{"command": c, "speech": ""} for c in candidate["checks"] or []]
    candidate["unstated"] = find_unconfirmed_results(checked["steps"] + reviewer_steps, checked.get("questions"))
    candidate["answers_filled"] = [q.get("answer") for q in checked.get("questions") or [] if isinstance(q, dict)]

    n = attempt + 1
    if candidate["unknown"]:
        logger.warning(f"Attempt {n} used nonexistent GeoGebra commands: {candidate['unknown']}")
    if candidate["invalid"]:
        logger.warning(f"Attempt {n} used placeholders that can never get a value: {candidate['invalid']}")
    if not candidate["draws"]:
        logger.warning(f"Attempt {n} draws nothing on the board")
    if candidate["failed_checks"]:
        logger.warning(f"Attempt {n} breaks its own checks: {candidate['failed_checks']}")
    if candidate["unstated"]:
        readable = {name: format_value(value) for name, value in candidate["unstated"].items()}
        logger.warning(f"Attempt {n} speeches do not state the values GeoGebra computes: {readable}")
    return candidate


def _review(candidate: dict, client, target_models: list, user_content: list) -> None:
    checks = write_checks(client, target_models, user_content, candidate["data"])
    candidate["reviewed"] = True
    candidate["review_failed"] = checks is None  # the provider failed: the lesson goes on unverified
    candidate["checks"] = checks or []


def _evaluate_checks(candidate: dict) -> None:
    steps = candidate["data"]["steps"]
    candidate["failed_checks"] = find_failed_checks(steps + [{"command": c} for c in candidate["checks"] or []])


def _next_retry_note(candidate: dict, used: set) -> tuple:
    """(kind, note) for the first problem worth a retry, or (None, None). Each kind is retried once, except
    nonexistent commands, which make GeoGebra reject steps."""
    if candidate["unknown"]:
        return "unknown", build_retry_note(candidate["unknown"])
    if candidate["invalid"] and "placeholders" not in used:
        return "placeholders", build_placeholder_retry_note(candidate["invalid"])
    if not candidate["draws"] and "drawing" not in used:
        return "drawing", build_drawing_retry_note()
    if candidate["failed_checks"] and "checks" not in used:
        return "checks", build_checks_retry_note(candidate["failed_checks"])
    if candidate["unstated"] and "arithmetic" not in used:
        # A second miss is more likely a false alarm than another mistake
        return "arithmetic", build_arithmetic_retry_note(candidate["unstated"])
    return None, None


def _candidate_rank(candidate: dict) -> tuple:
    """Lower is better: it draws, then fewer false checks, fewer broken commands and placeholders, fewer
    values the voice never says; on a tie the later attempt, which had more notes to follow."""
    return (not candidate["draws"], len(candidate["failed_checks"]), len(candidate["unknown"]),
            len(candidate["invalid"]), len(candidate["unstated"]), -candidate["attempt"])


def _finalize_lesson(candidate: dict, client, target_models: list, user_content: list, prompt_modules: list,
                     difficulty: str, provider_issues: list) -> dict:
    """Prepare the chosen candidate for /api/run."""
    data = candidate["data"]
    steps = data["steps"]
    if candidate["unknown"]:
        blank_unknown_commands(steps, candidate["unknown"])
    if candidate["invalid"]:
        replace_unfilled_placeholders(data, only=candidate["invalid"])
    if not candidate["reviewed"]:
        # Not reviewed because it draws nothing: review it now so a wrong result still gets its warning
        _review(candidate, client, target_models, user_content)
        _evaluate_checks(candidate)
    data["_checks"] = candidate["checks"]

    # Applied graphs only: in a functions lesson, Function(funcF, 0, 2) may highlight a piece of a curve that
    # must stay visible
    if "applied.md" in prompt_modules:
        hidden = hide_restricted_function_sources(steps)
        if hidden:
            logger.info(f"Hid complete functions drawn again restricted: {hidden}")

    # Only the delivered lesson is logged, one line per step, to diagnose what reached the board
    logger.info(f"Answers (arithmetic placeholders filled; the rest are filled by GeoGebra): {candidate['answers_filled']}")
    commands = [s.get("command", "") for s in steps if isinstance(s, dict)]
    logger.info("Lesson commands:\n" + "\n".join(f"  {i}. {c}" for i, c in enumerate(commands, 1)))
    if not candidate["draws"]:
        logger.warning("Delivering a lesson that draws nothing: no attempt drew anything")
    if candidate["failed_checks"]:
        logger.warning("Delivering the lesson although it still breaks its own checks; the student is warned")
    data["_meta"] = {
        "difficulty": difficulty,
        "model": candidate["model"],
        # Names of the lesson's checks that are false: the frontend warns that the result may be wrong
        "failed_checks": [c.split(":", 1)[0] for c in candidate["failed_checks"]],
        # Problems of the model provider along the way (app/provider.py codes): the frontend shows them too
        "provider_issues": list(dict.fromkeys(provider_issues + (["review_failed"] if candidate["review_failed"] else []))),
    }
    return data
