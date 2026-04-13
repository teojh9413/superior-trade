from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

import aiohttp

from core.config import AppConfig
from services.hyperliquid_service import MarketInfo

LOGGER = logging.getLogger(__name__)


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


@dataclass(frozen=True, slots=True)
class BriefContent:
    summary: str
    prompt: str


class PromptService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.brief_style = self._load_prompt("daily_news_prompt.txt")
        self.trade_style = self._load_prompt("trade_mode_prompt.txt")

    def is_configured(self) -> bool:
        return bool(self.config.deepseek_api_key and self.config.deepseek_model and self.config.deepseek_base_url)

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

    async def generate_trade_strategy(self, market: MarketInfo) -> TradeStrategy:
        fallback = self.build_trade_strategy(market)
        if not self.is_configured():
            return fallback

        user_prompt = f"""
Official ticker: {market.ticker}
Market type: {market.market_type}
Official pair: {market.pair}

Return strict JSON with keys:
- objective
- timeframe
- direction
- entry_logic
- exit_logic
- risk_management
- backtest_reminder
""".strip()
        payload = await self._chat_json(mode="trade", user_prompt=user_prompt)
        if not payload:
            return fallback

        direction = normalize_direction(str(payload.get("direction") or fallback.direction))
        return TradeStrategy(
            asset=market.ticker,
            suggested_bias=direction,
            objective=clean_sentence(str(payload.get("objective") or fallback.objective), limit=220),
            ticker=market.ticker,
            timeframe=clean_timeframe(str(payload.get("timeframe") or fallback.timeframe), fallback.timeframe),
            direction=direction,
            entry_logic=clean_sentence(str(payload.get("entry_logic") or fallback.entry_logic), limit=320),
            exit_logic=clean_sentence(str(payload.get("exit_logic") or fallback.exit_logic), limit=320),
            risk_management=clean_sentence(str(payload.get("risk_management") or fallback.risk_management), limit=320),
            backtest_reminder=clean_sentence(str(payload.get("backtest_reminder") or fallback.backtest_reminder), limit=220),
        )

    async def generate_brief_content(self, market: MarketInfo, headline: str, raw_summary: str) -> BriefContent:
        fallback_summary = compact_text(raw_summary, limit=170)
        fallback_prompt = self.build_brief_prompt(market, headline, raw_summary)
        if not self.is_configured():
            return BriefContent(summary=fallback_summary, prompt=fallback_prompt)

        user_prompt = f"""
Official ticker: {market.ticker}
Headline: {headline}
Article text: {raw_summary}

Return strict JSON with keys:
- summary
- prompt
""".strip()
        payload = await self._chat_json(mode="news", user_prompt=user_prompt)
        if not payload:
            return BriefContent(summary=fallback_summary, prompt=fallback_prompt)

        summary = clean_sentence(str(payload.get("summary") or fallback_summary), limit=170)
        prompt = clean_prompt(str(payload.get("prompt") or fallback_prompt), market=market, fallback=fallback_prompt)
        return BriefContent(summary=summary, prompt=prompt)

    def _load_prompt(self, filename: str) -> str:
        path = self.config.prompts_dir / filename
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8").strip()

    async def _chat_json(self, *, mode: str, user_prompt: str) -> dict[str, object] | None:
        body = {
            "model": self.config.deepseek_model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": self._system_prompt_for(mode)},
                {"role": "user", "content": user_prompt},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.config.deepseek_api_key}",
            "Content-Type": "application/json",
        }
        endpoint = build_chat_completions_url(self.config.deepseek_base_url)

        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.config.deepseek_timeout_seconds)
            ) as session:
                async with session.post(endpoint, headers=headers, json=body) as response:
                    text = await response.text()
                    if response.status >= 400:
                        LOGGER.warning("DeepSeek request failed with status %s: %s", response.status, text[:400])
                        return None
        except aiohttp.ClientError:
            LOGGER.exception("DeepSeek request failed before completion.")
            return None

        try:
            payload = json.loads(text)
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            LOGGER.warning("DeepSeek response did not match expected chat completion shape.")
            return None
        return extract_json_object(content)

    def _system_prompt_for(self, mode: str) -> str:
        if mode == "trade":
            return self.trade_style
        return self.brief_style


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


def build_chat_completions_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    if normalized.endswith("/v1"):
        return f"{normalized}/chat/completions"
    return f"{normalized}/chat/completions"


def extract_json_object(content: str) -> dict[str, object] | None:
    stripped = content.strip()
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, re.DOTALL)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return parsed if isinstance(parsed, dict) else None


def clean_sentence(text: str, limit: int) -> str:
    compact = compact_text(text, limit=limit)
    return compact.rstrip(" .") + "."


def compact_text(text: str, limit: int) -> str:
    compact = re.sub(r"\s+", " ", text).strip().strip('"')
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def clean_timeframe(value: str, fallback: str) -> str:
    compact = re.sub(r"\s+", "", value)
    return compact if compact else fallback


def normalize_direction(value: str) -> str:
    upper = value.strip().upper()
    if upper.startswith("SHORT"):
        return "Short"
    return "Long"


def clean_prompt(text: str, *, market: MarketInfo, fallback: str) -> str:
    compact = compact_text(text, limit=170)
    if market.ticker not in compact:
        return fallback
    if "when " not in compact.lower():
        return fallback
    return compact
