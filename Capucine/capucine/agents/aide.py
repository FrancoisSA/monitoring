"""Agent /aide : rappelle la liste des commandes disponibles. Texte statique
(aucun LLM) — à tenir à jour manuellement quand une commande est ajoutée ou
retirée du routeur (cf. capucine/service.py::build_router)."""
from __future__ import annotations

from capucine.agents.base import AgentResponse
from capucine.deps import Deps

_AIDE_TEXTE = """Commandes disponibles :

/echo <texte> — renvoie le texte tel quel (test de connectivité)
/synthese <texte> — résume un texte fourni
/presse — revue de presse automobile électrique
/renault — veille Renault/Ampère
/ia — digest actualité IA & frameworks agentiques
/agenda <demande> — assistant calendrier en langage naturel

/presse, /renault et /ia tentent d'abord le Mac (LM Studio + voix), avec \
repli sur Ollama local (texte seul) si le Mac est injoignable.

Dashboard (hors Telegram) : http://FSA-PI5.local:9192"""


class AideAgent:
    name = "aide"

    def handle(self, args: str, deps: Deps) -> AgentResponse:
        return AgentResponse(text=_AIDE_TEXTE)
