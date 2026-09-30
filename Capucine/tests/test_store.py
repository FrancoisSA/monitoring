from capucine.store import Store, normalize_title


def test_normalize_title_ignores_case_accents_spacing_and_trailing_punctuation():
    assert normalize_title("Apéro Guillaume") == normalize_title("apéro  guillaume.")


def test_normalize_title_still_distinguishes_different_titles():
    assert normalize_title("Apéro G") != normalize_title("apéro guillaume")


def test_weekend_note_round_trip(tmp_path):
    store = Store(tmp_path / "test.db")

    store.set_weekend_note("2025-06-14", "Randonnée")

    assert store.get_all_weekend_notes() == {"2025-06-14": "Randonnée"}


def test_agenda_pro_event_id_is_none_for_a_reservation_in_progress(tmp_path):
    store = Store(tmp_path / "test.db")

    store.reserve_agenda_pro_event("uid-1", "Ampere", title="Point équipe", start_time="2025-06-10T09:00:00")

    assert store.get_agenda_pro_event_id("uid-1") is None


def test_save_agenda_pro_event_id_makes_it_retrievable(tmp_path):
    store = Store(tmp_path / "test.db")

    store.save_agenda_pro_event_id("uid-1", "gcal-1", "Ampere", title="Point équipe", start_time="2025-06-10T09:00:00")

    assert store.get_agenda_pro_event_id("uid-1") == "gcal-1"


def test_find_agenda_pro_event_by_title_and_start_ignores_reservations(tmp_path):
    store = Store(tmp_path / "test.db")
    store.reserve_agenda_pro_event("uid-1", "Ampere", title="Point équipe", start_time="2025-06-10T09:00:00")

    assert store.find_agenda_pro_event_by_title_and_start("Point équipe", "2025-06-10T09:00:00") is None


def test_find_agenda_pro_event_by_title_and_start_matches_normalized_title(tmp_path):
    store = Store(tmp_path / "test.db")
    store.save_agenda_pro_event_id("uid-1", "gcal-1", "Ampere", title="Point Équipe", start_time="2025-06-10T09:00:00")

    match = store.find_agenda_pro_event_by_title_and_start("point  équipe.", "2025-06-10T09:00:00")

    assert match == ("uid-1", "gcal-1")


def test_cleanup_duplicate_agenda_pro_entries_keeps_only_the_given_uid(tmp_path):
    store = Store(tmp_path / "test.db")
    store.save_agenda_pro_event_id("uid-old", "gcal-old", "Ampere", title="Point équipe", start_time="2025-06-10T09:00:00")
    store.save_agenda_pro_event_id("uid-new", "gcal-new", "Ampere", title="Point équipe", start_time="2025-06-10T09:00:00")

    deleted = store.cleanup_duplicate_agenda_pro_entries("Point équipe", "2025-06-10T09:00:00", keep_uid="uid-new")

    assert deleted == 1
    assert store.get_agenda_pro_event_id("uid-old") is None
    assert store.get_agenda_pro_event_id("uid-new") == "gcal-new"


def test_agenda_pro_processed_email_round_trip(tmp_path):
    store = Store(tmp_path / "test.db")

    assert store.is_agenda_pro_email_processed("email-1") is False
    store.mark_agenda_pro_email_processed("email-1")
    assert store.is_agenda_pro_email_processed("email-1") is True


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
