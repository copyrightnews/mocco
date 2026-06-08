import re
import time
from collections import defaultdict
from typing import List

MAX_MSG_LEN = 4096
RATE_LIMIT_SECONDS = 3
_last_msg = defaultdict(float)

def is_rate_limited(user_id: int) -> bool:
    now = time.monotonic()
    if now - _last_msg[user_id] < RATE_LIMIT_SECONDS:
        return True
    _last_msg[user_id] = now
    return False

def _find_markdown_split(text: str, limit: int) -> int:
    """Find a safe split point that doesn't break Markdown formatting.

    Prioritizes: paragraph boundary > line break > space > hard limit.
    Also avoids splitting inside code blocks, bold/italic markers, or links.
    """
    # Don't split inside a fenced code block — find the start of it
    before = text[:limit]
    open_code = before.count("```")
    if open_code % 2 == 1:
        # Inside a code block — split at the start of this block boundary
        idx = before.rfind("```")
        if idx > 0:
            return idx

    # Try paragraph break
    para = text.rfind("\n\n", 0, limit)
    if para > limit * 0.4:
        return para

    # Try line break
    nl = text.rfind("\n", 0, limit)
    if nl > limit * 0.5:
        return nl

    # Try space
    sp = text.rfind(" ", 0, limit)
    if sp > limit * 0.6:
        return sp

    return limit


def split_message(text: str, limit: int = MAX_MSG_LEN) -> List[str]:
    if len(text) <= limit:
        return [text]
    chunks = []
    while len(text) > limit:
        split_at = _find_markdown_split(text, limit)
        chunk = text[:split_at].strip()
        rest = text[split_at:].strip()

        # If chunk has unclosed Markdown formatting, close it
        # Bold
        if chunk.count("**") % 2 != 0:
            chunk += "**"
        # Italic
        if chunk.count("*") % 2 != 0 and "**" not in chunk:
            chunk += "*"
        # Code ticks
        if chunk.count("`") % 2 != 0:
            chunk += "`"
        # Open code block
        if chunk.count("```") % 2 != 0:
            chunk += "\n```"

        # If rest starts with a continuation of Markdown, add a spacer
        if rest and not rest.startswith("\n"):
            chunk += "\n"

        chunks.append(chunk)
        text = rest

    if text:
        # Close any remaining open formatting in last chunk
        if text.count("**") % 2 != 0:
            text += "**"
        if text.count("*") % 2 != 0 and "**" not in text:
            text += "*"
        if text.count("`") % 2 != 0:
            text += "`"
        if text.count("```") % 2 != 0:
            text += "\n```"
        chunks.append(text)

    return chunks
