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
            target_models = ['openai/gpt-4o', 'anthropic/claude-sonnet-5.5', 'openai/gpt-4o-mini']

    system_prompt, prompt_modules = build_system_prompt(topic_text)
    logger.info(
        f"System prompt modules: {prompt_modules or 'all (no topic detected or image without extracted text)'} "
        f"(~{len(system_prompt) // 4} tokens)"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ]
    
    max_retries = 3
    arithmetic_retried = False
    placeholder_retried = False
    checks_retried = False
    drawing_retried = False
    for attempt in range(max_retries):
        if attempt == 1 and prompt_modules:
            # The first attempt may have failed because a topic module was left out: retry with all of them
            system_prompt, _ = build_system_prompt(None)
            messages[0] = {"role": "system", "content": system_prompt}
            logger.info(f"Retrying with the full system prompt (~{len(system_prompt) // 4} tokens)")
        try:
            logger.info(f"Generation attempt {attempt + 1} with target models: {target_models}")
            response = client.chat.send(
                models=target_models,
                messages=messages,
                temperature=0.3,  # lower variance: the prompt's rules and the arithmetic are followed more consistently
                max_tokens=2500
            )
            #logs helper, to see which model was used in each response
            logger.info(f"OpenRouter successfully routed the request to model: {response.model}")
            
            content = response.choices[0].message.content
            
            if content is None:
                logger.error(f"Model {response.model} returned empty/None content. This may be a safety refusal or API glitch.")
                content = ""
                
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
                            "difficulty": locals().get("difficulty", "basic"),
                            "model": response.model
                        }
                    }
            
            data = json.loads(clean_content)
            # The model answers every question here before writing the steps; logged only for debugging
            logger.info(f"Lesson questions: {data.get('questions')}")
            failed_checks = []
            if "steps" in data and isinstance(data["steps"], list):
                for step in data["steps"]:
                    if isinstance(step, dict) and "command" in step:
                        step["command"] = sanitize_geogebra_command(step.get("command", ""))

                unknown = find_unknown_commands(data["steps"])
                if unknown:
                    logger.warning(f"Attempt {attempt + 1} used nonexistent GeoGebra commands: {unknown}")
                    if attempt < max_retries - 1:
                        # Discard this lesson and ask again from scratch, telling the model what was wrong
                        messages = [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_content + [{"type": "text", "text": build_retry_note(unknown)}]},
                        ]
                        continue
                    blank_unknown_commands(data["steps"], unknown)

                # {name} placeholders (NUMBERS FROM THE BOARD) get their values later, from GeoGebra in the
                # browser (/api/voice); here only placeholders that can never get a value are rejected
                invalid = find_invalid_placeholders(data)
                if invalid:
                    logger.warning(f"Attempt {attempt + 1} used placeholders that can never get a value: {invalid}")
                    if not placeholder_retried and attempt < max_retries - 1:
                        placeholder_retried = True
                        messages = [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_content + [{"type": "text", "text": build_placeholder_retry_note(invalid)}]},
                        ]
                        continue
                    replace_unfilled_placeholders(data, only=invalid)

                # A lesson that only computes numbers leaves the board empty. Checked before the reviewer call,
                # so no review is paid for a lesson that is going to be rewritten anyway
                if not lesson_draws_something(data["steps"]):
                    logger.warning(f"Attempt {attempt + 1} draws nothing on the board")
                    if not drawing_retried and attempt < max_retries - 1:
                        drawing_retried = True
                        messages = [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_content + [{"type": "text", "text": build_drawing_retry_note()}]},
                        ]
                        continue

                # Checks: the lesson's own (CHECK YOUR CONDITIONS) plus those of a separate reviewer call
                # (app/checker.py), which does not depend on the generator remembering rule 11. A false one
                # means the solution breaks a condition of the exercise, which the generator rarely notices
                checker_commands = write_checks(client, target_models, user_content, data)
                data["_checks"] = checker_commands
                failed_checks = find_failed_checks(data["steps"] + [{"command": c} for c in checker_commands])
                if failed_checks:
                    logger.warning(f"Attempt {attempt + 1} breaks its own checks: {failed_checks}")
                    if not checks_retried and attempt < max_retries - 1:
                        checks_retried = True
                        messages = [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_content + [{"type": "text", "text": build_checks_retry_note(failed_checks)}]},
                        ]
                        continue

                # Numbers the model typed itself are checked against what the commands compute. Placeholders
                # count as stated, so the check runs on a copy with the arithmetic ones filled by the server
                checked = copy.deepcopy({"language": data.get("language"), "steps": data["steps"], "questions": data.get("questions")})
                fill_placeholders(checked)
                # The reviewer's checks go along so the values they test are not demanded in the answers too
                reviewer_steps = [{"command": c, "speech": ""} for c in checker_commands]
                real_values = find_unconfirmed_results(checked["steps"] + reviewer_steps, checked.get("questions"))
                if real_values:
                    readable = {name: format_value(value) for name, value in real_values.items()}
                    logger.warning(f"Attempt {attempt + 1} speeches do not state the values GeoGebra computes: {readable}")
                    if not arithmetic_retried and attempt < max_retries - 1:
                        # Only once per request: a second miss is more likely a false alarm than another mistake
                        arithmetic_retried = True
                        messages = [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_content + [{"type": "text", "text": build_arithmetic_retry_note(real_values)}]},
                        ]
                        continue

                # Applied graphs only: in a functions lesson, Function(funcF, 0, 2) may highlight a piece of a
                # curve that must stay visible
                if "applied.md" in prompt_modules:
                    hidden = hide_restricted_function_sources(data["steps"])
                    if hidden:
                        logger.info(f"Hid complete functions drawn again restricted: {hidden}")

                # Only the accepted lesson is logged, one line per step, to diagnose what reached the board
                final_answers = [q.get("answer") for q in checked.get("questions") or [] if isinstance(q, dict)]
                logger.info(f"Answers (arithmetic placeholders filled; the rest are filled by GeoGebra): {final_answers}")
                commands = [s.get("command", "") for s in data["steps"] if isinstance(s, dict)]
                logger.info("Lesson commands:\n" + "\n".join(f"  {i}. {c}" for i, c in enumerate(commands, 1)))
                if failed_checks:
                    logger.warning("Delivering the lesson although it still breaks its own checks; the student is warned")
            data["_meta"] = {
                "difficulty": locals().get("difficulty", "basic"),
                "model": response.model,
                # Names of the lesson's checks that are false: the frontend warns that the result may be wrong
                "failed_checks": [c.split(":", 1)[0] for c in failed_checks],
            }
            return data
            
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
                
            logger.error(f"Raw response: {content if 'content' in locals() else 'None'}")
            raise Exception(f"The model failed to generate a valid lesson. It may have refused the prompt due to safety filters. Last response: {content[:300] if 'content' in locals() and content else 'Empty/None'}")
            
        except Exception as e:
            logger.error(f"General Error: {e}")
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
            raise Exception(f"AI Processing Error: {e}")
