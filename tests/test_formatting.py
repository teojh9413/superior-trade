from datetime import datetime, timezone

from services.formatter import (
    format_daily_brief,
    format_health_status,
    format_trade_asset_not_found,
    format_trade_response,
)
from services.hyperliquid_service import MarketInfo
from services.news_service import DailyBrief, NewsArticle
from services.prompt_service import TradeStrategy


def test_format_daily_brief_matches_new_scope() -> None:
    market_btc = MarketInfo("BTC", "BTC", "BTC", "perp", "perp", ("btc",))
    market_eth = MarketInfo("ETH", "ETH", "ETH", "perp", "perp", ("eth",))
    market_tsla = MarketInfo("xyz:TSLA", "XYZ-TSLA", "TSLA", "perp", "perp", ("tsla",))
    brief = DailyBrief(
        generated_at_label="06 Apr 2026, GMT+8",
        items=[
            NewsArticle("Headline 1", "Reuters", datetime.now(timezone.utc), "Summary 1", "https://a", "crypto", market_btc),
            NewsArticle("Headline 2", "Bloomberg", datetime.now(timezone.utc), "Summary 2", "https://b", "crypto", market_eth),
            NewsArticle("Headline 3", "CNBC", datetime.now(timezone.utc), "Summary 3", "https://c", "tradfi", market_tsla),
        ],
        prompts=[
            "Long BTC on 15min when price breaks above the prior 4h range high with rising volume",
            "Short ETH on 1h when price closes below the 20 EMA with rising volume",
            "Long XYZ-TSLA on 30min when price reclaims VWAP and the prior session high",
        ],
    )

    output = format_daily_brief(brief)

    assert output.startswith("🗞️ Superior.Trade Daily Market Brief")
    assert "Trading strategy prompts to capitalize:" in output
    assert "₿ Headline 1" in output
    assert "🪙 Headline 2" in output
    assert "🌍 Headline 3" in output
    assert "1. Long BTC" in output


def test_format_trade_response_starts_with_required_line() -> None:
    strategy = TradeStrategy(
        asset="BTC",
        suggested_bias="Long",
        objective="Capture a clean long continuation setup in BTC.",
        ticker="BTC",
        timeframe="15min",
        direction="Long",
        entry_logic="Wait for a close above resistance.",
        exit_logic="Exit on failed retest.",
        risk_management="Keep risk fixed.",
        backtest_reminder="Backtest before deployment.",
    )

    output = format_trade_response(strategy)

    assert output.splitlines()[0] == "Try this strategy in Superior.Trade"
    assert "Asset: BTC" in output
    assert "Ticker: BTC" in output
    assert "Mapped pair" not in output


def test_format_health_status_is_simple() -> None:
    output = format_health_status(
        scheduler_description="15:00 Asia/Singapore",
        dry_run=False,
        market_count=321,
    )

    assert "Scheduler: 15:00 Asia/Singapore" in output
    assert "Known Markets: 321" in output


def test_format_trade_asset_not_found_is_clear() -> None:
    output = format_trade_asset_not_found("mysteryasset")

    assert "No official Hyperliquid market currently exists" in output
