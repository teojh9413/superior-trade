from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from core.exceptions import BacktestRunError, ConfigurationError, SuperiorApiError
from services.formatter import format_backtest_failure, format_backtest_success
from services.hyperliquid_service import looks_like_simple_asset

INVALID_BACKTEST_MESSAGE = "My role is to run backtests, please use /backtest + name of desired asset"


class BacktestCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="backtest", description="Run seven fixed backtests and return the best result.")
    @app_commands.describe(asset_name="Simple asset name, for example btc, eth, CL, or tesla.")
    async def backtest(self, interaction: discord.Interaction, asset_name: str) -> None:
        trimmed = asset_name.strip()
        if not looks_like_simple_asset(trimmed):
            await interaction.response.send_message(INVALID_BACKTEST_MESSAGE, ephemeral=True)
            return

        await interaction.response.defer(thinking=True)
        try:
            _, best = await self.bot.services.backtest.run_best_backtest_for_asset(trimmed)
        except BacktestRunError as error:
            await interaction.followup.send(format_backtest_failure(str(error)))
            return
        except ConfigurationError:
            await interaction.followup.send(format_backtest_failure("Backtesting is not configured right now."))
            return
        except SuperiorApiError:
            await interaction.followup.send(
                format_backtest_failure("Backtesting is temporarily unavailable right now. Please try again shortly.")
            )
            return

        await interaction.followup.send(format_backtest_success(best))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BacktestCog(bot))
