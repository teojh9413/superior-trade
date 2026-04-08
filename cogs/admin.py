from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from services.formatter import format_health_status


class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="health", description="Show basic bot health information.")
    async def health(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        response = format_health_status(
            scheduler_description=self.bot.scheduler.describe(),
            dry_run=self.bot.config.dry_run,
            market_count=await self.bot.services.hyperliquid.market_count(),
            superior_api_configured=self.bot.services.superior_api.is_configured(),
        )
        await interaction.followup.send(response, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AdminCog(bot))
