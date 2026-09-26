"""Client HTTP minimal pour l'API locale d'Ollama.

Pas de SDK : une requête HTTP directe suffit et évite une dépendance lourde
(contrainte de légèreté sur le Raspberry Pi).
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Optional

import requests

from capucine.llm.base import LLMResponse, Message, ToolCall, ToolCallResponse

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

    def chat(self, messages: "list[Message]", tools: "list[dict]") -> ToolCallResponse:
        """Implémente ToolCallingLLMClient (cf. capucine/llm/base.py) via
        l'API /api/chat d'Ollama, qui supporte le tool-calling pour les
        modèles récents (ex. familles qwen2.5/llama3.1) — contrairement à
        /api/generate utilisé par generate() ci-dessus."""
        payload = {
            "model": self.model,
            "messages": [
                {"role": m.role, "content": m.content} for m in messages
            ],
            "tools": tools,
            "stream": False,
        }
        data = self.post(f"{self.host}/api/chat", payload)
        message = data.get("message", {})

        raw_tool_calls = message.get("tool_calls") or []
        tool_calls = [
            ToolCall(
                id=f"tool_{i}",
                name=tc.get("function", {}).get("name", ""),
                arguments=tc.get("function", {}).get("arguments") or {},
            )
            for i, tc in enumerate(raw_tool_calls)
        ]

        return ToolCallResponse(text=message.get("content") or None, tool_calls=tool_calls)
