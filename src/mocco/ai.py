import logging
import time
from typing import List, Tuple, Optional
from datetime import datetime, timezone
import requests
from openai import OpenAI
from .config import load_config, OPENROUTER_BASE_URL
from .db import get_custom_prompt, get_chat_model, get_user_api_key, get_history
from .crypto import decrypt_api_key
from .providers import PROVIDERS, direct_route_for_model

logger = logging.getLogger("mocco")


class NoAPIKeyError(RuntimeError):
    """Raised when a chat/search/image call has no key from any source."""
    pass

SEARCH_KEYWORDS = [
    "latest", "news", "today", "current", "price", "score",
    "weather", "who won", "what happened", "right now", "live",
    "stock", "exchange rate", "update", "recently", "this week",
    "this month", "2024", "2025", "2026", "happening", "released", "launched",
]

ALL_MODELS_CACHE: List[dict] = []
ALL_MODELS_CACHE_TIME: float = 0.0
MODELS_CACHE_TTL = 3600


def _get_user_provider_key(user_id: Optional[int], provider: str) -> Optional[str]:
    """Return the decrypted API key the user stored for this provider, or None."""
    if user_id is None:
        return None
    enc = get_user_api_key(user_id, provider)
    if not enc:
        return None
    try:
        return decrypt_api_key(enc)
    except Exception as e:
        logger.error(f"Failed to decrypt {provider} key for {user_id}: {e}")
        return None


def _get_user_openrouter_key(user_id: Optional[int]) -> Optional[str]:
    """Backwards-compatible shim — only OpenRouter."""
    return _get_user_provider_key(user_id, "openrouter")


def get_openrouter_client(user_id: Optional[int] = None) -> OpenAI:
    """Always returns an OpenRouter-targeted client (user's OR key if present, else bot's)."""
    user_key = _get_user_openrouter_key(user_id)
    if user_key:
        return OpenAI(api_key=user_key, base_url=OPENROUTER_BASE_URL)
    cfg = load_config()
    return OpenAI(api_key=cfg.OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)


def get_client_for_chat(user_id: Optional[int], model_id: str) -> Tuple[OpenAI, str]:
    """Resolve which API + model_id to use for a chat request.

    Routing priority:
      1. Direct provider (e.g. openai/ prefix → OpenAI direct) if user has that key.
      2. User's OpenRouter key.
      3. Bot's OpenRouter key (if configured).

    Returns (client, model_id_to_send).

    Raises:
        NoAPIKeyError: if no key is available from any source. Caller should
            present a user-friendly prompt to /connect.
    """
    direct = direct_route_for_model(model_id)
    if direct:
        direct_key = _get_user_provider_key(user_id, direct)
        if direct_key:
            prov = PROVIDERS[direct]
            resolved = model_id[len(prov["model_strip_prefix"]):] if prov["model_strip_prefix"] else model_id
            logger.info(f"Routing {model_id} via {direct} direct → {resolved}")
            return OpenAI(api_key=direct_key, base_url=prov["base_url"]), resolved

    or_key = _get_user_provider_key(user_id, "openrouter")
    if or_key:
        return OpenAI(api_key=or_key, base_url=OPENROUTER_BASE_URL), model_id

    cfg = load_config()
    if not cfg.OPENROUTER_API_KEY:
        raise NoAPIKeyError(
            "No OpenRouter key is available. Run /connect to add your own, "
            "or ask the bot owner to set OPENROUTER_API_KEY as a fallback."
        )
    return OpenAI(api_key=cfg.OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL), model_id


def resolve_model(user_id: Optional[int] = None) -> str:
    """Resolve which model to use for a given user.
    Priority: user choice (DB) > env CHAT_MODEL > built-in default.
    """
    if user_id is not None:
        user_choice = get_chat_model(user_id)
        if user_choice:
            return user_choice
    return load_config().CHAT_MODEL


def user_has_key(user_id: Optional[int]) -> bool:
    """True if user has connected ANY provider key (any kind)."""
    if user_id is None:
        return False
    for prov in PROVIDERS:
        if _get_user_provider_key(user_id, prov) is not None:
            return True
    return False


def user_connected_providers(user_id: Optional[int]) -> List[str]:
    if user_id is None:
        return []
    return [p for p in PROVIDERS if _get_user_provider_key(user_id, p) is not None]


def can_use_paid_model(user_id: Optional[int], model_id: str) -> bool:
    """True if the user has an appropriate key to be billed for this paid model.

    - Any OpenRouter key works for any OpenRouter-listed model.
    - A direct-provider key works for models matching that provider's prefix.
    """
    if user_id is None:
        return False
    if _get_user_provider_key(user_id, "openrouter"):
        return True
    direct = direct_route_for_model(model_id)
    if direct and _get_user_provider_key(user_id, direct):
        return True
    return False


def fetch_all_models(force: bool = False, user_id: Optional[int] = None) -> List[dict]:
    """Fetch all text->text chat models from OpenRouter. Cached for MODELS_CACHE_TTL seconds.
    Returns a list of dicts: {"id", "name", "context_length", "is_free", "pricing"}.
    When user_id is provided, also appends direct-provider models (Groq, Anthropic,
    Google, Together) for providers the user has a key for, prefixed with the
    provider's `direct_route_prefix` so `get_client_for_chat` routes them directly.
    """
    global ALL_MODELS_CACHE, ALL_MODELS_CACHE_TIME
    now = time.time()
    if not force and ALL_MODELS_CACHE and (now - ALL_MODELS_CACHE_TIME) < MODELS_CACHE_TTL:
        out = list(ALL_MODELS_CACHE)
    else:
        out = []
        try:
            r = requests.get(f"{OPENROUTER_BASE_URL}/models", timeout=15)
            r.raise_for_status()
            data = r.json().get("data", [])
            for m in data:
                mid = m.get("id", "")
                arch = m.get("architecture", {}) or {}
                if arch.get("modality") != "text->text":
                    continue
                pricing = m.get("pricing", {}) or {}
                is_free = (
                    mid.endswith(":free")
                    or pricing.get("prompt", "0") in ("0", "0.0", 0, "0.0", None)
                    and pricing.get("completion", "0") in ("0", "0.0", 0, "0.0", None)
                )
                out.append({
                    "id": mid,
                    "name": m.get("name", mid),
                    "context_length": m.get("context_length", 0),
                    "is_free": bool(is_free),
                    "pricing": pricing,
                })
            out.sort(key=lambda x: (not x["is_free"], x["name"].lower()))
            ALL_MODELS_CACHE = out
            ALL_MODELS_CACHE_TIME = now
            logger.info(f"Loaded {len(out)} text->text models from OpenRouter ({sum(1 for m in out if m['is_free'])} free)")
        except Exception as e:
            logger.warning(f"fetch_all_models failed: {e}")
            if ALL_MODELS_CACHE:
                out = list(ALL_MODELS_CACHE)
            else:
                out = [
                    {"id": "minimax/minimax-m2.5:free", "name": "Minimax M2.5 (free)", "context_length": 196608, "is_free": True, "pricing": {}},
                    {"id": "meta-llama/llama-3.3-70b-instruct:free", "name": "Meta: Llama 3.3 70B (free)", "context_length": 131072, "is_free": True, "pricing": {}},
                    {"id": "qwen/qwen3-next-80b-a3b-instruct:free", "name": "Qwen 3 Next 80B (free)", "context_length": 262144, "is_free": True, "pricing": {}},
                ]
    if user_id is not None:
        for provider, p in PROVIDERS.items():
            prefix = p.get("direct_route_prefix")
            if not prefix:
                continue
            if not _get_user_provider_key(user_id, provider):
                continue
            for model_name in p.get("known_models", []):
                out.append({
                    "id": f"{prefix}{model_name}",
                    "name": model_name,
                    "context_length": 0,
                    "is_free": False,
                    "pricing": {},
                    "via": provider,
                })
    return out


def create_chat_completion(messages: List[dict], system_prompt: Optional[str] = None, user_id: Optional[int] = None) -> Optional[str]:
    """Create a chat completion. Returns the text on success or None."""
    try:
        model_id = resolve_model(user_id)
        client, resolved_model = get_client_for_chat(user_id, model_id)
        payload = messages
        if system_prompt:
            payload = [{"role": "system", "content": system_prompt}] + messages
        resp = client.chat.completions.create(
            model=resolved_model,
            messages=payload,
            max_tokens=800,
            temperature=0.65,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.warning(f"create_chat_completion failed: {e}")
        return None


def web_search(query: str) -> Tuple[str, list]:
    """Light wrapper around Serper/google.serper.dev. Returns text and raw results list.

    If SERPER_API_KEY is not configured, returns a "feature disabled" message
    instead of crashing.
    """
    cfg = load_config()
    if not cfg.SERPER_API_KEY:
        return (
            "*Web search is not configured by the bot owner.*\n"
            "The bot's SERPER_API_KEY is missing, so live web search is disabled.\n\n"
            "If you have your own Serper key, ask the bot owner to wire it up "
            "or open a feature request.",
            [],
        )
    try:
        r = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": cfg.SERPER_API_KEY, "Content-Type": "application/json"},
            json={"q": query, "num": 5},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        lines = []
        raw = []
        if "answerBox" in data:
            ab = data["answerBox"]
            answer = ab.get("answer") or ab.get("snippet") or ""
            if answer:
                lines.append(f"Direct Answer: {answer}")
                raw.append({"title": "Answer Box", "snippet": answer})
        organic = data.get("organic", [])[:4]
        if organic:
            if lines:
                lines.append("")
            lines.append("Top Results:")
            for i, item in enumerate(organic, 1):
                title = item.get("title", "").strip()
                snippet = item.get("snippet", "").strip()
                link = item.get("link", "")
                if title and snippet:
                    lines.append(f"{i}. {title}\n   {snippet}")
                    raw.append({"title": title, "snippet": snippet, "link": link})
        if not lines:
            return "No results found for your query.", []
        return "\n".join(lines), raw
    except requests.exceptions.Timeout:
        return "Search timed out. Please try again.", []
    except Exception as e:
        logger.warning(f"web_search failed: {e}")
        return "Search failed. Please try again in a moment.", []


def needs_search(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in SEARCH_KEYWORDS)


def get_system_prompt(user_id: Optional[int] = None) -> str:
    today = datetime.now(timezone.utc).strftime("%A, %B %d, %Y")
    base = (
        f"You are Mocco, an advanced AI assistant — smart, precise, and genuinely helpful.\n"
        f"Today's date is {today}.\n\n"
        "## How you behave:\n"
        "- Think carefully before answering. Be accurate and honest.\n"
        "- If unsure about something, say so clearly instead of guessing.\n"
        "- Give well-structured answers: use bullet points, numbered steps, or sections when it helps clarity.\n"
        "- For code, always use proper code blocks with the language specified.\n"
        "- For short factual questions, answer directly and concisely.\n"
        "- For complex topics, give a thorough but scannable answer.\n"
        "- Never pad answers with filler phrases like 'Great question!' or 'Certainly!'.\n"
        "- Never say your knowledge is limited to a past year. You are up to date.\n"
        "- If asked about real-time data (live scores, breaking news, stock prices), use web search "
        "results when provided, otherwise clearly state you don't have live data.\n"
        "- **Language Adaptability**: Dynamically detect and respond to the user in the exact language they use to query you. If they ask in Bengali (Bangla), reply in natural, fluent, grammatically correct standard Bengali Unicode script (বাংলা). Never use English transliteration (e.g. Banglish) or mix scripts unless explicitly requested. If they query in English or another language, reply in that language naturally.\n\n"
        "## Tone:\n"
        "- Calm, clear, and confident — like a knowledgeable friend who respects the user's time.\n"
        "- Warm but not over-the-top. No excessive emojis. No sycophancy.\n"
        "- Adapt depth to the question: brief for simple, detailed for complex.\n\n"
        "## Your capabilities:\n"
        "- Answer questions on any topic: coding, science, math, history, writing, business, and more.\n"
        "- Write, review, debug, and explain code in any programming language.\n"
        "- Summarize, translate, rewrite, and analyze text.\n"
        "- Generate creative content: stories, emails, essays, product descriptions, etc.\n"
        "- Help with planning, brainstorming, and decision-making.\n"
        "- Search the web for current information when triggered.\n"
    )
    if user_id:
        custom = get_custom_prompt(user_id)
        if custom:
            base += f"\n## Custom instructions from this user:\n{custom}\n"
    return base


def get_ai_reply(user_id: int, user_msg: str) -> Optional[str]:
    history = get_history(user_id)
    messages = [{"role": r["role"], "content": r["content"]} for r in history]

    if needs_search(user_msg):
        search_text, _ = web_search(user_msg)
        augmented = (
            f"{user_msg}\n\n"
            f"[Current web search results]:\n{search_text}\n\n"
            "Use the search results above to give an accurate, up-to-date answer."
        )
        messages.append({"role": "user", "content": augmented})
    else:
        messages.append({"role": "user", "content": user_msg})

    model_id = resolve_model(user_id)
    try:
        client, resolved_model = get_client_for_chat(user_id, model_id)
        response = client.chat.completions.create(
            model=resolved_model,
            messages=[{"role": "system", "content": get_system_prompt(user_id)}] + messages,
            max_tokens=800,
            temperature=0.65,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"chat completion error ({model_id}): {e}")
        return None
