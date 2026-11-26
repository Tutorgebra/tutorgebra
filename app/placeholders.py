import math
import re

from app.arithmetic_check import evaluate_lesson_values, format_value

# The prompt's NUMBERS FROM THE BOARD rule: speeches and answers never type a value a command computes,
# they write {name} instead. The browser runs the lesson in GeoGebra before the voice is synthesized and
# sends back the real values (static/ggb_evaluate.js -> /api/voice), so every number the student hears is
# the one on the board. The server's own evaluator (plain arithmetic only) is the fallback.

_PLACEHOLDER_RE = re.compile(r'\{\s*([A-Za-z][A-Za-z0-9]*)\s*\}')
# Anything else in braces that contains a letter or a call is a malformed placeholder ({Extremum(funcF)});
# a set of numbers such as {1, 2} is left alone
_BRACES_RE = re.compile(r'\{([^{}\n]{1,80})\}')
# "name = ...", "name: y = ...", "funcF(x) = ..." define a GeoGebra object called name
_DEFINED_NAME_RE = re.compile(r'^\s*([A-Za-z][A-Za-z0-9]*)\s*(?:\(\s*[A-Za-z][A-Za-z0-9]*\s*\))?\s*[:=](?!=)')
_UNRESOLVED_PHRASE = {"es": "el valor que muestra el tablero", "en": "the value shown on the board"}
MAX_CLIENT_VALUES = 200
MAX_ABS_VALUE = 1e15


def _fields(lesson: dict, keys=("speech", "answer")):
    """(dict, key) for every speech (steps) and answer (questions) of the lesson."""
    for key, items in (("speech", lesson.get("steps")), ("answer", lesson.get("questions"))):
        if key not in keys:
            continue
        for item in items if isinstance(items, list) else []:
            if isinstance(item, dict) and isinstance(item.get(key), str):
                yield item, key


def defined_names(steps) -> set:
    return {
        m.group(1)
        for s in (steps if isinstance(steps, list) else [])
        if isinstance(s, dict) and isinstance(s.get("command"), str)
        for m in [_DEFINED_NAME_RE.match(s["command"])] if m
    }


def _is_malformed(content: str) -> bool:
    return bool(re.search(r'[A-Za-z(]', content)) and not re.fullmatch(r'\s*[A-Za-z][A-Za-z0-9]*\s*', content)


def find_invalid_placeholders(lesson: dict) -> list:
    """Placeholders that can never get a value: an expression ({Extremum(funcF)}) or a name that no
    command of the lesson defines ({lotOptimal} when the command is lotOpt)."""
    names = defined_names(lesson.get("steps"))
    invalid = []
    for item, key in _fields(lesson):
        for match in _BRACES_RE.finditer(item[key]):
            content = match.group(1)
            simple = _PLACEHOLDER_RE.fullmatch(match.group(0))
            bad = (simple and simple.group(1) not in names) or (not simple and _is_malformed(content))
            if bad and match.group(0) not in invalid:
                invalid.append(match.group(0))
    return invalid


def placeholder_names(lesson: dict, keys=("speech",)) -> list:
    """Names of the valid placeholders, in order of appearance (what the browser must read in GeoGebra)."""
    names = []
    for item, key in _fields(lesson, keys):
        for name in _PLACEHOLDER_RE.findall(item[key]):
            if name not in names:
                names.append(name)
    return names


def _clean_client_value(value):
    """A number or an [x, y] pair from the browser as text, or None. Only numbers are accepted, so the
    request can change the digits the voice says but never make it read arbitrary text."""
    def number(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and abs(v) < MAX_ABS_VALUE

    if number(value):
        return format_value(float(value))
    if isinstance(value, list) and len(value) == 2 and all(number(v) for v in value):
        return f"({format_value(float(value[0]))}, {format_value(float(value[1]))})"
    return None


def fill_placeholders(lesson: dict, client_values=None, keys=("speech", "answer")) -> list:
    """Replace {name} with the value GeoGebra computed in the browser (client_values: name -> number or
    [x, y]), or else with the server's own evaluation of plain arithmetic. Returns the names left unfilled."""
    values = {}
    for v in evaluate_lesson_values(lesson.get("steps")):  # fallback, last definition wins
        values[v.name] = format_value(v.value)
    if isinstance(client_values, dict):
        for name, value in list(client_values.items())[:MAX_CLIENT_VALUES]:
            text = _clean_client_value(value) if isinstance(name, str) else None
            if text is not None:
                values[name] = text  # GeoGebra's own value wins over the server's evaluation
    unresolved = []

    def replace(match):
        name = match.group(1)
        if name in values:
            return values[name]
        if name not in unresolved:
            unresolved.append(name)
        return match.group(0)

    for item, key in _fields(lesson, keys):
        item[key] = _PLACEHOLDER_RE.sub(replace, item[key])
    return unresolved


def replace_unfilled_placeholders(lesson: dict, keys=("speech", "answer"), only=None) -> None:
    """Last resort for placeholders nothing could fill: the voice must not read a variable name or an
    expression in braces, so it says where the value is instead. only: replace just these placeholders
    (as written, e.g. "{Extremum(funcF)}") and keep the rest for GeoGebra to fill."""
    language = str(lesson.get("language", "en"))[:2].lower()
    phrase = _UNRESOLVED_PHRASE.get(language, _UNRESOLVED_PHRASE["en"])

    def replace(match):
        if only is not None and match.group(0) not in only:
            return match.group(0)
        content = match.group(1)
        return phrase if _PLACEHOLDER_RE.fullmatch(match.group(0)) or _is_malformed(content) else match.group(0)

    for item, key in _fields(lesson, keys):
        item[key] = _BRACES_RE.sub(replace, item[key])


def build_placeholder_retry_note(invalid: list) -> str:
    return (
        "[SYSTEM VALIDATION - CRITICAL] A previous answer to this request was REJECTED because its speeches or "
        f"answers use placeholders that can never get a value: {', '.join(invalid)}. A placeholder is ONLY the "
        "exact name of an object that one of your commands defines, between braces, e.g. {areaValue} for "
        "`areaValue = Area(poly1)`. NEVER put an expression or a command inside the braces. Write the complete "
        "lesson again from scratch."
    )
