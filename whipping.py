from redbot.core import commands, Config
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import pagify, box
import discord
from typing import Callable, Any, Dict, List, Optional, Set
import asyncio
import random
from datetime import datetime, timedelta
import json


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
    """Manages DM whipping operations for Libcord Update Command"""

    def __init__(self, bot: Red, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot
        self.config = Config.get_conf(self, identifier=12345678901234567890)

        # Guild config defaults
        default_guild = {
            "assignments": {},  # {uc_member_id: [assigned_user_ids]}
            "progress": {},  # {uc_member_id: {user_id: bool}}
            "update_progress": {},  # {user_id: [uc_members_who_messaged]}
            "stripe_count": 3,  # Number of UC members assigned to each user
            "zen_template": "Hey! Just establishing a DM connection for future updates. You can ignore this message.",
            "whip_template": "Update incoming! Check the update channel for details.",
        }

        self.config.register_guild(**default_guild)

    def cog_unload(self):
        pass

    def _safe_pagify_mentions(self, mention_list: List[str], page_length: int = 800) -> List[str]:
        """Custom pagify that ensures Discord mentions are not split across pages"""
        if not mention_list:
            return []

        pages = []
        current_page = []
        current_length = 0

        for mention in mention_list:
            # Account for space between mentions
            mention_length = len(mention) + 1 if current_page else len(mention)

            # If adding this mention would exceed the page length, start a new page
            if current_length + mention_length > page_length:
                # Join the current page and add it to pages
                pages.append(" ".join(current_page))
                current_page = [mention]
                current_length = len(mention)
            else:
                current_page.append(mention)
                current_length += mention_length

        # Add the last page if it has content
        if current_page:
            pages.append(" ".join(current_page))

        return pages

    def _stripe_users(self, uc_members: List[int], libcord_members: List[int], stripe_count: int = 3) -> Dict[
        int, List[int]]:
        """RAID-like striping algorithm to distribute users among UC members"""
        if not uc_members or not libcord_members:
            return {}

        assignments = {uc_id: [] for uc_id in uc_members}

        # Shuffle to ensure random distribution
        shuffled_members = libcord_members.copy()
        random.shuffle(shuffled_members)

        # Assign each user to multiple UC members (striping)
        for i, user_id in enumerate(shuffled_members):
            # Select UC members for this user
            start_idx = (i * stripe_count) % len(uc_members)
            for j in range(stripe_count):
                uc_idx = (start_idx + j) % len(uc_members)
                assignments[uc_members[uc_idx]].append(user_id)

        return assignments

    @commands.group(name="whip")
    @commands.guild_only()
    @commands.check(has_update_command_role)
    async def whip_group(self, ctx: commands.Context):
        """Whipping management commands"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @whip_group.command(name="setup")
    @commands.is_owner()
    async def setup_assignments(self, ctx: commands.Context, stripe_count: int = 3):
        """Set up initial user assignments with RAID-like striping"""
        guild = ctx.guild
        await self.config.guild(guild).stripe_count.set(stripe_count)

        # Get all UC members
        uc_role = discord.utils.get(guild.roles, name="Update Command")
        jc_role = discord.utils.get(guild.roles, name="Junior Command")
        if not uc_role:
            await ctx.send("Update Command role not found!")
            return

        uc_members = [m.id for m in guild.members if uc_role in m.roles or (jc_role and jc_role in m.roles)]

        # Get all regular members (excluding bots and UC)
        libcord_members = [m.id for m in guild.members if
                           not m.bot and uc_role not in m.roles and (not jc_role or jc_role not in m.roles)]

        # Create assignments
        assignments = self._stripe_users(uc_members, libcord_members, stripe_count)

        await self.config.guild(guild).assignments.set(assignments)

        # Initialize progress tracking
        progress = {}
        for uc_id in uc_members:
            progress[str(uc_id)] = {str(user_id): False for user_id in assignments.get(uc_id, [])}

        await self.config.guild(guild).progress.set(progress)

        await ctx.send(f"✅ Assignments created!\n"
                       f"- {len(uc_members)} UC members\n"
                       f"- {len(libcord_members)} Libcord members\n"
                       f"- Each user assigned to {stripe_count} UC members")

    @whip_group.command(name="zen")
    @commands.check(has_update_command_role)
    async def zen_mode(self, ctx: commands.Context, limit: Optional[int] = None):
        """Get list of users to message for establishing DM connections"""
        guild = ctx.guild
        user_id = str(ctx.author.id)

        assignments = await self.config.guild(guild).assignments()
        progress = await self.config.guild(guild).progress()
        zen_template = await self.config.guild(guild).zen_template()

        if user_id not in assignments:
            await ctx.send("You don't have any assigned users!")
            return

        my_assignments = assignments[user_id]
        my_progress = progress.get(user_id, {})

        # Get unmessaged users
        unmessaged = []
        for assigned_id in my_assignments:
            if not my_progress.get(str(assigned_id), False):
                member = guild.get_member(int(assigned_id))
                if member:
                    unmessaged.append(member)

        if not unmessaged:
            await ctx.send("✅ You've already messaged all your assigned users!")
            return

        if limit:
            unmessaged = unmessaged[:limit]

        # Create output
        user_list = "\\n".join([f"• {member.mention} ({member.name})" for member in unmessaged])

        embed = discord.Embed(
            title="🧘 Zen Mode - Establish DM Connections",
            description=f"You have **{len(unmessaged)}** users to message:",
            color=discord.Color.blue()
        )

        for page in pagify(user_list, page_length=1000):
            embed.add_field(name="Users", value=page, inline=False)

        embed.add_field(name="Template", value=f"```{zen_template}```", inline=False)
        embed.set_footer(text="Use [p]whip progress <@user> to mark as complete")

        await ctx.send(embed=embed)

    @whip_group.command(name="whipmode", aliases=["start"])
    @commands.check(has_update_command_role)
    async def whipping_mode(self, ctx: commands.Context, online_only: bool = True):
        """Start whipping mode for an update"""
        guild = ctx.guild
        user_id = str(ctx.author.id)

        assignments = await self.config.guild(guild).assignments()
        whip_template = await self.config.guild(guild).whip_template()

        if user_id not in assignments:
            await ctx.send("You don't have any assigned users!")
            return

        my_assignments = assignments[user_id]

        # Get the Updating role
        updating_role = discord.utils.get(guild.roles, name="Updating")

        # Get users to message
        to_message = []
        for assigned_id in my_assignments:
            member = guild.get_member(int(assigned_id))
            if member:
                # Skip users with the Updating role
                if updating_role and updating_role in member.roles:
                    continue
                if not online_only or member.status != discord.Status.offline:
                    to_message.append(member)

        if not to_message:
            await ctx.send("No users to message!")
            return

        user_list = "\\n".join([f"• {member.mention} ({member.name}) - {member.status}" for member in to_message])

        embed = discord.Embed(
            title="⚡ Whipping Mode - Update Active",
            description=f"{'Online only' if online_only else 'All users'}\\n"
                        f"**{len(to_message)}** users to message:",
            color=discord.Color.red()
        )

        for page in pagify(user_list, page_length=1000):
            embed.add_field(name="Users", value=page, inline=False)

        embed.add_field(name="Template", value=f"```{whip_template}```", inline=False)
        embed.set_footer(text="Use [p]whip done <@user> to mark as complete")

        await ctx.send(embed=embed)

    @whip_group.command(name="progress")
    @commands.check(has_update_command_role)
    async def mark_progress(self, ctx: commands.Context, user: discord.Member):
        """Mark a user as messaged in zen mode"""
        guild = ctx.guild
        uc_id = str(ctx.author.id)
        user_id = str(user.id)

        progress = await self.config.guild(guild).progress()

        if uc_id not in progress:
            progress[uc_id] = {}

        progress[uc_id][user_id] = True
        await self.config.guild(guild).progress.set(progress)

        await ctx.send(f"✅ Marked {user.mention} as messaged in your progress.")

    @whip_group.command(name="done")
    @commands.check(has_update_command_role)
    async def mark_whip_done(self, ctx: commands.Context, user: discord.Member):
        """Mark a user as messaged during the current update"""
        guild = ctx.guild
        uc_id = str(ctx.author.id)
        user_id = str(user.id)

        update_progress = await self.config.guild(guild).update_progress()

        if user_id not in update_progress:
            update_progress[user_id] = []

        if uc_id not in update_progress[user_id]:
            update_progress[user_id].append(uc_id)

        await self.config.guild(guild).update_progress.set(update_progress)

        await ctx.send(f"✅ Marked {user.mention} as messaged for the current update.")

    @whip_group.command(name="mystats")
    @commands.check(has_update_command_role)
    async def my_stats(self, ctx: commands.Context):
        """View your assignment statistics"""
        guild = ctx.guild
        user_id = str(ctx.author.id)

        assignments = await self.config.guild(guild).assignments()
        progress = await self.config.guild(guild).progress()

        if user_id not in assignments:
            await ctx.send("You don't have any assigned users!")
            return

        my_assignments = assignments[user_id]
        my_progress = progress.get(user_id, {})

        total = len(my_assignments)
        messaged = sum(1 for uid in my_assignments if my_progress.get(str(uid), False))

        embed = discord.Embed(
            title="📊 Your Whipping Statistics",
            color=discord.Color.green()
        )

        embed.add_field(name="Total Assigned", value=str(total), inline=True)
        embed.add_field(name="Messaged (Zen)", value=str(messaged), inline=True)
        embed.add_field(name="Remaining", value=str(total - messaged), inline=True)
        embed.add_field(name="Progress", value=f"{messaged / total * 100:.1f}%" if total > 0 else "N/A", inline=True)

        await ctx.send(embed=embed)

    @whip_group.command(name="templates")
    @commands.is_owner()
    async def manage_templates(self, ctx: commands.Context, template_type: str = None, *, new_template: str = None):
        """View or update message templates"""
        guild = ctx.guild

        if template_type is None:
            # Show current templates
            zen = await self.config.guild(guild).zen_template()
            whip = await self.config.guild(guild).whip_template()

            embed = discord.Embed(
                title="📝 Current Templates",
                color=discord.Color.blue()
            )
            embed.add_field(name="Zen Mode", value=f"```{zen}```", inline=False)
            embed.add_field(name="Whip Mode", value=f"```{whip}```", inline=False)

            await ctx.send(embed=embed)

        elif template_type.lower() in ["zen", "whip"] and new_template:
            if template_type.lower() == "zen":
                await self.config.guild(guild).zen_template.set(new_template)
            else:
                await self.config.guild(guild).whip_template.set(new_template)

            await ctx.send(f"✅ Updated {template_type} template!")
        else:
            await ctx.send("Usage: `[p]whip templates [zen|whip] [new template]`")

    @whip_group.command(name="report")
    @commands.check(has_update_command_role)
    async def update_report(self, ctx: commands.Context):
        """View report for the current update"""
        guild = ctx.guild

        update_progress = await self.config.guild(guild).update_progress()

        if not update_progress:
            await ctx.send("No update data found!")
            return

        # Calculate statistics
        total_messaged = len(update_progress)
        uc_stats = {}

        for user_id, uc_members in update_progress.items():
            for uc_id in uc_members:
                if uc_id not in uc_stats:
                    uc_stats[uc_id] = 0
                uc_stats[uc_id] += 1

        embed = discord.Embed(
            title="📊 Current Update Report",
            description=f"Total users messaged: **{total_messaged}**",
            color=discord.Color.gold()
        )

        # UC member statistics
        stats_text = ""
        for uc_id, count in sorted(uc_stats.items(), key=lambda x: x[1], reverse=True):
            member = guild.get_member(int(uc_id))
            name = member.name if member else f"Unknown ({uc_id})"
            stats_text += f"• {name}: {count} messages\n"

        if stats_text:
            for page in pagify(stats_text, page_length=1000):
                embed.add_field(name="UC Member Stats", value=page, inline=False)

        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Assign new members to UC members using striping"""
        if member.bot:
            return

        guild = member.guild
        assignments = await self.config.guild(guild).assignments()
        stripe_count = await self.config.guild(guild).stripe_count()

        # Get UC members
        uc_role = discord.utils.get(guild.roles, name="Update Command")
        jc_role = discord.utils.get(guild.roles, name="Junior Command")
        if not uc_role:
            return

        uc_members = [m.id for m in guild.members if uc_role in m.roles or (jc_role and jc_role in m.roles)]

        if not uc_members:
            return

        # Assign new member to UC members
        random.shuffle(uc_members)
        selected_uc = uc_members[:stripe_count]

        for uc_id in selected_uc:
            uc_id_str = str(uc_id)
            if uc_id_str not in assignments:
                assignments[uc_id_str] = []
            if member.id not in assignments[uc_id_str]:
                assignments[uc_id_str].append(member.id)

        await self.config.guild(guild).assignments.set(assignments)

        # Initialize progress for new member
        progress = await self.config.guild(guild).progress()
        for uc_id in selected_uc:
            uc_id_str = str(uc_id)
            if uc_id_str not in progress:
                progress[uc_id_str] = {}
            progress[uc_id_str][str(member.id)] = False

        await self.config.guild(guild).progress.set(progress)

    @whip_group.command(name="assignments")
    @commands.check(has_update_command_role)
    async def view_assignments(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """View user assignments"""
        guild = ctx.guild
        assignments = await self.config.guild(guild).assignments()

        if member:
            # View assignments for a specific UC member
            member_id = str(member.id)
            if member_id not in assignments:
                await ctx.send(f"{member.mention} has no assigned users.")
                return

            assigned_users = assignments[member_id]
            embed = discord.Embed(
                title=f"📋 Assignments for {member.name}",
                description=f"Total: **{len(assigned_users)}** users",
                color=discord.Color.blue()
            )

            user_list = []
            for uid in assigned_users:
                user = guild.get_member(int(uid))
                if user:
                    user_list.append(f"{user.mention}")

            # Use custom pagify to ensure mentions aren't split
            pages = self._safe_pagify_mentions(user_list, page_length=1000)
            for page in pages:
                embed.add_field(name="Assigned Users", value=page, inline=False)

            await ctx.send(embed=embed)
        else:
            # Overview of all assignments
            embed = discord.Embed(
                title="📊 Assignment Overview",
                color=discord.Color.green()
            )

            stats = []
            for uc_id, users in assignments.items():
                member = guild.get_member(int(uc_id))
                if member:
                    stats.append(f"• {member.mention}: {len(users)} users")

            for page in pagify("\\n".join(stats), page_length=1000):
                embed.add_field(name="UC Member Assignments", value=page, inline=False)

            await ctx.send(embed=embed)

    @whip_group.command(name="reassign")
    @commands.is_owner()
    async def reassign_user(self, ctx: commands.Context, user: discord.Member, from_uc: discord.Member,
                            to_uc: discord.Member):
        """Reassign a user from one UC member to another"""
        guild = ctx.guild
        assignments = await self.config.guild(guild).assignments()
        progress = await self.config.guild(guild).progress()

        from_id = str(from_uc.id)
        to_id = str(to_uc.id)
        user_id = user.id

        # Check if from_uc has the user
        if from_id not in assignments or user_id not in assignments[from_id]:
            await ctx.send(f"{user.mention} is not assigned to {from_uc.mention}")
            return

        # Remove from old UC member
        assignments[from_id].remove(user_id)
        if from_id in progress and str(user_id) in progress[from_id]:
            del progress[from_id][str(user_id)]

        # Add to new UC member
        if to_id not in assignments:
            assignments[to_id] = []
        if user_id not in assignments[to_id]:
            assignments[to_id].append(user_id)

        if to_id not in progress:
            progress[to_id] = {}
        progress[to_id][str(user_id)] = False

        await self.config.guild(guild).assignments.set(assignments)
        await self.config.guild(guild).progress.set(progress)

        await ctx.send(f"✅ Reassigned {user.mention} from {from_uc.mention} to {to_uc.mention}")

    @whip_group.command(name="whois")
    @commands.check(has_update_command_role)
    async def who_is_assigned(self, ctx: commands.Context, user: discord.Member):
        """Find which Update Command members a user is assigned to"""
        guild = ctx.guild
        assignments = await self.config.guild(guild).assignments()
        progress = await self.config.guild(guild).progress()
        
        # Find all UC members assigned to this user
        assigned_uc_members = []
        user_id = user.id
        
        for uc_id_str, assigned_users in assignments.items():
            if user_id in assigned_users:
                uc_member = guild.get_member(int(uc_id_str))
                if uc_member:
                    # Check if this UC member has messaged the user in zen mode
                    has_messaged = progress.get(uc_id_str, {}).get(str(user_id), False)
                    assigned_uc_members.append((uc_member, has_messaged))
        
        if not assigned_uc_members:
            await ctx.send(f"{user.mention} is not assigned to any Update Command members.")
            return
        
        embed = discord.Embed(
            title=f"🔍 UC Members Assigned to {user.name}",
            description=f"{user.mention} is assigned to **{len(assigned_uc_members)}** UC members:",
            color=discord.Color.blue()
        )
        
        # Sort by name for consistent display
        assigned_uc_members.sort(key=lambda x: x[0].name.lower())
        
        uc_list = []
        for uc_member, has_messaged in assigned_uc_members:
            status = "✅" if has_messaged else "❌"
            uc_list.append(f"{status} {uc_member.mention} ({uc_member.name})")
        
        embed.add_field(
            name="Assigned UC Members",
            value="\n".join(uc_list),
            inline=False
        )
        
        embed.set_footer(text="✅ = Already messaged in zen mode | ❌ = Not yet messaged")
        
        await ctx.send(embed=embed)
    
    @whip_group.command(name="zensilent")
    @commands.check(has_update_command_role)
    async def zen_mode_silent(self, ctx: commands.Context, limit: Optional[int] = None):
        """Get list of users to message with @silent prefix for minimal disruption"""
        guild = ctx.guild
        user_id = str(ctx.author.id)

        assignments = await self.config.guild(guild).assignments()
        progress = await self.config.guild(guild).progress()
        zen_template = await self.config.guild(guild).zen_template()

        if user_id not in assignments:
            await ctx.send("You don't have any assigned users!")
            return

        my_assignments = assignments[user_id]
        my_progress = progress.get(user_id, {})

        # Get unmessaged users
        unmessaged = []
        for assigned_id in my_assignments:
            if not my_progress.get(str(assigned_id), False):
                member = guild.get_member(int(assigned_id))
                if member:
                    unmessaged.append(member)

        if not unmessaged:
            await ctx.send("✅ You've already messaged all your assigned users!")
            return

        if limit:
            unmessaged = unmessaged[:limit]

        # Create output with @silent prefix
        user_list = "\\n".join([f"• {member.mention} ({member.name})" for member in unmessaged])

        embed = discord.Embed(
            title="🤫 Silent Zen Mode - Establish DM Connections",
            description=f"You have **{len(unmessaged)}** users to message:\\n"
                        f"**Note:** Use @silent prefix to minimize disruption",
            color=discord.Color.blue()
        )

        for page in pagify(user_list, page_length=1000):
            embed.add_field(name="Users", value=page, inline=False)

        # Add @silent to template
        silent_template = f"@silent {zen_template}"
        embed.add_field(name="Silent Template", value=f"```{silent_template}```", inline=False)
        embed.set_footer(text="Use [p]whip progress <@user> to mark as complete")

        await ctx.send(embed=embed)
    
    @whip_group.command(name="check_invalid")
    @commands.is_owner()
    async def check_invalid_assignments(self, ctx: commands.Context, fix: bool = False):
        """Check for UC/JC members who no longer have their roles and optionally fix assignments"""
        guild = ctx.guild
        assignments = await self.config.guild(guild).assignments()
        progress = await self.config.guild(guild).progress()
        stripe_count = await self.config.guild(guild).stripe_count()
        
        # Get UC and JC roles
        uc_role = discord.utils.get(guild.roles, name="Update Command")
        jc_role = discord.utils.get(guild.roles, name="Junior Command")
        
        if not uc_role:
            await ctx.send("Update Command role not found!")
            return
        
        # Find all UC/JC members who have assignments but no longer have the role
        invalid_uc_members = []
        valid_uc_members = []
        
        for uc_id_str in assignments.keys():
            member = guild.get_member(int(uc_id_str))
            if member:
                has_uc_role = uc_role in member.roles
                has_jc_role = jc_role and jc_role in member.roles
                
                if has_uc_role or has_jc_role:
                    valid_uc_members.append(int(uc_id_str))
                else:
                    invalid_uc_members.append((uc_id_str, member, len(assignments[uc_id_str])))
            else:
                # Member no longer in guild
                invalid_uc_members.append((uc_id_str, None, len(assignments[uc_id_str])))
        
        if not invalid_uc_members:
            await ctx.send("✅ All assignments are valid! No UC/JC members without roles found.")
            return
        
        # Create report embed
        embed = discord.Embed(
            title="🚨 Invalid UC/JC Assignments Found",
            description=f"Found **{len(invalid_uc_members)}** UC/JC members without proper roles",
            color=discord.Color.red()
        )
        
        # List invalid members
        invalid_list = []
        total_users_affected = 0
        for uc_id_str, member, user_count in invalid_uc_members:
            if member:
                invalid_list.append(f"• {member.mention} ({member.name}): {user_count} users")
            else:
                invalid_list.append(f"• Unknown (ID: {uc_id_str}): {user_count} users")
            total_users_affected += user_count
        
        embed.add_field(
            name="Invalid UC/JC Members",
            value="\n".join(invalid_list),
            inline=False
        )
        
        embed.add_field(
            name="Total Users Affected",
            value=str(total_users_affected),
            inline=True
        )
        
        embed.add_field(
            name="Valid UC/JC Members",
            value=str(len(valid_uc_members)),
            inline=True
        )
        
        if not fix:
            embed.set_footer(text="Run with fix=True to redistribute affected users")
            await ctx.send(embed=embed)
            return
        
        # Fix assignments if requested
        if not valid_uc_members:
            await ctx.send("❌ Cannot fix assignments: No valid UC/JC members found!")
            return
        
        # Collect all users that need reassignment
        users_to_reassign = []
        for uc_id_str, _, _ in invalid_uc_members:
            users_to_reassign.extend(assignments[uc_id_str])
            # Remove invalid UC member from assignments
            del assignments[uc_id_str]
            # Remove from progress tracking
            if uc_id_str in progress:
                del progress[uc_id_str]
        
        # Remove duplicates
        users_to_reassign = list(set(users_to_reassign))
        
        # Redistribute users using the striping algorithm
        new_assignments = self._stripe_users(valid_uc_members, users_to_reassign, stripe_count)
        
        # Merge new assignments with existing ones
        for uc_id, user_list in new_assignments.items():
            uc_id_str = str(uc_id)
            if uc_id_str not in assignments:
                assignments[uc_id_str] = []
            
            for user_id in user_list:
                if user_id not in assignments[uc_id_str]:
                    assignments[uc_id_str].append(user_id)
                    
                    # Initialize progress for new assignment
                    if uc_id_str not in progress:
                        progress[uc_id_str] = {}
                    progress[uc_id_str][str(user_id)] = False
        
        # Save updated assignments and progress
        await self.config.guild(guild).assignments.set(assignments)
        await self.config.guild(guild).progress.set(progress)
        
        # Create success embed
        success_embed = discord.Embed(
            title="✅ Assignments Fixed",
            description=f"Successfully redistributed **{len(users_to_reassign)}** users",
            color=discord.Color.green()
        )
        
        success_embed.add_field(
            name="Removed UC/JC Members",
            value=str(len(invalid_uc_members)),
            inline=True
        )
        
        success_embed.add_field(
            name="Users Redistributed",
            value=str(len(users_to_reassign)),
            inline=True
        )
        
        success_embed.add_field(
            name="Active UC/JC Members",
            value=str(len(valid_uc_members)),
            inline=True
        )
        
        await ctx.send(embed=success_embed)
