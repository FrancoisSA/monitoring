from types import SimpleNamespace

import pytest

from capucine.mac_stt import transcribe_voice_on_mac
from capucine.mac_wake import MacConfig


def _config() -> MacConfig:
    return MacConfig(
        host="10.0.0.8",
        ssh_user="francoissalazar",
        ssh_key_path="/home/fsalazar/.ssh/id_ed25519",
        mac_address="84:2f:57:d3:48:6c",
        model="unused",
        stt_model="mlx-community/whisper-large-v3-turbo",
    )


def _completed(returncode=0, stdout="", stderr=""):
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def test_transcribe_voice_on_mac_returns_the_transcribed_text(tmp_path):
    audio = tmp_path / "voice.ogg"
    audio.write_bytes(b"fake-ogg")

    text = transcribe_voice_on_mac(
        _config(),
        audio,
        run=lambda command: _completed(stdout="ajoute un rendez-vous demain 14h\n"),
        scp_push=lambda *a: True,
    )

    assert text == "ajoute un rendez-vous demain 14h"


def test_transcribe_voice_on_mac_forwards_configured_model_to_remote_command(tmp_path):
    """SSH ne forwarde pas l'environnement du Pi par défaut — le modèle
    mlx-whisper doit être injecté explicitement dans la commande distante
    (même pattern que CAPUCINE_TTS_MODEL_PATH, cf. mac_generate.py)."""
    config = MacConfig(
        host="10.0.0.8", ssh_user="francoissalazar", ssh_key_path="/unused",
        mac_address="84:2f:57:d3:48:6c", model="unused",
        stt_model="mlx-community/whisper-large-v3-turbo",
    )
    captured = {}

    def fake_run(command):
        captured["command"] = command
        return _completed(stdout="texte")

    transcribe_voice_on_mac(config, tmp_path / "voice.ogg", run=fake_run, scp_push=lambda *a: True)

    command_str = " ".join(captured["command"])
    assert "CAPUCINE_STT_MODEL=mlx-community/whisper-large-v3-turbo" in command_str


def test_transcribe_voice_on_mac_raises_when_scp_push_fails(tmp_path):
    with pytest.raises(RuntimeError, match="envoi du fichier audio"):
        transcribe_voice_on_mac(
            _config(),
            tmp_path / "voice.ogg",
            run=lambda command: pytest.fail("SSH ne doit pas être appelé si le scp a échoué"),
            scp_push=lambda *a: False,
        )


def test_transcribe_voice_on_mac_raises_on_nonzero_exit_code(tmp_path):
    with pytest.raises(RuntimeError, match="Échec transcription"):
        transcribe_voice_on_mac(
            _config(),
            tmp_path / "voice.ogg",
            run=lambda command: _completed(returncode=1, stderr="boom"),
            scp_push=lambda *a: True,
        )


def test_transcribe_voice_on_mac_raises_on_empty_transcription(tmp_path):
    with pytest.raises(RuntimeError, match="Transcription vide"):
        transcribe_voice_on_mac(
            _config(),
            tmp_path / "voice.ogg",
            run=lambda command: _completed(stdout="   "),
            scp_push=lambda *a: True,
        )
