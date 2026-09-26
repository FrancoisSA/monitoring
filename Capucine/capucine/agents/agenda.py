"""Agent conversationnel /agenda : langage naturel -> Google Calendar.

Le modèle (Ollama, cf. capucine/llm/ollama_client.py::OllamaClient.chat)
décide quel outil calendrier appeler à partir du texte libre de
l'utilisateur, dans une boucle agentique bornée par MAX_TOOL_ROUNDS —
schémas d'outils et boucle portés de
prj-jeffrey/agent/mistral_agent.py::TOOLS/process_message, adaptés au
protocole ToolCallingLLMClient de Capucine (cf. capucine/llm/base.py).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

import pytz

from capucine.agents.base import AgentResponse
from capucine.deps import Deps
from capucine.google_calendar import GoogleCalendarClient
from capucine.llm.base import Message, ToolCallingLLMClient
from capucine.prompts import load_prompt

# Modifiable sans toucher au code : cf. capucine/prompts/agenda_system.md.
_SYSTEM_PROMPT_TEMPLATE = load_prompt("agenda_system")

logger = logging.getLogger(__name__)

# Un aller-retour = un tour de tool-calling. Borne haute pour éviter une
# boucle infinie si le modèle rappelle des outils sans jamais conclure.
MAX_TOOL_ROUNDS = 5

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_events",
            "description": "Liste les événements Google Calendar à venir.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days_ahead": {"type": "integer", "description": "Nombre de jours à regarder en avant (défaut: 7)."},
                    "max_results": {"type": "integer", "description": "Nombre maximum d'événements (défaut: 20)."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_event",
            "description": "Ajoute un événement dans Google Calendar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "Titre de l'événement."},
                    "start": {"type": "string", "description": "Datetime de début ISO 8601 (ex: '2024-04-15T14:00:00')."},
                    "end": {"type": "string", "description": "Datetime de fin ISO 8601. Si absent, durée d'1h par défaut."},
                    "description": {"type": "string", "description": "Description / notes de l'événement. Optionnel."},
                    "location": {"type": "string", "description": "Lieu de l'événement. Optionnel."},
                },
                "required": ["summary", "start"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_event",
            "description": "Modifie un événement Google Calendar existant.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "L'ID Google de l'événement à modifier."},
                    "summary": {"type": "string", "description": "Nouveau titre. Optionnel."},
                    "start": {"type": "string", "description": "Nouveau début ISO 8601. Optionnel."},
                    "end": {"type": "string", "description": "Nouvelle fin ISO 8601. Optionnel."},
                    "description": {"type": "string", "description": "Nouvelle description. Optionnel."},
                    "location": {"type": "string", "description": "Nouveau lieu. Optionnel."},
                },
                "required": ["event_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_event",
            "description": "Supprime définitivement un événement du calendrier.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "L'ID Google de l'événement à supprimer."},
                },
                "required": ["event_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_events",
            "description": "Recherche des événements par mot-clé dans le calendrier.",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "Mot-clé à rechercher."},
                    "days_ahead": {"type": "integer", "description": "Plage de recherche en jours (défaut: 30)."},
                },
                "required": ["keyword"],
            },
        },
    },
]


class AgendaAgent:
    name = "agenda"

    def __init__(self, calendar: GoogleCalendarClient, llm_client: ToolCallingLLMClient) -> None:
        self.calendar = calendar
        self.llm_client = llm_client
        self._tool_functions = {
            "list_events": lambda args: calendar.list_events(**args),
            "add_event": lambda args: calendar.add_event(**args),
            "update_event": lambda args: calendar.update_event(**args),
            "delete_event": lambda args: calendar.delete_event(**args),
            "search_events": lambda args: calendar.search_events(**args),
        }

    def _execute_tool(self, name: str, arguments: dict) -> str:
        """Exécute l'outil demandé et retourne le résultat en JSON — jamais
        d'exception propagée : le modèle doit pouvoir se corriger ou
        informer l'utilisateur de l'échec plutôt que de faire planter
        l'agent (dispatch.py répondrait alors un message générique sans
        contexte utile)."""
        if name not in self._tool_functions:
            return json.dumps({"error": f"Outil inconnu : {name}"})
        try:
            result = self._tool_functions[name](arguments)
            return json.dumps(result, ensure_ascii=False, default=str)
        except Exception as e:  # noqa: BLE001 — erreur convertie en résultat d'outil pour le modèle
            logger.error("[agenda] Échec de l'outil %s : %s", name, e)
            return json.dumps({"error": str(e)})

    def handle(self, args: str, deps: Deps) -> AgentResponse:
        if not args.strip():
            return AgentResponse(text="Dites-moi ce que vous voulez faire sur votre calendrier.")

        now = datetime.now(pytz.timezone(self.calendar.timezone))
        system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
            now=now.strftime("%A %d %B %Y à %H:%M"),
            timezone=self.calendar.timezone,
        )
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=args),
        ]

        for _round in range(MAX_TOOL_ROUNDS):
            response = self.llm_client.chat(messages, TOOLS)

            if not response.tool_calls:
                return AgentResponse(text=response.text or "Désolé, je n'ai pas compris.")

            # Conserver le tour assistant avant les résultats d'outils, pour
            # que le modèle garde le fil de la conversation au tour suivant.
            messages.append(Message(role="assistant", content=response.text or ""))
            for tool_call in response.tool_calls:
                result = self._execute_tool(tool_call.name, tool_call.arguments)
                messages.append(Message(
                    role="tool", content=result, tool_call_id=tool_call.id, name=tool_call.name,
                ))

        logger.warning("[agenda] Limite de %s tours d'outils atteinte pour : %r", MAX_TOOL_ROUNDS, args)
        return AgentResponse(text="Désolé, je n'ai pas pu terminer cette demande.")
