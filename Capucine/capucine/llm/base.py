"""Interface commune aux backends LLM (Ollama local, Mistral cloud...).

Un agent appelle deps.llm_client.generate(...) sans savoir si la réponse
vient d'un modèle local ou d'une API cloud : le choix du backend est déclaré
une fois, dans la config de l'agent (backend statique, pas de classification
dynamique de la complexité en v1).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str
    latency_ms: float


class LLMClient(Protocol):
    def generate(self, prompt: str) -> LLMResponse:
        ...


# ─────────────────────────────────────────────────────────────────
# Tool-calling — protocole séparé de LLMClient (n'importe pas dessus, ne le
# modifie pas) : seul /agenda en a besoin, pour laisser le modèle décider
# quel outil calendrier appeler à partir d'une commande en langage naturel.
# Implémenté par OllamaClient.chat() (cf. capucine/llm/ollama_client.py),
# via l'API /api/chat d'Ollama — les petits modèles (0.5B-3B) restent moins
# fiables en tool-calling qu'un modèle plus gros, d'où AGENDA_OLLAMA_MODEL
# pour pointer /agenda vers un modèle dédié sans changer de code.
# ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Message:
    """Un message de la conversation envoyée au modèle. `tool_call_id` et
    `name` ne sont renseignés que pour role="tool" (résultat d'exécution
    d'un outil, à réinjecter dans la conversation)."""

    role: str  # "system" | "user" | "assistant" | "tool"
    content: str
    tool_call_id: "str | None" = None
    name: "str | None" = None


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ToolCallResponse:
    """Résultat d'un tour de conversation avec tool-calling.

    `tool_calls` est vide quand le modèle répond directement en texte
    (`text` est alors renseigné) ; sinon `text` peut être None et
    l'appelant doit exécuter les outils demandés puis rappeler `chat()`
    avec les résultats ajoutés aux messages (role="tool")."""

    text: "str | None"
    tool_calls: "list[ToolCall]" = field(default_factory=list)


class ToolCallingLLMClient(Protocol):
    def chat(self, messages: "list[Message]", tools: "list[dict]") -> ToolCallResponse:
        ...
