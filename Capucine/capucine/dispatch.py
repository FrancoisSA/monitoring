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
from typing import Callable

from capucine.agents.base import AgentResponse
from capucine.deps import Deps
from capucine.router import Router

logger = logging.getLogger(__name__)

# Commandes dont le traitement peut prendre plusieurs minutes (fetch RSS +
# LLM + TTS sur le Mac) : un accusé de réception immédiat évite à
# l'utilisateur de se demander si le bot a bien reçu la commande pendant
# qu'elle tourne en silence (cf. on_slow_command_start).
SLOW_COMMANDS = frozenset({"presse", "renault", "ia"})


@dataclass(frozen=True)
class IncomingMessage:
    chat_id: int
    text: str = ""
    # ID de fichier Telegram d'un message vocal (mutuellement exclusif avec
    # `text` non vide) — laissé à None pour un message texte classique.
    # service.py se charge du téléchargement + transcription (opérations
    # réseau), hors du périmètre pur de ce module (cf. docstring de fichier).
    voice_file_id: "str | None" = None


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
    si ce n'est ni un message texte ni un message vocal (photo, sticker,
    edit...)."""
    message = update.get("message")
    if not message:
        return None
    if "text" in message:
        return IncomingMessage(chat_id=message["chat"]["id"], text=message["text"])
    if "voice" in message:
        return IncomingMessage(chat_id=message["chat"]["id"], voice_file_id=message["voice"]["file_id"])
    return None


def handle_message(
    message: IncomingMessage,
    router: Router,
    deps: Deps,
    allowed_chat_id: int,
    on_slow_command_start: "Callable[[str], None] | None" = None,
) -> "AgentResponse | None":
    """Retourne la réponse à envoyer (texte + vocal éventuel), ou None si le
    message doit être ignoré (expéditeur non autorisé, ou texte sans
    commande).

    `on_slow_command_start` est appelé avant l'exécution d'une commande de
    SLOW_COMMANDS (ex. envoyer un accusé de réception Telegram) — injecté
    plutôt qu'un import direct de TelegramClient ici, pour garder ce module
    testable sans appel réseau (cf. docstring de fichier)."""
    if message.chat_id != allowed_chat_id:
        # Whitelist stricte : accès strictement personnel (cf. spec).
        logger.warning("[dispatch] Message ignoré, chat_id non autorisé: %s", message.chat_id)
        return None

    command, args = parse_command(message.text)
    if not command:
        return None

    if command in SLOW_COMMANDS and on_slow_command_start is not None:
        on_slow_command_start(command)

    agent = router.route(command)
    if agent is None:
        return AgentResponse(text=f"Commande inconnue : /{command}")

    try:
        return agent.handle(args, deps)
    except Exception:  # noqa: BLE001 — on répond toujours à l'utilisateur, jamais de catch silencieux
        logger.exception("[dispatch] Échec de l'agent /%s", command)
        return AgentResponse(text=f"Désolé, /{command} a rencontré une erreur.")
