"""Streaming variant of the LLM reply generator.

Yields SSE frames: `data: {"delta": "..."}\\n\\n` per token, then `data: {"done": True}\\n\\n`.
On error, yields `data: {"error": {"code": ..., "message": ...}}\\n\\n` before closing.
"""
from __future__ import annotations

import json
from typing import AsyncIterator, Optional

from .ai import get_client_for_chat, resolve_model
from .db import save_message


async def stream_ai_reply(
    user_id: int,
    messages: list[dict],
    system_prompt: Optional[str] = None,
    persist_to_db: bool = True,
) -> AsyncIterator[str]:
    """Stream an LLM reply as SSE frames. Optionally persist the full reply when done."""
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
        )
        full_reply: list[str] = []
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                full_reply.append(delta)
                yield f"data: {json.dumps({'delta': delta})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"
        if persist_to_db and full_reply:
            try:
                save_message(user_id, "assistant", "".join(full_reply))
            except Exception:
                pass
    except Exception as e:
        yield f"data: {json.dumps({'error': {'code': 'llm_error', 'message': str(e)}})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"
