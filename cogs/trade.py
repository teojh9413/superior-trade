from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from core.formatting import format_trade_response


class TradeCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="trade", description="Generate a structured trade prompt preview.")
    @app_commands.describe(asset_or_market="Asset, market, or pair to map.")
    async def trade(self, interaction: discord.Interaction, asset_or_market: str) -> None:
        await interaction.response.defer(thinking=True)
        mapping = self.bot.services.pair_mapper.resolve(asset_or_market)
        strategy = await self.bot.services.llm.generate_trade_prompt(
            asset_or_market=asset_or_market,
            mapping=mapping,
        )
        response = format_trade_response(
            asset_or_market=asset_or_market,
            mapping=mapping,
            strategy=strategy,
        )
        await interaction.followup.send(response)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TradeCog(bot))
