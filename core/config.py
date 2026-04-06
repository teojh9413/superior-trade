from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


def _to_bool(value: str | bool | None, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class AppConfig:
    base_dir: Path
    prompts_dir: Path
    discord_bot_token: str | None
    daily_post_channel_id: int | None
    dry_run: bool
    log_level: str
    timezone: str
    daily_brief_hour: int
    daily_brief_minute: int
    ddgs_cli_path: str | None
    hyperliquid_info_url: str
    config_file: Path | None


def load_config() -> AppConfig:
    base_dir = Path(__file__).resolve().parent.parent
    load_dotenv(base_dir / ".env")

    config_file_value = os.getenv("CONFIG_FILE", "config.local.json").strip()
    config_file = (base_dir / config_file_value) if config_file_value else None
    file_overrides = _load_json_file(config_file) if config_file and config_file.exists() else {}

    def pick(name: str, default: Any = None) -> Any:
        return file_overrides.get(name, os.getenv(name, default))

    channel_id_value = pick("DAILY_POST_CHANNEL_ID")
    channel_id = int(channel_id_value) if channel_id_value else None

    return AppConfig(
        base_dir=base_dir,
        prompts_dir=base_dir / "prompts",
        discord_bot_token=pick("DISCORD_BOT_TOKEN"),
        daily_post_channel_id=channel_id,
        dry_run=_to_bool(pick("DRY_RUN", False), default=False),
        log_level=str(pick("LOG_LEVEL", "INFO")).upper(),
        timezone=str(pick("TIMEZONE", "Asia/Singapore")),
        daily_brief_hour=int(pick("DAILY_BRIEF_HOUR", 15)),
        daily_brief_minute=int(pick("DAILY_BRIEF_MINUTE", 0)),
        ddgs_cli_path=pick("DDGS_CLI_PATH"),
        hyperliquid_info_url=str(pick("HYPERLIQUID_INFO_URL", "https://api.hyperliquid.xyz/info")),
        config_file=config_file,
    )


def _load_json_file(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)
