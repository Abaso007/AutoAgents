import os
from autoagents.system.tools import SearchEngineType, WebBrowserEngineType


# Core LLM settings
# Support both OPENAI_API_KEY and legacy LLM_API_KEY
LLM_API_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("OPENAI_API_MODEL", "gpt-4o")

# OpenAI/Azure-style settings
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "")
OPENAI_API_TYPE = os.getenv("OPENAI_API_TYPE", "")
OPENAI_API_VERSION = os.getenv("OPENAI_API_VERSION", "")
DEPLOYMENT_ID = os.getenv("DEPLOYMENT_ID", "")

# Rates and limits
def _as_int(name: str, default: int | None) -> int | None:
    try:
        val = os.getenv(name)
        return int(val) if val is not None else default
    except Exception:
        return default

def _as_float(name: str, default: float | None) -> float | None:
    try:
        val = os.getenv(name)
        return float(val) if val is not None else default
    except Exception:
        return default

def _as_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return str(val).strip().lower() in ("1", "true", "yes", "y", "on")

RPM = _as_int("RPM", 10) or 10
# Ensure RPM is at least 1
RPM = max(1, int(RPM))

MAX_TOKENS = _as_int("MAX_TOKENS", None)

# Generation/sampling settings
TEMPERATURE = _as_float("TEMPERATURE", 0.2)
# Clamp to OpenAI-compatible range
if TEMPERATURE is not None:
    TEMPERATURE = max(0.0, min(2.0, TEMPERATURE))

TOP_P = _as_float("TOP_P", 1.0)
PRESENCE_PENALTY = _as_float("PRESENCE_PENALTY", 0.0)
FREQUENCY_PENALTY = _as_float("FREQUENCY_PENALTY", 0.0)
N = _as_int("N", 1) or 1

# Comma-separated stop words, e.g. "STOP,END"
_STOP_RAW = os.getenv("STOP", os.getenv("STOP_WORDS", "")).strip()
STOP = [s.strip() for s in _STOP_RAW.split(",") if s.strip()] if _STOP_RAW else None

# Budget/billing
MAX_BUDGET = _as_float("MAX_BUDGET", 100.0) or 100.0
TOTAL_COST = 0.0

# Proxies
GLOBAL_PROXY = os.getenv("GLOBAL_PROXY", "")
OPENAI_PROXY = os.getenv("OPENAI_PROXY", "")

# Anthropic via LiteLLM
# Compatible with common env var aliases
CLAUDE_API_KEY = (
    os.getenv("Anthropic_API_KEY")
    or os.getenv("ANTHROPIC_API_KEY")
    or os.getenv("CLAUDE_API_KEY")
    or ""
)
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "anthropic/claude-2")

# Memory settings
LONG_TERM_MEMORY = _as_bool("LONG_TERM_MEMORY", False)

# Search / Google related API keys
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY", "")
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID", "")

# Search engine selection
_SEARCH_ENGINE_NAME = os.getenv("SEARCH_ENGINE", SearchEngineType.SERPAPI_GOOGLE.value)
try:
    SEARCH_ENGINE = SearchEngineType(_SEARCH_ENGINE_NAME)
except Exception:
    SEARCH_ENGINE = SearchEngineType.SERPAPI_GOOGLE

# Browser engine settings
try:
    WEB_BROWSER_ENGINE = WebBrowserEngineType(os.getenv("WEB_BROWSER_ENGINE", WebBrowserEngineType.PLAYWRIGHT.value))
except Exception:
    WEB_BROWSER_ENGINE = WebBrowserEngineType.PLAYWRIGHT
PLAYWRIGHT_BROWSER_TYPE = os.getenv("PLAYWRIGHT_BROWSER_TYPE", "chromium")
SELENIUM_BROWSER_TYPE = os.getenv("SELENIUM_BROWSER_TYPE", "chrome")

# Network / timeouts
LLM_TIMEOUT = _as_float("LLM_TIMEOUT", 60.0) or 60.0

# Optional: inject proxies into HTTP client env (e.g., httpx/requests)
_proxy_to_apply = OPENAI_PROXY or GLOBAL_PROXY
if _proxy_to_apply:
    # Do not override if already set
    os.environ.setdefault("HTTP_PROXY", _proxy_to_apply)
    os.environ.setdefault("HTTPS_PROXY", _proxy_to_apply)

# LLM parsing repair/safeguards
LLM_PARSER_REPAIR = _as_bool("LLM_PARSER_REPAIR", True)
LLM_PARSER_REPAIR_ATTEMPTS = max(0, _as_int("LLM_PARSER_REPAIR_ATTEMPTS", 1) or 1)
