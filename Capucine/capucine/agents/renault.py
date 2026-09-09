"""Agent de veille : recherche des actualités Renault (véhicules électriques)
et Ampere (marque VE de Renault) via Google News RSS, et ne notifie que les
articles jamais vus lors d'une exécution précédente (déclenchement prévu
toutes les heures, cf. scripts/trigger.sh + crontab)."""
from __future__ import annotations

from typing import Callable
from urllib.parse import urlencode

from capucine.agents.base import AgentResponse
from capucine.deps import Deps
from capucine.digest import build_prompt, format_for_telegram
from capucine.feeds import FeedEntry, fetch_recent_entries
from capucine.llm.base import LLMClient

_TELEGRAM_TITLE = "🚗 VEILLE — RENAULT / AMPERE"

# Fenêtre de récupération plus large que /presse (30h) : une recherche
# ciblée sur deux sujets précis a un volume d'actualité bien plus faible
# qu'un flux généraliste automobile électrique.
_SINCE_HOURS = 72


def google_news_search_url(query: str) -> str:
    params = {"q": query, "hl": "fr", "gl": "FR", "ceid": "FR:fr"}
    return f"https://news.google.com/rss/search?{urlencode(params)}"


class RenaultAgent:
    name = "renault"

    def __init__(
        self,
        search_queries: "list[str]",
        fetch_entries: Callable[..., "list[FeedEntry]"] = fetch_recent_entries,
        llm_client: "LLMClient | None" = None,
    ) -> None:
        self.search_queries = search_queries
        self.fetch_entries = fetch_entries
        self.llm_client = llm_client

    def handle(self, args: str, deps: Deps) -> AgentResponse:
        feed_urls = [google_news_search_url(query) for query in self.search_queries]
        entries = self.fetch_entries(feed_urls, since_hours=_SINCE_HOURS)

        new_entries = [entry for entry in entries if not deps.store.has_seen(self.name, entry.link)]
        for entry in new_entries:
            deps.store.mark_seen(self.name, entry.link)

        if not new_entries:
            return AgentResponse(
                text="Rien de nouveau sur Renault / Ampere depuis la dernière recherche.",
                notify=False,
            )

        prompt = build_prompt(new_entries)
        llm_client = self.llm_client or deps.llm_client
        response = llm_client.generate(prompt)

        deps.store.save_history(self.name, "user", "veille renault/ampere")
        deps.store.save_history(self.name, "assistant", response.text)  # brut, pas la version mise en forme

        return AgentResponse(text=format_for_telegram(response.text, _TELEGRAM_TITLE))
