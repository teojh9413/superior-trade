from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from services.formatter import format_trade_asset_not_found, format_trade_response
from services.hyperliquid_service import looks_like_simple_asset

INVALID_TRADE_MESSAGE = "My role is to suggest trading strategies, please use /trade + name of desired asset"


class TradeCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="trade", description="Suggest a practical strategy for a single asset.")
    @app_commands.describe(asset_name="Simple asset name, for example btc, eth, tesla, or gold.")
    async def trade(self, interaction: discord.Interaction, asset_name: str) -> None:
        trimmed = asset_name.strip()
        if not looks_like_simple_asset(trimmed):
            await interaction.response.send_message(INVALID_TRADE_MESSAGE, ephemeral=True)
            return

        await interaction.response.defer(thinking=True)
        market = await self.bot.services.hyperliquid.resolve_asset(trimmed)
        if market is None:
            await interaction.followup.send(format_trade_asset_not_found(trimmed))
            return

        current_price = await self.bot.services.hyperliquid.get_mid_price(market.ticker)
        strategy = await self.bot.services.prompt.generate_trade_strategy(market, current_price=current_price)
        await interaction.followup.send(format_trade_response(strategy))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TradeCog(bot))
