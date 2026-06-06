"""/v1/chat/stream — SSE chat endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from mocco.ai_stream import stream_ai_reply
from mocco.db import save_message, get_custom_prompt

from api.deps import current_user
from api.errors import ApiError
from api.models import ChatRequest

router = APIRouter()

# Simple per-user token bucket (process-local).
_BUCKETS: dict[int, tuple[float, int]] = {}
_LIMIT = 30
_WINDOW_S = 60.0


def _allow(user_id: int) -> bool:
    import time
    now = time.time()
    if user_id not in _BUCKETS:
        _BUCKETS[user_id] = (now, 0)
    ts, count = _BUCKETS[user_id]
    if now - ts > _WINDOW_S:
        _BUCKETS[user_id] = (now, 0)
        ts, count = now, 0
    if count >= _LIMIT:
        return False
    _BUCKETS[user_id] = (ts, count + 1)
    return True


@router.post("/chat/stream")
def chat_stream(req: ChatRequest, user_id: int = Depends(current_user)):
    if not _allow(user_id):
        raise ApiError(429, "rate_limited", "Too many requests.", {"retry_after": 30})
    # Persist the latest user message before generating.
    if req.messages and req.messages[-1].role == "user":
        try:
            save_message(user_id, "user", req.messages[-1].content)
        except Exception:
            pass
    system_prompt = req.system_prompt_override or get_custom_prompt(user_id) or None
    msgs = [m.model_dump() for m in req.messages]
    return StreamingResponse(
        stream_ai_reply(user_id, msgs, system_prompt=system_prompt, persist_to_db=True),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
