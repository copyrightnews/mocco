import logging
import base64
from typing import List, Tuple, Optional
from datetime import datetime, timezone
import requests
from groq import Groq
from .config import load_config
from .db import get_custom_prompt, get_history

logger = logging.getLogger("mocco")

SEARCH_KEYWORDS = [
    "latest", "news", "today", "current", "price", "score",
    "weather", "who won", "what happened", "right now", "live",
    "stock", "exchange rate", "update", "recently", "this week",
    "this month", "2024", "2025", "2026", "happening", "released", "launched",
]

def get_groq_client() -> Groq:
    cfg = load_config()
    return Groq(api_key=cfg.GROQ_API_KEY)

def create_chat_completion(messages: List[dict], system_prompt: Optional[str] = None) -> Optional[str]:
    """Create a chat completion using the Groq client. Returns the text on success or None."""
    try:
        client = get_groq_client()
        payload = messages
        if system_prompt:
            payload = [{"role": "system", "content": system_prompt}] + messages
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=payload,
            max_tokens=800,
            temperature=0.65,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.warning(f"create_chat_completion failed: {e}")
        return None

def web_search(query: str) -> Tuple[str, list]:
    """Light wrapper around Serper/google.serper.dev. Returns text and raw results list."""
    cfg = load_config()
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
                lines.append(f"📌 Direct Answer: {answer}")
                raw.append({"title": "Answer Box", "snippet": answer})
        organic = data.get("organic", [])[:4]
        if organic:
            if lines:
                lines.append("")
            lines.append("🔗 Top Results:")
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

def generate_image(prompt: str) -> Optional[Tuple[bytes | str, bool]]:
    """Generates an image from Together AI API.
    Returns:
        (image_bytes, False) if payload is base64
        (image_url, True) if payload is a URL
        None if generation failed.
    """
    cfg = load_config()
    models = [
        {"model": "black-forest-labs/FLUX.1-schnell", "steps": 4},
        {"model": "stabilityai/stable-diffusion-xl-base-1.0", "steps": 20},
    ]
    for m in models:
        try:
            logger.info(f"Trying image model: {m['model']}")
            r = requests.post(
                "https://api.together.xyz/v1/images/generations",
                headers={
                    "Authorization": f"Bearer {cfg.TOGETHER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model":  m["model"],
                    "prompt": prompt,
                    "steps":  m["steps"],
                    "n":      1,
                    "width":  1024,
                    "height": 1024,
                },
                timeout=120,
            )
            logger.info(f"Together status: {r.status_code} | {r.text[:300]}")
            r.raise_for_status()
            data = r.json()
            if "data" in data and data["data"]:
                item = data["data"][0]
                if item.get("b64_json"):
                    img_bytes = base64.b64decode(item["b64_json"])
                    logger.info(f"Image success (base64) with {m['model']}")
                    return img_bytes, False
                elif item.get("url"):
                    logger.info(f"Image success (URL) with {m['model']}")
                    return item["url"], True
        except requests.exceptions.Timeout:
            logger.error(f"Model {m['model']} timed out")
            continue
        except Exception as e:
            logger.error(f"Model {m['model']} failed: {e}")
            continue
    return None

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
        "- Send a voice note — Mocco will transcribe it and reply.\n"
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

    try:
        client = get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": get_system_prompt(user_id)}] + messages,
            max_tokens=800,
            temperature=0.65,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Groq error: {e}")
        return None
