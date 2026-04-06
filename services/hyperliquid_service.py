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
PERP_PREFIX_PRIORITY = {"xyz": 0, "km": 1, "flx": 2, "cash": 3, "vntl": 4, "hyna": 5}
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
    symbol: str
    market_type: str
    source_group: str
    searchable_keys: tuple[str, ...]


class HyperliquidService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._markets_cache: list[MarketInfo] = []
        self._markets_cache_time: datetime | None = None

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

        if category == "crypto" and any(term in lower for term in ("crypto", "bitcoin", "ethereum", "ether", "eth", "solana", "sol", "xrp", "ripple", "doge", "dogecoin", "stablecoin", "token")):
            return await self.resolve_asset("btc")
        if any(term in lower for term in ("stock market", "equities", "stocks", "s&p 500", "sp500")):
            return await self.resolve_asset("sp500")
        return None

    async def market_count(self) -> int:
        return len(await self._get_markets())

    async def _get_markets(self) -> list[MarketInfo]:
        now = datetime.now(timezone.utc)
        if self._markets_cache and self._markets_cache_time and now - self._markets_cache_time < timedelta(minutes=10):
            return self._markets_cache

        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=20)
        ) as session:
            perp_payload, spot_payload = await fetch_market_payloads(
                session=session,
                info_url=self.config.hyperliquid_info_url,
            )

        markets = build_market_catalog(perp_payload=perp_payload, spot_payload=spot_payload)
        self._markets_cache = markets
        self._markets_cache_time = now
        LOGGER.info("Loaded %s official Hyperliquid markets.", len(markets))
        return markets


async def fetch_market_payloads(
    *, session: aiohttp.ClientSession, info_url: str
) -> tuple[list[dict], dict]:
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
            searchable = build_searchable_keys(ticker=ticker, symbol=symbol, raw_name=raw_name)
            markets.append(
                MarketInfo(
                    raw_name=raw_name,
                    ticker=ticker,
                    symbol=symbol,
                    market_type="perp",
                    source_group="perp",
                    searchable_keys=searchable,
                )
            )

    for entry in spot_payload.get("universe", []):
        raw_name = str(entry.get("name", "")).strip()
        if not raw_name or raw_name.startswith("@"):
            continue
        base = raw_name.split("/", 1)[0]
        searchable = build_searchable_keys(ticker=base.upper(), symbol=base.upper(), raw_name=raw_name)
        markets.append(
            MarketInfo(
                raw_name=raw_name,
                ticker=base.upper(),
                symbol=base.upper(),
                market_type="spot",
                source_group="spot",
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
        return raw_name.upper()
    prefix = match.group("prefix").upper()
    symbol = match.group("symbol").upper()
    return f"{prefix}-{symbol}"


def extract_symbol(raw_name: str) -> str:
    match = RAW_NAME_RE.match(raw_name)
    if not match:
        return raw_name.upper().split("/", 1)[0]
    return match.group("symbol").upper()


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
    def sort_key(candidate: MarketInfo) -> tuple[int, int, str]:
        prefix = ""
        match = RAW_NAME_RE.match(candidate.raw_name)
        if match:
            prefix = match.group("prefix").lower()
        return (
            0 if candidate.market_type == "perp" else 1,
            0 if ":" not in candidate.raw_name else 1,
            PERP_PREFIX_PRIORITY.get(prefix, 99),
            candidate.ticker,
        )

    return sorted(candidates, key=sort_key)


def similarity(left: str, right: str) -> float:
    return SequenceMatcher(a=left, b=right).ratio()
