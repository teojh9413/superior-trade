from __future__ import annotations

from dataclasses import dataclass

from core.config import AppConfig
from services.hyperliquid_service import MarketInfo


@dataclass(frozen=True, slots=True)
class TradeStrategy:
    asset: str
    suggested_bias: str
    objective: str
    ticker: str
    timeframe: str
    direction: str
    entry_logic: str
    exit_logic: str
    risk_management: str
    backtest_reminder: str


class PromptService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.brief_style = self._load_prompt("daily_news_prompt.txt")
        self.trade_style = self._load_prompt("trade_mode_prompt.txt")

    def build_brief_prompt(self, market: MarketInfo, headline: str, summary: str) -> str:
        direction = infer_direction(headline=headline, summary=summary, ticker=market.ticker)
        timeframe = select_timeframe(market.ticker)
        trigger = select_entry_condition(direction=direction, ticker=market.ticker)
        return f"{direction} {market.ticker} on {timeframe} when {trigger}"

    def build_trade_strategy(self, market: MarketInfo) -> TradeStrategy:
        direction = infer_direction(headline="", summary="", ticker=market.ticker)
        timeframe = select_timeframe(market.ticker)
        return TradeStrategy(
            asset=market.ticker,
            suggested_bias=direction.title(),
            objective=f"Capture a clean {direction.lower()} continuation setup in {market.ticker} without chasing weak price action.",
            ticker=market.ticker,
            timeframe=timeframe,
            direction=direction,
            entry_logic=build_trade_entry(direction=direction, ticker=market.ticker, timeframe=timeframe),
            exit_logic="Take partial profits into the first strong extension, trail the remainder behind structure, and exit fully if price closes back through the trigger zone.",
            risk_management="Risk a fixed small amount per trade, avoid oversized entries after extended candles, and skip the setup if volume confirmation is missing.",
            backtest_reminder="Backtest this ticker on recent Hyperliquid data in Superior.Trade before deploying live.",
        )

    def _load_prompt(self, filename: str) -> str:
        path = self.config.prompts_dir / filename
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8").strip()


def infer_direction(*, headline: str, summary: str, ticker: str) -> str:
    text = f"{headline} {summary}".lower()
    short_markers = ("falls", "slides", "misses", "cuts", "warns", "lawsuit", "probe", "crackdown", "tariff")
    long_markers = ("surges", "rises", "beats", "approval", "launch", "rebound", "gains", "inflows")
    if any(marker in text for marker in short_markers):
        return "Short"
    if any(marker in text for marker in long_markers):
        return "Long"
    if ticker.startswith("VIX") or ticker.endswith("DXY"):
        return "Long"
    return "Long"


def select_timeframe(ticker: str) -> str:
    if ticker in {"BTC", "ETH", "SOL"}:
        return "15min"
    if ticker.startswith(("XYZ-", "KM-", "FLX-", "CASH-", "VNTL-", "HYNA-")):
        return "30min"
    return "1h"


def select_entry_condition(*, direction: str, ticker: str) -> str:
    if direction == "Short":
        return "price closes below the 20 EMA with volume expanding above the recent average"
    if ticker in {"BTC", "ETH", "SOL"}:
        return "price breaks above the prior 4h range high with rising volume"
    if ticker.endswith(("GOLD", "SILVER", "BRENTOIL", "CL", "NATGAS")):
        return "price reclaims VWAP and confirms above the prior intraday swing high"
    return "price reclaims VWAP and the prior session high"


def build_trade_entry(*, direction: str, ticker: str, timeframe: str) -> str:
    if direction == "Short":
        return (
            f"Wait for a {timeframe} candle close below the 20 EMA and the nearest support shelf in {ticker}, "
            "then enter on the first failed retest with volume still above the recent average."
        )
    return (
        f"Wait for a {timeframe} candle close above the nearest breakout level in {ticker}, "
        "then enter on the first shallow retest that holds above VWAP with volume confirmation."
    )
