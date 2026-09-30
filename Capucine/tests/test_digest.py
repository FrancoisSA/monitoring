from datetime import datetime, timedelta, timezone

import pytest

from capucine.digest import (
    MAX_ENTRIES_FOR_PROMPT,
    build_prompt,
    format_for_telegram,
    generate_digest,
    text_for_speech,
)
from capucine.feeds import FeedEntry
from capucine.llm.base import LLMResponse
from capucine.mac_wake import MacConfig


def _mac_config() -> MacConfig:
    return MacConfig(
        host="10.0.0.8",
        ssh_user="francoissalazar",
        ssh_key_path="/home/fsalazar/.ssh/id_ed25519",
        mac_address="84:2f:57:d3:48:6c",
        model="qwen3-coder-30b-a3b-instruct-mlx",
    )


def _entry(title: str, source: str = "Source", published=None) -> FeedEntry:
    return FeedEntry(
        source=source,
        title=title,
        link="https://example.com",
        summary="résumé",
        published=published or datetime.now(timezone.utc),
    )


def test_build_prompt_includes_entry_titles():
    prompt = build_prompt([_entry("Un titre bien précis")])

    assert "Un titre bien précis" in prompt


def test_build_prompt_caps_the_number_of_entries():
    now = datetime.now(timezone.utc)
    too_many_entries = [
        _entry(f"Titre {i}", published=now - timedelta(minutes=i))
        for i in range(MAX_ENTRIES_FOR_PROMPT + 5)
    ]

    prompt = build_prompt(too_many_entries)

    assert prompt.count("Titre ") == MAX_ENTRIES_FOR_PROMPT
    # Les plus récents (indices 0..N-1, minutes les plus faibles) sont gardés.
    assert "Titre 0" in prompt
    assert f"Titre {MAX_ENTRIES_FOR_PROMPT + 4}" not in prompt


def test_format_for_telegram_restructures_bullet_lines_with_source_headers():
    raw = "- [CleanTechnica] BYD a vendu 189 466 véhicules.\n- [Electrek] Kia lance trois GT EV."

    formatted = format_for_telegram(raw, "📰 TITRE", now=datetime(2026, 9, 9))

    assert "🔹 CleanTechnica\nBYD a vendu 189 466 véhicules." in formatted
    assert "🔹 Electrek\nKia lance trois GT EV." in formatted
    assert "9 septembre 2026" in formatted
    assert "📰 TITRE" in formatted


def test_format_for_telegram_keeps_non_matching_lines_as_is():
    formatted = format_for_telegram("Un texte libre sans le format attendu.", "TITRE")

    assert "Un texte libre sans le format attendu." in formatted


def test_format_for_telegram_falls_back_to_raw_text_when_empty_after_stripping():
    formatted = format_for_telegram("   \n  \n", "TITRE")

    assert "TITRE" in formatted


def test_text_for_speech_converts_bullet_lines_to_sentences():
    raw = "- [CleanTechnica] BYD a vendu 189 466 véhicules.\n- [Electrek] Kia lance trois GT EV."

    speech = text_for_speech(raw)

    assert speech == "CleanTechnica. BYD a vendu 189 466 véhicules. Electrek. Kia lance trois GT EV."


def test_text_for_speech_keeps_non_matching_lines_as_is():
    assert text_for_speech("Un texte libre.") == "Un texte libre."


def test_generate_digest_uses_mac_when_reachable(fake_llm):
    result = generate_digest(
        "un prompt",
        fallback_llm_client=fake_llm,
        mac_config=_mac_config(),
        wait_for_mac_fn=lambda config: True,
        generate_text_fn=lambda config, prompt: LLMResponse(
            text="- [Source] phrase.", model="mac-model", latency_ms=10.0
        ),
    )

    assert result.response.text == "- [Source] phrase."
    assert result.response.model == "mac-model"
    assert result.voice_path is None  # pas de voice_output_path demandé
    assert fake_llm.calls == []  # le repli Ollama n'est pas sollicité


def test_generate_digest_generates_voice_when_output_path_given(fake_llm, tmp_path):
    voice_path = tmp_path / "voice.ogg"
    speech_texts = []

    def fake_generate_voice(config, text, output_path):
        speech_texts.append(text)
        return output_path

    result = generate_digest(
        "un prompt",
        fallback_llm_client=fake_llm,
        mac_config=_mac_config(),
        voice_output_path=voice_path,
        wait_for_mac_fn=lambda config: True,
        generate_text_fn=lambda config, prompt: LLMResponse(
            text="- [Source] phrase.", model="mac-model", latency_ms=10.0
        ),
        generate_voice_fn=fake_generate_voice,
    )

    assert result.voice_path == voice_path
    assert speech_texts == ["Source. phrase."]


def test_generate_digest_falls_back_to_ollama_when_mac_unreachable(fake_llm):
    fake_llm.response_text = "réponse ollama"

    result = generate_digest(
        "un prompt",
        fallback_llm_client=fake_llm,
        mac_config=_mac_config(),
        wait_for_mac_fn=lambda config: False,
        generate_text_fn=lambda config, prompt: pytest.fail("ne doit pas être appelé"),
    )

    assert result.response.text == "réponse ollama"
    assert result.voice_path is None


def test_generate_digest_falls_back_to_ollama_when_mac_generation_raises(fake_llm):
    fake_llm.response_text = "réponse ollama"

    def raising_generate_text(config, prompt):
        raise RuntimeError("boom")

    result = generate_digest(
        "un prompt",
        fallback_llm_client=fake_llm,
        mac_config=_mac_config(),
        wait_for_mac_fn=lambda config: True,
        generate_text_fn=raising_generate_text,
    )

    assert result.response.text == "réponse ollama"
    assert result.voice_path is None


def test_generate_digest_falls_back_to_ollama_when_wait_for_mac_raises(fake_llm):
    # Ex. MAC_ADDRESS mal configurée : mac_wake.send_wol_packet lève ValueError.
    fake_llm.response_text = "réponse ollama"

    def raising_wait_for_mac(config):
        raise ValueError("adresse MAC invalide")

    result = generate_digest(
        "un prompt",
        fallback_llm_client=fake_llm,
        mac_config=_mac_config(),
        wait_for_mac_fn=raising_wait_for_mac,
        generate_text_fn=lambda config, prompt: pytest.fail("ne doit pas être appelé"),
    )

    assert result.response.text == "réponse ollama"
    assert result.voice_path is None


def test_generate_digest_without_mac_config_uses_fallback_directly(fake_llm):
    fake_llm.response_text = "réponse ollama"

    result = generate_digest("un prompt", fallback_llm_client=fake_llm, mac_config=None)

    assert result.response.text == "réponse ollama"
    assert result.voice_path is None


def test_generate_digest_falls_back_to_piper_voice_when_mac_unreachable(fake_llm, tmp_path):
    fake_llm.response_text = "- [Source] phrase."
    voice_path = tmp_path / "voice.ogg"
    speech_texts = []

    def fake_generate_voice_piper(text, output_path, model_path):
        speech_texts.append((text, model_path))
        return output_path

    result = generate_digest(
        "un prompt",
        fallback_llm_client=fake_llm,
        mac_config=_mac_config(),
        voice_output_path=voice_path,
        piper_model_path="/models/fr_FR-siwis-medium.onnx",
        wait_for_mac_fn=lambda config: False,
        generate_voice_piper_fn=fake_generate_voice_piper,
    )

    assert result.voice_path == voice_path
    assert speech_texts == [("Source. phrase.", "/models/fr_FR-siwis-medium.onnx")]


def test_generate_digest_without_piper_model_path_has_no_voice_on_fallback(fake_llm, tmp_path):
    """piper_model_path vide (défaut) = comportement d'origine, texte seul
    en repli — pas de régression pour les déploiements sans Piper configuré."""
    fake_llm.response_text = "réponse ollama"

    result = generate_digest(
        "un prompt",
        fallback_llm_client=fake_llm,
        mac_config=_mac_config(),
        voice_output_path=tmp_path / "voice.ogg",
        wait_for_mac_fn=lambda config: False,
    )

    assert result.voice_path is None
