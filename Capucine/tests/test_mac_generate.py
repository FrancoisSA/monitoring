from types import SimpleNamespace

import pytest

from capucine.mac_generate import generate_text_on_mac, generate_voice_on_mac
from capucine.mac_wake import MacConfig


def _config() -> MacConfig:
    return MacConfig(
        host="10.0.0.8",
        ssh_user="francoissalazar",
        ssh_key_path="/home/fsalazar/.ssh/id_ed25519",
        mac_address="84:2f:57:d3:48:6c",
        model="qwen3-coder-30b-a3b-instruct-mlx",
    )


def _completed(returncode=0, stdout="", stderr=""):
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def test_generate_text_on_mac_returns_the_response_on_success():
    response = generate_text_on_mac(
        _config(), "un prompt", run=lambda command, stdin: _completed(stdout="- [Source] phrase.\n")
    )

    assert response.text == "- [Source] phrase."
    assert response.model == "qwen3-coder-30b-a3b-instruct-mlx"


def test_generate_text_on_mac_raises_on_nonzero_exit_code():
    with pytest.raises(RuntimeError, match="Échec génération"):
        generate_text_on_mac(
            _config(), "un prompt", run=lambda command, stdin: _completed(returncode=1, stderr="boom")
        )


def test_generate_text_on_mac_raises_on_empty_response():
    with pytest.raises(RuntimeError, match="Réponse vide"):
        generate_text_on_mac(_config(), "un prompt", run=lambda command, stdin: _completed(stdout="   "))


def test_generate_text_on_mac_sends_the_prompt_via_stdin_not_argv():
    captured = {}

    def fake_run(command, stdin_text):
        captured["command"] = command
        captured["stdin"] = stdin_text
        return _completed(stdout="ok")

    generate_text_on_mac(_config(), "un prompt avec des \"guillemets\"", run=fake_run)

    assert captured["stdin"] == "un prompt avec des \"guillemets\""
    assert all("guillemets" not in part for part in captured["command"])


def test_generate_voice_on_mac_returns_the_local_path_on_success(tmp_path):
    local_path = tmp_path / "voice.ogg"
    scp_calls = []

    def fake_scp(config, remote_path, local):
        scp_calls.append((remote_path, local))
        return True

    result = generate_voice_on_mac(
        _config(), "texte à dire", local_path, run=lambda command, stdin: _completed(), scp=fake_scp
    )

    assert result == local_path
    assert len(scp_calls) == 1


def test_generate_voice_on_mac_forwards_configured_model_path_to_remote_command(tmp_path):
    """SSH ne forwarde pas l'environnement du Pi par défaut — le chemin du
    modèle, le timbre et l'instruction de ton doivent être injectés
    explicitement dans la commande distante, sinon mac_qwen_tts_to_ogg.sh
    échoue faute de ces variables (cf. bug équivalent rencontré avec
    l'ancien pipeline `say`/CAPUCINE_SAY_VOICE, corrigé le 2026-09-27)."""
    config = MacConfig(
        host="10.0.0.8", ssh_user="francoissalazar", ssh_key_path="/unused",
        mac_address="84:2f:57:d3:48:6c", model="unused",
        tts_model_path="/Users/francoissalazar/models/Qwen3-TTS",
        tts_voice="Vivian", tts_instruct="Parle avec enthousiasme",
    )
    captured = {}

    def fake_run(command, stdin):
        captured["command"] = command
        return _completed()

    generate_voice_on_mac(config, "texte", tmp_path / "voice.ogg", run=fake_run, scp=lambda *a: True)

    command_str = " ".join(captured["command"])
    assert "CAPUCINE_TTS_MODEL_PATH=/Users/francoissalazar/models/Qwen3-TTS" in command_str
    assert "CAPUCINE_TTS_VOICE=Vivian" in command_str
    assert "CAPUCINE_TTS_INSTRUCT='Parle avec enthousiasme'" in command_str


def test_generate_voice_on_mac_returns_none_when_ssh_fails(tmp_path):
    result = generate_voice_on_mac(
        _config(),
        "texte",
        tmp_path / "voice.ogg",
        run=lambda command, stdin: _completed(returncode=1, stderr="échec say"),
        scp=lambda *a: pytest.fail("scp ne doit pas être appelé si le SSH a échoué"),
    )

    assert result is None


def test_generate_voice_on_mac_returns_none_when_scp_fails(tmp_path):
    result = generate_voice_on_mac(
        _config(),
        "texte",
        tmp_path / "voice.ogg",
        run=lambda command, stdin: _completed(),
        scp=lambda *a: False,
    )

    assert result is None


def test_generate_voice_on_mac_returns_none_on_unexpected_exception(tmp_path):
    def raising_run(command, stdin):
        raise OSError("réseau indisponible")

    result = generate_voice_on_mac(_config(), "texte", tmp_path / "voice.ogg", run=raising_run)

    assert result is None
