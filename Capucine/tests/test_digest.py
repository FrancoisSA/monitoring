from datetime import datetime, timedelta, timezone

from capucine.digest import MAX_ENTRIES_FOR_PROMPT, build_prompt, format_for_telegram
from capucine.feeds import FeedEntry


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
