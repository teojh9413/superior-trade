from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from core.formatting import format_daily_brief


class BriefCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="briefnow", description="Preview the daily market brief.")
    async def briefnow(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        brief = await self.bot.services.news.generate_daily_brief(
            llm_service=self.bot.services.llm,
            pair_mapper=self.bot.services.pair_mapper,
        )
        message = format_daily_brief(brief)
        await interaction.followup.send(message)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BriefCog(bot))
