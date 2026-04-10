import asyncio

import discord
from discord.ext import commands

from cogs.brief import BriefCog


class DummyBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(command_prefix="!", intents=discord.Intents.none())


def test_brief_cog_registers_only_dailybrief() -> None:
    async def run() -> None:
        bot = DummyBot()
        try:
            await bot.add_cog(BriefCog(bot))
            assert [command.name for command in bot.tree.get_commands()] == ["dailybrief"]
        finally:
            await bot.close()

    asyncio.run(run())
