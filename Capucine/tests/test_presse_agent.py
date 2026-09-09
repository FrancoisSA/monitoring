from datetime import datetime, timezone

from capucine.agents.presse import PresseAgent
from capucine.feeds import FeedEntry
from capucine.llm.base import LLMResponse


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
