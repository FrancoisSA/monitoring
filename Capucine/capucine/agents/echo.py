"""Agent trivial (aucun LLM) servant à valider le chemin complet
service Telegram → routeur → agent → réponse, avant de brancher un vrai LLM.
"""
from __future__ import annotations

from capucine.agents.base import AgentResponse
from capucine.deps import Deps


class EchoAgent:
    def handle(self, args: str, deps: Deps) -> AgentResponse:
        return AgentResponse(text=args or "(rien à répéter)")
