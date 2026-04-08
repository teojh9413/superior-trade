from __future__ import annotations

from services.backtest_service import BacktestStats
from services.news_service import DailyBrief
from services.prompt_service import TradeStrategy


def format_health_status(
    *,
    scheduler_description: str,
    dry_run: bool,
    market_count: int,
    superior_api_configured: bool,
) -> str:
    return "\n".join(
        [
            "⚙️ Health",
            f"Scheduler: {scheduler_description}",
            f"Dry Run: {'on' if dry_run else 'off'}",
            f"Known Markets: {market_count}",
            f"Superior API: {'configured' if superior_api_configured else 'not configured'}",
        ]
    )


def format_daily_brief(brief: DailyBrief) -> str:
    lines = [f"🗞️ Superior.Trade Daily Market Brief — {brief.generated_at_label}"]
    emoji_by_category = ["₿", "🪙", "🌍"]

    for emoji, item in zip(emoji_by_category, brief.items):
        lines.extend(
            [
                "",
                f"{emoji} {item.title}",
                item.summary,
            ]
        )

    lines.append("")
    lines.append("Trading strategy prompts to capitalize:")
    for index, prompt in enumerate(brief.prompts, start=1):
        lines.append(f"{index}. {prompt}")
    return "\n".join(lines)


def format_trade_response(strategy: TradeStrategy) -> str:
    return "\n".join(
        [
            "Try this strategy in Superior.Trade",
            "",
            f"Asset: {strategy.asset}",
            f"Suggested bias: {strategy.suggested_bias}",
            "Strategy:",
            f"Objective: {strategy.objective}",
            f"Ticker: {strategy.ticker}",
            f"Timeframe: {strategy.timeframe}",
            f"Direction: {strategy.direction}",
            f"Entry logic: {strategy.entry_logic}",
            f"Exit logic: {strategy.exit_logic}",
            f"Risk management: {strategy.risk_management}",
            f"Backtest reminder: {strategy.backtest_reminder}",
        ]
    )


def format_trade_asset_not_found(asset_name: str) -> str:
    return f"No official Hyperliquid market currently exists for `{asset_name}`."


def format_backtest_success(stats: BacktestStats) -> str:
    return "\n".join(
        [
            f"You would have made {stats.total_profit_percent:.2f}% using {stats.strategy_name} on {stats.ticker} over the last 24 hours.",
            "",
            "Backtest statistics:",
            f"- Strategy: {stats.strategy_name}",
            f"- Ticker: {stats.ticker}",
            "- Timeframe: 15m",
            f"- Total trades: {stats.total_trades}",
            f"- Win rate: {stats.win_rate_percent:.2f}%",
            f"- Total profit: {stats.total_profit_percent:.2f}%",
            f"- Max drawdown: {stats.max_drawdown_percent:.2f}%",
            f"- Sharpe ratio: {stats.sharpe_ratio:.2f}",
            f"- Average trade duration: {stats.average_trade_duration}",
            "",
            "Backtested on Superior.Trade using the last 24 hours of 15-minute candles.",
        ]
    )


def format_backtest_failure(message: str) -> str:
    return message
