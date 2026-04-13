from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher

import aiohttp

from core.config import AppConfig

LOGGER = logging.getLogger(__name__)

SIMPLE_ASSET_RE = re.compile(r"^[A-Za-z0-9._-]{1,20}$")
RAW_NAME_RE = re.compile(r"^(?P<prefix>[a-z0-9]+):(?P<symbol>[A-Za-z0-9]+)$")
PERP_PREFIX_PRIORITY = {"": 0, "xyz": 1, "km": 2, "flx": 3, "cash": 4, "vntl": 5, "hyna": 6}
PERP_QUOTE_BY_PREFIX = {
    "": ("USDC", "USDC"),
    "xyz": ("USDC", "USDC"),
    "cash": ("USDT0", "USDT0"),
    "flx": ("USDH", "USDH"),
    "km": ("USDH", "USDH"),
    "hyna": ("USDE", "USDE"),
    "vntl": ("USDH", "USDH"),
}
ALIAS_MAP = {
    "bitcoin": "btc",
    "xrp": "xrp",
    "ripple": "xrp",
    "doge": "doge",
    "dogecoin": "doge",
    "ethereum": "eth",
    "ether": "eth",
    "solana": "sol",
    "tesla": "tsla",
    "apple": "aapl",
    "amazon": "amzn",
    "google": "googl",
    "alphabet": "googl",
    "nvidia": "nvda",
    "microsoft": "msft",
    "meta": "meta",
    "coinbase": "coin",
    "gold": "gold",
    "silver": "silver",
    "oil": "brentoil",
    "brent": "brentoil",
    "crude": "cl",
    "wti": "cl",
    "naturalgas": "natgas",
    "natural-gas": "natgas",
    "gas": "natgas",
    "sp500": "sp500",
    "s&p500": "sp500",
    "stocks": "sp500",
    "equities": "sp500",
    "dollar": "dxy",
    "vix": "vix",
}


@dataclass(frozen=True, slots=True)
class MarketInfo:
    raw_name: str
    ticker: str
    pair: str
    symbol: str
    market_type: str
    source_group: str
    margin_mode: str | None
    searchable_keys: tuple[str, ...]


class HyperliquidService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._markets_cache: list[MarketInfo] = []
        self._markets_cache_time: datetime | None = None
        self._mids_cache: dict[str, str] = {}
        self._mids_cache_time: datetime | None = None

    async def resolve_asset(self, asset_name: str) -> MarketInfo | None:
        markets = await self._get_markets()
        normalized = normalize_asset_request(asset_name)
        normalized = ALIAS_MAP.get(normalized, normalized)

        exact = [market for market in markets if normalized in market.searchable_keys]
        if exact:
            return sort_market_candidates(exact)[0]

        fuzzy = [
            market
            for market in markets
            if any(
                normalized in key or similarity(normalized, key) >= 0.88
                for key in market.searchable_keys
            )
        ]
        if fuzzy:
            return sort_market_candidates(fuzzy)[0]
        return None

    async def infer_market_from_text(self, text: str, category: str) -> MarketInfo | None:
        lower = text.lower()
        keyword_order = [
            "bitcoin",
            "btc",
            "ethereum",
            "ether",
            "eth",
            "xrp",
            "ripple",
            "doge",
            "dogecoin",
            "solana",
            "sol",
            "crypto",
            "stablecoin",
            "token",
            "tesla",
            "nvidia",
            "apple",
            "amazon",
            "google",
            "alphabet",
            "microsoft",
            "meta",
            "coinbase",
            "gold",
            "silver",
            "oil",
            "brent",
            "crude",
            "natural gas",
            "dollar",
            "vix",
            "s&p 500",
            "sp500",
            "stocks",
            "equities",
        ]
        for keyword in keyword_order:
            if keyword in lower:
                resolved = await self.resolve_asset(keyword.replace(" ", ""))
                if resolved is not None:
                    return resolved

        if category == "crypto" and any(
            term in lower
            for term in (
                "crypto",
                "bitcoin",
                "ethereum",
                "ether",
                "eth",
                "solana",
                "sol",
                "xrp",
                "ripple",
                "doge",
                "dogecoin",
                "stablecoin",
                "token",
            )
        ):
            return await self.resolve_asset("btc")
        if any(term in lower for term in ("stock market", "equities", "stocks", "s&p 500", "sp500")):
            return await self.resolve_asset("sp500")
        return None

    async def market_count(self) -> int:
        return len(await self._get_markets())

    async def get_mid_price(self, ticker: str) -> float | None:
        mids = await self._get_mids()
        raw = mids.get(ticker)
        if raw is None:
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    async def _get_markets(self) -> list[MarketInfo]:
        now = datetime.now(timezone.utc)
        if self._markets_cache and self._markets_cache_time and now - self._markets_cache_time < timedelta(minutes=10):
            return self._markets_cache

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
            perp_payload, spot_payload = await fetch_market_payloads(
                session=session,
                info_url=self.config.hyperliquid_info_url,
            )

        markets = build_market_catalog(perp_payload=perp_payload, spot_payload=spot_payload)
        self._markets_cache = markets
        self._markets_cache_time = now
        LOGGER.info("Loaded %s official Hyperliquid markets.", len(markets))
        return markets

    async def _get_mids(self) -> dict[str, str]:
        now = datetime.now(timezone.utc)
        if self._mids_cache and self._mids_cache_time and now - self._mids_cache_time < timedelta(seconds=30):
            return self._mids_cache

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
            async with session.post(self.config.hyperliquid_info_url, json={"type": "allMids"}) as response:
                response.raise_for_status()
                payload = await response.json()

        mids = payload if isinstance(payload, dict) else {}
        self._mids_cache = mids
        self._mids_cache_time = now
        return mids


async def fetch_market_payloads(*, session: aiohttp.ClientSession, info_url: str) -> tuple[list[dict], dict]:
    perp_task = session.post(info_url, json={"type": "allPerpMetas"})
    spot_task = session.post(info_url, json={"type": "spotMeta"})
    async with perp_task as perp_response, spot_task as spot_response:
        perp_response.raise_for_status()
        spot_response.raise_for_status()
        perp_payload = await perp_response.json()
        spot_payload = await spot_response.json()
    return perp_payload, spot_payload


def build_market_catalog(perp_payload: list[dict], spot_payload: dict) -> list[MarketInfo]:
    markets: list[MarketInfo] = []
    for meta in perp_payload:
        for entry in meta.get("universe", []):
            raw_name = str(entry.get("name", "")).strip()
            if not raw_name or entry.get("isDelisted"):
                continue
            ticker = standardize_market_name(raw_name)
            symbol = extract_symbol(raw_name)
            prefix = extract_prefix(raw_name)
            pair = build_pair_from_raw_name(raw_name)
            searchable = build_searchable_keys(ticker=ticker, symbol=symbol, raw_name=raw_name)
            margin_mode = "isolated" if entry.get("onlyIsolated") or entry.get("marginMode") == "strictIsolated" else "cross"
            markets.append(
                MarketInfo(
                    raw_name=raw_name,
                    ticker=ticker,
                    pair=pair,
                    symbol=symbol,
                    market_type="perp",
                    source_group=f"perp:{prefix or 'core'}",
                    margin_mode=margin_mode,
                    searchable_keys=searchable,
                )
            )

    for entry in spot_payload.get("universe", []):
        raw_name = str(entry.get("name", "")).strip()
        if not raw_name or raw_name.startswith("@"):
            continue
        base = raw_name.split("/", 1)[0].upper()
        searchable = build_searchable_keys(ticker=base, symbol=base, raw_name=raw_name)
        markets.append(
            MarketInfo(
                raw_name=raw_name,
                ticker=base,
                pair=raw_name.upper(),
                symbol=base,
                market_type="spot",
                source_group="spot",
                margin_mode=None,
                searchable_keys=searchable,
            )
        )
    return markets


def looks_like_simple_asset(value: str) -> bool:
    return bool(SIMPLE_ASSET_RE.fullmatch(value.strip()))


def normalize_asset_request(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.strip().lower())


def standardize_market_name(raw_name: str) -> str:
    match = RAW_NAME_RE.match(raw_name)
    if not match:
        return raw_name.upper().split("/", 1)[0]
    prefix = match.group("prefix").upper()
    symbol = match.group("symbol").upper()
    return f"{prefix}-{symbol}"


def extract_symbol(raw_name: str) -> str:
    match = RAW_NAME_RE.match(raw_name)
    if not match:
        return raw_name.upper().split("/", 1)[0]
    return match.group("symbol").upper()


def extract_prefix(raw_name: str) -> str:
    match = RAW_NAME_RE.match(raw_name)
    if not match:
        return ""
    return match.group("prefix").lower()


def build_pair_from_raw_name(raw_name: str) -> str:
    match = RAW_NAME_RE.match(raw_name)
    if not match:
        symbol = raw_name.upper()
        return f"{symbol}/USDC:USDC"
    prefix = match.group("prefix").lower()
    symbol = match.group("symbol").upper()
    quote, settle = PERP_QUOTE_BY_PREFIX.get(prefix, ("USDC", "USDC"))
    return f"{match.group('prefix').upper()}-{symbol}/{quote}:{settle}"


def build_searchable_keys(*, ticker: str, symbol: str, raw_name: str) -> tuple[str, ...]:
    keys = {
        normalize_asset_request(ticker),
        normalize_asset_request(symbol),
        normalize_asset_request(raw_name),
    }
    for alias, canonical in ALIAS_MAP.items():
        if canonical == normalize_asset_request(symbol):
            keys.add(normalize_asset_request(alias))
    return tuple(sorted(keys))


def sort_market_candidates(candidates: list[MarketInfo]) -> list[MarketInfo]:
    def sort_key(candidate: MarketInfo) -> tuple[int, int, int, str]:
        prefix = extract_prefix(candidate.raw_name)
        return (
            0 if candidate.market_type == "perp" else 1,
            0 if ":" not in candidate.raw_name else 1,
            PERP_PREFIX_PRIORITY.get(prefix, 99),
            candidate.ticker,
        )

    return sorted(candidates, key=sort_key)


def similarity(left: str, right: str) -> float:
    return SequenceMatcher(a=left, b=right).ratio()
