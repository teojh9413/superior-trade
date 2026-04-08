from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from core.config import AppConfig
from core.exceptions import BacktestRunError, SuperiorApiError
from services.backtest_registry import BacktestRegistry, RegistryEntry
from services.hyperliquid_service import HyperliquidService, MarketInfo
from services.strategy_templates import StrategyTemplate, get_strategy_templates
from services.superior_api_service import BacktestRecord, SuperiorApiService

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class BacktestStats:
    strategy_name: str
    ticker: str
    total_trades: int
    win_rate_percent: float
    total_profit_percent: float
    max_drawdown_percent: float
    sharpe_ratio: float
    average_trade_duration: str


class BacktestService:
    def __init__(
        self,
        *,
        config: AppConfig,
        hyperliquid_service: HyperliquidService,
        superior_api_service: SuperiorApiService,
        registry: BacktestRegistry,
    ) -> None:
        self.config = config
        self.hyperliquid_service = hyperliquid_service
        self.superior_api_service = superior_api_service
        self.registry = registry
        self.templates = get_strategy_templates()

    async def run_best_backtest_for_asset(self, asset_name: str) -> tuple[MarketInfo, BacktestStats]:
        market = await self.hyperliquid_service.resolve_asset(asset_name)
        if market is None:
            raise BacktestRunError(f"No official Hyperliquid market currently exists for {asset_name}.")

        await self.cleanup_old_bot_backtests()

        created_ids: list[str] = []
        completed_stats: list[BacktestStats] = []
        try:
            for template in self.templates:
                record = await self._create_backtest_with_retry(template=template, market=market)
                created_ids.append(record.backtest_id)
                self.registry.upsert(
                    RegistryEntry(
                        backtest_id=record.backtest_id,
                        strategy_name=template.name,
                        ticker=market.ticker,
                        created_at=datetime.now(timezone.utc).isoformat(),
                        status=record.status,
                    )
                )
                details = await self._run_and_collect(record=record)
                self.registry.upsert(
                    RegistryEntry(
                        backtest_id=record.backtest_id,
                        strategy_name=template.name,
                        ticker=market.ticker,
                        created_at=datetime.now(timezone.utc).isoformat(),
                        status=details.status,
                    )
                )
                if details.status == "completed" and details.results:
                    completed_stats.append(extract_backtest_stats(details.results, template.name, market.ticker))
        finally:
            await self.cleanup_created_backtests(created_ids)

        if not completed_stats:
            raise BacktestRunError("All seven backtests failed.")
        if all(result.total_trades == 0 for result in completed_stats):
            raise BacktestRunError("No valid trades were generated over the last 24 hours.")

        best = rank_backtest_results(completed_stats)[0]
        return market, best

    async def cleanup_old_bot_backtests(self) -> None:
        registry_entries = {entry.backtest_id: entry for entry in self.registry.list_entries()}
        if not registry_entries:
            return
        existing = await self.superior_api_service.list_backtests()
        existing_map = {item.backtest_id: item for item in existing}
        for backtest_id, entry in registry_entries.items():
            record = existing_map.get(backtest_id)
            if record is None:
                self.registry.remove(backtest_id)
                continue
            if record.status in {"completed", "failed"}:
                await self.superior_api_service.delete_backtest(backtest_id)
                self.registry.remove(backtest_id)

    async def cleanup_created_backtests(self, backtest_ids: list[str]) -> None:
        for backtest_id in backtest_ids:
            try:
                await self.superior_api_service.delete_backtest(backtest_id)
            except SuperiorApiError:
                LOGGER.warning("Failed to delete backtest %s during cleanup.", backtest_id)
            finally:
                self.registry.remove(backtest_id)

    async def _create_backtest_with_retry(self, *, template: StrategyTemplate, market: MarketInfo) -> BacktestRecord:
        for attempt in range(2):
            try:
                return await self.superior_api_service.create_backtest(
                    config=build_backtest_config(market),
                    code=template.code,
                    timerange=build_timerange(),
                )
            except SuperiorApiError as error:
                if "limit_exceeded" not in str(error) or attempt == 1:
                    raise
                await self.cleanup_old_bot_backtests()
        raise BacktestRunError("Unable to create backtest after cleanup retry.")

    async def _run_and_collect(self, *, record: BacktestRecord) -> BacktestRecord:
        if record.status == "pending":
            record = await self.superior_api_service.start_backtest(record.backtest_id)

        deadline = datetime.now(timezone.utc) + timedelta(seconds=self.config.backtest_timeout_seconds)
        while datetime.now(timezone.utc) < deadline:
            status_record = await self.superior_api_service.get_backtest_status(record.backtest_id)
            if status_record.status in {"completed", "failed"}:
                return await self.superior_api_service.get_backtest_details(record.backtest_id)
            await asyncio.sleep(self.config.backtest_poll_seconds)

        raise BacktestRunError(f"Backtest {record.backtest_id} timed out.")


def build_backtest_config(market: MarketInfo) -> dict[str, Any]:
    config: dict[str, Any] = {
        "exchange": {"name": "hyperliquid", "pair_whitelist": [market.pair]},
        "stake_currency": derive_stake_currency(market.pair),
        "stake_amount": 100,
        "timeframe": "15m",
        "max_open_trades": 1,
        "stoploss": -0.99,
        "minimal_roi": {"0": 100.0},
        "entry_pricing": {"price_side": "other"},
        "exit_pricing": {"price_side": "other"},
        "pairlists": [{"method": "StaticPairList"}],
    }
    if market.market_type == "perp":
        config["trading_mode"] = "futures"
        config["margin_mode"] = market.margin_mode or "cross"
    return config


def derive_stake_currency(pair: str) -> str:
    if "/" not in pair:
        return "USDC"
    return pair.split("/", 1)[1].split(":", 1)[0]


def build_timerange(now: datetime | None = None) -> dict[str, str]:
    current = now.astimezone(timezone.utc) if now else datetime.now(timezone.utc)
    start = (current - timedelta(hours=24)).date().isoformat()
    end = current.date().isoformat()
    return {"start": start, "end": end}


def extract_backtest_stats(results: dict[str, Any], strategy_name: str, ticker: str) -> BacktestStats:
    metrics = flatten_metrics(results)
    total_trades = int(first_number(metrics, ["total_trades", "trades", "total_closed_trades"], default=0))
    win_rate_percent = first_percent(metrics, ["win_rate", "profit_factor_win_rate", "wins_pct"], default=0.0)
    total_profit_percent = first_percent(metrics, ["total_profit_pct", "total_profit", "profit_total_pct"], default=0.0)
    max_drawdown_percent = first_percent(metrics, ["max_drawdown", "max_drawdown_pct", "drawdown"], default=0.0)
    sharpe_ratio = float(first_number(metrics, ["sharpe", "sharpe_ratio"], default=0.0))
    average_trade_duration = first_duration(metrics)
    return BacktestStats(
        strategy_name=strategy_name,
        ticker=ticker,
        total_trades=total_trades,
        win_rate_percent=win_rate_percent,
        total_profit_percent=total_profit_percent,
        max_drawdown_percent=max_drawdown_percent,
        sharpe_ratio=sharpe_ratio,
        average_trade_duration=average_trade_duration,
    )


def flatten_metrics(payload: Any, prefix: str = "") -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    if isinstance(payload, dict):
        for key, value in payload.items():
            joined = f"{prefix}.{key}" if prefix else str(key)
            flattened.update(flatten_metrics(value, joined))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            flattened.update(flatten_metrics(value, f"{prefix}[{index}]"))
    else:
        flattened[prefix] = payload
    return flattened


def first_number(metrics: dict[str, Any], keys: list[str], default: float) -> float:
    for metric_key, value in metrics.items():
        normalized = metric_key.lower()
        if any(key in normalized for key in keys):
            try:
                if isinstance(value, str):
                    return float(value.replace("%", "").strip())
                return float(value)
            except (TypeError, ValueError):
                continue
    return default


def first_percent(metrics: dict[str, Any], keys: list[str], default: float) -> float:
    value = first_number(metrics, keys, default)
    return value


def first_duration(metrics: dict[str, Any]) -> str:
    for metric_key, value in metrics.items():
        normalized = metric_key.lower()
        if "avg_duration" in normalized or "average_duration" in normalized or "trade_duration" in normalized:
            return str(value)
    return "n/a"


def rank_backtest_results(results: list[BacktestStats]) -> list[BacktestStats]:
    return sorted(
        results,
        key=lambda item: (
            -item.total_profit_percent,
            -item.sharpe_ratio,
            -item.win_rate_percent,
        ),
    )
