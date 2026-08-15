import importlib

import pytest


PRODUCTION_HOSTNAME = "https://inventory-qr-system.onrender.com"


def test_public_base_url_comes_from_environment(monkeypatch):
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://staging.example.com")
    monkeypatch.delenv("INTERNAL_API_BASE_URL", raising=False)
    import runtime_config

    assert runtime_config.get_public_base_url() == "https://staging.example.com"


def test_base_url_trailing_slash_is_normalized(monkeypatch):
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://staging.example.com/")
    import runtime_config

    assert runtime_config.get_public_base_url() == "https://staging.example.com"


def test_bot_internal_api_base_url_prefers_internal_over_public(monkeypatch):
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://public.example.com")
    monkeypatch.setenv("INTERNAL_API_BASE_URL", "https://internal.example.com/")
    import runtime_config

    assert runtime_config.get_internal_api_base_url() == "https://internal.example.com"


def test_bot_internal_api_base_url_falls_back_to_public(monkeypatch):
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://public.example.com/")
    monkeypatch.delenv("INTERNAL_API_BASE_URL", raising=False)
    import runtime_config

    assert runtime_config.get_internal_api_base_url() == "https://public.example.com"


def test_missing_public_base_url_has_no_hidden_production_fallback(monkeypatch):
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)
    monkeypatch.delenv("INTERNAL_API_BASE_URL", raising=False)
    monkeypatch.delenv("INVENTORY_TEST_MODE", raising=False)
    import runtime_config

    with pytest.raises(RuntimeError):
        runtime_config.get_public_base_url()
    with pytest.raises(RuntimeError):
        runtime_config.get_internal_api_base_url()


def test_bot_module_uses_environment_driven_api_url(monkeypatch):
    monkeypatch.setenv("INVENTORY_TEST_MODE", "1")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://public.example.com/")
    monkeypatch.setenv("INTERNAL_API_BASE_URL", "https://internal.example.com/")
    import bot

    reloaded_bot = importlib.reload(bot)
    assert reloaded_bot.API_URL == "https://internal.example.com"
    assert reloaded_bot.PUBLIC_WEB_URL == "https://public.example.com"
    assert reloaded_bot.API_URL != PRODUCTION_HOSTNAME
    assert reloaded_bot.PUBLIC_WEB_URL != PRODUCTION_HOSTNAME
