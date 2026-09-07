"""Client HTTP minimal pour l'API locale d'Ollama.

Pas de SDK : une requête HTTP directe suffit et évite une dépendance lourde
(contrainte de légèreté sur le Raspberry Pi).
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Optional

import requests

from capucine.llm.base import LLMResponse

PostFn = Callable[[str, dict], dict]

# Un modèle Ollama non chargé en mémoire (cold start, après une période
# d'inactivité) a été mesuré à ~14s sur le Pi pour une seule réponse courte —
# 60s laisse une marge raisonnable pour un cold start + un prompt plus long.
DEFAULT_TIMEOUT_S = 60


@dataclass
class OllamaClient:
    """Backend LLM local, via l'API HTTP d'Ollama (http://127.0.0.1:11434).

    `post` est injectable pour les tests : aucun appel réseau réel n'est
    nécessaire pour valider le comportement de generate().
    """

    model: str = "qwen2.5:3b"
    host: str = "http://127.0.0.1:11434"
    timeout: int = DEFAULT_TIMEOUT_S
    post: Optional[PostFn] = None

    def __post_init__(self) -> None:
        if self.post is None:
            self.post = self._default_post

    def _default_post(self, url: str, payload: dict) -> dict:
        response = requests.post(url, json=payload, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def generate(self, prompt: str) -> LLMResponse:
        start = time.monotonic()
        payload = {"model": self.model, "prompt": prompt, "stream": False}
        data = self.post(f"{self.host}/api/generate", payload)
        latency_ms = (time.monotonic() - start) * 1000

        text = data.get("response", "")
        if not text:
            raise RuntimeError(f"[ollama] Réponse vide du modèle {self.model}")

        return LLMResponse(text=text, model=self.model, latency_ms=latency_ms)
