"""Streaming variant of the LLM reply generator.

Yields SSE frames: `data: {"delta": "..."}\\n\\n` per token, then optionally
`data: {"usage": {"total_tokens": N}}\\n\\n` once on completion (when the upstream
honors `stream_options.include_usage`), then `data: {"done": True}\\n\\n`.
On error, yields `data: {"error": {"code": ..., "message": ...}}\\n\\n` before closing.
"""
from __future__ import annotations

import json
from typing import AsyncIterator, Optional

from .ai import get_client_for_chat, resolve_model
from .db import save_message, increment_daily_token_usage


async def stream_ai_reply(
    user_id: int,
    messages: list[dict],
    system_prompt: Optional[str] = None,
    persist_to_db: bool = True,
    track_tokens: bool = False,
) -> AsyncIterator[str]:
    """Stream an LLM reply as SSE frames. Optionally persist the full reply when done.

    When `track_tokens` is True the total token count reported in the final usage
    chunk is added to the user's daily fallback quota counter.
    """
    try:
        model_id = resolve_model(user_id)
        client, real_model = get_client_for_chat(user_id, model_id)
        payload = messages[:]
        if system_prompt:
            payload = [{"role": "system", "content": system_prompt}] + payload
        stream = await client.chat.completions.create(
            model=real_model,
            messages=payload,
            stream=True,
            max_tokens=800,
            temperature=0.65,
            stream_options={"include_usage": True},
        )
        full_reply: list[str] = []
        total_tokens: Optional[int] = None
        async for chunk in stream:
            try:
                delta = chunk.choices[0].delta.content
            except (IndexError, AttributeError):
                delta = None
            if delta:
                full_reply.append(delta)
                yield f"data: {json.dumps({'delta': delta})}\n\n"
            usage = getattr(chunk, "usage", None)
            if usage is not None and getattr(usage, "total_tokens", None) is not None:
                try:
                    total_tokens = int(usage.total_tokens)
                except (TypeError, ValueError):
                    total_tokens = None
        if total_tokens is not None:
            yield f"data: {json.dumps({'usage': {'total_tokens': total_tokens}})}\n\n"
            if track_tokens:
                try:
                    increment_daily_token_usage(user_id, total_tokens)
                except Exception:
                    pass
        yield f"data: {json.dumps({'done': True})}\n\n"
        if persist_to_db and full_reply:
            try:
                save_message(user_id, "assistant", "".join(full_reply))
            except Exception:
                pass
    except Exception as e:
        yield f"data: {json.dumps({'error': {'code': 'llm_error', 'message': str(e)}})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"
