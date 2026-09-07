"""Résout une commande Telegram (ex. "echo", "synthese") vers l'agent
correspondant.

Interface volontairement minimale — un simple dict — pour pouvoir être
remplacée plus tard par un routage par intention/LLM sans changer
l'appelant (dispatch.py n'a besoin que de .route()).
"""
from __future__ import annotations

from capucine.agents.base import Agent


class Router:
    def __init__(self, routes: "dict[str, Agent]") -> None:
        self._routes = routes

    def route(self, command: str) -> "Agent | None":
        return self._routes.get(command)
