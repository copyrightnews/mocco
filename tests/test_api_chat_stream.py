import pytest
from unittest.mock import MagicMock, AsyncMock

from mocco.ai_stream import stream_ai_reply


class _FakeChunk:
    def __init__(self, content: str | None):
        self.choices = [MagicMock(delta=MagicMock(content=content))]


class _FakeStream:
    def __init__(self, chunks):
        self._chunks = chunks
        self._i = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._i >= len(self._chunks):
            raise StopAsyncIteration
        c = self._chunks[self._i]
        self._i += 1
        return c


@pytest.mark.asyncio
async def test_stream_ai_reply_yields_deltas_and_done(monkeypatch):
    # Patch the client factory to return a fake.
    fake_stream = _FakeStream([_FakeChunk("Hel"), _FakeChunk("lo"), _FakeChunk(None)])
    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(return_value=fake_stream)

    async def fake_get_client(_user_id, _model_id):
        return fake_client, "test-model"

    monkeypatch.setattr("mocco.ai_stream.get_client_for_chat", fake_get_client)
    monkeypatch.setattr("mocco.ai_stream.resolve_model", lambda _u: "test-model")

    import json
    deltas = []
    done = False
    async for frame in stream_ai_reply(123, [{"role": "user", "content": "hi"}]):
        if frame.startswith("data: "):
            payload = json.loads(frame[len("data: "):].strip())
            if "delta" in payload:
                deltas.append(payload["delta"])
            if payload.get("done"):
                done = True
    assert "".join(deltas) == "Hello"
    assert done is True
