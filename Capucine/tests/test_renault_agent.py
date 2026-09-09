from datetime import datetime, timezone

from capucine.agents.renault import RenaultAgent, google_news_search_url
from capucine.feeds import FeedEntry


def _entry(link: str, title: str = "Titre", source: str = "Source") -> FeedEntry:
    return FeedEntry(
        source=source, title=title, link=link, summary="résumé", published=datetime.now(timezone.utc)
    )


def test_google_news_search_url_encodes_the_query():
    url = google_news_search_url("Renault véhicules électriques")

    assert url.startswith("https://news.google.com/rss/search?")
    assert "hl=fr" in url
    assert "gl=FR" in url


def test_renault_notifies_and_marks_new_entries_as_seen(deps, store, fake_llm):
    fake_llm.response_text = "- [Source] Une actualité Renault."
    entry = _entry("https://example.com/article-1")
    agent = RenaultAgent(search_queries=["Renault"], fetch_entries=lambda urls, since_hours: [entry])

    response = agent.handle("", deps)

    assert response.notify is True
    assert "Une actualité Renault." in response.text
    assert store.has_seen("renault", "https://example.com/article-1") is True


def test_renault_does_not_notify_when_nothing_new(deps, store, fake_llm):
    store.mark_seen("renault", "https://example.com/article-1")
    entry = _entry("https://example.com/article-1")
    agent = RenaultAgent(search_queries=["Renault"], fetch_entries=lambda urls, since_hours: [entry])

    response = agent.handle("", deps)

    assert response.notify is False
    assert fake_llm.calls == []


def test_renault_only_summarizes_entries_not_seen_before(deps, fake_llm):
    store_entry = _entry("https://example.com/deja-vu", title="Déjà vu")
    new_entry = _entry("https://example.com/nouveau", title="Nouveau")
    agent = RenaultAgent(
        search_queries=["Renault"],
        fetch_entries=lambda urls, since_hours: [store_entry, new_entry],
    )
    deps.store.mark_seen("renault", "https://example.com/deja-vu")

    agent.handle("", deps)

    prompt = fake_llm.calls[0]
    assert "Nouveau" in prompt
    assert "Déjà vu" not in prompt


def test_renault_uses_its_own_llm_client_when_provided(deps, fake_llm):
    class _FakeDedicatedLLMClient:
        def generate(self, prompt: str):
            from capucine.llm.base import LLMResponse

            return LLMResponse(text="réponse dédiée", model="fake", latency_ms=0.0)

    entry = _entry("https://example.com/article-1")
    agent = RenaultAgent(
        search_queries=["Renault"],
        fetch_entries=lambda urls, since_hours: [entry],
        llm_client=_FakeDedicatedLLMClient(),
    )

    response = agent.handle("", deps)

    assert "réponse dédiée" in response.text
    assert fake_llm.calls == []
