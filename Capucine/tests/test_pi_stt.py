from types import SimpleNamespace

import pytest

from capucine.pi_stt import PiSttConfig, transcribe_voice_on_pi


def _config() -> PiSttConfig:
    return PiSttConfig(
        whisper_cli_path="/home/fsalazar/04-capucine-stt/whisper.cpp/build/bin/whisper-cli",
        whisper_model_path="/home/fsalazar/04-capucine-stt/whisper.cpp/models/ggml-base.bin",
    )


def _completed(returncode=0, stdout="", stderr=""):
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def test_transcribe_voice_on_pi_returns_the_transcribed_text(tmp_path):
    audio = tmp_path / "voice.ogg"
    audio.write_bytes(b"fake-ogg")

    text = transcribe_voice_on_pi(
        _config(),
        audio,
        run=lambda command, env: _completed(stdout="ajoute un rendez-vous demain 14h\n"),
    )

    assert text == "ajoute un rendez-vous demain 14h"


def test_transcribe_voice_on_pi_forwards_configured_paths_via_env(tmp_path):
    """Pas de SSH ici (contrairement à mac_stt.py) : whisper-cli/le modèle
    sont injectés via l'environnement du subprocess, pas la commande."""
    captured = {}

    def fake_run(command, env):
        captured["env"] = env
        return _completed(stdout="texte")

    transcribe_voice_on_pi(_config(), tmp_path / "voice.ogg", run=fake_run)

    assert captured["env"]["CAPUCINE_WHISPER_CLI"] == _config().whisper_cli_path
    assert captured["env"]["CAPUCINE_WHISPER_MODEL"] == _config().whisper_model_path


def test_transcribe_voice_on_pi_raises_on_nonzero_exit_code(tmp_path):
    with pytest.raises(RuntimeError, match="Échec transcription locale"):
        transcribe_voice_on_pi(
            _config(),
            tmp_path / "voice.ogg",
            run=lambda command, env: _completed(returncode=1, stderr="boom"),
        )


def test_transcribe_voice_on_pi_raises_on_empty_transcription(tmp_path):
    with pytest.raises(RuntimeError, match="Transcription vide"):
        transcribe_voice_on_pi(
            _config(),
            tmp_path / "voice.ogg",
            run=lambda command, env: _completed(stdout="   "),
        )
