import pytest

from capucine.llm.ollama_client import OllamaClient


def test_generate_returns_the_model_response_text():
    def fake_post(url, payload):
        assert url == "http://fake-host/api/generate"
        assert payload["model"] == "qwen2.5:3b"
        assert payload["prompt"] == "dis bonjour"
        return {"response": "bonjour !"}

    client = OllamaClient(model="qwen2.5:3b", host="http://fake-host", post=fake_post)

    response = client.generate("dis bonjour")

    assert response.text == "bonjour !"
    assert response.model == "qwen2.5:3b"
    assert response.latency_ms >= 0


def test_generate_raises_on_empty_response():
    client = OllamaClient(post=lambda url, payload: {"response": ""})

    with pytest.raises(RuntimeError, match="Réponse vide"):
        client.generate("dis bonjour")


def test_default_post_uses_the_configured_timeout(monkeypatch):
    captured_kwargs = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"response": "ok"}

    def fake_requests_post(url, json, timeout):
        captured_kwargs["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(
        "capucine.llm.ollama_client.requests.post", fake_requests_post
    )

    # Pas de `post` fourni explicitement : on utilise le transport par défaut,
    # qui doit respecter le timeout configuré sur le client (cold start Ollama
    # mesuré à ~14s sur le Pi, 30s était trop juste).
    client = OllamaClient(timeout=60)
    client.generate("dis bonjour")

    assert captured_kwargs["timeout"] == 60
