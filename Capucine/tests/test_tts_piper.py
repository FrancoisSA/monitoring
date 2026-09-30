from types import SimpleNamespace

from capucine.tts_piper import generate_voice_with_piper


def _completed(returncode=0, stdout="", stderr=""):
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def test_generate_voice_with_piper_returns_none_when_model_path_is_empty(tmp_path):
    result = generate_voice_with_piper(
        "texte", tmp_path / "voice.ogg", model_path="",
        run=lambda command, stdin: _fail_if_called(),
    )

    assert result is None


def _fail_if_called():
    raise AssertionError("run ne doit pas être appelé si model_path est vide")


def test_generate_voice_with_piper_returns_the_local_path_on_success(tmp_path):
    result = generate_voice_with_piper(
        "texte à dire",
        tmp_path / "voice.ogg",
        model_path="/models/fr_FR-siwis-medium.onnx",
        run=lambda command, stdin: _completed(),
        convert=lambda wav_path, ogg_path: _completed(),
    )

    assert result == tmp_path / "voice.ogg"


def test_generate_voice_with_piper_forwards_model_path_and_text(tmp_path):
    captured = {}

    def fake_run(command, stdin_text):
        captured["command"] = command
        captured["stdin"] = stdin_text
        return _completed()

    generate_voice_with_piper(
        "texte à synthétiser",
        tmp_path / "voice.ogg",
        model_path="/models/fr_FR-siwis-medium.onnx",
        run=fake_run,
        convert=lambda wav_path, ogg_path: _completed(),
    )

    assert captured["stdin"] == "texte à synthétiser"
    assert "/models/fr_FR-siwis-medium.onnx" in captured["command"]
    assert "/models/fr_FR-siwis-medium.onnx.json" in captured["command"]


def test_generate_voice_with_piper_returns_none_when_piper_fails(tmp_path):
    result = generate_voice_with_piper(
        "texte",
        tmp_path / "voice.ogg",
        model_path="/models/fr_FR-siwis-medium.onnx",
        run=lambda command, stdin: _completed(returncode=1, stderr="boom"),
        convert=lambda wav_path, ogg_path: _fail_if_called(),
    )

    assert result is None


def test_generate_voice_with_piper_returns_none_when_ffmpeg_fails(tmp_path):
    result = generate_voice_with_piper(
        "texte",
        tmp_path / "voice.ogg",
        model_path="/models/fr_FR-siwis-medium.onnx",
        run=lambda command, stdin: _completed(),
        convert=lambda wav_path, ogg_path: _completed(returncode=1, stderr="ffmpeg boom"),
    )

    assert result is None


def test_generate_voice_with_piper_returns_none_on_unexpected_exception(tmp_path):
    def raising_run(command, stdin):
        raise OSError("piper introuvable")

    result = generate_voice_with_piper(
        "texte", tmp_path / "voice.ogg", model_path="/models/fr_FR-siwis-medium.onnx", run=raising_run
    )

    assert result is None
