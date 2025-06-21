from redbot.core.bot import Red
from .whipping import Whipping


async def setup(bot: Red):
    cog = Whipping(bot)
    await bot.add_cog(cog)
