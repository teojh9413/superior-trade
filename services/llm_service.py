from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

import aiohttp

from core.config import AppConfig
from services.knowledge_service import KnowledgeSection
from services.pair_mapper import PairMappingResult
from services.website_service import LookupSnippet

LOGGER = logging.getLogger(__name__)

UNCERTAINTY_FALLBACK = "I’m not fully sure on that. I’ll call on the Superior.Trade team members to assist."


@dataclass(frozen=True, slots=True)
class AskResult:
    answer: str
    confidence: str
    sources: list[str]
    used_web: bool
    used_fallback: bool


@dataclass(frozen=True, slots=True)
class TradeStrategy:
    objective: str
    pair: str
    timeframe: str
    direction: str
    entry_logic: str
    exit_logic: str
    risk_management: str
    backtest_reminder: str
    used_fallback: bool


@dataclass(frozen=True, slots=True)
class NewsInsight:
    why_it_matters: str
    direction: str
    strategy_prompt: str | None
    used_fallback: bool


class LLMService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.core_prompt = self._load_prompt("core_system_prompt.txt")
        self.mode_prompts = {
            "ask": self._load_prompt("ask_mode_prompt.txt"),
            "trade": self._load_prompt("trade_mode_prompt.txt"),
            "news": self._load_prompt("daily_news_prompt.txt"),
        }

    def is_configured(self) -> bool:
        return bool(self.config.llm_api_key and self.config.llm_base_url and self.config.llm_model)

    async def generate_ask_response(
        self,
        question: str,
        knowledge_sections: list[KnowledgeSection],
        knowledge_context: str,
        website_snippets: list[LookupSnippet],
        github_snippets: list[LookupSnippet],
    ) -> AskResult:
        references = [
            f"{section.source_name} -> {section.heading_path_display}" for section in knowledge_sections
        ]
        if not self.is_configured():
            return self._fallback_ask_result(knowledge_sections, references, bool(website_snippets or github_snippets))

        website_context = render_snippets(website_snippets)
        github_context = render_snippets(github_snippets)
        user_prompt = f"""
Question:
{question}

Local knowledge context:
{knowledge_context or "None"}

Official website snippets:
{website_context or "None"}

Official GitHub snippets:
{github_context or "None"}

Return strict JSON with keys:
- answer
- confidence ("high", "medium", or "low")
- should_fallback (boolean)
""".strip()

        payload = await self._chat_json(mode="ask", user_prompt=user_prompt)
        if not payload:
            return self._fallback_ask_result(knowledge_sections, references, bool(website_snippets or github_snippets))

        answer = str(payload.get("answer", "")).strip()
        confidence = str(payload.get("confidence", "low")).lower()
        should_fallback = bool(payload.get("should_fallback", False))
        if should_fallback or not answer:
            return AskResult(
                answer=UNCERTAINTY_FALLBACK,
                confidence="low",
                sources=references + collect_lookup_labels(website_snippets + github_snippets),
                used_web=bool(website_snippets or github_snippets),
                used_fallback=True,
            )

        return AskResult(
            answer=answer,
            confidence=confidence if confidence in {"high", "medium", "low"} else "medium",
            sources=references + collect_lookup_labels(website_snippets + github_snippets),
            used_web=bool(website_snippets or github_snippets),
            used_fallback=False,
        )

    async def generate_trade_prompt(
        self, asset_or_market: str, mapping: PairMappingResult
    ) -> TradeStrategy:
        if not mapping.found or not mapping.pair:
            return TradeStrategy(
                objective=f"Build a practical strategy for {asset_or_market}.",
                pair="UNMAPPED",
                timeframe="15m",
                direction="NO CLEAR EDGE",
                entry_logic="No safe pair mapping is available, so the strategy stops here.",
                exit_logic="No trade plan should be proposed without a verified pair.",
                risk_management="Do not trade until the pair is confirmed from supported Hyperliquid listings.",
                backtest_reminder="No backtest until mapping is confirmed.",
                used_fallback=True,
            )

        if not self.is_configured():
            return self._fallback_trade_strategy(asset_or_market=asset_or_market, mapping=mapping)

        user_prompt = f"""
Requested market:
{asset_or_market}

Deterministic pair mapping:
- pair: {mapping.pair}
- market_type: {mapping.market_type}
- explanation: {mapping.explanation}

Return strict JSON with keys:
- objective
- timeframe
- direction ("LONG", "SHORT", or "NO CLEAR EDGE")
- entry_logic
- exit_logic
- risk_management
- backtest_reminder
""".strip()

        payload = await self._chat_json(mode="trade", user_prompt=user_prompt)
        if not payload:
            return self._fallback_trade_strategy(asset_or_market=asset_or_market, mapping=mapping)

        direction = str(payload.get("direction", "NO CLEAR EDGE")).upper()
        if direction not in {"LONG", "SHORT", "NO CLEAR EDGE"}:
            direction = "NO CLEAR EDGE"

        return TradeStrategy(
            objective=str(payload.get("objective") or f"Trade {asset_or_market} with a practical ruleset."),
            pair=mapping.pair,
            timeframe=str(payload.get("timeframe") or "15m"),
            direction=direction,
            entry_logic=str(payload.get("entry_logic") or "Wait for clear, testable setup conditions."),
            exit_logic=str(payload.get("exit_logic") or "Exit on invalidation or planned profit-taking."),
            risk_management=str(
                payload.get("risk_management")
                or "Use isolated risk, defined stop distance, and position sizing that survives a losing streak."
            ),
            backtest_reminder=str(
                payload.get("backtest_reminder")
                or "Backtest on recent Hyperliquid data before any live deployment."
            ),
            used_fallback=False,
        )

    async def generate_news_insight(
        self,
        *,
        title: str,
        description: str,
        source_name: str,
        pair: str,
        market_context: str,
    ) -> NewsInsight:
        if not self.is_configured():
            return self._fallback_news_insight(title=title, description=description, pair=pair)

        user_prompt = f"""
Headline:
{title}

Description:
{description or "No description provided."}

Source:
{source_name}

Mapped pair:
{pair}

Market context:
{market_context}

Return strict JSON with keys:
- why_it_matters
- direction ("LONG", "SHORT", or "NO CLEAR EDGE")
- strategy_prompt
""".strip()

        payload = await self._chat_json(mode="news", user_prompt=user_prompt)
        if not payload:
            return self._fallback_news_insight(title=title, description=description, pair=pair)

        direction = str(payload.get("direction", "NO CLEAR EDGE")).upper()
        if direction not in {"LONG", "SHORT", "NO CLEAR EDGE"}:
            direction = "NO CLEAR EDGE"
        strategy_prompt = str(payload.get("strategy_prompt") or "").strip() or None
        if direction == "NO CLEAR EDGE":
            strategy_prompt = None

        return NewsInsight(
            why_it_matters=str(payload.get("why_it_matters") or "This headline may affect risk appetite or positioning."),
            direction=direction,
            strategy_prompt=strategy_prompt,
            used_fallback=False,
        )

    async def _chat_json(self, mode: str, user_prompt: str) -> dict[str, object] | None:
        endpoint = build_chat_completions_url(self.config.llm_base_url)
        body = {
            "model": self.config.llm_model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": f"{self.core_prompt}\n\n{self.mode_prompts[mode]}"},
                {"role": "user", "content": user_prompt},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.config.llm_api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.config.llm_timeout_seconds)
            ) as session:
                async with session.post(endpoint, headers=headers, json=body) as response:
                    text = await response.text()
                    if response.status >= 400:
                        LOGGER.warning("LLM request failed with status %s: %s", response.status, text[:400])
                        return None
        except aiohttp.ClientError:
            LOGGER.exception("LLM request failed before completion.")
            return None

        try:
            payload = json.loads(text)
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            LOGGER.warning("LLM response did not match expected chat completion shape.")
            return None

        return extract_json_object(content)

    def _fallback_ask_result(
        self, knowledge_sections: list[KnowledgeSection], references: list[str], used_web: bool
    ) -> AskResult:
        if not knowledge_sections:
            return AskResult(
                answer=UNCERTAINTY_FALLBACK,
                confidence="low",
                sources=references,
                used_web=used_web,
                used_fallback=True,
            )

        top_section = knowledge_sections[0]
        preview = compact_text(top_section.content, limit=320)
        answer = f"{preview}\n\nIf you want, I can narrow this further once the live LLM provider is configured."
        return AskResult(
            answer=answer,
            confidence="medium",
            sources=references,
            used_web=used_web,
            used_fallback=True,
        )

    def _fallback_trade_strategy(
        self, asset_or_market: str, mapping: PairMappingResult
    ) -> TradeStrategy:
        return TradeStrategy(
            objective=f"Build a practical rules-based strategy for {asset_or_market}.",
            pair=mapping.pair or "UNMAPPED",
            timeframe="15m",
            direction="NO CLEAR EDGE",
            entry_logic="Wait for a clean trend-and-retest or range-break confirmation before entering.",
            exit_logic="Take partial profits into strength, and exit fully if the setup invalidates.",
            risk_management="Use isolated risk, keep size modest, and define the stop before entry.",
            backtest_reminder="Backtest on recent Hyperliquid data before considering any live deployment.",
            used_fallback=True,
        )

    def _fallback_news_insight(self, *, title: str, description: str, pair: str) -> NewsInsight:
        summary_source = description or title
        why_it_matters = compact_text(summary_source, limit=180) or "This headline may change short-term positioning."
        direction = infer_direction_from_text(f"{title} {description}")
        strategy_prompt = None
        if direction in {"LONG", "SHORT"}:
            strategy_prompt = (
                f"Objective: react to the headline-driven move on {pair}. "
                f"Timeframe: 15m. Direction: {direction}. "
                "Entry Logic: wait for momentum confirmation and a controlled retest. "
                "Exit Logic: scale out into extension and exit on loss of momentum. "
                "Risk Management: keep risk capped and backtest before deployment."
            )
        return NewsInsight(
            why_it_matters=why_it_matters,
            direction=direction,
            strategy_prompt=strategy_prompt,
            used_fallback=True,
        )

    def _load_prompt(self, filename: str) -> str:
        return (self.config.prompts_dir / filename).read_text(encoding="utf-8").strip()


def build_chat_completions_url(base_url: str | None) -> str:
    if not base_url:
        raise ValueError("LLM_BASE_URL must be configured for live LLM requests.")
    normalized = base_url.rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    return f"{normalized}/chat/completions"


def extract_json_object(content: str) -> dict[str, object] | None:
    content = content.strip()
    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def render_snippets(snippets: list[LookupSnippet]) -> str:
    return "\n\n".join(
        f"[{snippet.source_type.upper()}] {snippet.title}\nURL: {snippet.url}\nExcerpt: {snippet.excerpt}"
        for snippet in snippets
    )


def collect_lookup_labels(snippets: list[LookupSnippet]) -> list[str]:
    return [f"{snippet.source_type}: {snippet.title}" for snippet in snippets]


def compact_text(text: str, limit: int) -> str:
    compacted = re.sub(r"\s+", " ", text).strip()
    if len(compacted) <= limit:
        return compacted
    return compacted[: limit - 3].rstrip() + "..."


def infer_direction_from_text(text: str) -> str:
    lower = text.lower()
    long_markers = ("surge", "rally", "approval", "beat", "inflow", "launch", "rise", "gain")
    short_markers = ("hack", "crackdown", "miss", "drop", "slump", "lawsuit", "outflow", "fall")
    if any(marker in lower for marker in long_markers):
        return "LONG"
    if any(marker in lower for marker in short_markers):
        return "SHORT"
    return "NO CLEAR EDGE"
