from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import pagify
import discord
from typing import Callable, Any


def check_all(*predicates: Callable[[commands.Context], Any]):
    """
    Decorator that requires all provided predicates to be true.
    Usage: @check_all(predicate1, predicate2, predicate3)
    """
    async def predicate(ctx):
        for pred in predicates:
            if not await pred(ctx):
                return False
        return True
    return commands.check(predicate)


async def has_update_command_role(ctx: commands.Context) -> bool:
    """
    Checks if the user has the update command role.
    """
    if ctx.guild is None:
        return False
    uc_role = discord.utils.get(ctx.guild.roles, name="Update Command")
    jc_role = discord.utils.get(ctx.guild.roles, name="Junior Command")
    if uc_role is None:
        return False
    return (uc_role in ctx.author.roles) or (jc_role in ctx.author.roles) or (ctx.author.id == 300681028920541199)


async def has_liberator_role(ctx: commands.Context) -> bool:
    """
    Checks if the user has the update command role.
    """
    if ctx.guild is None:
        return False
    liberator_role = discord.utils.get(ctx.guild.roles, name="Liberator")
    return liberator_role in ctx.author.roles


async def has_updating_role(ctx: commands.Context) -> bool:
    """
    Checks if the user does not have the Updating role.
    """
    if ctx.guild is None:
        return False
    updating_role = discord.utils.get(ctx.guild.roles, name="Updating")
    return updating_role in ctx.author.roles


async def is_update_planning_channel(ctx: commands.Context) -> bool:
    """
    Checks if the command is being used in the Update Planning channel.
    """
    if ctx.guild is None:
        return False
    update_planning_channel = discord.utils.get(ctx.guild.channels, name="update-planning")
    return ctx.channel == update_planning_channel


class Whipping(commands.Cog):

    def __init__(self, bot: Red, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

    def cog_unload(self):
        pass



