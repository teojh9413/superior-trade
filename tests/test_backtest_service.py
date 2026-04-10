import asyncio
from pathlib import Path

from core.config import AppConfig
from services.backtest_registry import BacktestRegistry, RegistryEntry
from services.backtest_service import (
    BacktestService,
    BacktestStats,
    build_backtest_config,
    rank_backtest_results,
)
from services.hyperliquid_service import MarketInfo
from services.superior_api_service import BacktestRecord


class FakeHyperliquidService:
    async def resolve_asset(self, asset_name: str):
        return MarketInfo("BTC", "BTC", "BTC/USDC:USDC", "BTC", "perp", "perp", "cross", ("btc",))


class FakeSuperiorApiService:
    def __init__(self, records: list[BacktestRecord] | None = None) -> None:
        self.records = records or []
        self.deleted: list[str] = []

    async def list_backtests(self) -> list[BacktestRecord]:
        return self.records

    async def delete_backtest(self, backtest_id: str) -> None:
        self.deleted.append(backtest_id)


def test_rank_backtest_results_uses_profit_then_sharpe_then_win_rate() -> None:
    ranked = rank_backtest_results(
        [
            BacktestStats("A", "BTC", 2, 55.0, 2.0, 1.0, 1.0, "1h"),
            BacktestStats("B", "BTC", 2, 50.0, 2.0, 1.0, 1.2, "1h"),
            BacktestStats("C", "BTC", 2, 70.0, 1.0, 1.0, 3.0, "1h"),
        ]
    )

    assert [item.strategy_name for item in ranked] == ["B", "A", "C"]


def test_build_backtest_config_uses_signal_only_placeholders() -> None:
    market = MarketInfo("xyz:TSLA", "XYZ-TSLA", "XYZ-TSLA/USDC:USDC", "TSLA", "perp", "perp:xyz", "isolated", ("tsla",))

    config = build_backtest_config(market)

    assert config["timeframe"] == "15m"
    assert config["exchange"]["pair_whitelist"] == ["XYZ-TSLA/USDC:USDC"]
    assert config["minimal_roi"] == {"0": 100.0}
    assert config["stoploss"] == -0.99
    assert config["entry_pricing"] == {"price_side": "other"}
    assert config["exit_pricing"] == {"price_side": "other"}
    assert config["margin_mode"] == "isolated"


def test_cleanup_old_bot_backtests_only_deletes_completed_or_failed_registry_entries(tmp_path: Path) -> None:
    registry = BacktestRegistry(tmp_path / "registry.json")
    registry.upsert(RegistryEntry("done-id", "MACD", "BTC", "2026-04-08T00:00:00Z", "completed"))
    registry.upsert(RegistryEntry("run-id", "RSI Reversal", "BTC", "2026-04-08T00:00:00Z", "running"))
    fake_api = FakeSuperiorApiService(
        records=[
            BacktestRecord("done-id", "completed"),
            BacktestRecord("run-id", "running"),
        ]
    )
    service = BacktestService(
        config=build_test_config(tmp_path),
        hyperliquid_service=FakeHyperliquidService(),
        superior_api_service=fake_api,
        registry=registry,
    )

    asyncio.run(service.cleanup_old_bot_backtests())

    assert fake_api.deleted == ["done-id"]
    assert registry.find("done-id") is None
    assert registry.find("run-id") is not None


def test_cleanup_existing_backtests_deletes_all_statuses(tmp_path: Path) -> None:
    registry = BacktestRegistry(tmp_path / "registry.json")
    registry.upsert(RegistryEntry("pending-id", "MACD", "BTC", "2026-04-08T00:00:00Z", "pending"))
    fake_api = FakeSuperiorApiService(
        records=[
            BacktestRecord("pending-id", "pending"),
            BacktestRecord("running-id", "running"),
            BacktestRecord("failed-id", "failed"),
        ]
    )
    service = BacktestService(
        config=build_test_config(tmp_path),
        hyperliquid_service=FakeHyperliquidService(),
        superior_api_service=fake_api,
        registry=registry,
    )

    asyncio.run(service.cleanup_existing_backtests())

    assert fake_api.deleted == ["pending-id", "running-id", "failed-id"]
    assert registry.find("pending-id") is None


def test_build_timerange_uses_last_completed_24h_window() -> None:
    from datetime import datetime, timezone
    from services.backtest_service import build_timerange

    timerange = build_timerange(datetime(2026, 4, 10, 15, 30, tzinfo=timezone.utc))

    assert timerange == {"start": "2026-04-06", "end": "2026-04-07"}


def test_build_timerange_supports_custom_lag_days() -> None:
    from datetime import datetime, timezone
    from services.backtest_service import build_timerange

    timerange = build_timerange(datetime(2026, 4, 10, 15, 30, tzinfo=timezone.utc), lag_days=2)

    assert timerange == {"start": "2026-04-07", "end": "2026-04-08"}


def test_extract_backtest_stats_handles_freqtrade_style_fractional_metrics() -> None:
    from services.backtest_service import extract_backtest_stats

    stats = extract_backtest_stats(
        {
            "total_trades": 3,
            "winrate": 0.6667,
            "profit_total": 0.0125,
            "max_drawdown_account": 0.034,
            "sharpe": 1.75,
            "duration_avg": "1:30:00",
        },
        "MACD",
        "BTC",
    )

    assert stats.total_trades == 3
    assert round(stats.win_rate_percent, 2) == 66.67
    assert round(stats.total_profit_percent, 2) == 1.25
    assert round(stats.max_drawdown_percent, 2) == 3.40
    assert stats.average_trade_duration == "1:30:00"


def build_test_config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        base_dir=tmp_path,
        prompts_dir=tmp_path / "prompts",
        discord_bot_token=None,
        superior_trade_api_key="test-key",
        superior_trade_api_url="https://api.superior.trade",
        backtest_registry_path=tmp_path / "registry.json",
        daily_post_channel_id=None,
        dry_run=True,
        log_level="INFO",
        timezone="Asia/Singapore",
        daily_brief_hour=15,
        daily_brief_minute=0,
        ddgs_cli_path=None,
        hyperliquid_info_url="https://api.hyperliquid.xyz/info",
        backtest_poll_seconds=1,
        backtest_timeout_seconds=30,
        backtest_data_lag_days=3,
        config_file=None,
    )
