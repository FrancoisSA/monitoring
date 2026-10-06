"""Agent de digest quotidien : agrège les flux RSS suivis (config IA_FEEDS)
sur l'actualité IA et les frameworks agentiques, et les résume via LM Studio
(Mac, si disponible) ou le LLMClient injecté (Ollama local en repli). Clone
de PresseAgent."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from capucine.agents.base import AgentResponse
from capucine.deps import Deps
from capucine.digest import (
    build_prompt,
    format_for_telegram,
    generate_digest,
    mark_entries_sent,
    select_unseen_entries,
)
from capucine.feeds import FeedEntry, fetch_recent_entries
from capucine.llm.base import LLMClient
from capucine.mac_wake import MacConfig

_TELEGRAM_TITLE = "🤖 DIGEST — IA & FRAMEWORKS AGENTIQUES"


class IaAgent:
    name = "ia"

    def __init__(
        self,
        feed_urls: "list[str]",
        fetch_entries: Callable[["list[str]"], "list[FeedEntry]"] = fetch_recent_entries,
        llm_client: "LLMClient | None" = None,
        mac_config: "MacConfig | None" = None,
        piper_model_path: "str | None" = None,
    ) -> None:
        self.feed_urls = feed_urls
        self.fetch_entries = fetch_entries
        self.llm_client = llm_client
        self.mac_config = mac_config
        self.piper_model_path = piper_model_path

    def handle(self, args: str, deps: Deps) -> AgentResponse:
        entries = select_unseen_entries(deps.store, self.name, self.fetch_entries(self.feed_urls))
        if not entries:
            # notify=False : pas de message proactif vide lors des envois
            # planifiés (4 par jour) ; un /ia tapé à la main répond
            # quand même (cf. AgentResponse.notify, agents/base.py).
            return AgentResponse(
                text="Rien de nouveau sur l'IA depuis la dernière revue.",
                notify=False,
            )

        prompt = build_prompt(entries)
        llm_client = self.llm_client or deps.llm_client
        result = generate_digest(
            prompt,
            fallback_llm_client=llm_client,
            mac_config=self.mac_config,
            voice_output_path=Path(f"/tmp/capucine-voice-{self.name}.ogg"),
            piper_model_path=self.piper_model_path,
        )
        mark_entries_sent(deps.store, self.name, entries)

        return AgentResponse(
            text=format_for_telegram(result.response.text, _TELEGRAM_TITLE),
            voice_path=result.voice_path,
        )
