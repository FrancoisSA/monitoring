import os
import queue
import socket
import threading
import time
import uuid

from capucine.agents.base import AgentResponse
from capucine.router import Router
from capucine.service import run_scheduled_trigger, serve_trigger_socket


class _FakeAgent:
    def __init__(self, text: str = "ok", raises: bool = False, notify: bool = True) -> None:
        self.text = text
        self.raises = raises
        self.notify = notify

    def handle(self, args, deps):
        if self.raises:
            raise RuntimeError("boom")
        return AgentResponse(text=self.text, notify=self.notify)


class _FakeTelegram:
    def __init__(self) -> None:
        self.sent: "list[tuple[int, str]]" = []

    def send_message(self, chat_id: int, text: str) -> None:
        self.sent.append((chat_id, text))


def test_run_scheduled_trigger_sends_the_agent_response(deps):
    router = Router({"presse": _FakeAgent(text="revue du jour")})
    telegram = _FakeTelegram()

    run_scheduled_trigger("presse", router, deps, telegram, chat_id=42)

    assert telegram.sent == [(42, "revue du jour")]


def test_run_scheduled_trigger_unknown_command_does_not_notify(deps):
    router = Router({})
    telegram = _FakeTelegram()

    run_scheduled_trigger("inconnue", router, deps, telegram, chat_id=42)

    assert telegram.sent == []


def test_run_scheduled_trigger_agent_failure_does_not_notify(deps):
    router = Router({"presse": _FakeAgent(raises=True)})
    telegram = _FakeTelegram()

    run_scheduled_trigger("presse", router, deps, telegram, chat_id=42)

    assert telegram.sent == []


def test_run_scheduled_trigger_respects_notify_false(deps):
    router = Router({"renault": _FakeAgent(text="rien de neuf", notify=False)})
    telegram = _FakeTelegram()

    run_scheduled_trigger("renault", router, deps, telegram, chat_id=42)

    assert telegram.sent == []


def test_serve_trigger_socket_enqueues_the_received_command():
    # /tmp directement (pas tmp_path de pytest) : la taille d'un chemin
    # AF_UNIX est limitée (~104 octets sur macOS) et tmp_path est trop long.
    socket_path = f"/tmp/capucine-test-{uuid.uuid4().hex}.sock"
    trigger_queue: "queue.Queue[str]" = queue.Queue()

    thread = threading.Thread(
        target=serve_trigger_socket, args=(socket_path, trigger_queue), daemon=True
    )
    thread.start()
    try:
        time.sleep(0.1)  # laisse le temps au bind()/listen() de s'exécuter

        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.connect(socket_path)
            client.sendall(b"presse")

        assert trigger_queue.get(timeout=2) == "presse"
    finally:
        if os.path.exists(socket_path):
            os.unlink(socket_path)
