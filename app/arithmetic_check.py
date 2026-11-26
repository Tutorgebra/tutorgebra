import ast
import math
import re
import statistics
from decimal import ROUND_HALF_UP, Decimal
from typing import NamedTuple

# The model writes the `questions` answers before the steps, computing them in its head, and the
# speeches follow those answers. GeoGebra then computes the real values on the board, so a wrong
# mental calculation makes the lesson say one number and show another. This module evaluates the
# lesson's plain-arithmetic assignments ("name = <arithmetic over numbers, lists and earlier names>")
# the same way GeoGebra will, and reports when a final result is missing from the answers or speeches.
# Anything else (points, sliders, GeoGebra commands other than a few list statistics, functions) is skipped.
# It checks that the lesson agrees with its own commands; it cannot tell whether the commands use the
# right method (that is up to the prompt rules).

_ASSIGNMENT_RE = re.compile(r'^\s*([A-Za-z][A-Za-z0-9]*)\s*=\s*([^=]+)$')
_NUMBER_RE = re.compile(r'\d[\d.,]*\d|\d')
_PERCENT_AFTER_RE = re.compile(r'\s*(?:%|por\s*ciento|percent)', re.IGNORECASE)
# Commands whose numeric arguments only set up the drawing: the view, a function's interval, a slider's range
_LAYOUT_CALL_RE = re.compile(r'\b(?:ZoomIn|Function|Slider)\s*\(')
MAX_EXPRESSION_CHARS = 300
MAX_EXPONENT = 1000
# A written number matches a value within half a unit of its last digit ("19" for 18.97, "632.46" for
# 632.4555), or within this fraction of the value, whichever is larger, so answers computed from rounded
# intermediate values still match (1898.69 for 1897.37). A guessed value is usually much further off.
RELATIVE_TOLERANCE = 0.002


# Decimals kept before rounding: they drop the binary noise of a float (0.3 * 142 + 0.7 * 125.55 is stored as
# 130.48499999999999, which must round to 130.49 as GeoGebra shows it, not to 130.48)
_NOISE_DECIMALS = 10


def _round_half_up_decimal(value: float, digits: int) -> Decimal:
    """value rounded to digits decimals the way GeoGebra rounds: halves away from zero, after dropping the
    binary noise. Python's round() rounds halves to even and keeps the noise (round(130.485, 2) == 130.48)."""
    cleaned = Decimal(f"{value:.{_NOISE_DECIMALS}f}")
    return cleaned.quantize(Decimal(1).scaleb(-int(digits)), rounding=ROUND_HALF_UP)


def _round_half_up(value, digits=0):
    # The round(x) and round(x, n) commands of GeoGebra
    return float(_round_half_up_decimal(value, digits))


_FUNCTIONS = {
    "sqrt": math.sqrt,
    "cbrt": lambda x: math.copysign(abs(x) ** (1 / 3), x),
    "abs": abs,
    "ceil": math.ceil,
    "floor": math.floor,
    "round": _round_half_up,
    "exp": math.exp,
    "ln": math.log,
}
# GeoGebra list statistics, called with one list: Mean({1, 2, 3}) or Mean(salesList)
_LIST_FUNCTIONS = {
    "Mean": statistics.fmean,
    "Sum": math.fsum,
    "Median": statistics.median,
    "Max": max,
    "Min": min,
    "Length": len,
}
_CONSTANTS = {"pi": math.pi}
_BINARY_OPERATORS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.Pow: lambda a, b: a ** b,
}
# Nodes allowed in a "scaled copy": one name combined with constants by + - * / (e.g. 2 * eoq, 1.1 * lotEnd + 5)
_SCALED_COPY_NODES = (
    ast.BinOp, ast.UnaryOp, ast.Constant, ast.Name, ast.Load,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.USub, ast.UAdd,
)


class LessonValue(NamedTuple):
    name: str
    value: float
    step_index: int
    is_input: bool        # a number typed as given data, e.g. "demand = 12000"
    is_scaled_copy: bool  # one earlier value scaled or shifted by constants, e.g. "lotEnd = 2 * eoq"
    refs: frozenset       # earlier values (numbers or lists) its expression uses


class _NotArithmetic(Exception):
    pass


def _evaluate_list(node, env: dict, refs: set) -> list:
    if isinstance(node, ast.List):
        return [_evaluate(element, env, refs) for element in node.elts]
    if isinstance(node, ast.Name) and isinstance(env.get(node.id), list):
        refs.add(node.id)
        return env[node.id]
    raise _NotArithmetic("not a list of numbers")


def _evaluate(node, env: dict, refs: set) -> float:
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return float(node.value)
    if isinstance(node, ast.Name):
        if isinstance(env.get(node.id), float):
            refs.add(node.id)
            return env[node.id]
        if node.id in _CONSTANTS:
            return _CONSTANTS[node.id]
        raise _NotArithmetic(node.id)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        value = _evaluate(node.operand, env, refs)
        return -value if isinstance(node.op, ast.USub) else value
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPERATORS:
        left = _evaluate(node.left, env, refs)
        right = _evaluate(node.right, env, refs)
        if isinstance(node.op, ast.Pow) and abs(right) > MAX_EXPONENT:
            raise _NotArithmetic("exponent too large")
        result = _BINARY_OPERATORS[type(node.op)](left, right)
        if isinstance(result, complex):  # e.g. a negative base with a fractional exponent
            raise _NotArithmetic("complex result")
        return float(result)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
        name = node.func.id
        if name in _LIST_FUNCTIONS and len(node.args) == 1:
            return float(_LIST_FUNCTIONS[name](_evaluate_list(node.args[0], env, refs)))
        if name in ("Max", "Min") and len(node.args) >= 2:  # Max(a, b) also exists for plain numbers
            values = [_evaluate(arg, env, refs) for arg in node.args]
            return max(values) if name == "Max" else min(values)
        if name in _FUNCTIONS:
            args = [_evaluate(arg, env, refs) for arg in node.args]
            return float(_FUNCTIONS[name](*args))
    raise _NotArithmetic(type(node).__name__)


def _is_scaled_copy(body) -> bool:
    nodes = list(ast.walk(body))
    return all(isinstance(n, _SCALED_COPY_NODES) for n in nodes) and sum(isinstance(n, ast.Name) for n in nodes) == 1


def evaluate_lesson_values(steps) -> list:
    """Return a LessonValue for every plain-arithmetic assignment, in lesson order (lists are kept
    only to evaluate later statistics such as Mean(salesList), they are not results themselves)."""
    env, results = {}, []
    for index, step in enumerate(steps if isinstance(steps, list) else []):
        command = step.get("command") if isinstance(step, dict) else None
        if not isinstance(command, str):
            continue
        match = _ASSIGNMENT_RE.match(command)
        if not match or len(match.group(2)) > MAX_EXPRESSION_CHARS:
            continue
        name, expression = match.groups()
        refs = set()
        # GeoGebra lists {1, 2} become Python lists [1, 2]; ^ is a power
        python_expression = expression.strip().replace("^", "**").replace("{", "[").replace("}", "]")
        try:
            tree = ast.parse(python_expression, mode="eval")
            if isinstance(tree.body, ast.List):
                env[name] = _evaluate_list(tree.body, env, refs)
                continue
            value = _evaluate(tree.body, env, refs)
        except (_NotArithmetic, SyntaxError, ValueError, TypeError, ZeroDivisionError, OverflowError, RecursionError):
            env.pop(name, None)  # redefined as something we cannot evaluate: forget the old value
            continue
        if not math.isfinite(value):
            env.pop(name, None)
            continue
        env[name] = value
        body = tree.body.operand if isinstance(tree.body, ast.UnaryOp) else tree.body
        results.append(LessonValue(
            name, value, index, isinstance(body, ast.Constant), _is_scaled_copy(tree.body), frozenset(refs),
        ))
    return results


def _layout_helpers(steps, evaluated: list) -> set:
    """Names of values that only set up the drawing, so the answers need not mention them.

    A helper is a scaled copy that a later ZoomIn, Function or Slider uses (e.g. "lotEnd = 2 * eoq" as
    the end of the graph's interval), or a scaled copy another helper is built from. A real result that
    combines several values (totalCost = ...) is never a helper, even when a ZoomIn uses it.
    """
    commands = [
        s["command"] if isinstance(s, dict) and isinstance(s.get("command"), str) else ""
        for s in (steps if isinstance(steps, list) else [])
    ]
    helpers = set()
    for v in evaluated:
        if not v.is_scaled_copy:
            continue
        name_re = re.compile(rf'\b{re.escape(v.name)}\b')
        if any(_LAYOUT_CALL_RE.search(c) and name_re.search(c) for c in commands[v.step_index + 1:]):
            helpers.add(v.name)
    changed = True
    while changed:  # e.g. "costTop = 2 * costOpt" only used to build "yTop = 1.2 * costTop"
        changed = False
        for v in evaluated:
            if v.is_scaled_copy and v.name not in helpers and any(
                v.name in h.refs for h in evaluated if h.name in helpers
            ):
                helpers.add(v.name)
                changed = True
    return helpers


def _number_readings(token: str) -> list:
    """The plain-number spellings of a written number: as 1,234.5 (comma = thousands) and as 1.234,5
    (dot = thousands). A separator only counts as thousands when every group after it has exactly 3 digits,
    so "18.97" is never read as 1897 (that once confirmed a total cost of 1897.37 with "18.97 orders")."""
    candidates = []
    for thousands, decimal in ((",", "."), (".", ",")):
        integer_part, _, decimal_part = token.partition(decimal)
        if (token.count(decimal) > 1 or thousands in decimal_part
                or any(len(group) != 3 for group in integer_part.split(thousands)[1:])):
            continue
        candidates.append(token.replace(thousands, "").replace(decimal, "."))
    return candidates


def _written_numbers(text: str) -> list:
    """One entry per number written in the text: (its readings as (value, decimals), written as a percentage?).
    Each number is read both as 1,234.5 and as 1.234,5, since answers may use either."""
    found = []
    for match in _NUMBER_RE.finditer(text):
        token = match.group()
        readings = []
        for candidate in _number_readings(token):
            try:
                value = float(candidate)
            except ValueError:
                continue
            decimals = len(candidate.split(".", 1)[1]) if "." in candidate else 0
            readings.append((value, decimals))
        if readings:
            found.append((readings, bool(_PERCENT_AFTER_RE.match(text, match.end()))))
    return found


def _matches(value: float, written) -> bool:
    readings, is_percentage = written
    # A fraction may be said as a percentage (0.875 as "87.5 %"), but only a number written with % counts for that
    targets = [abs(value)] + ([abs(value) * 100] if is_percentage else [])
    return any(
        abs(number - target) <= max(0.5 * 10 ** -decimals, RELATIVE_TOLERANCE * target)
        for number, decimals in readings for target in targets
    )


def _count_stated(values: list, written: list) -> int:
    """How many values can be paired, each with a different written number (maximum bipartite matching).
    One number cannot confirm two values: the "140" of one answer must not also confirm a result of 140.44."""
    candidates = [[j for j, w in enumerate(written) if _matches(value, w)] for value in values]
    owner = {}  # written number index -> value index

    def assign(i, seen):  # augmenting path
        for j in candidates[i]:
            if j not in seen:
                seen.add(j)
                if j not in owner or assign(owner[j], seen):
                    owner[j] = i
                    return True
        return False

    return sum(assign(i, set()) for i in range(len(values)))


def _all_stated(values: list, written: list) -> bool:
    return _count_stated(values, written) == len(values)


def count_stated_in_text(values: list, text: str) -> int:
    """How many of the values the text states, each with its own number (used by the local benchmark in exercises_test/, kept out of the repo)."""
    return _count_stated(values, _written_numbers(text))


def find_unconfirmed_results(steps, questions) -> dict:
    """If a final result of the lesson's arithmetic is never stated in the speeches, return every computed
    result (name -> value) so the model can be told the real values. Otherwise return {}.

    Only the speeches count: they are what the student hears and reads, while the `questions` answers are
    never shown. Requiring the answers too made every intermediate value the answers did not repeat (the
    time of each station) cost a retry. The answers are only the gate: a lesson whose answers hold no
    number (a drawing) has no numeric result to verify.

    A final result is one that no later assignment uses (e.g. the total cost, not the EOQ it is built from).
    Layout helpers (see _layout_helpers) are neither checked nor reported.
    Speeches that write a result in words ("six hundred") do not count as stating it.
    """
    if not isinstance(questions, list):
        return {}
    answers = " ".join(q["answer"] for q in questions if isinstance(q, dict) and isinstance(q.get("answer"), str))
    if not _written_numbers(answers):
        return {}
    speeches = " ".join(
        s["speech"] for s in steps if isinstance(s, dict) and isinstance(s.get("speech"), str)
    ) if isinstance(steps, list) else ""

    evaluated = evaluate_lesson_values(steps)
    helpers = _layout_helpers(steps, evaluated)
    results = [v for v in evaluated if not v.is_input and v.name not in helpers]
    # A value a check compares (the time of a station) is verified by the check
    checked = _names_used_by_checks(steps)
    final_values = [
        v.value for v in results
        if v.name not in checked
        and not any(v.name in later.refs for later in evaluated if later.step_index > v.step_index and later.name not in helpers)
    ]
    if _all_stated(final_values, _written_numbers(speeches)):
        return {}
    return {v.name: v.value for v in results}


# --- Checks (prompt rule CHECK YOUR CONDITIONS) --------------------------------------------------------
# The model writes the conditions its solution must meet as booleans ("checkStation1 = station1Time <=
# taktTime"). It states conditions well but rarely notices when its own solution breaks one, so the server
# evaluates them and rejects the lesson when one is false. Checks over other GeoGebra commands (Root,
# Intersect...) cannot be evaluated here; the browser computes them and /api/voice logs the false ones.

_CHECK_RE = re.compile(r'^\s*([cC]heck[A-Za-z0-9]*)\s*[:=]\s*(.+)$')
_IDENTIFIER_RE = re.compile(r'\b[A-Za-z][A-Za-z0-9]*\b')
_CHECK_TOLERANCE = 1e-9  # relative: 0.1 + 0.2 <= 0.3 must hold
_COMPARISONS = {
    ast.Lt: ("<", lambda a, b, eps: a < b),
    ast.LtE: ("<=", lambda a, b, eps: a <= b + eps),
    ast.Gt: (">", lambda a, b, eps: a > b),
    ast.GtE: (">=", lambda a, b, eps: a >= b - eps),
    ast.Eq: ("==", lambda a, b, eps: abs(a - b) <= eps),
    ast.NotEq: ("!=", lambda a, b, eps: abs(a - b) > eps),
}


def _check_commands(steps):
    """(name, expression) for every check of the lesson."""
    for step in steps if isinstance(steps, list) else []:
        command = step.get("command") if isinstance(step, dict) else None
        match = _CHECK_RE.match(command) if isinstance(command, str) else None
        if match:
            yield match.group(1), match.group(2).strip()


def check_names(steps) -> list:
    return list(dict.fromkeys(name for name, _ in _check_commands(steps)))


def _names_used_by_checks(steps) -> set:
    return {name for _, expression in _check_commands(steps) for name in _IDENTIFIER_RE.findall(expression)}


def find_failed_checks(steps) -> list:
    """The lesson's checks that are false, as text for the retry note, e.g.
    "checkStation1: station1Time <= taktTime, that is 5 <= 4". Only checks over plain arithmetic are evaluated."""
    values = {v.name: v.value for v in evaluate_lesson_values(steps)}  # last definition wins
    failed = []
    for name, expression in _check_commands(steps):
        python_expression = (expression.replace("≤", "<=").replace("≥", ">=").replace("≠", "!=")
                             .replace("^", "**"))
        try:
            node = ast.parse(python_expression, mode="eval").body
            if not isinstance(node, ast.Compare) or not all(type(op) in _COMPARISONS for op in node.ops):
                continue
            operands = [_evaluate(n, values, set()) for n in [node.left, *node.comparators]]
        except (_NotArithmetic, SyntaxError, ValueError, TypeError, ZeroDivisionError, OverflowError, RecursionError):
            continue  # not plain arithmetic: the browser evaluates it
        pairs = list(zip(node.ops, operands, operands[1:]))
        if all(_COMPARISONS[type(op)][1](a, b, _CHECK_TOLERANCE * max(1.0, abs(a), abs(b))) for op, a, b in pairs):
            continue
        shown = format_value(operands[0]) + "".join(
            f" {_COMPARISONS[type(op)][0]} {format_value(b)}" for op, _, b in pairs)
        failed.append(f"{name}: {expression}, that is {shown}")
    return failed


def build_checks_retry_note(failed: list) -> str:
    return (
        "[SYSTEM VALIDATION - CRITICAL] A previous answer to this request was REJECTED because these checks of its "
        f"solution are FALSE: {'; '.join(failed)}. The solution breaks a condition of the exercise. Change the "
        "solution itself (for example one more station, another grouping, another vertex or another value) so that "
        "every condition holds, and write the complete lesson again from scratch. The corrected solution MUST be "
        "drawn again (diagram, graph or figure), never only computed."
    )


def format_value(value: float) -> str:
    """Two decimals, or four for values below 1 (0.6927 must not become 0.69), rounded as GeoGebra shows
    them, so the voice says the same digits the board displays."""
    rounded = _round_half_up_decimal(value, 4 if abs(value) < 1 else 2)
    text = format(rounded, "f").rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def build_arithmetic_retry_note(values: dict) -> str:
    listed = ", ".join(f"{name} = {format_value(value)}" for name, value in values.items())
    return (
        "[SYSTEM VALIDATION - CRITICAL] A previous answer to this request was REJECTED because its speeches "
        "contradict or never state the values that its own GeoGebra commands compute. "
        f"GeoGebra computes: {listed}. Write the complete lesson again from scratch with the same calculations: "
        "every `answer` and the `speech` of the step that computes each result MUST state these values with "
        "digits, rounded the way a teacher would: at most 2 decimals, or whole units when the quantity must be "
        "whole (e.g. 18.97 orders is about 19 orders)."
    )
