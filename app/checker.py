import json
import logging
import re

from app.placeholders import defined_names
from app.provider import completion_limits, log_usage, response_problem

# A separate, focused call that writes the conditions a lesson's solution must satisfy, as GeoGebra checks.
# The generator often skips its own rule 11 (CHECK YOUR CONDITIONS) or never notices that its solution
# breaks a condition; a reviewer with only that task, that did not choose the solution, is more reliable.
# The server evaluates the checks (app/arithmetic_check.py) and the generation is retried when one is false.

logger = logging.getLogger('TutorGebraChecker')

CHECKER_MAX_TOKENS = 900
CHECKER_REASONING_BUDGET = 1500  # only for models that reason (app/provider.py)
MAX_CHECK_COMMANDS = 30
MAX_COMMAND_CHARS = 200
_AUX_RE = re.compile(r'^\s*(aux[A-Za-z0-9]*)\s*=\s*[^=].*$')
_CHECK_RE = re.compile(r'^\s*(check[A-Za-z0-9]*)\s*=\s*.+$')
# An equality check is almost always the lesson's own formula restated ("timeStation1 == 3 + 2"), which is
# always true and tests nothing. "Equals zero" is written abs(...) < 0.001 instead, which is kept.
_EQUALITY_RE = re.compile(r'==|≟')

CHECKER_PROMPT = """You are the reviewer of a math lesson written as GeoGebra commands. You receive the exercise, the lesson's answers and its commands. Do NOT solve the exercise yourself and do NOT recompute the lesson: test THE SOLUTION THE LESSON PRESENTS against the LIMITS of the exercise, so that a computer can find out whether it breaks one.

Work in two parts:
1. "limits": first list in words every limit the exercise states or implies for its solution, with its value. For example: "the time of each station is at most the takt time (4 min)", "the hours used are at most the 240 available", "quantities are not negative", "a probability is between 0 and 1", "the optimum satisfies every constraint", "a root makes its function 0".
2. "checks": then write one check per limit and per element it applies to (one per station, one per resource...): `checkName = <a value of the lesson's solution> <= <the limit>`, or with >=, < or >. When the lesson does not name a value you need (for example the time of a station it only describes in a text), first define it as `auxName = <arithmetic with the exercise's data>`, following exactly the lesson's own grouping or choice.

FORBIDDEN:
- Restating a formula of the lesson: `checkTime1 = timeStation1 == 3 + 2` or `checkTakt = taktTime == 480 / 120` tests nothing, because the lesson already computes it that way. A check always compares a value of the solution with a LIMIT of the exercise.
- `==`: for a condition such as "makes the function 0" write `abs(funcF(root1)) < 0.001`.
- Solving the exercise yourself and checking your own solution instead of the lesson's.

Use ONLY the names the lesson's commands define, your own aux names and numbers from the exercise. camelCase names, no underscores, explicit `*` for multiplication. Functions you may use: sqrt, abs, round, floor, ceil, and the lesson's own objects and functions (e.g. funcF(root1)).

Return ONLY a JSON object: {"limits": ["..."], "checks": ["..."]}. If the exercise has no limit to test (e.g. a plain drawing), return {"limits": [], "checks": []}.

Example. Exercise: takt time 6 min, tasks in order of 4, 3, 4 and 1 min. Lesson: taktTime = 6, texts "Station 1: tasks 1 and 2", "Station 2: tasks 3 and 4". Answer:
{"limits": ["the time of each station is at most the takt time (6 min)"], "checks": ["auxStation1 = 4 + 3", "auxStation2 = 4 + 1", "checkStation1 = auxStation1 <= taktTime", "checkStation2 = auxStation2 <= taktTime"]}"""


def _describe_lesson(lesson: dict) -> str:
    answers = [q.get("answer", "") for q in lesson.get("questions") or [] if isinstance(q, dict)]
    commands = [s.get("command", "") for s in lesson.get("steps") or [] if isinstance(s, dict)]
    return ("Lesson answers:\n" + "\n".join(f"- {a}" for a in answers if isinstance(a, str)) +
            "\n\nLesson commands:\n" + "\n".join(f"{i}. {c}" for i, c in enumerate(commands, 1) if c))


def _parse_review(content: str, lesson_names: set) -> tuple:
    """(limits in words, usable commands, dropped equality checks) from the reviewer's JSON."""
    start, end = content.find("{"), content.rfind("}")
    if start == -1 or end == -1:
        return [], [], []
    review = json.loads(content[start:end + 1])
    if not isinstance(review, dict):
        return [], [], []
    limits = [l for l in review.get("limits", []) if isinstance(l, str)] if isinstance(review.get("limits"), list) else []
    raw = review.get("checks", [])
    commands, dropped = [], []
    for command in raw if isinstance(raw, list) else []:
        if not isinstance(command, str) or len(command) > MAX_COMMAND_CHARS:
            continue
        command = command.strip()
        aux = _AUX_RE.match(command)
        check = _CHECK_RE.match(command)
        if aux and aux.group(1) not in lesson_names:  # never overwrite a value of the lesson
            commands.append(command)
        elif check and check.group(1) not in lesson_names:
            if _EQUALITY_RE.search(command):
                dropped.append(command)
            else:
                commands.append(command)
    return limits, commands[:MAX_CHECK_COMMANDS], dropped


def _parse_checks(content: str, lesson_names: set) -> list:
    return _parse_review(content, lesson_names)[1]


def write_checks(client, models: list, exercise_content: list, lesson: dict) -> list | None:
    """GeoGebra commands (aux values and checks) that test the lesson's solution ([] when there is no limit
    to test). None if the review failed (provider error, cut or empty answer): the lesson then goes on
    without these checks and the UI says it could not be verified."""
    messages = [
        {"role": "system", "content": CHECKER_PROMPT},
        {"role": "user", "content": exercise_content + [{"type": "text", "text": _describe_lesson(lesson)}]},
    ]
    try:
        response = client.chat.send(models=models, messages=messages, temperature=0, response_format={'type': 'json_object'},
                                    **completion_limits(models, CHECKER_MAX_TOKENS, CHECKER_REASONING_BUDGET))
        log_usage("Checker", response)
        problem = response_problem(response)
        if problem:
            logger.warning(f"The checker's answer is {problem}: the lesson goes on without its checks")
            return None
        limits, commands, dropped = _parse_review(response.choices[0].message.content or "",
                                                  defined_names(lesson.get("steps")))
    except Exception as exc:
        logger.warning(f"The checker call failed, the lesson goes on without its checks: {exc}")
        return None
    logger.info(f"Checker limits: {limits}")
    logger.info(f"Checker wrote: {commands}")
    if dropped:
        logger.info(f"Checker equality checks dropped (they restate the lesson's formulas): {dropped}")
    return commands
