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


def generate_geogebra_script(prompt: str, api_key: str = "", image_b64: str = None, selected_model: str = "auto") -> dict:
    final_api_key = api_key.strip() if api_key else os.environ.get("OPENROUTER_API_KEY")
    if not final_api_key:
        raise ValueError("OpenRouter API Key is missing. Please provide one in the UI or configure the server with OPENROUTER_API_KEY.")
        
    client = OpenRouter(api_key=final_api_key)

    # Text used to pick the topic modules of the system prompt. A photo without extracted text has
    # unknown content, so None makes build_system_prompt include every module.
    topic_text = None if image_b64 else prompt

    logger.info(f"Sending prompt to OpenRouter: {prompt}")
    
    user_content = [{"type": "text", "text": prompt}]
    if image_b64:
        user_content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{image_b64}"
            }
        })
        logger.info("Included image in the prompt")
        
    target_models = ['openai/gpt-4o-mini']
    difficulty = "manual"
    # Problems the model provider had along the way (app/provider.py codes); the UI tells the user about them
    provider_issues = []

    if selected_model != "auto":
        logger.info(f"User manually selected model: {selected_model}. Bypassing Smart Routing.")
        target_models = [selected_model]
    else:
        try:
            logger.info("Performing preliminary Difficulty Classification with gpt-4o-mini...")
            ocr_messages = [
                {
                    "role": "system",
                    "content": "You are a Math Classifier. Read the prompt (and image if any). 1. If there's an image, extract all text/math. 2. Classify difficulty. If it's university-level (physics, advanced calculus, abstract algebra, PDEs, etc.), requires complex spatial reasoning, or involves Analytical Geometry (ellipses, parabolas, conics), output 'advanced'. If basic arithmetic or simple elementary school shapes, output 'basic'. Return EXACTLY JSON: {\"extracted_text\": \"...\", \"difficulty\": \"basic\" | \"advanced\"}"
                },
                {"role": "user", "content": user_content}
            ]
            
            ocr_resp = client.chat.send(
                models=['openai/gpt-4o-mini'],
                messages=ocr_messages,
                response_format={'type': 'json_object'},
                temperature=0.1,
                max_tokens=1000
            )
            
            ocr_content = ocr_resp.choices[0].message.content
            match_ocr = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', ocr_content, re.DOTALL)
            if match_ocr:
                clean_ocr = match_ocr.group(1).strip()
            else:
                start_ocr = ocr_content.find('{')
                end_ocr = ocr_content.rfind('}')
                if start_ocr != -1 and end_ocr != -1:
                    clean_ocr = ocr_content[start_ocr:end_ocr+1].strip()
                else:
                    clean_ocr = ocr_content.strip()
        
            ocr_data = json.loads(clean_ocr)
            difficulty = ocr_data.get("difficulty", "basic").lower()
            extracted = ocr_data.get("extracted_text", "")
            if extracted:
                topic_text = f"{prompt}\n{extracted}"

            logger.info(f"Problem classified as: {difficulty}")
            
            if difficulty == "advanced":
                logger.info("Advanced problem detected! Routing to powerful models (GPT-4o / Sonnet 5.5).")
                if image_b64:
                    logger.info("Stripping image to save Vision costs and using extracted text.")
                    user_content = [
                        {"type": "text", "text": f"User Request: {prompt}\n\n[Extracted Mathematical Content from User's Image]:\n{extracted}\n\n(CRITICAL: Solve this advanced problem step-by-step, but you MUST provide all 'speech' explanations in the EXACT SAME LANGUAGE as the User Request above)."}
                    ]
                target_models = ['openai/gpt-4o', 'anthropic/claude-sonnet-5.5', 'openai/gpt-4o-mini']
            else:
                logger.info("Basic problem detected. Proceeding with gpt-4o-mini to save costs.")
                
        except Exception as e:
            logger.warning(f"Smart Routing failed, falling back to standard pipeline: {e}")
            if is_provider_error(e):
                provider_issues.append(classify_provider_error(e))
            target_models = ['openai/gpt-4o', 'anthropic/claude-sonnet-5.5', 'openai/gpt-4o-mini']

    system_prompt, prompt_modules = build_system_prompt(topic_text)
    logger.info(
        f"System prompt modules: {prompt_modules or 'all (no topic detected or image without extracted text)'} "
        f"(~{len(system_prompt) // 4} tokens)"
    )

    max_retries = 3
    full_prompt_sent = not prompt_modules
    # Every validation note so far goes along with each retry: when one note replaced the previous one, fixing
    # one problem brought back another (a lesson rewritten for a false check dropped its diagram)
    notes, used_notes, candidates = [], set(), []
    for attempt in range(max_retries):
        if attempt >= 1 and not full_prompt_sent:
            # The first attempt may have failed because a topic module was left out: retry with all of them
            system_prompt, _ = build_system_prompt(None)
            full_prompt_sent = True
            logger.info(f"Retrying with the full system prompt (~{len(system_prompt) // 4} tokens)")
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content + [{"type": "text", "text": note} for note in notes]},
        ]
        try:
            logger.info(f"Generation attempt {attempt + 1} with target models: {target_models}")
            response = client.chat.send(
                models=target_models,
                messages=messages,
                temperature=0.3,  # lower variance: the prompt's rules and the arithmetic are followed more consistently
                # 2500 tokens for the lesson, plus a reasoning budget for models that reason (app/provider.py)
                **completion_limits(target_models, LESSON_MAX_TOKENS),
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

        except ProviderError:
            raise  # already classified above: the router shows its code to the user

        except json.JSONDecodeError as e:
            logger.error(f"JSON Parsing Error on attempt {attempt + 1}: {e}")
            if selected_model == "auto":
                if attempt == 0:
                    logger.info("Attempt 1 failed. Forcing fallback to gpt-4o for the next attempt...")
                    target_models = ['openai/gpt-4o']
                    continue
                elif attempt == 1:
                    logger.info("Attempt 2 failed. Forcing fallback to gpt-4o-mini for the final attempt...")
                    target_models = ['openai/gpt-4o-mini']
                    continue
            else:
                if attempt < max_retries - 1:
                    logger.info(f"Attempt {attempt + 1} failed. Retrying with manually selected model {selected_model}...")
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
            if selected_model == "auto":
                if attempt == 0:
                    target_models = ['openai/gpt-4o']
                    continue
                elif attempt == 1:
                    target_models = ['openai/gpt-4o-mini']
                    continue
            else:
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
