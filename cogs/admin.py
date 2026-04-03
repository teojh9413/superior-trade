from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from core.formatting import format_health_status


class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="health", description="Show basic bot health information.")
    async def health(self, interaction: discord.Interaction) -> None:
        response = format_health_status(
            knowledge_sources=self.bot.services.knowledge.list_sources(),
            scheduler_description=self.bot.scheduler.describe(),
            dry_run=self.bot.config.dry_run,
            llm_configured=self.bot.services.llm.is_configured(),
            news_configured=bool(self.bot.config.news_api_key),
        )
        await interaction.response.send_message(response, ephemeral=True)

    @app_commands.command(name="reloadkb", description="Reload local markdown knowledge files.")
    async def reloadkb(self, interaction: discord.Interaction) -> None:
        self.bot.services.knowledge.reload()
        response = format_health_status(
            knowledge_sources=self.bot.services.knowledge.list_sources(),
            scheduler_description=self.bot.scheduler.describe(),
            dry_run=self.bot.config.dry_run,
            llm_configured=self.bot.services.llm.is_configured(),
            news_configured=bool(self.bot.config.news_api_key),
            heading="⚙️ Knowledge Reloaded",
        )
        await interaction.response.send_message(response, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AdminCog(bot))
