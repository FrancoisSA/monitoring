"""Interface commune que doit respecter chaque agent Capucine.

Ajouter un agent = écrire une classe qui respecte cette interface (un module
sous capucine/agents/), sans toucher au routeur ni au service Telegram.
C'est ce qui rend le framework extensible.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from capucine.deps import Deps


@dataclass(frozen=True)
class AgentResponse:
    """Ce qu'un agent renvoie : le texte à répondre sur Telegram."""

    text: str


class Agent(Protocol):
    def handle(self, args: str, deps: Deps) -> AgentResponse:
        ...
