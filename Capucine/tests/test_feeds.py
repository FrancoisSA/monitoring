from datetime import datetime, timedelta, timezone

from capucine.feeds import fetch_recent_entries

_RSS_TEMPLATE = """<?xml version="1.0"?>
<rss version="2.0"><channel>
<title>{source}</title>
{item}
</channel></rss>"""

_ITEM_TEMPLATE = """<item>
<title>{title}</title>
<link>{link}</link>
<description>{summary}</description>
<pubDate>{pub_date}</pubDate>
</item>"""


def _rfc822(dt: datetime) -> str:
    return dt.strftime("%a, %d %b %Y %H:%M:%S +0000")


def _rss(source: str, *, title: str, link: str, summary: str, pub_date: str) -> bytes:
    item = _ITEM_TEMPLATE.format(title=title, link=link, summary=summary, pub_date=pub_date)
    return _RSS_TEMPLATE.format(source=source, item=item).encode("utf-8")


def test_fetch_recent_entries_keeps_only_entries_within_the_window():
    now = datetime.now(timezone.utc)
    responses = {
        "https://recent.example/feed": _rss(
            "Source récente",
            title="Article récent",
            link="https://example.com/recent",
            summary="résumé récent",
            pub_date=_rfc822(now - timedelta(hours=2)),
        ),
        "https://old.example/feed": _rss(
            "Source ancienne",
            title="Article ancien",
            link="https://example.com/old",
            summary="résumé ancien",
            pub_date=_rfc822(now - timedelta(hours=48)),
        ),
    }

    entries = fetch_recent_entries(
        list(responses.keys()), since_hours=30, fetch=lambda url: responses[url]
    )

    assert [entry.title for entry in entries] == ["Article récent"]
    assert entries[0].source == "Source récente"
    assert entries[0].link == "https://example.com/recent"


def test_fetch_recent_entries_ignores_a_failing_source_without_raising():
    ok_feed = _rss(
        "Source OK",
        title="Article OK",
        link="https://example.com/ok",
        summary="résumé",
        pub_date=_rfc822(datetime.now(timezone.utc)),
    )

    def fetch(url: str) -> bytes:
        if url == "https://broken.example/feed":
            raise ConnectionError("boom")
        return ok_feed

    entries = fetch_recent_entries(
        ["https://broken.example/feed", "https://ok.example/feed"], fetch=fetch
    )

    assert [entry.title for entry in entries] == ["Article OK"]


def test_fetch_recent_entries_ignores_an_unparseable_feed():
    entries = fetch_recent_entries(
        ["https://empty.example/feed"], fetch=lambda url: b"pas du xml"
    )

    assert entries == []


def test_fetch_recent_entries_uses_per_item_source_when_present():
    # Format des agrégateurs (ex. Google News) : élément <source> par article,
    # avec le titre qui répète souvent "... - éditeur" en suffixe.
    feed = (
        b'<?xml version="1.0"?><rss version="2.0"><channel>'
        b"<title>Recherche Google Actualites</title>"
        b"<item>"
        b"<title>Un article - exemple.com</title>"
        b"<link>https://example.com/a</link>"
        b'<source url="https://exemple.com">exemple.com</source>'
        b"<pubDate>" + _rfc822(datetime.now(timezone.utc)).encode() + b"</pubDate>"
        b"</item></channel></rss>"
    )

    entries = fetch_recent_entries(["https://news.example/search"], fetch=lambda url: feed)

    assert entries[0].source == "exemple.com"
    assert entries[0].title == "Un article"  # suffixe "- exemple.com" retiré


def test_fetch_recent_entries_decodes_html_entities_in_the_summary():
    feed = _rss(
        "Source",
        title="Article",
        link="https://example.com/a",
        summary="Un texte&amp;nbsp;avec des entit&amp;eacute;s",
        pub_date=_rfc822(datetime.now(timezone.utc)),
    )

    entries = fetch_recent_entries(["https://feed.example"], fetch=lambda url: feed)

    assert "&amp;" not in entries[0].summary
    assert "&nbsp;" not in entries[0].summary


def test_fetch_recent_entries_strips_html_and_truncates_the_summary():
    huge_html_summary = (
        "<table><tr><td><img src='x.jpg'/>Un texte utile pour la revue</td></tr></table>"
        + "blabla " * 100
    )
    feed = _rss(
        "Source",
        title="Article",
        link="https://example.com/a",
        summary=f"<![CDATA[{huge_html_summary}]]>",
        pub_date=_rfc822(datetime.now(timezone.utc)),
    )

    entries = fetch_recent_entries(["https://feed.example"], fetch=lambda url: feed)

    assert "<" not in entries[0].summary
    assert "img" not in entries[0].summary
    assert len(entries[0].summary) <= 221  # _MAX_SUMMARY_CHARS + l'ellipse
