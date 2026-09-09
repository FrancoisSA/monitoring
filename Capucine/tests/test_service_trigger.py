import os
import queue
import socket
import threading
import time
import uuid
from pathlib import Path

import requests

from capucine.agents.base import AgentResponse
from capucine.config import load_config
from capucine.router import Router
from capucine.service import build_mac_config, run_scheduled_trigger, send_response, serve_trigger_socket


class _FakeAgent:
    def __init__(
        self, text: str = "ok", raises: bool = False, notify: bool = True, voice_path=None
    ) -> None:
        self.text = text
        self.raises = raises
        self.notify = notify
        self.voice_path = voice_path

    def handle(self, args, deps):
        if self.raises:
            raise RuntimeError("boom")
        return AgentResponse(text=self.text, notify=self.notify, voice_path=self.voice_path)


class _FakeTelegram:
    def __init__(self, raise_on_voice: "Exception | None" = None) -> None:
        self.sent: "list[tuple[int, str]]" = []
        self.voices_sent: "list[tuple[int, str]]" = []
        self.raise_on_voice = raise_on_voice

    def send_message(self, chat_id: int, text: str) -> None:
        self.sent.append((chat_id, text))

    def send_voice(self, chat_id: int, voice_path) -> None:
        if self.raise_on_voice is not None:
            raise self.raise_on_voice
        self.voices_sent.append((chat_id, str(voice_path)))


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


def test_run_scheduled_trigger_also_sends_the_voice_note(deps):
    router = Router({"presse": _FakeAgent(text="revue du jour", voice_path=Path("/tmp/voice.ogg"))})
    telegram = _FakeTelegram()

    run_scheduled_trigger("presse", router, deps, telegram, chat_id=42)

    assert telegram.sent == [(42, "revue du jour")]
    assert telegram.voices_sent == [(42, "/tmp/voice.ogg")]


def test_send_response_sends_text_even_if_voice_fails_with_request_exception(deps):
    telegram = _FakeTelegram(raise_on_voice=requests.exceptions.RequestException("échec réseau"))
    response = AgentResponse(text="le texte", voice_path=Path("/tmp/voice.ogg"))

    send_response(telegram, 42, response, context="test")

    assert telegram.sent == [(42, "le texte")]
    assert telegram.voices_sent == []  # a échoué, mais n'a pas fait planter l'appel


def test_send_response_sends_text_even_if_voice_file_is_missing(deps):
    # Scénario réel : send_voice ouvre le fichier avant l'appel réseau —
    # un fichier manquant lève OSError, pas RequestException.
    telegram = _FakeTelegram(raise_on_voice=FileNotFoundError("fichier vocal introuvable"))
    response = AgentResponse(text="le texte", voice_path=Path("/tmp/voice-absent.ogg"))

    send_response(telegram, 42, response, context="test")

    assert telegram.sent == [(42, "le texte")]
    assert telegram.voices_sent == []


def test_send_response_skips_voice_when_none(deps):
    telegram = _FakeTelegram()
    response = AgentResponse(text="le texte")

    send_response(telegram, 42, response, context="test")

    assert telegram.sent == [(42, "le texte")]
    assert telegram.voices_sent == []


def test_build_mac_config_is_none_when_mac_host_not_set(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    monkeypatch.delenv("MAC_HOST", raising=False)

    assert build_mac_config(load_config()) is None


def test_build_mac_config_builds_a_config_when_mac_host_set(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    monkeypatch.setenv("MAC_HOST", "10.0.0.8")
    monkeypatch.setenv("MAC_SSH_USER", "francoissalazar")
    monkeypatch.setenv("MAC_ADDRESS", "84:2f:57:d3:48:6c")

    mac_config = build_mac_config(load_config())

    assert mac_config is not None
    assert mac_config.host == "10.0.0.8"
    assert mac_config.mac_address == "84:2f:57:d3:48:6c"


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
