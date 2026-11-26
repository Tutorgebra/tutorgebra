import json
import logging
import re

from app.placeholders import defined_names

# A separate, focused call that writes the conditions a lesson's solution must satisfy, as GeoGebra checks.
# The generator often skips its own rule 11 (CHECK YOUR CONDITIONS) or never notices that its solution
# breaks a condition; a reviewer with only that task, that did not choose the solution, is more reliable.
# The server evaluates the checks (app/arithmetic_check.py) and the generation is retried when one is false.

logger = logging.getLogger('TutorGebraChecker')

CHECKER_MAX_TOKENS = 700
MAX_CHECK_COMMANDS = 30
MAX_COMMAND_CHARS = 200
_AUX_RE = re.compile(r'^\s*(aux[A-Za-z0-9]*)\s*=\s*[^=].*$')
_CHECK_RE = re.compile(r'^\s*(check[A-Za-z0-9]*)\s*=\s*.+$')

CHECKER_PROMPT = """You are the reviewer of a math lesson written as GeoGebra commands. You receive the exercise, the lesson's answers and its commands. Do NOT solve the exercise yourself: write the conditions that THE SOLUTION THE LESSON PRESENTS must satisfy, so that a computer can test them.

Rules:
1. Check exactly what the lesson claims: its groups, its chosen numbers, its vertex, its roots, as the lesson states them in its commands, texts and answers.
2. Cover every condition of the exercise: each station or group fits in the cycle or takt time, each machine, worker or resource is within its capacity or what is available, quantities are not negative (and whole when they count units), a probability is between 0 and 1, an optimum satisfies every constraint, a root makes its function 0, a stated total matches the sum of its parts.
3. Write each check as `checkName = <comparison>` using <=, >=, <, > or ==. When you need a value the lesson does not name (for example the time of a station the lesson only describes in a text), first define it as `auxName = <arithmetic with the exercise's data>`.
4. Use ONLY the names the lesson's commands define, your own aux names, and numbers from the exercise. camelCase names, no underscores, explicit `*` for multiplication. Functions you may use: sqrt, abs, round, floor, ceil, and the lesson's own objects and functions (e.g. funcF(root1)).
5. Return ONLY a JSON object: {"checks": ["auxStation1 = 4 + 3", "checkStation1 = auxStation1 <= taktTime"]}. If the exercise has no condition to test (e.g. a plain drawing), return {"checks": []}.

Example. Exercise: takt time 6 min, tasks in order of 4, 3, 4 and 1 min. Lesson: taktTime = 6, texts "Station 1: tasks 1 and 2", "Station 2: tasks 3 and 4". Answer:
{"checks": ["auxStation1 = 4 + 3", "auxStation2 = 4 + 1", "checkStation1 = auxStation1 <= taktTime", "checkStation2 = auxStation2 <= taktTime"]}"""


def _describe_lesson(lesson: dict) -> str:
    answers = [q.get("answer", "") for q in lesson.get("questions") or [] if isinstance(q, dict)]
    commands = [s.get("command", "") for s in lesson.get("steps") or [] if isinstance(s, dict)]
    return ("Lesson answers:\n" + "\n".join(f"- {a}" for a in answers if isinstance(a, str)) +
            "\n\nLesson commands:\n" + "\n".join(f"{i}. {c}" for i, c in enumerate(commands, 1) if c))


def _parse_checks(content: str, lesson_names: set) -> list:
    start, end = content.find("{"), content.rfind("}")
    if start == -1 or end == -1:
        return []
    raw = json.loads(content[start:end + 1]).get("checks", [])
    commands = []
    for command in raw if isinstance(raw, list) else []:
        if not isinstance(command, str) or len(command) > MAX_COMMAND_CHARS:
            continue
        command = command.strip()
        aux = _AUX_RE.match(command)
        if aux and aux.group(1) not in lesson_names:  # never overwrite a value of the lesson
            commands.append(command)
        elif _CHECK_RE.match(command) and _CHECK_RE.match(command).group(1) not in lesson_names:
            commands.append(command)
    return commands[:MAX_CHECK_COMMANDS]


def write_checks(client, models: list, exercise_content: list, lesson: dict) -> list:
    """GeoGebra commands (aux values and checks) that test the lesson's solution. [] if the review fails:
    the lesson then goes on without these checks, as before."""
    messages = [
        {"role": "system", "content": CHECKER_PROMPT},
        {"role": "user", "content": exercise_content + [{"type": "text", "text": _describe_lesson(lesson)}]},
    ]
    try:
        response = client.chat.send(models=models, messages=messages, temperature=0,
                                    max_tokens=CHECKER_MAX_TOKENS, response_format={'type': 'json_object'})
        commands = _parse_checks(response.choices[0].message.content or "", defined_names(lesson.get("steps")))
    except Exception as exc:
        logger.warning(f"The checker call failed, the lesson goes on without its checks: {exc}")
        return []
    logger.info(f"Checker wrote: {commands}")
    return commands
