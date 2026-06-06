import sys
import pathlib
import pytest

# Ensure src is importable during tests
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from mocco.config import load_config

def test_load_config_missing_env(monkeypatch):
    for k in ["TELEGRAM_TOKEN","OPENROUTER_API_KEY","SERPER_API_KEY","TOGETHER_API_KEY","DATABASE_URL"]:
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(RuntimeError):
        load_config()
