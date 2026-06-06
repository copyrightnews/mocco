import time
from collections import defaultdict
from typing import List

MAX_MSG_LEN = 4000
RATE_LIMIT_SECONDS = 3
_last_msg = defaultdict(float)

def is_rate_limited(user_id: int) -> bool:
    now = time.monotonic()
    if now - _last_msg[user_id] < RATE_LIMIT_SECONDS:
        return True
    _last_msg[user_id] = now
    return False

def split_message(text: str, limit: int = MAX_MSG_LEN) -> List[str]:
    if len(text) <= limit:
        return [text]
    chunks = []
    while len(text) > limit:
        split_at = text.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = text.rfind(" ", 0, limit)
        if split_at == -1:
            split_at = limit
        chunks.append(text[:split_at].strip())
        text = text[split_at:].strip()
    if text:
        chunks.append(text)
    return chunks
