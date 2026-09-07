import pytest

from capucine.config import load_config


def test_load_config_fails_fast_when_token_missing(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # pas de .env local à charger par erreur
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
        load_config()


def test_load_config_reads_required_and_default_values(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)

    config = load_config()

    assert config.telegram_bot_token == "fake-token"
    assert config.telegram_chat_id == 42
    assert config.ollama_model == "qwen2.5:3b"  # valeur par défaut
