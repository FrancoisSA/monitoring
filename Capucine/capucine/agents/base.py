"""Interface commune que doit respecter chaque agent Capucine.

Ajouter un agent = écrire une classe qui respecte cette interface (un module
sous capucine/agents/), sans toucher au routeur ni au service Telegram.
C'est ce qui rend le framework extensible.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from capucine.deps import Deps


@dataclass(frozen=True)
class AgentResponse:
    """Ce qu'un agent renvoie : le texte à répondre sur Telegram, et
    éventuellement un vocal.

    `notify` ne concerne que les déclenchements planifiés (cron → socket,
    cf. service.py::run_scheduled_trigger) : à False, rien n'est envoyé
    proactivement sur Telegram (ex. veille horaire sans rien de nouveau à
    signaler). Un déclenchement manuel (commande Telegram tapée par
    l'utilisateur) ignore ce champ et répond toujours.

    `voice_path` pointe vers un fichier OGG/Opus local (Pi) à envoyer comme
    message vocal Telegram en plus du texte — None si l'agent n'en produit
    pas, ou si la génération vocale a échoué (le texte est envoyé quand même,
    cf. digest.py::generate_digest).
    """

    text: str
    notify: bool = True
    voice_path: "Path | None" = None


class Agent(Protocol):
    def handle(self, args: str, deps: Deps) -> AgentResponse:
        ...
