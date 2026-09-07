"""Fixtures partagées : un faux LLMClient (aucun appel réseau en test) et un
Store SQLite temporaire (vrai fichier, pas mocké — cf. spec)."""
from __future__ import annotations

import pytest

from capucine.deps import Deps
from capucine.llm.base import LLMResponse
from capucine.store import Store


class FakeLLMClient:
    """Double de test : renvoie une réponse fixe, enregistre les prompts reçus."""

    def __init__(self, response_text: str = "réponse factice") -> None:
        self.response_text = response_text
        self.calls: "list[str]" = []

    def generate(self, prompt: str) -> LLMResponse:
        self.calls.append(prompt)
        return LLMResponse(text=self.response_text, model="fake-model", latency_ms=0.0)


@pytest.fixture
def fake_llm() -> FakeLLMClient:
    return FakeLLMClient()


@pytest.fixture
def store(tmp_path) -> Store:
    return Store(tmp_path / "test.db")


@pytest.fixture
def deps(fake_llm, store) -> Deps:
    return Deps(llm_client=fake_llm, store=store)
