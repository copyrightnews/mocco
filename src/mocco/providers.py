import logging
from typing import Optional
import requests

logger = logging.getLogger("mocco")

# Return values for verify_key()
VERIFY_OK = "ok"             # 2xx — key is valid
VERIFY_AUTH = "auth_failed"  # 401 / 403 / 407 — key is bad
VERIFY_TRANSIENT = "transient"  # 429 / 5xx / network error — try again later
VERIFY_BAD_REQUEST = "bad_request"  # 400 / 404 — unusual; treat as rejected

PROVIDERS = {
    "openrouter": {
        "label":   "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "key_hint": ("sk-or-", "sk-"),
        "verify_path":   "/auth/key",
        "verify_method": "GET",
        "verify_headers": {},
        "direct_route_prefix": None,
        "model_strip_prefix": "",
        "signup_url": "https://openrouter.ai/settings/keys",
        "blurb": "One key, every model. The bot's fallback uses OpenRouter too.",
        "known_models": [],
    },
    "openai": {
        "label":   "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "key_hint": ("sk-",),
        "verify_path":   "/models",
        "verify_method": "GET",
        "verify_headers": {},
        "direct_route_prefix": "openai/",
        "model_strip_prefix": "openai/",
        "signup_url": "https://platform.openai.com/api-keys",
        "blurb": "Direct billing. Used automatically when you pick an `openai/...` model.",
        "known_models": [
            "gpt-5.5",
            "gpt-5.5-pro",
            "gpt-5.4",
            "gpt-5.4-mini",
            "gpt-5.4-nano",
            "gpt-5-mini",
        ],
    },
    "anthropic": {
        "label":   "Anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "key_hint": ("sk-ant-",),
        "verify_path":   "/models",
        "verify_method": "GET",
        "verify_headers": {
            "x-api-key":         "{KEY}",
            "anthropic-version": "2023-06-01",
        },
        "direct_route_prefix": "anthropic/",
        "model_strip_prefix": "anthropic/",
        "signup_url": "https://console.anthropic.com/settings/keys",
        "blurb": "Claude models, direct billing. Used when you pick an `anthropic/...` model.",
        "known_models": [
            "claude-opus-4-8",
            "claude-opus-4-7",
            "claude-opus-4-6",
            "claude-opus-4-5-20251101",
            "claude-sonnet-4-6",
            "claude-sonnet-4-5-20250929",
            "claude-haiku-4-5-20251001",
        ],
    },
    "google": {
        "label":   "Google AI (Gemini)",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "key_hint": ("AIza",),
        "verify_path":   "/models",
        "verify_method": "GET",
        "verify_headers": {},
        "direct_route_prefix": "google/",
        "model_strip_prefix": "google/",
        "signup_url": "https://aistudio.google.com/apikey",
        "blurb": "Gemini models, direct billing. Used when you pick a `google/...` model.",
        "known_models": [
            "gemini-3.5-flash",
            "gemini-3.1-pro-preview",
            "gemini-3.1-flash-lite",
            "gemini-3-flash-preview",
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
        ],
    },
    "groq": {
        "label":   "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "key_hint": ("gsk_",),
        "verify_path":   "/models",
        "verify_method": "GET",
        "verify_headers": {},
        "direct_route_prefix": "groq/",
        "model_strip_prefix": "groq/",
        "signup_url": "https://console.groq.com/keys",
        "blurb": "Ultra-fast Llama/Mixtral. Used when you pick a `groq/...` model.",
        "known_models": [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b",
            "meta-llama/llama-4-scout-17b-16e-instruct",
            "qwen/qwen3-32b",
        ],
    },
    "together": {
        "label":   "Together AI",
        "base_url": "https://api.together.xyz/v1",
        "key_hint": (),
        "verify_path":   "/models",
        "verify_method": "GET",
        "verify_headers": {},
        "direct_route_prefix": "together/",
        "model_strip_prefix": "together/",
        "signup_url": "https://api.together.xyz/settings/api-keys",
        "blurb": "Open-source models + image gen. Used when you pick a `together/...` model.",
        "known_models": [
            "meta-llama/Llama-4-Maverick-17B-128E-Instruct",
            "meta-llama/Llama-4-Scout-17B-16E-Instruct",
            "meta-llama/Llama-3.3-70B-Instruct-Turbo",
            "meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo",
            "Qwen/Qwen3.7-Max",
            "Qwen/Qwen3.6-Plus",
            "Qwen/Qwen3-235B-A22B-Instruct-2507-tput",
            "Qwen/Qwen3.5-9B",
            "Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8",
            "deepseek-ai/DeepSeek-V4-Pro",
            "MiniMaxAI/MiniMax-M2.7",
        ],
    },
}


def is_known_provider(provider: str) -> bool:
    return provider in PROVIDERS


def looks_like_provider_key(provider: str, key: str) -> bool:
    """Cheap format check before hitting the network."""
    p = PROVIDERS.get(provider)
    if not p:
        return False
    if len(key) < 20:
        return False
    hints = p["key_hint"]
    if not hints:
        return True
    return any(key.startswith(h) for h in hints)


def verify_key(provider: str, key: str, timeout: int = 10) -> str:
    """Live-verify a key against the provider's API.

    Returns one of:
        VERIFY_OK          — 2xx
        VERIFY_AUTH         — 401/403/407 (key is bad)
        VERIFY_TRANSIENT    — 429, 5xx, or network error (try again later)
        VERIFY_BAD_REQUEST  — 400/404 (treat as rejected)
    """
    p = PROVIDERS.get(provider)
    if not p:
        logger.warning(f"verify_key: unknown provider {provider!r}")
        return VERIFY_AUTH

    url = p["base_url"].rstrip("/") + "/" + p["verify_path"].lstrip("/")
    headers = {}
    if p["verify_headers"]:
        for h, v in p["verify_headers"].items():
            headers[h] = v.replace("{KEY}", key)
    else:
        headers["Authorization"] = f"Bearer {key}"

    try:
        r = requests.request(p["verify_method"], url, headers=headers, timeout=timeout)
        if 200 <= r.status_code < 300:
            return VERIFY_OK
        logger.info(f"verify_key {provider}: HTTP {r.status_code} — {r.text[:160]}")
        if r.status_code in (401, 403, 407):
            return VERIFY_AUTH
        if r.status_code == 429 or 500 <= r.status_code < 600:
            return VERIFY_TRANSIENT
        return VERIFY_BAD_REQUEST
    except requests.exceptions.Timeout:
        logger.warning(f"verify_key {provider}: timeout")
        return VERIFY_TRANSIENT
    except Exception as e:
        logger.warning(f"verify_key {provider} failed: {e}")
        return VERIFY_TRANSIENT


def direct_route_for_model(model_id: str) -> Optional[str]:
    """Return provider name if this model_id should be routed direct, else None."""
    for name, p in PROVIDERS.items():
        prefix = p.get("direct_route_prefix")
        if prefix and model_id.startswith(prefix):
            return name
    return None
