"""Boucle principale : polling Telegram + dispatch vers les agents.

Couche de câblage volontairement fine — la logique testée en profondeur vit
dans dispatch.py, router.py et les agents. Ajouter un agent ici = une ligne
dans build_router(), rien d'autre à modifier dans ce fichier.
"""
from __future__ import annotations

import logging
import queue
import socket
import threading
import time
from pathlib import Path

import requests

from capucine.agents.agenda import AgendaAgent
from capucine.agents.agenda_check import AgendaCheckAgent
from capucine.agents.base import AgentResponse
from capucine.agents.echo import EchoAgent
from capucine.agents.ia import IaAgent
from capucine.agents.presse import PresseAgent
from capucine.agents.renault import RenaultAgent
from capucine.agents.synthese import SyntheseAgent
from capucine.config import Config, load_config
from capucine.deps import Deps
from capucine.dispatch import extract_message, handle_message
from capucine.google_calendar import GoogleCalendarClient
from capucine.google_gmail import GmailClient
from capucine.llm.ollama_client import OllamaClient
from capucine.mac_wake import MacConfig
from capucine.router import Router
from capucine.store import Store
from capucine.telegram_client import TelegramClient

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


def build_mac_config(config: Config) -> "MacConfig | None":
    """None si MAC_HOST n'est pas configuré — l'intégration Mac/LM Studio est
    alors désactivée et les agents utilisent uniquement Ollama (comportement
    d'origine, cf. capucine/digest.py::generate_digest)."""
    if not config.mac_host:
        return None
    return MacConfig(
        host=config.mac_host,
        ssh_user=config.mac_ssh_user,
        ssh_key_path=config.mac_ssh_key_path,
        mac_address=config.mac_address,
        model=config.mac_model,
        wake_timeout_s=config.mac_wake_timeout_s,
        retry_interval_s=config.mac_retry_interval_s,
        tts_model_path=config.mac_tts_model_path,
    )


def build_router(config: Config) -> Router:
    # /presse, /renault et /ia ont besoin d'un timeout largement supérieur aux
    # autres agents (cf. commentaire dans capucine/digest.py) : client Ollama
    # dédié par agent plutôt que le deps.llm_client partagé (calibré pour des
    # réponses courtes, type /synthese).
    presse_llm_client = OllamaClient(
        model=config.ollama_model, host=config.ollama_host, timeout=config.presse_llm_timeout
    )
    renault_llm_client = OllamaClient(
        model=config.ollama_model, host=config.ollama_host, timeout=config.renault_llm_timeout
    )
    ia_llm_client = OllamaClient(
        model=config.ollama_model, host=config.ollama_host, timeout=config.ia_llm_timeout
    )
    mac_config = build_mac_config(config)

    # /agenda et /agenda_check partagent le même client Google Calendar
    # (cache de calendarId compris) — un seul construit ici.
    calendar = GoogleCalendarClient(
        credentials_file=config.google_credentials_file,
        token_file=config.google_token_file,
        timezone=config.calendar_timezone,
    )
    gmail = GmailClient(
        credentials_file=config.google_credentials_file,
        token_file=config.google_token_file,
    )
    # Client Ollama dédié au tool-calling de /agenda (modèle/timeout
    # potentiellement différents des autres agents, cf. capucine/config.py).
    agenda_llm_client = OllamaClient(
        model=config.agenda_ollama_model, host=config.ollama_host, timeout=config.agenda_llm_timeout
    )

    return Router(
        {
            "echo": EchoAgent(),
            "synthese": SyntheseAgent(),
            "presse": PresseAgent(
                feed_urls=config.presse_feeds, llm_client=presse_llm_client, mac_config=mac_config
            ),
            "renault": RenaultAgent(
                search_queries=config.renault_search_queries,
                llm_client=renault_llm_client,
                mac_config=mac_config,
            ),
            "ia": IaAgent(feed_urls=config.ia_feeds, llm_client=ia_llm_client, mac_config=mac_config),
            "agenda": AgendaAgent(calendar=calendar, llm_client=agenda_llm_client),
            "agenda_check": AgendaCheckAgent(
                calendar=calendar,
                gmail=gmail,
                reminder_advance_minutes=config.calendar_reminder_advance_minutes,
                agenda_pro_calendar_name=config.calendar_agenda_pro_name,
            ),
        }
    )


def build_deps(config: Config) -> Deps:
    return Deps(
        llm_client=OllamaClient(
            model=config.ollama_model, host=config.ollama_host, timeout=config.ollama_timeout
        ),
        store=Store(config.db_path),
    )


def send_response(telegram: TelegramClient, chat_id: int, response: AgentResponse, context: str) -> None:
    """Envoie le texte puis, s'il existe, le vocal — un échec sur l'un
    n'empêche pas de tenter l'autre, et jamais ne fait planter l'appelant
    (cf. décision produit : un vocal manqué ne prive pas du texte)."""
    try:
        telegram.send_message(chat_id, response.text)
    except requests.exceptions.RequestException:
        logger.exception("[%s] Échec d'envoi du texte Telegram", context)

    if response.voice_path is not None:
        try:
            telegram.send_voice(chat_id, response.voice_path)
        except Exception:  # noqa: BLE001 — send_voice ouvre un fichier (OSError possible) en plus de l'appel réseau (RequestException) ; un vocal manqué ne doit jamais faire planter le service
            logger.exception("[%s] Échec d'envoi du vocal Telegram", context)


def run_scheduled_trigger(
    command: str,
    router: Router,
    deps: Deps,
    telegram: TelegramClient,
    chat_id: int,
) -> None:
    """Exécute un agent hors d'un message Telegram entrant (déclenchement
    planifié via le socket local) et envoie sa réponse proactivement."""
    agent = router.route(command)
    if agent is None:
        logger.warning("[trigger] Commande planifiée inconnue : %s", command)
        return

    try:
        response = agent.handle("", deps)
    except Exception:  # noqa: BLE001 — ne jamais laisser un échec planifié tuer le service
        logger.exception("[trigger] Échec de l'agent planifié /%s", command)
        return

    if not response.notify:
        # Ex. /renault sans rien de nouveau depuis la dernière recherche :
        # pas de message proactif (spam horaire), contrairement à un usage
        # manuel de la commande qui, lui, répond toujours (cf. dispatch.py).
        return

    send_response(telegram, chat_id, response, context="trigger")


def serve_trigger_socket(socket_path: str, trigger_queue: "queue.Queue[str]") -> None:
    """Écoute les commandes envoyées par cron (cf. scripts/trigger.sh) sur un
    socket Unix local — pas de port réseau, contrôle d'accès assuré par les
    permissions du fichier socket (0600, local au Pi).

    Les commandes reçues sont empilées dans `trigger_queue` plutôt
    qu'exécutées ici directement : le Store SQLite (cf. store.py) n'est pas
    conçu pour être partagé entre threads, donc seule la boucle principale
    (celle qui possède `deps`) doit jamais l'utiliser.
    """
    path = Path(socket_path)
    if path.exists():
        path.unlink()  # socket orphelin d'un précédent démarrage interrompu

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(path))
    path.chmod(0o600)
    server.listen(1)

    logger.info("[trigger] En écoute sur %s", socket_path)
    while True:
        conn, _ = server.accept()
        with conn:
            command = conn.recv(256).decode("utf-8", errors="replace").strip()
        if command:
            trigger_queue.put(command)


def run() -> None:
    config = load_config()
    telegram = TelegramClient(config.telegram_bot_token)
    router = build_router(config)
    deps = build_deps(config)

    trigger_queue: "queue.Queue[str]" = queue.Queue()
    threading.Thread(
        target=serve_trigger_socket,
        args=(config.socket_path, trigger_queue),
        daemon=True,
    ).start()

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
                send_response(telegram, message.chat_id, reply, context="service")

        # Déclenchements planifiés (cron → socket) : traités ici, jamais
        # depuis le thread du socket, pour rester sur l'unique connexion
        # SQLite du Store (cf. serve_trigger_socket).
        while not trigger_queue.empty():
            command = trigger_queue.get_nowait()
            run_scheduled_trigger(command, router, deps, telegram, config.telegram_chat_id)


if __name__ == "__main__":
    run()
