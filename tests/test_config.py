import sys
import pathlib
import pytest

# Ensure src is importable during tests
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from mocco.config import load_config, get_missing_optional_features


def test_load_config_missing_required_env(monkeypatch):
    """Both TELEGRAM_TOKEN and DATABASE_URL are hard requirements."""
    for k in ["TELEGRAM_TOKEN", "DATABASE_URL", "OPENROUTER_API_KEY", "SERPER_API_KEY", "ENCRYPTION_KEY"]:
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(RuntimeError) as exc:
        load_config()
    assert "TELEGRAM_TOKEN" in str(exc.value)
    assert "DATABASE_URL" in str(exc.value)


def test_load_config_only_required(monkeypatch):
    """Bot should start with ONLY TELEGRAM_TOKEN + DATABASE_URL set."""
    for k in ["OPENROUTER_API_KEY", "SERPER_API_KEY", "ENCRYPTION_KEY", "OWNER_ID", "BOT_ID", "CHAT_MODEL", "LOG_LEVEL"]:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("TELEGRAM_TOKEN", "tg-token")
    monkeypatch.setenv("DATABASE_URL", "postgresql://x:x@x:5432/x")
    cfg = load_config()
    assert cfg.TELEGRAM_TOKEN == "tg-token"
    assert cfg.DATABASE_URL == "postgresql://x:x@x:5432/x"
    assert cfg.OPENROUTER_API_KEY == ""
    assert cfg.SERPER_API_KEY == ""
    assert cfg.ENCRYPTION_KEY == ""
    assert cfg.OWNER_ID == 0
    assert cfg.BOT_ID == 0
    assert cfg.CHAT_MODEL == "minimax/minimax-m2.5:free"


def test_get_missing_optional_features(monkeypatch):
    """Detect which features are disabled by missing config."""
    for k in ["OPENROUTER_API_KEY", "SERPER_API_KEY", "ENCRYPTION_KEY"]:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("TELEGRAM_TOKEN", "x")
    monkeypatch.setenv("DATABASE_URL", "x")
    cfg = load_config()
    disabled = get_missing_optional_features(cfg)
    assert any("fallback LLM" in d for d in disabled)
    assert any("web search" in d for d in disabled)
    assert any("/connect" in d for d in disabled)

    # With all keys set, no features should be reported as missing
    monkeypatch.setenv("OPENROUTER_API_KEY", "k1")
    monkeypatch.setenv("SERPER_API_KEY", "k2")
    monkeypatch.setenv("ENCRYPTION_KEY", "k4")
    cfg = load_config()
    assert get_missing_optional_features(cfg) == []


def test_load_config_only_telegram_token(monkeypatch):
    """Missing DATABASE_URL alone should also raise (it's hard-required)."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    for k in ["OPENROUTER_API_KEY", "SERPER_API_KEY", "ENCRYPTION_KEY"]:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("TELEGRAM_TOKEN", "tg")
    with pytest.raises(RuntimeError) as exc:
        load_config()
    assert "DATABASE_URL" in str(exc.value)
    assert "TELEGRAM_TOKEN" not in str(exc.value)
