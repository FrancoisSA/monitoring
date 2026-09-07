"""Point d'accès unique à la configuration (variables d'environnement).

Toute variable sensible ou de config vit dans .env — jamais de valeur
hardcodée ailleurs dans le code.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    telegram_bot_token: str
    telegram_chat_id: int
    ollama_host: str
    ollama_model: str
    ollama_timeout: int
    db_path: str


def load_config() -> Config:
    load_dotenv()

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise ValueError(
            "[config] TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID sont obligatoires "
            "— copiez .env.example vers .env et renseignez-les."
        )

    return Config(
        telegram_bot_token=token,
        telegram_chat_id=int(chat_id),
        ollama_host=os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "qwen2.5:3b"),
        ollama_timeout=int(os.getenv("OLLAMA_TIMEOUT", "60")),
        db_path=os.getenv("CAPUCINE_DB_PATH", "capucine.db"),
    )
