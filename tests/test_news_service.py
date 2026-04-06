from datetime import datetime, timezone

from services.hyperliquid_service import MarketInfo
from services.news_service import (
    NewsArticle,
    deduplicate_articles,
    parse_ddgs_date,
    similar_titles,
    summarize_text,
)


def test_parse_ddgs_date_handles_iso_timestamp() -> None:
    parsed = parse_ddgs_date("2026-04-06T04:15:02+00:00", now=datetime.now(timezone.utc))

    assert parsed is not None
    assert parsed.year == 2026
    assert parsed.month == 4


def test_parse_ddgs_date_handles_relative_timestamp() -> None:
    now = datetime(2026, 4, 6, 10, 0, tzinfo=timezone.utc)
    parsed = parse_ddgs_date("Opinion 2 hours ago", now=now)

    assert parsed == datetime(2026, 4, 6, 8, 0, tzinfo=timezone.utc)


def test_summarize_text_keeps_output_concise() -> None:
    summary = summarize_text("word " * 100, limit=60)

    assert len(summary) <= 60


def test_similar_titles_detects_near_duplicates() -> None:
    assert similar_titles(
        "Bitcoin jumps as ETF flows return",
        "Bitcoin jumps as ETF inflows return",
    )


def test_deduplicate_articles_removes_duplicate_headlines() -> None:
    market = MarketInfo("BTC", "BTC", "BTC", "perp", "perp", ("btc",))
    articles = [
        NewsArticle(
            "Bitcoin jumps as ETF flows return",
            "Reuters",
            datetime.now(timezone.utc),
            "Summary A",
            "https://example.com/a",
            "crypto",
            market,
        ),
        NewsArticle(
            "Bitcoin jumps as ETF inflows return",
            "Bloomberg",
            datetime.now(timezone.utc),
            "Summary B",
            "https://example.com/b",
            "crypto",
            market,
        ),
    ]

    deduped = deduplicate_articles(articles)

    assert len(deduped) == 1
