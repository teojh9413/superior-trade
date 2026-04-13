from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class RegistryEntry:
    backtest_id: str
    strategy_name: str
    ticker: str
    created_at: str
    status: str


class BacktestRegistry:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def list_entries(self) -> list[RegistryEntry]:
        payload = self._read()
        return [RegistryEntry(**item) for item in payload.get("entries", [])]

    def upsert(self, entry: RegistryEntry) -> None:
        payload = self._read()
        entries = [item for item in payload.get("entries", []) if item.get("backtest_id") != entry.backtest_id]
        entries.append(asdict(entry))
        payload["entries"] = entries
        self._write(payload)

    def remove(self, backtest_id: str) -> None:
        payload = self._read()
        payload["entries"] = [item for item in payload.get("entries", []) if item.get("backtest_id") != backtest_id]
        self._write(payload)

    def find(self, backtest_id: str) -> RegistryEntry | None:
        for entry in self.list_entries():
            if entry.backtest_id == backtest_id:
                return entry
        return None

    def get_state_value(self, key: str, default: Any = None) -> Any:
        payload = self._read()
        return payload.get("state", {}).get(key, default)

    def set_state_value(self, key: str, value: Any) -> None:
        payload = self._read()
        state = payload.get("state", {})
        state[key] = value
        payload["state"] = state
        self._write(payload)

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"entries": [], "state": {}}
        with self.path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        payload.setdefault("entries", [])
        payload.setdefault("state", {})
        return payload

    def _write(self, payload: dict[str, Any]) -> None:
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
