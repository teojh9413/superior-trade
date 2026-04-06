from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from core.config import AppConfig
from services.hyperliquid_service import HyperliquidService, MarketInfo
from services.prompt_service import PromptService

LOGGER = logging.getLogger(__name__)

SOURCE_PRIORITY = {
    "Reuters": 0,
    "Bloomberg": 1,
    "Associated Press": 2,
    "AP News": 2,
    "Financial Times": 3,
    "The Wall Street Journal": 4,
    "WSJ": 4,
    "CNBC": 5,
    "MarketWatch": 6,
    "Yahoo Finance": 7,
    "Benzinga": 8,
    "Business Insider": 8,
    "CoinDesk": 9,
    "The Block": 10,
    "CryptoSlate": 11,
    "Cointelegraph": 12,
    "PYMNTS.com": 13,
}
CRYPTO_QUERIES = [
    "crypto market",
    "bitcoin ethereum",
    "crypto ETF",
    "stablecoin regulation",
]
TRADFI_QUERIES = [
    "stock market today",
    "tesla stock",
    "nvidia stock",
    "gold price",
    "oil market",
]
CRYPTO_KEYWORDS = (
    "crypto",
    "bitcoin",
    "btc",
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
    "blockchain",
)
TRADFI_KEYWORDS = (
    "stock",
    "stocks",
    "equity",
    "equities",
    "s&p",
    "sp500",
    "nasdaq",
    "dow",
    "fed",
    "federal reserve",
    "treasury",
    "bond",
    "yield",
    "gold",
    "silver",
    "oil",
    "crude",
    "tesla",
    "nvidia",
    "apple",
    "amazon",
    "microsoft",
    "market",
)


@dataclass(frozen=True, slots=True)
class NewsArticle:
    title: str
    source: str
    published_at: datetime
    summary: str
    url: str
    category: str
    market: MarketInfo


@dataclass(frozen=True, slots=True)
class DailyBrief:
    generated_at_label: str
    items: list[NewsArticle]
    prompts: list[str]


class NewsService:
    def __init__(
        self,
        *,
        config: AppConfig,
        hyperliquid_service: HyperliquidService,
        prompt_service: PromptService,
    ) -> None:
        self.config = config
        self.hyperliquid_service = hyperliquid_service
        self.prompt_service = prompt_service

    async def generate_daily_brief(self, now: datetime | None = None) -> DailyBrief:
        tz = resolve_brief_timezone(self.config.timezone)
        current = now.astimezone(tz) if now else datetime.now(tz)
        crypto_pool = await self._gather_news_pool(CRYPTO_QUERIES, category="crypto", now=current)
        tradfi_pool = await self._gather_news_pool(TRADFI_QUERIES, category="tradfi", now=current)

        selected = crypto_pool[:2] + tradfi_pool[:1]
        if len(selected) != 3:
            raise RuntimeError("Unable to build a complete 24-hour brief with 2 crypto and 1 tradfi headlines.")

        prompts = [
            self.prompt_service.build_brief_prompt(article.market, article.title, article.summary)
            for article in selected
        ]
        return DailyBrief(
            generated_at_label=current.strftime("%d %b %Y, GMT+8"),
            items=selected,
            prompts=prompts,
        )

    async def _gather_news_pool(
        self, queries: list[str], *, category: str, now: datetime
    ) -> list[NewsArticle]:
        articles: list[NewsArticle] = []
        for query in queries:
            raw_results = await self._search_news(query=query)
            for result in raw_results:
                article = await self._build_article_from_result(result=result, category=category, now=now)
                if article is not None:
                    articles.append(article)

        deduped = deduplicate_articles(articles)
        return sort_articles(deduped)

    async def _build_article_from_result(
        self, *, result: dict[str, str], category: str, now: datetime
    ) -> NewsArticle | None:
        published_at = parse_ddgs_date(result.get("date", ""), now=now)
        if published_at is None:
            return None
        if published_at < now.astimezone(timezone.utc) - timedelta(hours=24):
            return None

        title = clean_text(result.get("title", ""))
        summary = summarize_text(result.get("body", ""))
        source = clean_source(result.get("source", "Unknown"))
        url = result.get("url", "").strip()
        if not title or not summary or not url:
            return None
        if "opinion" in title.lower():
            return None
        if not matches_requested_category(title=title, summary=summary, category=category):
            return None

        market = await self.hyperliquid_service.infer_market_from_text(f"{title} {summary}", category)
        if market is None:
            return None

        return NewsArticle(
            title=title,
            source=source,
            published_at=published_at,
            summary=summary,
            url=url,
            category=category,
            market=market,
        )

    async def _search_news(self, *, query: str) -> list[dict[str, str]]:
        return await asyncio.to_thread(run_ddgs_news_search, query, self.config)


def run_ddgs_news_search(query: str, config: AppConfig) -> list[dict[str, str]]:
    ddgs_executable = resolve_ddgs_cli_path(config)
    for backend in ("auto", "all", "duckduckgo", "bing"):
        temp_file = Path(tempfile.gettempdir()) / f"superior_ddgs_{os.getpid()}_{abs(hash((query, backend)))}.json"
        command = [
            ddgs_executable,
            "news",
            "-q",
            query,
            "-t",
            "d",
            "-m",
            "15",
            "-b",
            backend,
            "-o",
            str(temp_file),
            "-nc",
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            LOGGER.warning("DDGS news search failed for query '%s' with backend '%s': %s", query, backend, completed.stderr.strip())
            continue
        if not temp_file.exists():
            continue
        try:
            payload = json.loads(temp_file.read_text(encoding="utf-8"))
        finally:
            temp_file.unlink(missing_ok=True)
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
    return []


def resolve_ddgs_cli_path(config: AppConfig) -> str:
    if config.ddgs_cli_path:
        return config.ddgs_cli_path
    which = shutil.which("ddgs")
    if which:
        return which
    scripts_dir = Path(sys.executable).resolve().parent / ("Scripts" if os.name == "nt" else "bin")
    executable = scripts_dir / ("ddgs.exe" if os.name == "nt" else "ddgs")
    if executable.exists():
        return str(executable)
    raise FileNotFoundError("DDGS CLI was not found. Install the 'ddgs' package or set DDGS_CLI_PATH.")


def parse_ddgs_date(value: str, *, now: datetime) -> datetime | None:
    raw = value.strip()
    if not raw:
        return None
    cleaned = re.sub(r"^[A-Za-z]+\s*", "", raw).strip()
    try:
        return datetime.fromisoformat(cleaned.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        pass

    relative_match = re.search(r"(\d+)\s+(minute|minutes|hour|hours|day|days)\s+ago", cleaned.lower())
    if not relative_match:
        return None
    amount = int(relative_match.group(1))
    unit = relative_match.group(2)
    if unit.startswith("minute"):
        delta = timedelta(minutes=amount)
    elif unit.startswith("hour"):
        delta = timedelta(hours=amount)
    else:
        delta = timedelta(days=amount)
    return now.astimezone(timezone.utc) - delta


def summarize_text(text: str, limit: int = 170) -> str:
    compact = clean_text(text)
    if len(compact) <= limit:
        return compact
    sentence_match = re.match(r"^(.{1," + str(limit) + r"}?[.!?])\s", compact)
    if sentence_match:
        return sentence_match.group(1).strip()
    return compact[: limit - 3].rstrip() + "..."


def clean_text(text: str) -> str:
    text = text.replace("鈥", "'")
    return re.sub(r"\s+", " ", text).strip()


def clean_source(source: str) -> str:
    source = clean_text(source)
    source = source.replace("路 via Yahoo Finance", "")
    return source


def deduplicate_articles(articles: list[NewsArticle]) -> list[NewsArticle]:
    deduped: list[NewsArticle] = []
    seen_urls: set[str] = set()
    for article in articles:
        if article.url in seen_urls:
            continue
        if any(similar_titles(article.title, existing.title) for existing in deduped):
            continue
        seen_urls.add(article.url)
        deduped.append(article)
    return deduped


def similar_titles(left: str, right: str) -> bool:
    normalized_left = re.sub(r"[^a-z0-9]+", " ", left.lower()).strip()
    normalized_right = re.sub(r"[^a-z0-9]+", " ", right.lower()).strip()
    if not normalized_left or not normalized_right:
        return False
    if normalized_left == normalized_right:
        return True
    return SequenceMatcher(a=normalized_left, b=normalized_right).ratio() >= 0.82


def sort_articles(articles: list[NewsArticle]) -> list[NewsArticle]:
    return sorted(
        articles,
        key=lambda article: (
            source_rank(article.source),
            -article.published_at.timestamp(),
            article.title,
        ),
    )


def source_rank(source: str) -> int:
    for known_source, rank in SOURCE_PRIORITY.items():
        if known_source.lower() in source.lower():
            return rank
    return 50


def matches_requested_category(*, title: str, summary: str, category: str) -> bool:
    text = f"{title} {summary}".lower()
    has_crypto = any(keyword in text for keyword in CRYPTO_KEYWORDS)
    has_tradfi = any(keyword in text for keyword in TRADFI_KEYWORDS)
    if category == "crypto":
        return has_crypto
    return has_tradfi and not has_crypto


def resolve_brief_timezone(timezone_name: str):
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        if timezone_name == "Asia/Singapore":
            LOGGER.warning("ZoneInfo data for Asia/Singapore is unavailable; falling back to fixed GMT+8.")
            return timezone(timedelta(hours=8), name="GMT+8")
        raise
