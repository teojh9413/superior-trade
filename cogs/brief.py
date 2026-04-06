from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from services.formatter import format_daily_brief


class BriefCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="briefnow", description="Generate the current 24-hour market brief.")
    async def briefnow(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        brief = await self.bot.services.news.generate_daily_brief()
        await interaction.followup.send(format_daily_brief(brief))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BriefCog(bot))
