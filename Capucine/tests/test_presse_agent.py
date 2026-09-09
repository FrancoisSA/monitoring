from datetime import datetime, timezone
from pathlib import Path

from capucine.agents.presse import PresseAgent
from capucine.digest import DigestResult
from capucine.feeds import FeedEntry
from capucine.llm.base import LLMResponse
from capucine.mac_wake import MacConfig


class _FakeDedicatedLLMClient:
    def __init__(self, response_text: str) -> None:
        self.response_text = response_text
        self.calls: "list[str]" = []

    def generate(self, prompt: str) -> LLMResponse:
        self.calls.append(prompt)
        return LLMResponse(text=self.response_text, model="fake-dedicated", latency_ms=0.0)


def _entry(title: str, source: str = "Source") -> FeedEntry:
    return FeedEntry(
        source=source,
        title=title,
        link="https://example.com",
        summary="résumé",
        published=datetime.now(timezone.utc),
    )


def test_presse_returns_the_formatted_llm_synthesis(deps, fake_llm):
    fake_llm.response_text = "- [Source] Voici la revue."
    agent = PresseAgent(
        feed_urls=["https://feed.example"], fetch_entries=lambda urls: [_entry("Titre 1")]
    )

    response = agent.handle("", deps)

    assert "Voici la revue." in response.text
    assert "REVUE DE PRESSE" in response.text


def test_presse_saves_the_raw_exchange_in_history(deps, store, fake_llm):
    fake_llm.response_text = "résumé du jour"
    agent = PresseAgent(
        feed_urls=["https://feed.example"], fetch_entries=lambda urls: [_entry("Titre")]
    )

    agent.handle("", deps)

    history = store.get_history("presse")
    assert history == [("user", "revue de presse"), ("assistant", "résumé du jour")]


def test_presse_with_no_entries_does_not_call_the_llm(deps, fake_llm):
    agent = PresseAgent(feed_urls=["https://feed.example"], fetch_entries=lambda urls: [])

    response = agent.handle("", deps)

    assert fake_llm.calls == []
    assert "Aucune actualité récente" in response.text


def test_presse_uses_its_own_llm_client_when_provided(deps, fake_llm):
    dedicated_llm = _FakeDedicatedLLMClient(response_text="réponse du client dédié")
    agent = PresseAgent(
        feed_urls=["https://feed.example"],
        fetch_entries=lambda urls: [_entry("Titre")],
        llm_client=dedicated_llm,
    )

    response = agent.handle("", deps)

    assert "réponse du client dédié" in response.text
    assert fake_llm.calls == []  # le client de deps n'est pas sollicité


def test_presse_passes_mac_config_and_voice_output_path_to_generate_digest(deps, fake_llm, monkeypatch):
    mac_config = MacConfig(
        host="10.0.0.8", ssh_user="u", ssh_key_path="/k", mac_address="84:2f:57:d3:48:6c", model="m"
    )
    captured = {}

    def fake_generate_digest(prompt, fallback_llm_client, mac_config=None, voice_output_path=None, **kwargs):
        captured["mac_config"] = mac_config
        captured["voice_output_path"] = voice_output_path
        return DigestResult(
            response=LLMResponse(text="- [Source] ok", model="fake", latency_ms=0.0),
            voice_path=Path("/tmp/capucine-voice-presse.ogg"),
        )

    monkeypatch.setattr("capucine.agents.presse.generate_digest", fake_generate_digest)
    agent = PresseAgent(
        feed_urls=["https://feed.example"],
        fetch_entries=lambda urls: [_entry("Titre")],
        mac_config=mac_config,
    )

    response = agent.handle("", deps)

    assert captured["mac_config"] is mac_config
    assert captured["voice_output_path"] == Path("/tmp/capucine-voice-presse.ogg")
    assert response.voice_path == Path("/tmp/capucine-voice-presse.ogg")
