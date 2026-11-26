import re

# Real GeoGebra commands the model is allowed to emit. It covers every command documented in
# app/prompts/ plus other common ones, so a correct lesson is never rejected. Anything
# capitalized and followed by "(" that is not listed here is treated as a hallucination
# (e.g. RegularPolygon, Incenter, Circumcenter, Orthocenter, Label, VerticalAsymptote).
VALID_COMMANDS = frozenset({
    # Points, lines and polygons
    "Point", "PointIn", "ClosestPoint", "Midpoint", "Intersect", "IntersectPath",
    "Segment", "Line", "Ray", "Vector", "Polygon", "Polyline", "RigidPolygon",
    "PerpendicularLine", "ParallelLine", "PerpendicularBisector", "AngleBisector",
    "Tangent", "Direction", "UnitVector", "PerpendicularVector", "UnitPerpendicularVector",
    "Corner", "Vertex", "Centroid", "Barycenter",
    # Circles, arcs and conics
    "Circle", "Semicircle", "Arc", "Sector", "CircularArc", "CircularSector",
    "CircumcircularArc", "CircumcircularSector", "Incircle", "Center", "Radius", "Diameter",
    "Conic", "Ellipse", "Hyperbola", "Parabola", "Focus", "Directrix", "Axes",
    "MajorAxis", "MinorAxis", "SemiMajorAxisLength", "SemiMinorAxisLength",
    "Eccentricity", "LinearEccentricity", "Parameter", "Polar", "OsculatingCircle",
    # Triangles
    "TriangleCenter", "TriangleCurve", "Trilinear",
    # Measurement
    "Angle", "Distance", "Area", "Perimeter", "Circumference", "Length", "Slope",
    "Curvature", "AffineRatio", "CrossRatio",
    # Transformations and matrices
    "Translate", "Rotate", "Reflect", "Dilate", "Shear", "Stretch", "ApplyMatrix",
    "Determinant", "Invert", "Transpose", "Identity", "Dot", "Cross",
    # Functions and calculus
    "Function", "If", "Curve", "Root", "Roots", "ComplexRoot", "Extremum", "InflectionPoint",
    "Asymptote", "Derivative", "Integral", "IntegralBetween", "NIntegral", "Limit",
    "LimitAbove", "LimitBelow", "TaylorPolynomial", "UpperSum", "LowerSum", "LeftSum",
    "RectangleSum", "TrapezoidalSum", "SlopeField", "SolveODE", "NSolveODE", "Polynomial",
    "Spline", "Numerator", "Denominator", "Degree", "Coefficients", "Factor", "Expand",
    "Simplify", "Division", "Iteration", "IterationList",
    # Lists, sequences and loci
    "Sequence", "Element", "First", "Last", "Take", "Append", "Join", "Flatten", "Reverse",
    "Sort", "Unique", "Zip", "KeepIf", "RemoveUndefined", "IndexOf", "Count", "CountIf",
    "Sum", "Product", "Min", "Max", "Locus", "LocusEquation",
    # Discrete math (needs "discrete" in the applet's preloadModules, see static/app.js)
    "ConvexHull", "Voronoi", "DelaunayTriangulation", "MinimumSpanningTree",
    "ShortestDistance", "TravelingSalesman",
    # Numbers
    "Mod", "Div", "GCD", "LCM", "RandomBetween", "RandomElement", "RandomUniform",
    "RandomNormal", "ToPoint", "ToComplex", "ToPolar",
    # Statistics and charts
    "Mean", "Median", "Mode", "SD", "SampleSD", "Variance", "SampleVariance", "Q1", "Q3",
    "Covariance", "CorrelationCoefficient", "Classes", "Frequency", "FitLine", "FitLineX",
    "FitPoly", "FitExp", "FitLog", "FitPow", "FitSin", "FitLogistic", "BarChart",
    "Histogram", "BoxPlot", "DotPlot", "FrequencyPolygon", "LineGraph", "PieChart",
    "Normal", "BinomialDist",
    # Text
    "Text", "FormulaText", "FractionText", "SurdText", "ScientificText", "TableText", "Name",
    # Interactivity, view and style
    "Slider", "Checkbox", "StartAnimation", "SetValue", "SetCoords", "ZoomIn", "ZoomOut",
    "CenterView", "Pan", "ShowAxes", "ShowGrid", "ShowLabel", "ShowLayer", "HideLayer",
    "SetColor", "SetDynamicColor", "SetBackgroundColor", "SetLineThickness", "SetLineStyle",
    "SetPointSize", "SetPointStyle", "SetFilling", "SetCaption", "SetLabelMode",
    "SetVisibleInView", "SetConditionToShowObject", "SetFixed", "SetLayer", "SetTrace",
    "Rename", "Delete", "UpdateConstruction",
})

_STRING_RE = re.compile(r'"[^"]*"')
_CALL_RE = re.compile(r'\b([A-Z][A-Za-z0-9]*)\s*\(')
# "funcF(x) = ..." defines a function, so later calls to it are not commands
_FUNCTION_DEF_RE = re.compile(r'^\s*([A-Za-z][A-Za-z0-9]*)\s*\(\s*[a-z][A-Za-z0-9]*\s*\)\s*:?=')


def _step_commands(steps):
    if not isinstance(steps, list):
        return
    for step in steps:
        if isinstance(step, dict) and isinstance(step.get("command"), str):
            yield step, step["command"]


def _called_names(cmd: str) -> list:
    return _CALL_RE.findall(_STRING_RE.sub('""', cmd))


def find_unknown_commands(steps) -> list:
    """Return the capitalized command names used in the lesson that GeoGebra does not have."""
    defined = set()
    for _, cmd in _step_commands(steps):
        m = _FUNCTION_DEF_RE.match(cmd)
        if m:
            defined.add(m.group(1))

    unknown = []
    for _, cmd in _step_commands(steps):
        for name in _called_names(cmd):
            if name not in VALID_COMMANDS and name not in defined and name not in unknown:
                unknown.append(name)
    return unknown


def build_retry_note(unknown: list) -> str:
    return (
        "[SYSTEM VALIDATION - CRITICAL] A previous answer to this request was REJECTED because it used "
        f"GeoGebra commands that DO NOT EXIST: {', '.join(unknown)}. "
        "Write the complete lesson again from scratch. You MUST use ONLY commands from this list of valid "
        f"GeoGebra commands: {', '.join(sorted(VALID_COMMANDS))}."
    )


# --- Does the lesson draw anything? ------------------------------------------------------------------
# TutorGebra is a visual tutor, but the model sometimes answers with numbers only, typically when it rewrites
# a lesson after a validation note (it then focuses on the numbers and drops the diagram).

# Commands that put something visible on the board
DRAWING_COMMANDS = frozenset({
    "Polygon", "Polyline", "Segment", "Line", "Ray", "Vector", "Circle", "Ellipse", "Hyperbola", "Parabola",
    "Conic", "Semicircle", "CircularArc", "CircularSector", "Function", "Curve", "Text", "Point", "PointIn",
    "Intersect", "Midpoint", "Centroid", "Center", "TriangleCenter", "Incircle", "Tangent", "PerpendicularLine",
    "ParallelLine", "PerpendicularBisector", "AngleBisector", "Angle", "Locus", "ConvexHull", "FitLine",
    "Asymptote", "Extremum", "Root", "Focus", "Vertex", "Directrix", "MajorAxis", "MinorAxis", "InflectionPoint",
    "Integral", "IntegralBetween", "UpperSum", "LowerSum", "Translate", "Rotate", "Reflect", "Dilate",
    "ApplyMatrix", "BarChart", "Histogram", "BoxPlot", "DotPlot", "StemPlot", "PieChart", "Slider", "Sequence",
})
_POINT_RE = re.compile(r'^\s*[A-Z][A-Za-z0-9]*\s*=\s*\(')                        # A = (1, 2)
_NAMED_EQUATION_RE = re.compile(r'^\s*[A-Za-z][A-Za-z0-9]*\s*:')                  # line1: y = 2x + 1
_BARE_EQUATION_RE = re.compile(r'^[^=<>!]*\b[xy]\b[^=<>!]*(?<![<>!=])=(?!=)')       # y = 2x + 1, x^2 + y^2 = 16


_CHECK_OR_AUX_RE = re.compile(r'^\s*(?:check|aux)[A-Za-z0-9]*\s*[:=]')  # booleans and helper numbers, never visible


def _draws(cmd: str) -> bool:
    if not cmd.strip() or _CHECK_OR_AUX_RE.match(cmd):
        return False
    if _POINT_RE.match(cmd) or _FUNCTION_DEF_RE.match(cmd) or _NAMED_EQUATION_RE.match(cmd):
        return True
    if _BARE_EQUATION_RE.match(cmd):
        return True
    return any(name in DRAWING_COMMANDS for name in _called_names(cmd))


def lesson_draws_something(steps) -> bool:
    return any(_draws(cmd) for _, cmd in _step_commands(steps))


def build_drawing_retry_note() -> str:
    return (
        "[SYSTEM VALIDATION - CRITICAL] A previous answer to this request was REJECTED because its lesson draws "
        "NOTHING on the board: every command only computes numbers or checks. TutorGebra is a visual tutor. Follow "
        "VISUALIZATION CHOICE and draw the situation (for example a block diagram with one Polygon box per station "
        "joined by Vector arrows and labelled with Text, the graph of the function with its key points, a bar chart, "
        "or the figure itself), keeping every calculation and check. Write the complete lesson again from scratch."
    )


_RESTRICTED_SOURCE_RE = re.compile(r'\bFunction\s*\(\s*([A-Za-z][A-Za-z0-9]*)\s*,')


def _is_hidden_later(steps, name: str) -> bool:
    hide_re = re.compile(
        rf'\b(?:SetVisibleInView\s*\(\s*{re.escape(name)}\s*,\s*1\s*,\s*false|'
        rf'SetConditionToShowObject\s*\(\s*{re.escape(name)}\s*,\s*false)\s*\)'
    )
    return any(hide_re.search(cmd) for _, cmd in _step_commands(steps))


def hide_restricted_function_sources(steps) -> list:
    """Hide a lesson function that is drawn again restricted with Function(funcF, a, b).

    GeoGebra keeps drawing funcF complete, so the board shows the curve twice, including the negative
    branch an applied quantity cannot have. Unless the lesson already hides funcF, a step
    SetVisibleInView(funcF, 1, false) (no speech) is inserted right after the restriction.
    Returns the names hidden, for logging.
    """
    if not isinstance(steps, list):
        return []
    defined, hidden = set(), []
    i = 0
    while i < len(steps):
        cmd = steps[i].get("command") if isinstance(steps[i], dict) else None
        if isinstance(cmd, str):
            for name in _RESTRICTED_SOURCE_RE.findall(_STRING_RE.sub('""', cmd)):
                if name in defined and name not in hidden and not _is_hidden_later(steps, name):
                    steps.insert(i + 1, {"command": f"SetVisibleInView({name}, 1, false)", "speech": ""})
                    hidden.append(name)
            m = _FUNCTION_DEF_RE.match(cmd)
            if m:
                defined.add(m.group(1))
        i += 1
    return hidden


def blank_unknown_commands(steps, unknown: list) -> None:
    """Last resort: keep the explanation but drop commands GeoGebra would reject with a popup."""
    for step, cmd in _step_commands(steps):
        if any(name in unknown for name in _called_names(cmd)):
            step["command"] = ""
