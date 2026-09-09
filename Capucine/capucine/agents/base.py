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
    """Ce qu'un agent renvoie : le texte à répondre sur Telegram.

    `notify` ne concerne que les déclenchements planifiés (cron → socket,
    cf. service.py::run_scheduled_trigger) : à False, rien n'est envoyé
    proactivement sur Telegram (ex. veille horaire sans rien de nouveau à
    signaler). Un déclenchement manuel (commande Telegram tapée par
    l'utilisateur) ignore ce champ et répond toujours — dispatch.py ne
    transmet que `.text`.
    """

    text: str
    notify: bool = True


class Agent(Protocol):
    def handle(self, args: str, deps: Deps) -> AgentResponse:
        ...
