import logging

# What the OpenRouter calls have in common: output limits for models that reason, usage logging, and turning
# provider failures into a short code the UI can explain to the user (static/i18n.js, keys provider.reason.*).

logger = logging.getLogger('TutorGebraProvider')

# Anthropic models on OpenRouter reason before answering, and the reasoning counts against max_tokens: with
# 2500 tokens, Claude Sonnet 5.5 spent 2229 reasoning and the lesson came back cut. They get their own budget.
REASONING_BUDGET = 3000


def completion_limits(models: list, answer_tokens: int, reasoning_budget: int = REASONING_BUDGET) -> dict:
    """max_tokens (and the reasoning budget, for models that reason) for a chat call.

    The reasoning budget is a target, not a cap: Claude Sonnet 5.5 reasoned 3635 tokens on a 3000 budget and
    the lesson was cut. max_tokens leaves room for half the budget more; only the tokens generated are paid."""
    if any(isinstance(m, str) and m.startswith("anthropic/") for m in models):
        return {"max_tokens": answer_tokens + reasoning_budget + reasoning_budget // 2,
                "reasoning": {"max_tokens": reasoning_budget}}
    return {"max_tokens": answer_tokens}


def log_usage(label: str, response) -> None:
    """One line per call with the tokens and the cost OpenRouter reports."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return
    details = getattr(usage, "completion_tokens_details", None)
    reasoning = getattr(details, "reasoning_tokens", None) if details is not None else None
    cost = getattr(usage, "cost", None)
    finish = response.choices[0].finish_reason if getattr(response, "choices", None) else None
    logger.info(
        f"{label} usage: prompt {getattr(usage, 'prompt_tokens', '?')}, completion {getattr(usage, 'completion_tokens', '?')}"
        + (f" (reasoning {reasoning})" if reasoning else "")
        + (f", cost ${cost:.4f}" if isinstance(cost, (int, float)) else "")
        + f", finish {finish}, model {getattr(response, 'model', '?')}"
    )


def response_problem(response) -> str | None:
    """'truncated' or 'empty' when a response carries no usable text, else None."""
    choice = response.choices[0]
    if getattr(choice, "finish_reason", None) == "length":
        return "truncated"
    content = getattr(getattr(choice, "message", None), "content", None)
    if not isinstance(content, str) or not content.strip():
        return "empty"
    return None


# Error classes of the openrouter SDK (and status codes, for anything else) -> code shown to the user
_CLASS_CODES = (
    ("PaymentRequired", "credits"),
    ("TooManyRequests", "rate_limit"),
    ("Timeout", "timeout"),
    ("NoResponse", "timeout"),
    ("ServiceUnavailable", "unavailable"),
    ("ProviderOverloaded", "unavailable"),
    ("BadGateway", "unavailable"),
    ("InternalServer", "unavailable"),
    ("Forbidden", "moderation"),
    ("Unauthorized", "auth"),
)
_STATUS_CODES = {402: "credits", 429: "rate_limit", 408: "timeout", 504: "timeout", 502: "unavailable",
                 503: "unavailable", 500: "unavailable", 403: "moderation", 401: "auth"}

# Fallback text for the 'error' event (the UI shows its own translation of the code); Spanish, like every
# user-facing error detail of the API
ERROR_DETAILS = {
    "credits": "No se pudo generar la lección: la cuenta del proveedor del modelo no tiene crédito suficiente.",
    "rate_limit": "No se pudo generar la lección: el proveedor del modelo está limitando las peticiones. Espera un momento.",
    "timeout": "No se pudo generar la lección: el proveedor del modelo tardó demasiado en responder.",
    "unavailable": "No se pudo generar la lección: el proveedor del modelo no está disponible en este momento.",
    "moderation": "No se pudo generar la lección: el proveedor rechazó la petición por sus filtros de contenido.",
    "auth": "No se pudo generar la lección: la clave de API no es válida.",
    "truncated": "No se pudo generar la lección: la respuesta del modelo se cortó por el límite de tokens.",
    "empty": "No se pudo generar la lección: el modelo devolvió una respuesta vacía.",
    "provider": "No se pudo generar la lección: el proveedor del modelo devolvió un error.",
}


def is_provider_error(exc: Exception) -> bool:
    """True for failures of the call to OpenRouter (the SDK's errors, network errors), not bugs in our code."""
    names = {cls.__name__ for cls in type(exc).__mro__}
    if names & {"OpenRouterError", "NoResponseError", "HTTPError", "TimeoutException", "NetworkError", "TransportError"}:
        return True
    return type(exc).__module__.split(".")[0] in ("openrouter", "httpx", "httpcore")


def classify_provider_error(exc: Exception) -> str:
    name = type(exc).__name__
    for fragment, code in _CLASS_CODES:
        if fragment in name:
            return code
    status = getattr(getattr(exc, "raw_response", None), "status_code", None) or getattr(exc, "status_code", None)
    if status in _STATUS_CODES:
        return _STATUS_CODES[status]
    text = str(exc).lower()
    if "credit" in text:
        return "credits"
    if "timed out" in text or "timeout" in text:
        return "timeout"
    return "provider"


class ProviderError(Exception):
    """The lesson could not be generated because of the model provider; code says why (see ERROR_DETAILS)."""

    def __init__(self, code: str, message: str = ""):
        super().__init__(message or code)
        self.code = code if code in ERROR_DETAILS else "provider"
