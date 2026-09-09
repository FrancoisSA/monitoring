from capucine.store import Store


def test_save_and_get_history_round_trip(tmp_path):
    store = Store(tmp_path / "test.db")

    store.save_history("synthese", "user", "un texte")
    store.save_history("synthese", "assistant", "un résumé")

    history = store.get_history("synthese")

    assert history == [("user", "un texte"), ("assistant", "un résumé")]


def test_get_history_is_scoped_per_agent(tmp_path):
    store = Store(tmp_path / "test.db")

    store.save_history("synthese", "user", "message synthese")
    store.save_history("planning", "user", "message planning")

    assert store.get_history("synthese") == [("user", "message synthese")]


def test_get_history_respects_limit_and_order(tmp_path):
    store = Store(tmp_path / "test.db")

    for i in range(5):
        store.save_history("synthese", "user", f"message {i}")

    history = store.get_history("synthese", limit=2)

    # Les 2 derniers messages, dans l'ordre chronologique (pas l'inverse)
    assert history == [("user", "message 3"), ("user", "message 4")]


def test_has_seen_is_false_for_an_unknown_link(tmp_path):
    store = Store(tmp_path / "test.db")

    assert store.has_seen("renault", "https://example.com/article") is False


def test_mark_seen_makes_has_seen_true(tmp_path):
    store = Store(tmp_path / "test.db")

    store.mark_seen("renault", "https://example.com/article")

    assert store.has_seen("renault", "https://example.com/article") is True


def test_seen_links_are_scoped_per_agent(tmp_path):
    store = Store(tmp_path / "test.db")

    store.mark_seen("renault", "https://example.com/article")

    assert store.has_seen("autre-agent", "https://example.com/article") is False


def test_mark_seen_twice_does_not_raise(tmp_path):
    store = Store(tmp_path / "test.db")

    store.mark_seen("renault", "https://example.com/article")
    store.mark_seen("renault", "https://example.com/article")  # ne doit pas lever d'erreur

    assert store.has_seen("renault", "https://example.com/article") is True
