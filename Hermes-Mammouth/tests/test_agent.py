"""
Tests locaux de l'agent Hermes — aucun appel API requis.

Lançable directement (python tests/test_agent.py) ou via pytest.
Le LLM est simulé : seul le cœur (normalisation, registre, boucle) est testé.
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace

# Rendre src/ importable quel que soit le répertoire d'appel
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import hermes_agent as ha  # noqa: E402


# --- Normalisation des messages -------------------------------------------

def test_to_api_messages_user_and_dicts():
    msgs = [
        {"role": "user", "content": "Bonjour"},
        ha.Message(role="user", content="Salut"),
    ]
    out = ha._to_api_messages(msgs)
    assert out == [
        {"role": "user", "content": "Bonjour"},
        {"role": "user", "content": "Salut"},
    ]


def test_to_api_messages_preserves_tool_round():
    tool_calls = [{
        "id": "call_1",
        "type": "function",
        "function": {"name": "google_tasks", "arguments": "{\"action\": \"add\"}"},
    }]
    msgs = [
        {"role": "user", "content": "Ajoute une tâche"},
        ha.Message(role="assistant", content="", tool_calls=tool_calls),
        ha.Message(role="tool", content="résultat", tool_call_id="call_1", name="google_tasks"),
    ]
    out = ha._to_api_messages(msgs)
    assert out[1]["tool_calls"] == tool_calls
    assert out[2]["role"] == "tool"
    assert out[2]["tool_call_id"] == "call_1"
    assert out[2]["name"] == "google_tasks"


# --- Normalisation des tool_calls du SDK ----------------------------------

def test_normalize_tool_calls_from_sdk_objects():
    raw = [SimpleNamespace(
        id="call_9",
        function=SimpleNamespace(name="google_gmail", arguments={"action": "read"}),
    )]
    calls = ha._normalize_tool_calls(raw)
    assert calls[0]["id"] == "call_9"
    assert calls[0]["type"] == "function"
    assert calls[0]["function"]["name"] == "google_gmail"
    assert calls[0]["function"]["arguments"] == "{\"action\": \"read\"}"


def test_normalize_tool_calls_none():
    assert ha._normalize_tool_calls(None) == []


# --- Registre et exécution d'outils ---------------------------------------

def test_execute_tool_stub_is_honest():
    result = ha._execute_tool("google_tasks", '{"action": "add", "title": "Test"}')
    assert "google_tasks" in result
    assert "pas encore connecté" in result


def test_execute_tool_unknown():
    result = ha._execute_tool("inexistant", "{}")
    assert "inconnu" in result
    assert "google_calendar" in result  # liste les outils disponibles


def test_execute_tool_bad_json():
    result = ha._execute_tool("google_tasks", "{pas du json")
    assert "invalides" in result


def test_registry_matches_tools():
    names = {t["function"]["name"] for t in ha.TOOLS}
    assert names == set(ha.TOOL_REGISTRY)


# --- Boucle agentique (LLM simulé) ----------------------------------------

class _FakeLLM:
    """Remplace call_llm : renvoie les réponses fournies une par une."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.seen_histories = []

    def __call__(self, messages, tools=None):
        self.seen_histories.append(list(messages))
        return self.responses.pop(0)


def test_run_agent_executes_tool_and_feeds_result_back(monkeypatch=None):
    tool_calls = [{
        "id": "call_1",
        "type": "function",
        "function": {"name": "google_tasks", "arguments": "{\"action\": \"add\"}"},
    }]
    fake = _FakeLLM([
        ha.Message(role="assistant", content="", tool_calls=tool_calls),
        ha.Message(role="assistant", content="C'est fait !"),
    ])
    ha.call_llm = fake

    result = ha.run_agent([{"role": "user", "content": "Ajoute une tâche"}])

    assert result.message.content == "C'est fait !"
    assert result.tools_used == ["google_tasks"]
    assert result.rounds == 2
    # Le 2e tour doit contenir le résultat de l'outil avec son tool_call_id
    second = fake.seen_histories[1]
    tool_msgs = [m for m in second if (m.role if hasattr(m, "role") else m.get("role")) == "tool"]
    assert len(tool_msgs) == 1
    assert getattr(tool_msgs[0], "tool_call_id", None) == "call_1"


def test_run_agent_stops_at_max_rounds():
    tool_calls = [{
        "id": "call_x",
        "type": "function",
        "function": {"name": "google_calendar", "arguments": "{}"},
    }]
    fake = _FakeLLM([
        ha.Message(role="assistant", content="", tool_calls=tool_calls)
        for _ in range(ha.MAX_TOOL_ROUNDS + 2)
    ])
    ha.call_llm = fake

    result = ha.run_agent([{"role": "user", "content": "boucle"}], max_rounds=3)
    assert result.rounds == 3
    assert fake.seen_histories[-1].__len__() >= 1


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted({
        n: f for n, f in list(globals().items())
        if n.startswith("test_") and callable(f)
    }.items()):
        try:
            fn()
            print(f"✅ {name}")
        except AssertionError as exc:
            failures += 1
            print(f"❌ {name} : {exc}")
    print(f"\n{'ÉCHEC' if failures else 'OK'} — {failures} échec(s)")
    sys.exit(1 if failures else 0)
