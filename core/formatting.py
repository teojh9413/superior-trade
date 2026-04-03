from __future__ import annotations

from collections.abc import Iterable

from services.llm_service import AskResult, TradeStrategy
from services.news_service import DailyBrief
from services.pair_mapper import PairMappingResult


def format_ask_response(question: str, result: AskResult) -> str:
    lines = [
        "⚙️ **Superior Ask**",
        f"Question: {question}",
        result.answer,
    ]
    if result.sources:
        lines.append("🧪 Sources: " + "; ".join(result.sources[:5]))
    if result.used_web:
        lines.append("🌍 Included official site or GitHub snippets where useful.")
    if result.used_fallback:
        lines.append("⚠️ Fallback mode was used for part of this answer.")
    return "\n".join(lines)


def format_trade_response(asset_or_market: str, mapping: PairMappingResult, strategy: TradeStrategy) -> str:
    if not mapping.found:
        return (
            "⚠️ **Superior Trade**\n"
            f"Request: {asset_or_market}\n"
            "No verified Hyperliquid mapping is available in the curated rules, so I won't invent a pair."
        )

    lines = [
        "🎯 **Superior Trade**",
        f"Objective: {strategy.objective}",
        f"Pair: `{strategy.pair}`",
        f"Timeframe: `{strategy.timeframe}`",
        f"Direction: `{strategy.direction}`",
        f"Entry Logic: {strategy.entry_logic}",
        f"Exit Logic: {strategy.exit_logic}",
        f"Risk Management: {strategy.risk_management}",
        f"Backtest Reminder: {strategy.backtest_reminder}",
        f"⚙️ Mapping: {mapping.explanation}",
    ]
    if strategy.used_fallback:
        lines.append("⚠️ LLM fallback mode was used for this strategy draft.")
    return "\n".join(lines)


def format_daily_brief(brief: DailyBrief) -> str:
    lines = [
        "🗞️ **Superior Daily Market Brief**",
        f"⚙️ Generated: {brief.generated_at}",
    ]

    category_emoji = {"crypto": "₿", "macro": "🌍"}
    for item in brief.items[:3]:
        emoji = category_emoji.get(item.category, "🪙")
        lines.extend(
            [
                "",
                f"{emoji} **{item.headline}**",
                f"Source: {item.source_name}",
                f"Why it matters: {item.why_it_matters}",
                f"Pair: `{item.pair}`",
                f"Signal: {direction_emoji(item.direction)} `{item.direction}`",
            ]
        )
        if item.strategy_prompt:
            lines.append(f"Strategy Prompt: {item.strategy_prompt}")
        lines.append(f"Link: {item.url}")

    if brief.used_fallback:
        lines.append("")
        lines.append("⚠️ Some brief components used fallback logic because live providers were unavailable or returned weak results.")
    return "\n".join(lines)


def format_health_status(
    knowledge_sources: Iterable[str],
    scheduler_description: str,
    dry_run: bool,
    llm_configured: bool = False,
    news_configured: bool = False,
    heading: str = "🧪 Health",
) -> str:
    files = ", ".join(sorted(knowledge_sources)) or "none"
    lines = [
        heading,
        f"Knowledge: {files}",
        f"Scheduler: {scheduler_description}",
        f"Dry Run: {'on' if dry_run else 'off'}",
        f"LLM: {'configured' if llm_configured else 'not configured'}",
        f"News API: {'configured' if news_configured else 'not configured'}",
    ]
    return "\n".join(lines)


def direction_emoji(direction: str) -> str:
    if direction == "LONG":
        return "📈"
    if direction == "SHORT":
        return "📉"
    return "⚪"
