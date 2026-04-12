from __future__ import annotations

from discord.ext import commands

from cogs.music.cog import MusicCog


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MusicCog(bot))
