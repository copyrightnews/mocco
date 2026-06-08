import logging
import time
from typing import List, Tuple, Optional
from datetime import datetime, timezone
import requests
from openai import OpenAI
from openai import (
    RateLimitError,
    AuthenticationError,
    PermissionDeniedError,
    APIConnectionError,
    APITimeoutError,
    BadRequestError,
    InternalServerError,
)
from .config import load_config, OPENROUTER_BASE_URL
from .db import get_custom_prompt, get_chat_model, get_user_api_key, get_history, get_bot_config
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
    "google", "search", "who is", "what is", "where is", "how to",
    "define", "meaning", "population", "president", "ceo",
    "twitter", "trending", "forecast", "prediction", "upcoming",
]

ALL_MODELS_CACHE: List[dict] = []
ALL_MODELS_CACHE_TIME: float = 0.0
MODELS_CACHE_TTL = 3600

# Curated June 2026 picks shown first in the OpenRouter catalog picker.
# Anything not listed here follows alphabetically after. Order = display order.
# If a model ID is no longer live on OpenRouter it is silently skipped.
FEATURED_FREE_IDS = [
    "openai/gpt-oss-120b:free",
    "openai/gpt-oss-20b:free",
    "qwen/qwen3-coder:free",
    "qwen/qwen3-next-80b-a3b-instruct:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "nvidia/nemotron-3-nano-30b-a3b:free",
    "nvidia/nemotron-nano-9b-v2:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "z-ai/glm-4.5-air:free",
    "liquid/lfm-2.5-1.2b-instruct:free",
    "liquid/lfm-2.5-1.2b-thinking:free",
    "poolside/laguna-m.1:free",
    "poolside/laguna-xs.2:free",
    "cognitivecomputations/dolphin-mistral-24b-venice-edition:free",
    "openrouter/owl-alpha",
]
FEATURED_PAID_IDS = [
    "openai/gpt-5.5",
    "openai/gpt-5.5-pro",
    "openai/gpt-5.4",
    "openai/gpt-5.4-mini",
    "anthropic/claude-opus-4-8",
    "anthropic/claude-sonnet-4-6",
    "anthropic/claude-haiku-4-5",
    "google/gemini-3.5-flash",
    "google/gemini-2.5-pro",
    "google/gemini-2.5-flash",
    "x-ai/grok-4",
    "meta-llama/llama-4-maverick",
    "meta-llama/llama-4-scout",
    "deepseek/deepseek-chat-v3",
    "qwen/qwen3-235b-a22b-instruct",
    "mistralai/mistral-large-2",
]

# Free model ids that are old / stale — dropped from the picker silently.
HIDDEN_FREE_IDS = {
    "meta-llama/llama-3.2-3b-instruct:free",       # Sep 2024, 3B
    "nousresearch/hermes-3-llama-3.1-405b:free",   # Aug 2024
}


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
            return _new_client(direct_key, prov["base_url"]), resolved

    or_key = _get_user_provider_key(user_id, "openrouter")
    if or_key:
        return _new_client(or_key, OPENROUTER_BASE_URL), model_id

    cfg = load_config()
    if not cfg.OPENROUTER_API_KEY:
        raise NoAPIKeyError(
            "No OpenRouter key is available. Run /connect to add your own, "
            "or ask the bot owner to set OPENROUTER_API_KEY as a fallback."
        )
    return _new_client(cfg.OPENROUTER_API_KEY, OPENROUTER_BASE_URL), model_id


def _new_client(api_key: str, base_url: str) -> OpenAI:
    """OpenAI client with auto-retry DISABLED — fail fast and let the handler
    surface the error to the user instead of silently waiting 30+ seconds
    on rate limits.
    """
    return OpenAI(api_key=api_key, base_url=base_url, max_retries=0, timeout=45.0)


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
    """Fetch the model catalog to show in the /model picker.

    Behavior depends on whether the user has connected a direct-route provider
    (any of openai, anthropic, google, groq, together):

    - If YES: returns ONLY the direct-provider models for the connected
      providers, prefixed with the provider's `direct_route_prefix` (e.g.
      `groq/llama-3.1-8b-instant`). The OpenRouter catalog is hidden because
      the user has keys and would only be billed correctly on direct routes.

    - If NO: returns the OpenRouter catalog (free + paid text->text models).
      Cached for MODELS_CACHE_TTL seconds.

    Each entry: {"id", "name", "context_length", "is_free", "pricing", "via?"}.
    """
    global ALL_MODELS_CACHE, ALL_MODELS_CACHE_TIME

    # If the user has any direct-route provider connected, build a personalized
    # list from those providers only.
    direct_models: List[dict] = []
    if user_id is not None:
        for provider, p in PROVIDERS.items():
            prefix = p.get("direct_route_prefix")
            if not prefix:
                continue  # OpenRouter (and any future non-routed provider)
            if not _get_user_provider_key(user_id, provider):
                continue
            for model_name in p.get("known_models", []):
                direct_models.append({
                    "id": f"{prefix}{model_name}",
                    "name": model_name,
                    "context_length": 0,
                    "is_free": False,
                    "pricing": {},
                    "via": provider,
                })
    if direct_models:
        direct_models.sort(key=lambda x: (x["via"], x["name"].lower()))
        return direct_models

    # Fallback: OpenRouter catalog.
    now = time.time()
    if not force and ALL_MODELS_CACHE and (now - ALL_MODELS_CACHE_TIME) < MODELS_CACHE_TTL:
        return list(ALL_MODELS_CACHE)
    out: List[dict] = []
    by_id: dict = {}
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
            if is_free and mid in HIDDEN_FREE_IDS:
                continue
            entry = {
                "id": mid,
                "name": m.get("name", mid),
                "context_length": m.get("context_length", 0),
                "is_free": bool(is_free),
                "pricing": pricing,
            }
            by_id[mid] = entry
        # Featured first (free then paid), then everything else (free first, then paid),
        # alphabetical within each group.
        featured = [by_id[m] for m in FEATURED_FREE_IDS + FEATURED_PAID_IDS if m in by_id]
        featured_ids = {m["id"] for m in featured}
        rest = [m for m in by_id.values() if m["id"] not in featured_ids]
        rest.sort(key=lambda x: (not x["is_free"], x["name"].lower()))
        out = featured + rest
        ALL_MODELS_CACHE = out
        ALL_MODELS_CACHE_TIME = now
        logger.info(f"Loaded {len(out)} text->text models from OpenRouter ({sum(1 for m in out if m['is_free'])} free, {len(featured)} featured)")
        return out
    except Exception as e:
        logger.warning(f"fetch_all_models failed: {e}")
        if ALL_MODELS_CACHE:
            return list(ALL_MODELS_CACHE)
        # Fallback defaults — confirmed live on OpenRouter as of June 2026.
        return [
            {"id": "openai/gpt-oss-120b:free", "name": "OpenAI: gpt-oss-120b (free)", "context_length": 131072, "is_free": True, "pricing": {}},
            {"id": "openai/gpt-oss-20b:free", "name": "OpenAI: gpt-oss-20b (free)", "context_length": 131072, "is_free": True, "pricing": {}},
            {"id": "qwen/qwen3-coder:free", "name": "Qwen: Qwen3 Coder 480B A35B (free)", "context_length": 1048576, "is_free": True, "pricing": {}},
            {"id": "qwen/qwen3-next-80b-a3b-instruct:free", "name": "Qwen: Qwen3 Next 80B A3B Instruct (free)", "context_length": 262144, "is_free": True, "pricing": {}},
            {"id": "nvidia/nemotron-3-ultra-550b-a55b:free", "name": "NVIDIA: Nemotron 3 Ultra (free)", "context_length": 1000000, "is_free": True, "pricing": {}},
            {"id": "meta-llama/llama-3.3-70b-instruct:free", "name": "Meta: Llama 3.3 70B Instruct (free)", "context_length": 131072, "is_free": True, "pricing": {}},
            {"id": "anthropic/claude-opus-4-8", "name": "Anthropic: Claude Opus 4.8", "context_length": 1000000, "is_free": False, "pricing": {}},
            {"id": "google/gemini-3.5-flash", "name": "Google: Gemini 3.5 Flash", "context_length": 1000000, "is_free": False, "pricing": {}},
            {"id": "openai/gpt-5.5", "name": "OpenAI: GPT-5.5", "context_length": 1000000, "is_free": False, "pricing": {}},
        ]


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
            max_tokens=8192,
            temperature=0.75,
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
            json={"q": query, "num": 8},
            timeout=12,
        )
        r.raise_for_status()
        data = r.json()
        lines = []
        raw = []
        if "answerBox" in data:
            ab = data["answerBox"]
            answer = ab.get("answer") or ab.get("snippet") or ""
            title = ab.get("title", "")
            if answer:
                source = f" ({title})" if title else ""
                lines.append(f"Answer{source}: {answer}")
                raw.append({"title": title or "Answer Box", "snippet": answer})
        organic = data.get("organic", [])[:6]
        if organic:
            for i, item in enumerate(organic, 1):
                title = item.get("title", "").strip()
                snippet = item.get("snippet", "").strip()
                link = item.get("link", "")
                if title and snippet:
                    lines.append(f"{i}. {title}")
                    lines.append(f"   {snippet}")
                    raw.append({"title": title, "snippet": snippet, "link": link})
        if not lines:
            return f"No results found for: {query}", []
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
        "## THINKING STYLE — MAXIMUM DEPTH & DETAIL:\n"
        "- **You MUST explain everything in maximum detail.** Never give short answers.\n"
        "- Think step by step. Before answering, reason through the question carefully "
        "considering all angles, edge cases, and deeper context.\n"
        "- Structure each answer like a comprehensive guide: start with a brief summary, "
        "then go deep into explanation, reasoning, examples, background context, "
        "related concepts, and practical applications.\n"
        "- Always explain **why** and **how**, not just **what**.\n"
        "- For technical topics: explain from first principles, build up layer by layer, "
        "include code examples, compare alternatives, mention trade-offs.\n"
        "- For factual topics: provide historical context, key figures, dates, "
        "underlying mechanisms, and real-world implications.\n"
        "- For opinions/analysis: present multiple perspectives, evidence for each, "
        "then your reasoned conclusion.\n"
        "- For how-to: give complete step-by-step with reasoning at each step, "
        "common pitfalls, and best practices.\n"
        "- Include examples, analogies, and comparisons to make concepts concrete.\n"
        "- If a topic has interesting tangents or related fields, explore them.\n"
        "- **The user wants to truly understand.** Write as much as needed — "
        "500 words, 1000 words, or more. Be comprehensive.\n"
        "- Never cut an explanation short. Never say 'in summary' or 'to keep it brief'.\n\n"
        "## CRITICAL FORMATTING RULES:\n"
        "- NEVER use hashtags (#) in your responses. Never.\n"
        "- NEVER use markdown formatting inappropriately. No unnecessary bold, italics, or headers.\n"
        "- Use `code` only for actual code, file names, or commands.\n"
        "- Use **bold** sparingly for key terms.\n"
        "- Use bullet points (-) or numbered lists (1.) when listing multiple items.\n"
        "- Keep paragraphs reasonably short (2-4 sentences) for readability.\n"
        "- Separate sections with a blank line, never dividers like --- or ===.\n\n"
        "## How you behave:\n"
        "- Think carefully before answering. Be accurate and honest.\n"
        "- If unsure about something, say so clearly instead of guessing.\n"
        "- For code, always use proper code blocks with the language specified.\n"
        "- Never pad answers with filler phrases like 'Great question!' or 'Certainly!'.\n"
        "- Never say your knowledge is limited to a past year. You are up to date.\n"
        "- If asked about real-time data (live scores, breaking news, stock prices), use web search "
        "results when provided, otherwise clearly state you don't have live data.\n"
        "- **Language Adaptability**: Dynamically detect and respond to the user in the exact language they use to query you. If they ask in Bengali (Bangla), reply in natural, fluent, grammatically correct standard Bengali Unicode script (বাংলা). Never use English transliteration (e.g. Banglish) or mix scripts unless explicitly requested. If they query in English or another language, reply in that language naturally.\n\n"
        "## Tone:\n"
        "- Calm, clear, and confident — like a knowledgeable professor who enjoys teaching.\n"
        "- Warm but not over-the-top. No excessive emojis. No sycophancy.\n"
        "- Be thorough and patient — take the time to explain properly.\n\n"
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


def get_assistant_system_prompt() -> str:
    """System prompt for Chat Automation / personal AI assistant mode.

    Used when the bot is connected as the user's personal assistant via
    Settings > Chat Automation. The bot replies on behalf of the user
    to people who message their account.
    """
    owner_name = get_bot_config("owner_name") or "the account owner"
    today = datetime.now(timezone.utc).strftime("%A, %B %d, %Y")
    return (
        f"You are an AI personal assistant for {owner_name} on Telegram.\n"
        f"Today's date is {today}.\n\n"
        "## YOUR ROLE:\n"
        "- You are helping people who are messaging {owner_name}'s Telegram account.\n"
        "- You reply ON BEHALF OF {owner_name} — be helpful, polite, and professional.\n"
        "- You represent {owner_name}, so match their tone and style.\n"
        "- If someone asks a question, answer it thoroughly on their behalf.\n"
        "- If someone needs help, provide it.\n"
        "- If a question is personal or you don't know how {owner_name} would respond, "
        "say you'll pass the message along.\n"
        "- Never say you are a bot or AI assistant unless directly asked.\n"
        "- Keep responses natural and conversational.\n\n"
        "## THINKING STYLE — MAXIMUM DEPTH & DETAIL:\n"
        "- Explain everything thoroughly with full context and reasoning.\n"
        "- Cover background, details, examples, and practical applications.\n"
        "- Write as much as needed — be comprehensive.\n\n"
        "## CRITICAL RULES:\n"
        "- NEVER use hashtags (#).\n"
        "- NEVER use dividers like --- or ===.\n"
        "- Keep formatting clean and minimal.\n"
        "- For code, use proper code blocks with language specified.\n"
        "- Be warm and helpful — you are representing a real person.\n"
    )


def get_ai_reply(user_id: int, user_msg: str, assistant_mode: bool = False) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Run a chat completion. Returns (reply, error_kind, error_msg).

    When assistant_mode=True: uses the business-assistant system prompt,
    no chat history (each business chat is a separate conversation).

    error_kind is one of:
      - "rate_limited"  : 429 — provider is throttling this key/model
      - "auth"          : 401/403 — key rejected
      - "timeout"       : request timed out
      - "server"        : 5xx from provider
      - "bad_request"   : 400 — model/params invalid
      - "other"         : anything else
    error_msg is the raw exception text (for logging).
    """
    if assistant_mode:
        messages = []
    else:
        history = get_history(user_id)
        messages = [{"role": r["role"], "content": r["content"]} for r in history]

    if needs_search(user_msg):
        search_text, _ = web_search(user_msg)
        augmented = (
            f"{user_msg}\n\n"
            f"Web search results for reference:\n{search_text}\n\n"
            "Using the web search results above, answer the user's question accurately. "
            "Cite relevant sources naturally. If results are insufficient, say so."
        )
        messages.append({"role": "user", "content": augmented})
    else:
        messages.append({"role": "user", "content": user_msg})

    model_id = resolve_model(user_id)
    try:
        client, resolved_model = get_client_for_chat(user_id, model_id)
        prompt = get_assistant_system_prompt() if assistant_mode else get_system_prompt(user_id)
        response = client.chat.completions.create(
            model=resolved_model,
            messages=[{"role": "system", "content": prompt}] + messages,
            max_tokens=8192,
            temperature=0.75,
        )
        return response.choices[0].message.content.strip(), None, None
    except RateLimitError as e:
        logger.warning(f"Rate limit on {model_id}: {e}")
        return None, "rate_limited", str(e)
    except (AuthenticationError, PermissionDeniedError) as e:
        logger.warning(f"Auth failure on {model_id}: {e}")
        return None, "auth", str(e)
    except APITimeoutError as e:
        logger.warning(f"Timeout on {model_id}: {e}")
        return None, "timeout", str(e)
    except APIConnectionError as e:
        logger.warning(f"Connection error on {model_id}: {e}")
        return None, "timeout", str(e)
    except BadRequestError as e:
        logger.warning(f"Bad request on {model_id}: {e}")
        return None, "bad_request", str(e)
    except InternalServerError as e:
        logger.warning(f"Server error on {model_id}: {e}")
        return None, "server", str(e)
    except Exception as e:
        logger.error(f"chat completion error ({model_id}): {e}")
        return None, "other", str(e)
