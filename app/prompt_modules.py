import os
import re
import unicodedata

# --- Modular system prompt ---------------------------------------------------------------
# The system prompt is assembled per request from app/prompts/: core.md (always), the topic
# modules whose keywords appear in the request, and output_format.md (always, last). core.md
# goes first so the start of the prompt is identical in every request and provider prompt
# caching keeps working. Files are read on every request, so prompt edits apply without restart.

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")


def _keywords(*words: str) -> str:
    """Words matched at the start of a word: 'triangul' covers triangulo, triangulos, triangular."""
    return r"\b(?:" + "|".join(words) + ")"


# Statistics exercises also need the list syntax of lists.md, so both modules share these words.
_STATISTICS_WORDS = _keywords(
    r"media\b", r"medias\b", "promedio", "mediana", r"moda\b", "desviacion", "varianza",
    r"mean\b", "average", "median", r"mode\b", "standard deviation", "variance",
    "regresion", "regression", "ajuste lineal", "linea de tendencia", "trend line", "correlaci", "correlation",
    "grafico de barras", "grafica de barras", "diagrama de barras", "bar chart", "bar graph",
    "histogram", "diagrama de caja", "boxplot", "box plot", "cuartil", "quartile", "percentil",
    r"dato", r"data\b", "frecuencia", "frequenc", "estadistic", "statistic", "probabilid", "probabilit",
    "muestra aleatoria", "muestreo", r"tamano de (?:la )?muestra", "sample", "encuesta", "survey", "dispersi", "scatter",
)

# (file, pattern) in the order the modules are appended after core.md. Keywords are written
# lowercase without accents and are deliberately broad: an extra module costs a few hundred
# tokens, a missing one makes the model avoid the right command and break the lesson.
PROMPT_MODULES = [
    ("inequalities.md", "|".join([
        _keywords("desigualdad", "inecuaci", "inequalit", "region factible", "feasible", "programacion lineal",
                  "linear programming", "restriccion", "constraint", "maximiz", "minimiz", "optimiz",
                  "funcion objetivo", "objective function", "semiplano", "half-plane", "half plane"),
        r"[<>≤≥]",
    ])),
    ("regular_polygons.md", "|".join([
        _keywords("poligono regular", "poligonos regulares", "regular", "pentagon", "hexagon", "heptagon",
                  "octagon", "octogon", "eneagon", "nonagon", "decagon", "dodecagon", "equilater",
                  "lados iguales", "equal sides", "apotema", "apothem"),
        r"\d+\s*(?:lados|sides)\b",
    ])),
    ("conics.md", "|".join([
        _keywords("circul", "circunferenc", "circle", "circumferen", "radio", "radius", "radii", "diametr",
                  "diameter", "arco", r"arc\b", r"arcs\b", "sector", "semicircul", "semicircle", "elips", "ellips",
                  "parabol", "hiperbol", "hyperbol", "conic", "foco", "focus", "foci", "directri",
                  "excentricidad", "eccentricit", "eje mayor", "eje menor", "major axis", "minor axis",
                  "semieje", "semi-major", "semimajor", "semi-minor", "asintot", "asymptot", "inscrit",
                  "circunscrit", "inscribed", "circumscrib", "tangen"),
        r"y\s*(?:\^|\*\*)\s*2", r"y²",
    ])),
    ("triangles.md", _keywords(
        "triangul", "triangle", "incentr", "incenter", "circuncentr", "circumcent", "circumcircle", "baricentr",
        "centroid", "ortocentr", "orthocent", "altura", "altitude", "mediana", "median", "mediatri", "bisectri",
        "bisector", "inscrit", "circunscrit", "inscribed", "circumscrib", "incircle", "pitagor", "pythagor",
        "cateto", "hipotenusa", "hypotenuse", "isoscel", "escaleno", "scalene", "equilater",
    )),
    ("functions.md", "|".join([
        _keywords("funcion", "function", "derivad", "derivar", "derivative", "differentiat", "diferencial",
                  "integra", "antiderivad", "primitiva", "limite", "limit", "continuidad", "continuity", "tangen",
                  "raiz", "raices", "root", "cero de", "ceros de", "zeros of", "asintot", "asymptot", "maxim",
                  "minim", "extremum", r"extrema\b", "extremo relativo", "extremos relativos", "extremo absoluto",
                  "extremos absolutos", "valor extremo", "valores extremos", "inflexi", "inflection", "concavidad", "concavity", "crecient", "decrecient",
                  "increasing", "decreasing", "monoton", "taylor", "maclaurin", "riemann", "suma superior",
                  "suma inferior", "upper sum", "lower sum", "area bajo", "area entre", "area under", "area between",
                  "parametric", "parametriz", "curva", "curve", "a trozos", "por partes", "por tramos", "piecewise",
                  "vector", "grafic", "graph", "plot", "polinom", "polynomial", "cuadratic", "quadratic", "cubic",
                  "exponencial", "exponential", "logarit", "trigonometr", "seno", "coseno", "sine", "cosine",
                  r"sin\b", r"sen\b", r"cos\b", r"tan\b", r"ln\b", r"log\b", r"exp\b", "sqrt", "dominio", "domain",
                  "recorrido", r"lim\b", r"dx\b",
                  # applied.md draws quantities that change over time as functions (VISUALIZATION CHOICE)
                  "interes", "interest", "prestamo", "loan", "depreciaci", "depreciat", "crecimiento", "growth",
                  "decaimiento", "decay"),
        r"\b[a-z]\s*'?\s*\(\s*x\s*\)", r"\by\s*=", r"\^", r"[²³√∫∞]",
    ])),
    ("transformations.md", "|".join([
        _keywords("matri", "transforma", "trasla", "translac", "translat", "rota", "gira", "giro", "refle",
                  "simetri", "symmetr", "homoteci", "dilat", "escala", "scal", "applymatrix", "element",
                  "isometri", "shear", "cizall"),
        r"\{\s*\{", r"\*\s*\{",
    ])),
    ("lists.md", "|".join([
        _keywords("lista", "list", "sucesion", "secuencia", "sequence", "lugar geometrico", "lugares geometricos",
                  "locus", "loci", "envolvente convexa", "envoltura convexa", "cierre convexo", "casco convexo",
                  "convex hull", "conjunto de puntos", "set of points", "nube de puntos", "point cloud"),
        _STATISTICS_WORDS,
        r"\{",
    ])),
    ("statistics.md", _STATISTICS_WORDS),
    ("applied.md", "|".join([
        _keywords(
            # production and operations
            "produc", "estacion", "station", "ciclo", "cycle", "takt", "cuello de botella", "bottleneck",
            "eficienc", "efficienc", "balance", "linea de ensamble", "ensambl", "assembly", "operari",
            "trabajador", "worker", "empleado", "employee", "maquina", "machine", "turno", "inventario",
            "inventory", "demanda", "demand", "capacidad", "capacity", "fabric", "factory", "actividad", "activit",
            "pronostic", "forecast", "suavizacion", "smoothing", "promedio movil", "moving average",
            # economics and finance
            "costo", "coste", "cost", "precio", "price", "ingreso", "income", "revenue", "ganancia", "utilidad",
            "profit", "beneficio", "interes", "interest", "prestamo", "loan", "deuda", "debt", "capital",
            "inversion", "invest", "ahorro", "saving", "depreciaci", "depreciat", "inflacion", "inflation", "tasa",
            r"rate\b", r"rates\b", "punto de equilibrio", "break-even", "break even", "breakeven", r"venta\b", r"ventas\b",
            "vend", "sell", r"sold\b", r"sales\b", "compra", "buy", "pago", "pagar", "pay", "salario", "salary", "sueldo", "dinero",
            "money", "presupuesto", "budget", "dolar", "dollar", "euro", "porcentaje", "percent", "descuento",
            "discount", "impuesto", r"tax\b",
            # rates, physics and other quantities
            "velocidad", "speed", "velocity", "rapidez", "aceleraci", "acceleration", "kilometr", r"km\b", "metros",
            "meter", "metre", r"kg\b", "kilogram", "litro", "liter", "litre", "hora", "hour", "minuto", "minute",
            "seconds", r"dia\b", r"dias\b", r"day", "semana", "week", r"mes\b", "meses", "month", "anual", "annual",
            "year", "mezcla", "mixture", "concentraci", "concentration", "fuerza", "force", "energia", "energy",
            "masa", r"mass\b", "temperatura", "temperature", "densidad", "density", "presion", "pressure", "caja",
            r"box\b", r"boxes\b", "poblacion", "population", "crecimiento", "growth",
        ),
        r"[$€%]", r"\d\s*(?:km/h|m/s|kg|min|hrs?|h)\b",
    ])),
]
PROMPT_MODULES = [(name, re.compile(pattern)) for name, pattern in PROMPT_MODULES]


def _normalize_for_topics(text: str) -> str:
    """Lowercase and strip accents (NFD keeps symbols such as ² and ≤ intact, unlike NFKD)."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def _read_prompt_file(name: str) -> str:
    with open(os.path.join(PROMPTS_DIR, name), "r", encoding="utf-8") as f:
        return f.read().strip("\n")


# Added when the student ticks "Explain more" in the UI, whatever the topic
EXPLAIN_MODULE = "explain.md"


def build_system_prompt(topic_text: str | None, explain: bool = False) -> tuple[str, list]:
    """Assemble core.md + the topic modules that topic_text mentions + explain.md (when explain is set)
    + output_format.md.

    topic_text=None means the content of the request is unknown (a photo without extracted text).
    When it is None or no module matches, every topic module is included.
    Returns the prompt and the names of the matched topic modules (empty list = full prompt).
    """
    matched = []
    if topic_text:
        text = _normalize_for_topics(topic_text)
        matched = [name for name, pattern in PROMPT_MODULES if pattern.search(text)]
    modules = (matched or [name for name, _ in PROMPT_MODULES]) + ([EXPLAIN_MODULE] if explain else [])
    parts = [_read_prompt_file("core.md")] + [_read_prompt_file(name) for name in modules] + [_read_prompt_file("output_format.md")]
    return "\n\n".join(parts), matched
