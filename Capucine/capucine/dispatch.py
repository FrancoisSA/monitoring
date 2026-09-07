"""Logique pure de traitement d'un message Telegram entrant.

Séparée de la boucle de polling réseau (service.py) pour rester testable
sans dépendre d'un vrai appel à l'API Telegram — c'est le seam qui couvre
la partie de la couche Telegram qui mérite des tests (parsing, whitelist,
routage). La boucle de polling elle-même reste une fine couche de câblage,
volontairement peu testée (cf. spec).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from capucine.deps import Deps
from capucine.router import Router

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IncomingMessage:
    chat_id: int
    text: str


def parse_command(text: str) -> "tuple[str, str]":
    """"/echo bonjour" -> ("echo", "bonjour"). Sans "/" initial -> pas de commande.

    Coupe sur le premier bloc d'espaces ou de retours à la ligne (pas
    seulement un espace) : un message Telegram naturel peut avoir un saut de
    ligne entre la commande et son texte (ex. commande tapée, puis un
    article collé en dessous).
    """
    text = text.strip()
    if not text.startswith("/"):
        return "", text
    parts = text[1:].split(None, 1)
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def extract_message(update: dict) -> "IncomingMessage | None":
    """Traduit un update brut de l'API Telegram en IncomingMessage, ou None
    si ce n'est pas un message texte (photo, sticker, edit...)."""
    message = update.get("message")
    if not message or "text" not in message:
        return None
    return IncomingMessage(chat_id=message["chat"]["id"], text=message["text"])


def handle_message(
    message: IncomingMessage,
    router: Router,
    deps: Deps,
    allowed_chat_id: int,
) -> "str | None":
    """Retourne le texte à répondre, ou None si le message doit être ignoré
    (expéditeur non autorisé, ou texte sans commande)."""
    if message.chat_id != allowed_chat_id:
        # Whitelist stricte : accès strictement personnel (cf. spec).
        logger.warning("[dispatch] Message ignoré, chat_id non autorisé: %s", message.chat_id)
        return None

    command, args = parse_command(message.text)
    if not command:
        return None

    agent = router.route(command)
    if agent is None:
        return f"Commande inconnue : /{command}"

    try:
        return agent.handle(args, deps).text
    except Exception:  # noqa: BLE001 — on répond toujours à l'utilisateur, jamais de catch silencieux
        logger.exception("[dispatch] Échec de l'agent /%s", command)
        return f"Désolé, /{command} a rencontré une erreur."
