"""Agent de synthèse : résume un texte fourni en argument de la commande
/synthese, via le LLMClient injecté (Ollama local par défaut)."""
from __future__ import annotations

from capucine.agents.base import AgentResponse
from capucine.deps import Deps

_PROMPT_TEMPLATE = (
    "Résume le texte suivant en français, en 3 phrases maximum, "
    "sans ajouter d'information absente du texte :\n\n{texte}"
)


class SyntheseAgent:
    name = "synthese"

    def handle(self, args: str, deps: Deps) -> AgentResponse:
        texte = args.strip()
        if not texte:
            return AgentResponse(text="Envoie /synthese suivi du texte à résumer.")

        deps.store.save_history(self.name, "user", texte)
        response = deps.llm_client.generate(_PROMPT_TEMPLATE.format(texte=texte))
        deps.store.save_history(self.name, "assistant", response.text)

        return AgentResponse(text=response.text)
