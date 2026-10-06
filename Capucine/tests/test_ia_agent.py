from datetime import datetime, timezone

import pytest

from capucine.agents.ia import IaAgent
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


def test_ia_returns_the_formatted_llm_synthesis(deps, fake_llm):
    fake_llm.response_text = "- [Source] Voici le digest."
    agent = IaAgent(feed_urls=["https://feed.example"], fetch_entries=lambda urls: [_entry("Titre 1")])

    response = agent.handle("", deps)

    assert "Voici le digest." in response.text
    assert "DIGEST" in response.text


def test_ia_with_no_entries_does_not_call_the_llm(deps, fake_llm):
    agent = IaAgent(feed_urls=["https://feed.example"], fetch_entries=lambda urls: [])

    response = agent.handle("", deps)

    assert fake_llm.calls == []
    assert "Rien de nouveau" in response.text
    assert response.notify is False


def test_ia_uses_its_own_llm_client_when_provided(deps, fake_llm):
    dedicated_llm = _FakeDedicatedLLMClient(response_text="réponse du client dédié")
    agent = IaAgent(
        feed_urls=["https://feed.example"],
        fetch_entries=lambda urls: [_entry("Titre")],
        llm_client=dedicated_llm,
    )

    response = agent.handle("", deps)

    assert "réponse du client dédié" in response.text
    assert fake_llm.calls == []  # le client de deps n'est pas sollicité


def test_ia_does_not_repeat_articles_already_sent(deps, fake_llm):
    agent = IaAgent(feed_urls=["https://feed.example"], fetch_entries=lambda urls: [_entry("Titre")])
    agent.handle("", deps)

    response = agent.handle("", deps)

    assert len(fake_llm.calls) == 1
    assert response.notify is False


def test_ia_keeps_articles_for_next_run_when_generation_fails(deps, fake_llm):
    def failing_generate(prompt):
        raise RuntimeError("LLM injoignable")

    fake_llm.generate = failing_generate
    agent = IaAgent(feed_urls=["https://feed.example"], fetch_entries=lambda urls: [_entry("Titre")])

    with pytest.raises(RuntimeError):
        agent.handle("", deps)

    assert deps.store.has_seen(agent.name, "https://example.com") is False
