from core.formatting import (
    direction_emoji,
    format_ask_response,
    format_daily_brief,
    format_health_status,
    format_trade_response,
)
from services.llm_service import AskResult, TradeStrategy
from services.news_service import DailyBrief, DailyBriefItem
from services.pair_mapper import PairMappingResult


def test_format_ask_response_includes_sources_and_fallback_note() -> None:
    result = AskResult(
        answer="Users do not need their own Hyperliquid wallet.",
        confidence="medium",
        sources=["SKILL.md -> Wallet Architecture"],
        used_web=False,
        used_fallback=True,
    )

    output = format_ask_response("Do users need a wallet?", result)

    assert "Superior Ask" in output
    assert "SKILL.md -> Wallet Architecture" in output
    assert "Fallback mode" in output


def test_format_trade_response_includes_required_strategy_fields() -> None:
    mapping = PairMappingResult(
        requested="gold",
        found=True,
        pair="XYZ-GOLD/USDC:USDC",
        market_type="HIP3 perp",
        explanation="Mapped from the curated HIP3 list.",
    )
    strategy = TradeStrategy(
        objective="Trade gold using a practical momentum-retest plan.",
        pair="XYZ-GOLD/USDC:USDC",
        timeframe="15m",
        direction="LONG",
        entry_logic="Wait for a breakout and controlled retest.",
        exit_logic="Exit on failed retest or target hit.",
        risk_management="Use isolated risk and pre-defined stop distance.",
        backtest_reminder="Backtest on recent data before deployment.",
        used_fallback=False,
    )

    output = format_trade_response("gold", mapping, strategy)

    assert "Objective:" in output
    assert "Pair: `XYZ-GOLD/USDC:USDC`" in output
    assert "Direction: `LONG`" in output
    assert "Risk Management:" in output


def test_format_daily_brief_outputs_three_slots() -> None:
    brief = DailyBrief(
        generated_at="2026-04-03 09:15 UTC",
        items=[
            DailyBriefItem(
                category="crypto",
                headline="BTC headline",
                source_name="Reuters",
                url="https://example.com/btc",
                why_it_matters="BTC matters.",
                pair="BTC/USDC:USDC",
                direction="LONG",
                strategy_prompt="Trade BTC.",
            ),
            DailyBriefItem(
                category="crypto",
                headline="ETH headline",
                source_name="Bloomberg",
                url="https://example.com/eth",
                why_it_matters="ETH matters.",
                pair="ETH/USDC:USDC",
                direction="SHORT",
                strategy_prompt="Trade ETH.",
            ),
            DailyBriefItem(
                category="macro",
                headline="Macro headline",
                source_name="FT",
                url="https://example.com/macro",
                why_it_matters="Macro matters.",
                pair="XYZ-SP500/USDC:USDC",
                direction="NO CLEAR EDGE",
                strategy_prompt=None,
            ),
        ],
        used_fallback=False,
    )

    output = format_daily_brief(brief)

    assert output.count("Source: ") == 3
    assert "BTC headline" in output
    assert "ETH headline" in output
    assert "Macro headline" in output


def test_format_health_status_shows_provider_flags() -> None:
    output = format_health_status(
        knowledge_sources=["FAQ.md", "SKILL.md"],
        scheduler_description="15:00 Asia/Singapore",
        dry_run=True,
        llm_configured=True,
        news_configured=False,
    )

    assert "Knowledge: FAQ.md, SKILL.md" in output
    assert "LLM: configured" in output
    assert "News API: not configured" in output


def test_direction_emoji_covers_all_signal_types() -> None:
    assert direction_emoji("LONG")
    assert direction_emoji("SHORT")
    assert direction_emoji("NO CLEAR EDGE")
