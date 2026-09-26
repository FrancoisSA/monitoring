"""Agent de synthèse : résume un texte fourni en argument de la commande
/synthese, via le LLMClient injecté (Ollama local par défaut)."""
from __future__ import annotations

from capucine.agents.base import AgentResponse
from capucine.deps import Deps
from capucine.prompts import load_prompt

# Modifiable sans toucher au code : cf. capucine/prompts/synthese.md.
_PROMPT_TEMPLATE = load_prompt("synthese")


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
