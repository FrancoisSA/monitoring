"""Dépendances injectées dans chaque agent — le cœur du seam de test.

En test, on construit un Deps avec un faux LLMClient et un Store SQLite
temporaire : aucun appel réseau réel vers Ollama ou Mistral n'est nécessaire
pour tester le comportement d'un agent.
"""
from __future__ import annotations

from dataclasses import dataclass

from capucine.llm.base import LLMClient
from capucine.store import Store


@dataclass
class Deps:
    llm_client: LLMClient
    store: Store
