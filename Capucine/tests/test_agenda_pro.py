from capucine.agenda_pro import detect_cancellation, parse_agenda_pro_blocks

_SINGLE_BLOCK_EMAIL = """
Bonjour,

EVENT_UID:abc-123
SUBJECT:Réunion budget
STARTTIME:2025-06-10T12:00:00
ENDTIME:2025-06-10T13:00:00
Join: https://meet.example.com/abc

Merci.
"""

_MULTI_BLOCK_EMAIL = """
EVENT_UID:uid-1
SUBJECT:Point équipe
STARTTIME:2025-06-10T09:00:00
ENDTIME:2025-06-10T09:30:00

EVENT_UID:uid-2
SUBJECT:Revue de code
STARTTIME:2025-06-10T15:00:00
ENDTIME:2025-06-10T16:00:00
Join: https://meet.example.com/xyz
"""

_INCOMPLETE_BLOCK_EMAIL = """
EVENT_UID:uid-missing-fields
SUBJECT:Réunion sans horaire
"""


def test_parse_single_block():
    blocks = parse_agenda_pro_blocks(_SINGLE_BLOCK_EMAIL)

    assert len(blocks) == 1
    block = blocks[0]
    assert block.event_uid == "abc-123"
    assert block.subject == "Réunion budget"
    assert block.raw_start == "2025-06-10T12:00:00"
    assert block.raw_end == "2025-06-10T13:00:00"
    assert block.location == "https://meet.example.com/abc"


def test_parse_multiple_blocks():
    blocks = parse_agenda_pro_blocks(_MULTI_BLOCK_EMAIL)

    assert [b.event_uid for b in blocks] == ["uid-1", "uid-2"]
    assert blocks[0].location == ""
    assert blocks[1].location == "https://meet.example.com/xyz"


def test_incomplete_block_is_ignored():
    blocks = parse_agenda_pro_blocks(_INCOMPLETE_BLOCK_EMAIL)

    assert blocks == []


def test_no_event_uid_returns_empty_list():
    assert parse_agenda_pro_blocks("Un email sans rapport avec AGENDA PRO.") == []


def test_detect_cancellation_recognizes_all_known_prefixes():
    for prefix, subject in [
        ("declined:", "Declined: Réunion budget"),
        ("annulé:", "[AMPERE] Annulé: Point équipe"),
        ("annule:", "Annule: Revue de code"),
        ("cancelled:", "Cancelled: Point équipe"),
        ("canceled:", "Canceled: Point équipe"),
    ]:
        clean = detect_cancellation(subject)
        assert clean is not None, f"préfixe {prefix!r} non détecté dans {subject!r}"
        assert "declined" not in clean.lower()
        assert "annul" not in clean.lower()
        assert "cancel" not in clean.lower()


def test_detect_cancellation_returns_none_for_normal_subject():
    assert detect_cancellation("Réunion budget") is None
