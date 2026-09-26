"""Point d'accès unique à la configuration (variables d'environnement).

Toute variable sensible ou de config vit dans .env — jamais de valeur
hardcodée ailleurs dans le code.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import find_dotenv, load_dotenv

# Flux RSS suivis par défaut par l'agent /presse (automobile électrique),
# reconfigurables via PRESSE_FEEDS sans toucher au code.
_DEFAULT_PRESSE_FEEDS = (
    "https://www.automobile-propre.com/feed/",
    "https://electrek.co/feed/",
    "https://insideevs.com/rss/articles/all/",
    "https://cleantechnica.com/feed/",
)

# Requêtes de veille par défaut pour l'agent /renault, reconfigurables via
# RENAULT_SEARCH_QUERIES sans toucher au code. La phrase entre guillemets
# pour Ampere évite la confusion avec l'unité de courant électrique.
_DEFAULT_RENAULT_QUERIES = (
    "Renault véhicules électriques",
    '"Renault Ampere"',
)

# Flux RSS suivis par défaut par l'agent /ia (actualité IA & frameworks
# agentiques), reconfigurables via IA_FEEDS sans toucher au code.
_DEFAULT_IA_FEEDS = (
    "https://simonwillison.net/atom/everything/",
    "https://huggingface.co/blog/feed.xml",
    "https://openai.com/blog/rss.xml",
    "https://www.interconnects.ai/feed",
)


@dataclass(frozen=True)
class Config:
    telegram_bot_token: str
    telegram_chat_id: int
    ollama_host: str
    ollama_model: str
    ollama_timeout: int
    db_path: str
    presse_feeds: "list[str]"
    socket_path: str
    presse_llm_timeout: int
    renault_search_queries: "list[str]"
    renault_llm_timeout: int
    ia_feeds: "list[str]"
    ia_llm_timeout: int
    mac_host: "str | None"
    mac_ssh_user: str
    mac_ssh_key_path: str
    mac_address: str
    mac_model: str
    mac_wake_timeout_s: int
    mac_retry_interval_s: int
    google_credentials_file: str
    google_token_file: str
    calendar_timezone: str
    calendar_agenda_pro_name: str
    extra_calendar_names: "list[str]"
    calendar_reminder_advance_minutes: int
    agenda_ollama_model: str
    agenda_llm_timeout: int
    dashboard_port: int
    oauth_redirect_uri: str
    dashboard_cache_ttl_seconds: int


def _parse_comma_separated(raw: "str | None", default: "tuple[str, ...]") -> "list[str]":
    if not raw:
        return list(default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def load_config() -> Config:
    # usecwd=True : cherche .env depuis le répertoire courant, pas depuis
    # l'emplacement de ce fichier (défaut de find_dotenv) — sans ça, un test
    # qui fait chdir() vers un répertoire vide peut quand même charger le
    # vrai .env du projet en remontant l'arborescence depuis capucine/.
    load_dotenv(find_dotenv(usecwd=True))

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise ValueError(
            "[config] TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID sont obligatoires "
            "— copiez .env.example vers .env et renseignez-les."
        )

    mac_host = os.getenv("MAC_HOST")
    mac_ssh_user = os.getenv("MAC_SSH_USER", "")
    mac_address = os.getenv("MAC_ADDRESS", "")
    if mac_host and (not mac_ssh_user or not mac_address):
        # Fail-fast : une MAC_ADDRESS vide fait planter send_wol_packet (ValueError)
        # et un MAC_SSH_USER vide rend toute connexion SSH impossible — mieux
        # vaut le signaler au démarrage qu'à la première tentative de réveil.
        raise ValueError(
            "[config] MAC_HOST est défini mais MAC_SSH_USER et/ou MAC_ADDRESS "
            "sont manquants — renseignez les deux ou laissez MAC_HOST vide "
            "pour désactiver l'intégration Mac/LM Studio."
        )

    ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")

    return Config(
        telegram_bot_token=token,
        telegram_chat_id=int(chat_id),
        ollama_host=os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434"),
        ollama_model=ollama_model,
        ollama_timeout=int(os.getenv("OLLAMA_TIMEOUT", "60")),
        db_path=os.getenv("CAPUCINE_DB_PATH", "capucine.db"),
        presse_feeds=_parse_comma_separated(os.getenv("PRESSE_FEEDS"), _DEFAULT_PRESSE_FEEDS),
        socket_path=os.getenv("CAPUCINE_SOCKET_PATH", "/tmp/capucine.sock"),
        presse_llm_timeout=int(os.getenv("PRESSE_LLM_TIMEOUT", "420")),
        renault_search_queries=_parse_comma_separated(
            os.getenv("RENAULT_SEARCH_QUERIES"), _DEFAULT_RENAULT_QUERIES
        ),
        renault_llm_timeout=int(os.getenv("RENAULT_LLM_TIMEOUT", "420")),
        ia_feeds=_parse_comma_separated(os.getenv("IA_FEEDS"), _DEFAULT_IA_FEEDS),
        ia_llm_timeout=int(os.getenv("IA_LLM_TIMEOUT", "420")),
        # MAC_HOST absent = intégration Mac/LM Studio désactivée (agents.*.py
        # utilisent alors uniquement le backend Ollama local, comme avant).
        mac_host=mac_host,
        mac_ssh_user=mac_ssh_user,
        mac_ssh_key_path=os.getenv("MAC_SSH_KEY_PATH", "/home/fsalazar/.ssh/capucine_mac_ed25519"),
        mac_address=mac_address,
        mac_model=os.getenv("MAC_MODEL", "qwen3-coder-30b-a3b-instruct-mlx"),
        mac_wake_timeout_s=int(os.getenv("MAC_WAKE_TIMEOUT_S", "180")),
        mac_retry_interval_s=int(os.getenv("MAC_RETRY_INTERVAL_S", "10")),
        google_credentials_file=os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json"),
        google_token_file=os.getenv("GOOGLE_TOKEN_FILE", "token.json"),
        calendar_timezone=os.getenv("CALENDAR_TIMEZONE", "Europe/Paris"),
        calendar_agenda_pro_name=os.getenv("CALENDAR_AGENDA_PRO_NAME", "Ampere"),
        # Calendriers additionnels (autres comptes Google partagés en lecture
        # avec le compte authentifié) à inclure dans /api/events. Vide = seul
        # le calendrier "primary" est interrogé.
        extra_calendar_names=_parse_comma_separated(os.getenv("EXTRA_CALENDAR_NAMES"), ()),
        calendar_reminder_advance_minutes=int(os.getenv("CALENDAR_REMINDER_ADVANCE_MINUTES", "20")),
        # Modèle Ollama dédié au tool-calling de /agenda — même modèle que
        # OLLAMA_MODEL par défaut, surchageable si le tool-calling se révèle
        # peu fiable sur un petit modèle (cf. capucine/llm/ollama_client.py).
        agenda_ollama_model=os.getenv("AGENDA_OLLAMA_MODEL") or ollama_model,
        agenda_llm_timeout=int(os.getenv("AGENDA_LLM_TIMEOUT", "60")),
        # 9090 = Pi Monitor, 9191 = Jeffrey : 9192 par défaut pour Capucine sur le même Pi.
        dashboard_port=int(os.getenv("DASHBOARD_PORT", "9192")),
        oauth_redirect_uri=os.getenv("OAUTH_REDIRECT_URI", "http://localhost:9192/auth/callback"),
        # Durée de vie du cache des appels Google Calendar/Tasks (cf.
        # capucine/cache.py). Inférieur au rafraîchissement client (60s) pour
        # rester réactif après une action utilisateur (tâche complétée...).
        dashboard_cache_ttl_seconds=int(os.getenv("DASHBOARD_CACHE_TTL_SECONDS", "30")),
    )
