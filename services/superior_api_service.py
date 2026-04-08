from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import aiohttp

from core.config import AppConfig
from core.exceptions import ConfigurationError, SuperiorApiError

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class BacktestRecord:
    backtest_id: str
    status: str
    config: dict[str, Any] | None = None
    code: str | None = None
    result_url: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    completed_at: str | None = None
    results: dict[str, Any] | None = None


class SuperiorApiService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def is_configured(self) -> bool:
        return bool(self.config.superior_trade_api_key)

    async def list_backtests(self) -> list[BacktestRecord]:
        items: list[BacktestRecord] = []
        cursor: str | None = None
        while True:
            payload = await self._request("GET", "/v2/backtesting", params={"cursor": cursor} if cursor else None)
            for item in payload.get("items", []):
                items.append(parse_backtest_record(item))
            cursor = payload.get("nextCursor")
            if not cursor:
                break
        return items

    async def create_backtest(self, *, config: dict[str, Any], code: str, timerange: dict[str, str]) -> BacktestRecord:
        payload = await self._request(
            "POST",
            "/v2/backtesting",
            json_body={"config": config, "code": code, "timerange": timerange},
            allow_400=True,
        )
        if payload.get("error"):
            raise SuperiorApiError(payload.get("error", "unknown_error"))
        return parse_backtest_record(payload)

    async def start_backtest(self, backtest_id: str) -> BacktestRecord:
        payload = await self._request(
            "PUT",
            f"/v2/backtesting/{backtest_id}/status",
            json_body={"action": "start"},
        )
        return parse_backtest_record(payload)

    async def get_backtest_status(self, backtest_id: str) -> BacktestRecord:
        payload = await self._request("GET", f"/v2/backtesting/{backtest_id}/status")
        return parse_backtest_record(payload)

    async def get_backtest_details(self, backtest_id: str) -> BacktestRecord:
        payload = await self._request("GET", f"/v2/backtesting/{backtest_id}")
        record = parse_backtest_record(payload)
        if record.result_url:
            results = await self.fetch_result_json(record.result_url)
            return BacktestRecord(
                backtest_id=record.backtest_id,
                status=record.status,
                config=record.config,
                code=record.code,
                result_url=record.result_url,
                created_at=record.created_at,
                updated_at=record.updated_at,
                completed_at=record.completed_at,
                results=results,
            )
        return record

    async def delete_backtest(self, backtest_id: str) -> None:
        await self._request("DELETE", f"/v2/backtesting/{backtest_id}", allow_404=True)

    async def fetch_result_json(self, url: str) -> dict[str, Any]:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.get(url) as response:
                response.raise_for_status()
                return await response.json()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        allow_400: bool = False,
        allow_404: bool = False,
    ) -> dict[str, Any]:
        if not self.config.superior_trade_api_key:
            raise ConfigurationError("SUPERIOR_TRADE_API_KEY is required for /backtest.")

        url = f"{self.config.superior_trade_api_url}{path}"
        headers = {
            "x-api-key": self.config.superior_trade_api_key,
            "Content-Type": "application/json",
        }
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=45)) as session:
            async with session.request(method, url, headers=headers, params=params, json=json_body) as response:
                text = await response.text()
                if response.status == 404 and allow_404:
                    return {"error": "not_found", "message": text}
                if response.status == 400 and allow_400:
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError:
                        return {"error": "bad_request", "message": text}
                if response.status >= 400:
                    LOGGER.warning("Superior API request failed %s %s: %s", method, path, text[:800])
                    raise SuperiorApiError(extract_error_code(text))
                if not text.strip():
                    return {}
                return json.loads(text)


def parse_backtest_record(payload: dict[str, Any]) -> BacktestRecord:
    return BacktestRecord(
        backtest_id=str(payload.get("id", "")),
        status=str(payload.get("status", "unknown")),
        config=payload.get("config"),
        code=payload.get("code"),
        result_url=payload.get("result_url"),
        created_at=payload.get("created_at"),
        updated_at=payload.get("updated_at"),
        completed_at=payload.get("completed_at"),
        results=payload.get("results") if isinstance(payload.get("results"), dict) else None,
    )


def extract_error_code(text: str) -> str:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return "unknown_error"
    return str(payload.get("error") or payload.get("message") or "unknown_error")
