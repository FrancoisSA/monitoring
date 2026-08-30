"""
Hermes Agent via Mammouth AI API

Assistant personnel basé sur le modèle Hermes 3 (Nous Research)
utilisant l'API Mammouth AI comme backend LLM.

Cœur de l'agent :
    - get_llm_client()  : client Mistral pointant vers Mammouth AI
    - TOOLS             : schémas des outils (format OpenAI)
    - TOOL_REGISTRY     : implémentations des outils (bouchons Google pour l'instant)
    - call_llm()        : un tour d'appel LLM (les tool_calls sont renvoyés bruts)
    - run_agent()       : boucle agentique complète (appels d'outils exécutés,
                          résultats renvoyés au modèle, jusqu'à MAX_TOOL_ROUNDS)

Usage :
    python -m src.main            (terminal interactif)
    python -m src.api             (API web Flask, port 9191)
"""

from __future__ import annotations

import os
import json
import logging
from typing import Any, Callable
from dataclasses import dataclass, field

# Import Mistral SDK (OpenAI-compatible) pour Mammouth AI.
# Compatibilité : mistralai 1.x expose Mistral à la racine, 2.x dans mistralai.client.
try:
    from mistralai import Mistral
except ImportError:
    from mistralai.client import Mistral

# Charger les variables d'environnement (.env à la racine du projet)
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# Nombre maximum de tours d'appels d'outils dans la boucle agentique
MAX_TOOL_ROUNDS = 5


def _env_float(key: str, default: float) -> float:
    """Lit un float de l'environnement en tolérant un commentaire en fin de ligne.

    Nécessaire car systemd EnvironmentFile ne supprime PAS les commentaires
    en ligne (contrairement à python-dotenv) : TEMPERATURE=0.7  # note → "0.7  # note".
    """
    raw = (os.getenv(key) or "").split("#", 1)[0].strip()
    try:
        return float(raw) if raw else default
    except ValueError:
        logger.warning("Valeur invalide pour %s (%r), défaut %s utilisé", key, raw, default)
        return default


def _env_int(key: str, default: int) -> int:
    """Comme _env_float, pour les entiers (MAX_TOKENS, API_TIMEOUT)."""
    raw = (os.getenv(key) or "").split("#", 1)[0].strip()
    try:
        return int(raw) if raw else default
    except ValueError:
        logger.warning("Valeur invalide pour %s (%r), défaut %s utilisé", key, raw, default)
        return default


# Paramètres d'inférence lus depuis .env
MODEL_NAME = os.getenv("MAMMOUTH_MODEL", "mammouth-recommended").split("#", 1)[0].strip()
TEMPERATURE = _env_float("TEMPERATURE", 0.7)
MAX_TOKENS = _env_int("MAX_TOKENS", 4096)
API_TIMEOUT = _env_int("API_TIMEOUT", 120)


@dataclass
class Message:
    """Représente un message dans la conversation."""
    role: str  # "user", "assistant", "tool", "system"
    content: str = ""
    tool_calls: list[dict[str, Any]] | None = None  # appels d'outils émis par l'assistant
    tool_call_id: str | None = None  # pour les messages "tool" (résultat d'un appel)
    name: str | None = None  # nom de l'outil pour les messages "tool"


@dataclass
class AgentResponse:
    """Résultat complet d'un passage dans la boucle agentique."""
    message: Message                 # réponse finale de l'assistant
    tools_used: list[str] = field(default_factory=list)  # outils appelés, dans l'ordre
    rounds: int = 0                  # nombre de tours LLM effectués


# Client LLM mis en cache : le créer à chaque appel coûterait une connexion TLS
_llm_client: Mistral | None = None


def get_llm_client() -> Mistral:
    """
    Crée (une seule fois) le client LLM pointant vers Mammouth AI.

    Pour Mammouth AI :
        - URL API : https://api.mammouth.ai/v1/chat/completions
        - Modèle recommandé : mammouth-recommended (alias du meilleur modèle du moment)
    """
    global _llm_client
    if _llm_client is not None:
        return _llm_client

    mammouth_api_key = os.getenv("MAMMOUTH_API_KEY")
    if not mammouth_api_key:
        raise ValueError(
            "MAMMOUTH_API_KEY n'est pas définie. "
            "Obtenez votre clé API sur https://mammouth.ai/app/account/settings/api"
        )

    _llm_client = Mistral(
        api_key=mammouth_api_key,
        # Le SDK ajoute lui-même /v1/chat/completions → ne pas inclure /v1 ici
        server_url="https://api.mammouth.ai",
        timeout_ms=API_TIMEOUT * 1000,
    )
    return _llm_client


def _function_tool(name: str, description: str, parameters: dict[str, Any]) -> dict:
    """Construit un outil au format OpenAI (function calling), compatible Mammouth AI."""
    return {
        "type": "function",
        "function": {"name": name, "description": description, "parameters": parameters},
    }


# Définition des outils disponibles (Google Tasks, Calendar, Gmail, etc.)
# Dicts simples plutôt que types du SDK : la structure du SDK a changé entre
# mistralai 1.x et 2.x, le format OpenAI en dicts reste lui stable.
TOOLS: list[dict] = [
    # Google Tasks
    _function_tool(
        "google_tasks",
        "Gérer les tâches Google Tasks (ajouter, lister, supprimer, etc.)",
        {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["add", "list", "delete"], "description": "Action à effectuer"},
                "title": {"type": "string", "description": "Titre de la tâche"},
                "due": {"type": "string", "description": "Date d'échéance (format ISO 8601)"},
                "notes": {"type": "string", "description": "Notes de la tâche"},
            },
            "required": ["action"],
        },
    ),
    # Google Calendar
    _function_tool(
        "google_calendar",
        "Gérer les événements Google Calendar (ajouter, lister, supprimer, etc.)",
        {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["add", "list", "delete"], "description": "Action à effectuer"},
                "summary": {"type": "string", "description": "Titre de l'événement"},
                "start_time": {"type": "string", "description": "Heure de début (format ISO 8601)"},
                "end_time": {"type": "string", "description": "Heure de fin (format ISO 8601)"},
                "location": {"type": "string", "description": "Lieu de l'événement"},
                "description": {"type": "string", "description": "Description de l'événement"},
            },
            "required": ["action", "summary", "start_time"],
        },
    ),
    # Google Gmail
    _function_tool(
        "google_gmail",
        "Gérer les emails Google Gmail (lire, répondre, supprimer, etc.)",
        {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["read", "reply", "delete"], "description": "Action à effectuer"},
                "query": {"type": "string", "description": "Recherche d'emails"},
                "reply_to": {"type": "string", "description": "Adresse email du destinataire"},
                "reply_content": {"type": "string", "description": "Contenu de la réponse"},
            },
            "required": ["action"],
        },
    ),
]


# ---------------------------------------------------------------------------
# Registre des outils : chaque entrée exécute un appel d'outil et retourne une
# chaîne (le résultat renvoyé au modèle). Les outils Google sont des bouchons
# tant que l'OAuth2 Google n'est pas branché : ils répondent honnêtement.
# Pour brancher un vrai outil, remplacer la fonction dans TOOL_REGISTRY.
# ---------------------------------------------------------------------------

def _tool_not_connected(tool_name: str, arguments: dict) -> str:
    """Réponse honnête pour un outil pas encore relié à l'API Google."""
    return (
        f"ERREUR OUTIL : {tool_name} n'est pas encore connecté à l'API Google (bouchon actif). "
        f"Paramètres reçus : {json.dumps(arguments, ensure_ascii=False)}. "
        "Dis à l'utilisateur que cette action nécessite la connexion des API Google "
        "(OAuth2), prévue dans une prochaine version. Ne prétends pas avoir effectué l'action."
    )


def _google_tasks_stub(arguments: dict) -> str:
    return _tool_not_connected("google_tasks", arguments)


def _google_calendar_stub(arguments: dict) -> str:
    return _tool_not_connected("google_calendar", arguments)


def _google_gmail_stub(arguments: dict) -> str:
    return _tool_not_connected("google_gmail", arguments)


TOOL_REGISTRY: dict[str, Callable[[dict], str]] = {
    "google_tasks": _google_tasks_stub,
    "google_calendar": _google_calendar_stub,
    "google_gmail": _google_gmail_stub,
}


def _execute_tool(tool_name: str, arguments: str | dict) -> str:
    """
    Exécute un appel d'outil et retourne le résultat sous forme de chaîne.

    Ne lève jamais d'exception : une erreur devient un message clair renvoyé
    au modèle, qui saura en informer l'utilisateur.
    """
    handler = TOOL_REGISTRY.get(tool_name)
    if handler is None:
        return f"ERREUR OUTIL : outil inconnu « {tool_name} ». Outils disponibles : {', '.join(TOOL_REGISTRY)}."

    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments) if arguments.strip() else {}
        except json.JSONDecodeError as exc:
            return f"ERREUR OUTIL : arguments JSON invalides pour {tool_name} ({exc})."

    try:
        return handler(arguments if isinstance(arguments, dict) else {})
    except Exception as exc:  # un outil qui plante ne doit jamais tuer l'agent
        logger.exception("L'outil %s a échoué", tool_name)
        return f"ERREUR OUTIL : {tool_name} a échoué ({exc})."


def _normalize_tool_calls(raw_tool_calls: Any) -> list[dict[str, Any]]:
    """
    Normalise les tool_calls renvoyés par le SDK au format OpenAI (dicts) :
    {"id": ..., "type": "function", "function": {"name": ..., "arguments": "<json str>"}}
    """
    calls: list[dict[str, Any]] = []
    for tc in raw_tool_calls or []:
        if isinstance(tc, dict):
            calls.append({"type": "function", **tc})
            continue
        fn = getattr(tc, "function", None)
        arguments = getattr(fn, "arguments", "") if fn else ""
        if not isinstance(arguments, str):
            arguments = json.dumps(arguments or {}, ensure_ascii=False)
        calls.append({
            "id": getattr(tc, "id", None) or f"call_{len(calls)}",
            "type": "function",
            "function": {
                "name": getattr(fn, "name", "") if fn else "",
                "arguments": arguments,
            },
        })
    return calls


def _to_api_messages(messages: list) -> list[dict]:
    """
    Convertit l'historique (objets Message ou dicts bruts) en messages
    au format OpenAI attendu par Mammouth AI, en préservant les tool_calls
    de l'assistant et les résultats d'outils (role "tool" + tool_call_id).
    """
    api_messages: list[dict] = []
    for msg in messages:
        if isinstance(msg, dict):
            role = msg.get("role", "user")
            entry: dict[str, Any] = {"role": role, "content": msg.get("content") or ""}
            if role == "assistant" and msg.get("tool_calls"):
                entry["tool_calls"] = msg["tool_calls"]
            if role == "tool":
                entry["tool_call_id"] = msg.get("tool_call_id", "")
                if msg.get("name"):
                    entry["name"] = msg["name"]
            api_messages.append(entry)
            continue

        role = msg.role or "user"
        if role == "tool":
            api_messages.append({
                "role": "tool",
                "content": msg.content or "",
                "tool_call_id": msg.tool_call_id or "",
                **({"name": msg.name} if msg.name else {}),
            })
        elif role == "assistant" and msg.tool_calls:
            api_messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": msg.tool_calls,
            })
        else:
            api_messages.append({"role": role, "content": msg.content or ""})
    return api_messages


# Consigne système : les outils sont passés nativement à l'API (tools=),
# on rappelle juste au modèle de les utiliser plutôt que d'inventer.
_SYSTEM_PROMPT = (
    "Tu es Hermes, un assistant personnel. Des outils sont à ta disposition "
    "(Google Tasks, Google Calendar, Gmail). Utilise-les dès que la demande le nécessite. "
    "Si tu ne peux pas répondre à la demande, dis-le clairement plutôt que d'inventer une réponse."
)


def call_llm(messages: list, tools: list[dict] | None = None) -> Message:
    """
    Un tour d'appel au LLM (sans exécution des outils).

    Args:
        messages : Liste de messages (objets Message ou dicts role/content)
        tools : Liste d'outils au format OpenAI (défaut : TOOLS)

    Returns:
        Message de l'assistant, avec tool_calls normalisés le cas échéant.
    """
    client = get_llm_client()

    api_messages = _to_api_messages(messages)
    if tools:
        api_messages.append({"role": "system", "content": _SYSTEM_PROMPT})

    response = client.chat.complete(
        model=MODEL_NAME,
        messages=api_messages,
        tools=tools or None,
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
    )

    message = response.choices[0].message
    return Message(
        role=getattr(message, "role", "assistant") or "assistant",
        content=message.content or "",
        tool_calls=_normalize_tool_calls(getattr(message, "tool_calls", None)),
    )


def run_agent(messages: list, tools: list[dict] | None = None,
              max_rounds: int = MAX_TOOL_ROUNDS) -> AgentResponse:
    """
    Boucle agentique complète : appelle le LLM, exécute les appels d'outils,
    renvoie les résultats au modèle et recommence jusqu'à la réponse finale
    ou jusqu'à max_rounds tours.

    Args:
        messages : historique de la conversation (Messages ou dicts)
        tools : outils au format OpenAI (défaut : TOOLS)
        max_rounds : nombre maximum de tours LLM

    Returns:
        AgentResponse(message=..., tools_used=[...], rounds=...)
    """
    if tools is None:
        tools = TOOLS

    history = list(messages)
    tools_used: list[str] = []
    response: Message | None = None

    for round_num in range(1, max_rounds + 1):
        response = call_llm(history, tools)

        # Pas d'appel d'outil → réponse finale
        if not response.tool_calls:
            return AgentResponse(message=response, tools_used=tools_used, rounds=round_num)

        # Appel(s) d'outil → exécution → résultats renvoyés au modèle
        history.append(response)
        for tool_call in response.tool_calls:
            tool_name = tool_call["function"]["name"]
            logger.info("Tour %d : appel de l'outil %s", round_num, tool_name)
            result = _execute_tool(tool_name, tool_call["function"].get("arguments", "{}"))
            tools_used.append(tool_name)
            history.append(Message(role="tool", content=result, tool_call_id=tool_call.get("id", "")))

    # Budget de tours épuisé : renvoyer la dernière réponse de l'assistant
    logger.warning("Nombre maximum de tours d'outils atteint (%d)", max_rounds)
    return AgentResponse(message=response or Message(role="assistant", content="Désolé, je n'ai pas compris."),
                         tools_used=tools_used, rounds=max_rounds)


if __name__ == "__main__":
    logger.info("Hermes Agent via Mammouth AI - Test direct de la boucle agentique")

    messages = [
        {"role": "user", "content": "Ajoute une tâche 'Acheter des fruits' pour demain à 10h"},
    ]

    try:
        result = run_agent(messages)
        logger.info("Tours : %d, outils appelés : %s", result.rounds, result.tools_used or "aucun")
        logger.info("Réponse finale : %s", result.message.content)
    except Exception as e:
        logger.error(f"Erreur : {e}")
