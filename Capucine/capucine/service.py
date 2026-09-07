"""Boucle principale : polling Telegram + dispatch vers les agents.

Couche de câblage volontairement fine — la logique testée en profondeur vit
dans dispatch.py, router.py et les agents. Ajouter un agent ici = une ligne
dans build_router(), rien d'autre à modifier dans ce fichier.
"""
from __future__ import annotations

import logging
import time

import requests

from capucine.agents.echo import EchoAgent
from capucine.agents.synthese import SyntheseAgent
from capucine.config import Config, load_config
from capucine.deps import Deps
from capucine.dispatch import extract_message, handle_message
from capucine.llm.ollama_client import OllamaClient
from capucine.router import Router
from capucine.store import Store
from capucine.telegram_client import TelegramClient

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


def build_router() -> Router:
    return Router(
        {
            "echo": EchoAgent(),
            "synthese": SyntheseAgent(),
        }
    )


def build_deps(config: Config) -> Deps:
    return Deps(
        llm_client=OllamaClient(
            model=config.ollama_model, host=config.ollama_host, timeout=config.ollama_timeout
        ),
        store=Store(config.db_path),
    )


def run() -> None:
    config = load_config()
    telegram = TelegramClient(config.telegram_bot_token)
    router = build_router()
    deps = build_deps(config)

    logger.info(
        "[service] Capucine démarré, en écoute pour chat_id=%s", config.telegram_chat_id
    )

    offset = None
    while True:
        try:
            updates = telegram.get_updates(offset)
        except requests.exceptions.RequestException:
            # Panne réseau transitoire (Wi-Fi, DNS, Telegram indisponible) :
            # ne pas tuer le service pour ça, juste réessayer au tour suivant.
            logger.exception("[service] Échec temporaire de get_updates, nouvelle tentative")
            time.sleep(5)
            continue

        for update in updates:
            offset = update["update_id"] + 1
            message = extract_message(update)
            if message is None:
                continue
            reply = handle_message(message, router, deps, config.telegram_chat_id)
            if reply is not None:
                try:
                    telegram.send_message(message.chat_id, reply)
                except requests.exceptions.RequestException:
                    logger.exception("[service] Échec d'envoi de la réponse Telegram")


if __name__ == "__main__":
    run()
