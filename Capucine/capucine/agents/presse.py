"""Agent de revue de presse : agrège les flux RSS suivis (config PRESSE_FEEDS)
et les résume via le LLMClient injecté (Ollama local par défaut)."""
from __future__ import annotations

from typing import Callable

from capucine.agents.base import AgentResponse
from capucine.deps import Deps
from capucine.digest import build_prompt, format_for_telegram
from capucine.feeds import FeedEntry, fetch_recent_entries
from capucine.llm.base import LLMClient

_TELEGRAM_TITLE = "📰 REVUE DE PRESSE — AUTOMOBILE ÉLECTRIQUE"


class PresseAgent:
    name = "presse"

    def __init__(
        self,
        feed_urls: "list[str]",
        fetch_entries: Callable[["list[str]"], "list[FeedEntry]"] = fetch_recent_entries,
        llm_client: "LLMClient | None" = None,
    ) -> None:
        self.feed_urls = feed_urls
        self.fetch_entries = fetch_entries
        # Un prompt de revue de presse (plusieurs articles) prend nettement
        # plus de temps à traiter par le modèle local que les autres agents
        # (~3-4 min mesurées sur le Pi, contre quelques secondes pour
        # /synthese) — client LLM dédié avec un timeout plus généreux,
        # injecté par service.py plutôt que de partager deps.llm_client.
        self.llm_client = llm_client

    def handle(self, args: str, deps: Deps) -> AgentResponse:
        entries = self.fetch_entries(self.feed_urls)
        if not entries:
            return AgentResponse(
                text="Aucune actualité récente trouvée sur les flux automobile électrique suivis."
            )

        prompt = build_prompt(entries)
        llm_client = self.llm_client or deps.llm_client
        response = llm_client.generate(prompt)

        deps.store.save_history(self.name, "user", "revue de presse")
        deps.store.save_history(self.name, "assistant", response.text)  # brut, pas la version mise en forme

        return AgentResponse(text=format_for_telegram(response.text, _TELEGRAM_TITLE))
