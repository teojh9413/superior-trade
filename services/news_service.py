from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import aiohttp

from core.config import AppConfig
from services.llm_service import LLMService, NewsInsight
from services.pair_mapper import PairMapper, PairMappingResult

LOGGER = logging.getLogger(__name__)

CRYPTO_DOMAINS = "reuters.com,bloomberg.com,coindesk.com,theblock.co,cointelegraph.com"
MACRO_DOMAINS = "reuters.com,bloomberg.com,wsj.com,ft.com,cnbc.com,apnews.com"


@dataclass(frozen=True, slots=True)
class NewsArticle:
    title: str
    description: str
    url: str
    source_name: str
    category: str
    published_at: str


@dataclass(frozen=True, slots=True)
class DailyBriefItem:
    category: str
    headline: str
    source_name: str
    url: str
    why_it_matters: str
    pair: str
    direction: str
    strategy_prompt: str | None


@dataclass(frozen=True, slots=True)
class DailyBrief:
    generated_at: str
    items: list[DailyBriefItem]
    used_fallback: bool


class NewsService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    async def generate_daily_brief(
        self, *, llm_service: LLMService, pair_mapper: PairMapper
    ) -> DailyBrief:
        articles = await self._fetch_curated_articles()
        selected = self._select_exact_slots(articles)
        items: list[DailyBriefItem] = []
        used_fallback = not bool(self.config.news_api_key)

        for article in selected:
            market_request = infer_market_request(article.title, article.description, article.category)
            mapping = pair_mapper.resolve(market_request)
            if not mapping.found or not mapping.pair:
                mapping = fallback_mapping(article.category)
            insight = await llm_service.generate_news_insight(
                title=article.title,
                description=article.description,
                source_name=article.source_name,
                pair=mapping.pair or "BTC/USDC:USDC",
                market_context=mapping.explanation,
            )
            if article.source_name == "Superior fallback":
                insight = NewsInsight(
                    why_it_matters=insight.why_it_matters,
                    direction="NO CLEAR EDGE",
                    strategy_prompt=None,
                    used_fallback=True,
                )
            used_fallback = used_fallback or insight.used_fallback
            items.append(
                DailyBriefItem(
                    category=article.category,
                    headline=article.title,
                    source_name=article.source_name,
                    url=article.url,
                    why_it_matters=insight.why_it_matters,
                    pair=mapping.pair or "BTC/USDC:USDC",
                    direction=insight.direction,
                    strategy_prompt=insight.strategy_prompt,
                )
            )

        return DailyBrief(
            generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            items=items,
            used_fallback=used_fallback,
        )

    def build_placeholder_brief(self) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        lines = [
            "🗞️ **Superior Market Brief Preview**",
            f"Generated: {timestamp}",
            "₿ Crypto slot 1: Placeholder headline pending Phase 2 news integration.",
            "🪙 Crypto slot 2: Placeholder headline pending Phase 2 news integration.",
            "🌍 Macro slot: Placeholder headline pending Phase 2 news integration.",
            "⚙️ Scheduler and formatting are live. News fetching arrives in Phase 2.",
        ]
        return "\n".join(lines)

    async def _fetch_curated_articles(self) -> list[NewsArticle]:
        if not self.config.news_api_key:
            LOGGER.info("NEWS_API_KEY not configured; using fallback daily brief headlines.")
            return fallback_articles()

        crypto_query = (
            '(bitcoin OR btc OR ethereum OR eth OR solana OR sol OR crypto) '
            'AND (ETF OR inflows OR regulation OR exchange OR treasury OR adoption OR hack)'
        )
        macro_query = (
            '(Federal Reserve OR inflation OR tariffs OR oil OR gold OR S&P 500 OR Nasdaq OR dollar '
            'OR crude OR OPEC OR Nvidia OR Apple OR Tesla)'
        )
        crypto_articles = await self._fetch_newsapi_articles(
            query=crypto_query,
            domains=CRYPTO_DOMAINS,
            category="crypto",
            page_size=8,
        )
        macro_articles = await self._fetch_newsapi_articles(
            query=macro_query,
            domains=MACRO_DOMAINS,
            category="macro",
            page_size=8,
        )
        return dedupe_articles(crypto_articles + macro_articles)

    async def _fetch_newsapi_articles(
        self, *, query: str, domains: str, category: str, page_size: int
    ) -> list[NewsArticle]:
        since = (datetime.now(timezone.utc) - timedelta(days=2)).date().isoformat()
        url = f"{self.config.news_api_base_url.rstrip('/')}/everything"
        params = {
            "q": query,
            "domains": domains,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": str(page_size),
            "from": since,
        }
        headers = {"X-Api-Key": self.config.news_api_key or ""}
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.config.llm_timeout_seconds)
            ) as session:
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status != 200:
                        LOGGER.warning("News API request failed with status %s.", response.status)
                        return []
                    payload = await response.json()
        except aiohttp.ClientError:
            LOGGER.exception("News API request failed before completion.")
            return []

        articles = []
        for item in payload.get("articles", []):
            title = (item.get("title") or "").strip()
            url = (item.get("url") or "").strip()
            if not title or not url:
                continue
            articles.append(
                NewsArticle(
                    title=title,
                    description=(item.get("description") or "").strip(),
                    url=url,
                    source_name=((item.get("source") or {}).get("name") or "Unknown source").strip(),
                    category=category,
                    published_at=(item.get("publishedAt") or "").strip(),
                )
            )
        return articles

    def _select_exact_slots(self, articles: list[NewsArticle]) -> list[NewsArticle]:
        crypto = [article for article in articles if article.category == "crypto"]
        macro = [article for article in articles if article.category == "macro"]

        selected = crypto[:2] + macro[:1]
        if len(selected) == 3:
            return selected

        fallback_pool = fallback_articles()
        crypto_fallback = [article for article in fallback_pool if article.category == "crypto"]
        macro_fallback = [article for article in fallback_pool if article.category == "macro"]

        while len(crypto) < 2 and crypto_fallback:
            crypto.append(crypto_fallback.pop(0))
        while len(macro) < 1 and macro_fallback:
            macro.append(macro_fallback.pop(0))
        return crypto[:2] + macro[:1]


def fallback_articles() -> list[NewsArticle]:
    return [
        NewsArticle(
            title="Bitcoin holds key risk barometer status as traders watch ETF and macro flows",
            description="With no verified live feed configured, BTC remains the default crypto benchmark for the brief.",
            url="https://superior.trade",
            source_name="Superior fallback",
            category="crypto",
            published_at="",
        ),
        NewsArticle(
            title="Ether sentiment stays event-driven with positioning sensitive to regulation and flows",
            description="ETH serves as the second crypto slot when live non-duplicate headlines are unavailable.",
            url="https://superior.trade",
            source_name="Superior fallback",
            category="crypto",
            published_at="",
        ),
        NewsArticle(
            title="Macro risk tone remains the main driver for equity, metals, and energy proxies",
            description="The non-crypto slot falls back to broad risk appetite when no current macro headline is available.",
            url="https://superior.trade",
            source_name="Superior fallback",
            category="macro",
            published_at="",
        ),
    ]


def dedupe_articles(articles: list[NewsArticle]) -> list[NewsArticle]:
    deduped: list[NewsArticle] = []
    seen_keys: set[str] = set()
    for article in sorted(articles, key=lambda item: item.published_at, reverse=True):
        key = normalize_title(article.title)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(article)
    return deduped


def normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def infer_market_request(title: str, description: str, category: str) -> str:
    text = f"{title} {description}".lower()
    keyword_map = [
        ("bitcoin", "btc"),
        ("btc", "btc"),
        ("ethereum", "eth"),
        ("ether", "eth"),
        ("eth", "eth"),
        ("solana", "sol"),
        ("sol ", "sol"),
        ("gold", "gold"),
        ("silver", "silver"),
        ("brent", "brent"),
        ("oil", "oil"),
        ("crude", "wti"),
        ("opec", "oil"),
        ("s&p", "sp500"),
        ("sp 500", "sp500"),
        ("nasdaq", "nvda"),
        ("nvidia", "nvda"),
        ("apple", "aapl"),
        ("amazon", "amzn"),
        ("google", "googl"),
        ("alphabet", "googl"),
        ("microsoft", "msft"),
        ("meta", "meta"),
        ("tesla", "tsla"),
        ("dollar", "dxy"),
        ("dxy", "dxy"),
        ("vix", "vix"),
    ]
    for needle, mapped in keyword_map:
        if contains_term(text, needle):
            return mapped
    return "btc" if category == "crypto" else "sp500"


def fallback_mapping(category: str) -> PairMappingResult:
    if category == "crypto":
        return PairMappingResult(
            requested="btc",
            found=True,
            pair="BTC/USDC:USDC",
            market_type="crypto perp",
            explanation="Fallback to BTC as the broad crypto benchmark.",
        )
    return PairMappingResult(
        requested="sp500",
        found=True,
        pair="XYZ-SP500/USDC:USDC",
        market_type="HIP3 perp",
        explanation="Fallback to SP500 as the broad macro risk proxy.",
    )


def contains_term(text: str, needle: str) -> bool:
    pattern = r"(?<![a-z0-9])" + re.escape(needle.strip()) + r"(?![a-z0-9])"
    return re.search(pattern, text) is not None
