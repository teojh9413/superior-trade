from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from core.formatting import format_ask_response


class AskCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="ask", description="Ask a Superior.Trade product question.")
    @app_commands.describe(question="Your question about Superior.Trade.")
    async def ask(self, interaction: discord.Interaction, question: str) -> None:
        await interaction.response.defer(thinking=True)
        sections = self.bot.services.knowledge.search(question, top_k=3)
        context = self.bot.services.knowledge.build_context_block(question, top_k=4)
        website_snippets = await self.bot.services.website.fetch_site_snippets(question)
        github_snippets = await self.bot.services.github.fetch_repo_snippets(question)
        result = await self.bot.services.llm.generate_ask_response(
            question=question,
            knowledge_sections=sections,
            knowledge_context=context,
            website_snippets=website_snippets,
            github_snippets=github_snippets,
        )
        response = format_ask_response(question=question, result=result)
        await interaction.followup.send(response)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AskCog(bot))
