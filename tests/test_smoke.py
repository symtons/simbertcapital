import importlib

import pytest
from pydantic import ValidationError

from simbert.config import Settings


def test_core_packages_import():
    for name in [
        "langgraph",
        "langgraph.checkpoint.sqlite",
        "mcp",
        "openai",
        "langsmith",
        "pydantic_settings",
        "httpx",
        "feedparser",
        "bs4",
    ]:
        importlib.import_module(name)


def test_defaults_are_safe(monkeypatch):
    for var in ["ENV", "SHADOW_MODE", "LLM_PROVIDER", "LLM_SPEND_CAP_USD",
                "OANDA_ENV", "LANGSMITH_TRACING"]:
        monkeypatch.delenv(var, raising=False)
    s = Settings(_env_file=None)
    assert s.shadow_mode is True
    assert s.llm_provider == "fake"
    assert s.oanda_env == "practice"
    assert s.langsmith_tracing is False


def test_secrets_are_hidden_when_printed():
    s = Settings(_env_file=None, openai_api_key="sk-test-123")
    assert "sk-test-123" not in repr(s)


def test_spend_cap_has_hard_ceiling():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, llm_spend_cap_usd=500)