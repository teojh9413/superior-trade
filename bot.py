from __future__ import annotations

import argparse
import asyncio
import logging
from dataclasses import dataclass
from typing import Iterable

import discord
from discord import app_commands
from discord.ext import commands

from core.config import AppConfig, load_config
from core.exceptions import ConfigurationError
from core.logging import configure_logging
from core.scheduler import DailyScheduler
from services.formatter import format_daily_brief
from services.hyperliquid_service import HyperliquidService
from services.news_service import NewsService
from services.prompt_service import PromptService

LOGGER = logging.getLogger(__name__)


class SuperiorCommandTree(app_commands.CommandTree):
    async def on_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        LOGGER.exception("App command failed: %s", error)
        message = "⚠️ Something went wrong while handling that command. Please try again shortly."
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


@dataclass(slots=True)
class ServiceContainer:
    news: NewsService
    hyperliquid: HyperliquidService
    prompt: PromptService


class SuperiorTradeBot(commands.Bot):
    def __init__(self, config: AppConfig, services: ServiceContainer) -> None:
        intents = discord.Intents.none()
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
            tree_cls=SuperiorCommandTree,
        )
        self.config = config
        self.services = services
        self.scheduler = DailyScheduler(
            timezone_name=config.timezone,
            hour=config.daily_brief_hour,
            minute=config.daily_brief_minute,
        )

    async def setup_hook(self) -> None:
        await self._load_extensions(
            [
                "cogs.trade",
                "cogs.brief",
                "cogs.admin",
            ]
        )
        self.scheduler.start(self._scheduled_brief_callback)
        LOGGER.info("Bot setup complete. Scheduler enabled for %s.", self.scheduler.describe())

    async def on_ready(self) -> None:
        synced = await self.tree.sync()
        LOGGER.info("Connected as %s. Synced %s slash commands.", self.user, len(synced))

    async def close(self) -> None:
        self.scheduler.stop()
        await super().close()

    async def _load_extensions(self, extensions: Iterable[str]) -> None:
        for extension in extensions:
            await self.load_extension(extension)
            LOGGER.info("Loaded extension %s", extension)

    async def _scheduled_brief_callback(self) -> None:
        channel_id = self.config.daily_post_channel_id
        if not channel_id:
            LOGGER.warning("Scheduled brief skipped because DAILY_POST_CHANNEL_ID is not configured.")
            return

        channel = self.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.fetch_channel(channel_id)
            except discord.DiscordException:
                LOGGER.exception("Unable to fetch configured daily brief channel %s.", channel_id)
                return

        if not isinstance(channel, discord.abc.Messageable):
            LOGGER.warning("Configured channel %s is not messageable.", channel_id)
            return

        brief = await self.services.news.generate_daily_brief()
        await channel.send(format_daily_brief(brief))
        LOGGER.info("Posted scheduled brief to channel %s.", channel_id)


def build_services(config: AppConfig) -> ServiceContainer:
    hyperliquid = HyperliquidService(config=config)
    prompt = PromptService(config=config)
    news = NewsService(config=config, hyperliquid_service=hyperliquid, prompt_service=prompt)
    return ServiceContainer(
        news=news,
        hyperliquid=hyperliquid,
        prompt=prompt,
    )


async def run_dry_mode(config: AppConfig, services: ServiceContainer) -> None:
    LOGGER.info("Dry-run mode enabled. No Discord connection will be made.")
    LOGGER.info("DDGS CLI resolved to: %s", config.ddgs_cli_path or "auto")
    LOGGER.info("Scheduler configured for %s.", f"{config.daily_brief_hour:02d}:{config.daily_brief_minute:02d} {config.timezone}")
    bot = SuperiorTradeBot(config=config, services=services)
    await bot.setup_hook()
    LOGGER.info("Dry-run loaded %s slash commands.", len(bot.tree.get_commands()))
    bot.scheduler.stop()
    await bot.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Superior.Trade Discord market brief bot")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load configuration and commands without connecting to Discord.",
    )
    return parser.parse_args()


async def async_main() -> None:
    args = parse_args()
    config = load_config()
    configure_logging(config.log_level)
    services = build_services(config)

    if args.dry_run or config.dry_run:
        await run_dry_mode(config, services)
        return

    if not config.discord_bot_token:
        raise ConfigurationError("DISCORD_BOT_TOKEN is required unless dry-run mode is enabled.")

    bot = SuperiorTradeBot(config=config, services=services)
    await bot.start(config.discord_bot_token)


def main() -> None:
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        LOGGER.info("Shutdown requested by user.")


if __name__ == "__main__":
    main()
