"""Agent de revue de presse : agrège les flux RSS suivis (config PRESSE_FEEDS)
et les résume via LM Studio (Mac, si disponible) ou le LLMClient injecté
(Ollama local en repli)."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from capucine.agents.base import AgentResponse
from capucine.deps import Deps
from capucine.digest import build_prompt, format_for_telegram, generate_digest
from capucine.feeds import FeedEntry, fetch_recent_entries
from capucine.llm.base import LLMClient
from capucine.mac_wake import MacConfig

_TELEGRAM_TITLE = "📰 REVUE DE PRESSE — AUTOMOBILE ÉLECTRIQUE"


class PresseAgent:
    name = "presse"

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
        # Un prompt de revue de presse (plusieurs articles) prend nettement
        # plus de temps à traiter par le modèle local que les autres agents
        # (~3-4 min mesurées sur le Pi, contre quelques secondes pour
        # /synthese) — client LLM dédié avec un timeout plus généreux,
        # injecté par service.py plutôt que de partager deps.llm_client.
        self.llm_client = llm_client
        # Si fourni, generate_digest tente Mac + LM Studio (texte + vocal)
        # avant de basculer sur llm_client — cf. capucine/digest.py.
        self.mac_config = mac_config
        # Vocal du repli Ollama via Piper (local, Pi) si le Mac est
        # injoignable — cf. capucine/tts_piper.py.
        self.piper_model_path = piper_model_path

    def handle(self, args: str, deps: Deps) -> AgentResponse:
        entries = self.fetch_entries(self.feed_urls)
        if not entries:
            return AgentResponse(
                text="Aucune actualité récente trouvée sur les flux automobile électrique suivis."
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

        return AgentResponse(
            text=format_for_telegram(result.response.text, _TELEGRAM_TITLE),
            voice_path=result.voice_path,
        )
