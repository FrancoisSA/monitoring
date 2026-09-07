"""Interface commune aux backends LLM (Ollama local, Mistral cloud...).

Un agent appelle deps.llm_client.generate(...) sans savoir si la réponse
vient d'un modèle local ou d'une API cloud : le choix du backend est déclaré
une fois, dans la config de l'agent (backend statique, pas de classification
dynamique de la complexité en v1).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str
    latency_ms: float


class LLMClient(Protocol):
    def generate(self, prompt: str) -> LLMResponse:
        ...
