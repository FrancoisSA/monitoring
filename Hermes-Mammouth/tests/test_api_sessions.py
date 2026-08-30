"""
Tests de l'API web Hermes (sessions, historique) — aucun serveur ni appel API réel.

Lançable directement (python tests/test_api_sessions.py) ou via pytest.
L'agent est simulé : on vérifie la plomberie HTTP (cookie de session,
historique conservé d'une requête à l'autre, bornage, erreurs).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import api as hermes_api  # noqa: E402
from hermes_agent import AgentResponse, Message  # noqa: E402


class _FakeAgent:
    """Remplace run_agent : répond "écho: <dernier message>" et mémorise l'historique reçu."""

    def __init__(self):
        self.histories = []

    def __call__(self, messages, tools=None, max_rounds=5):
        self.histories.append([dict(m) for m in messages])
        return AgentResponse(
            message=Message(role="assistant", content=f"écho: {messages[-1]['content']}")
        )


def _fresh_app(fake: _FakeAgent):
    hermes_api._sessions.clear()
    hermes_api.run_agent = fake
    return hermes_api.create_app()


def test_chat_and_session_memory():
    fake = _FakeAgent()
    client = _fresh_app(fake).test_client()

    # Premier échange : pose le cookie de session
    r1 = client.post("/api/chat", json={"message": "premier message"})
    assert r1.status_code == 200, r1.data
    assert r1.get_json()["content"] == "écho: premier message"
    assert "hermes_session" in (r1.headers.get("Set-Cookie") or "")

    # Deuxième échange (même client → mêmes cookies) : l'historique doit contenir le 1er
    r2 = client.post("/api/chat", json={"message": "second message"})
    assert r2.status_code == 200
    history = fake.histories[1]
    assert history[0]["content"] == "premier message"
    assert history[1]["content"] == "écho: premier message"
    assert history[2]["content"] == "second message"


def test_history_is_bounded():
    fake = _FakeAgent()
    client = _fresh_app(fake).test_client()

    for i in range(hermes_api.MAX_HISTORY + 4):
        client.post("/api/chat", json={"message": f"msg {i}"})

    last_history = fake.histories[-1]
    assert len(last_history) <= hermes_api.MAX_HISTORY
    assert last_history[-1]["content"] == f"msg {hermes_api.MAX_HISTORY + 3}"


def test_empty_message_rejected():
    client = _fresh_app(_FakeAgent()).test_client()
    r = client.post("/api/chat", json={"message": "   "})
    assert r.status_code == 400
    r = client.post("/api/chat", data="not json", content_type="application/json")
    assert r.status_code == 400


def test_agent_error_returns_500_not_crash():
    def boom(messages, tools=None, max_rounds=5):
        raise RuntimeError("panne simulée")

    hermes_api._sessions.clear()
    hermes_api.run_agent = boom
    client = hermes_api.create_app().test_client()
    r = client.post("/api/chat", json={"message": "hello"})
    assert r.status_code == 500
    assert "panne simulée" in r.get_json()["error"]


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
