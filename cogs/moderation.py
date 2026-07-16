import os
from datetime import datetime
from typing import Optional

import discord
from discord.ext import commands
from discord.ext.commands import Context


class Moderation(commands.Cog, name="moderation"):
    def __init__(self, bot) -> None:
        self.bot = bot

    @commands.hybrid_command(
        name="purge",
        description="Delete a number of messages.",
    )
    @discord.app_commands.describe(
        amount="The number of messages to delete.",
        channel="The channel to purge messages from (defaults to current channel).",
    )
    @commands.has_guild_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def purge(self, context: Context, amount: int, channel: Optional[discord.TextChannel] = None) -> None:
        target_channel = channel or context.channel
        embed = discord.Embed(title="Deleting messages...", description="Please wait...")
        reply_msg = await context.reply(embed=embed)
        limit = amount if channel else amount + 1
        purged_messages = await target_channel.purge(limit=limit)
        deleted = len(purged_messages) if channel else len(purged_messages) - 1
        embed = discord.Embed(description=f"**{context.author}** cleared **{deleted}** messages in {target_channel.mention}!")
        await context.reply(embed=embed)

    @commands.hybrid_command(
        name="purgekeywords",
        description="Delete a number of messages containing specified keywords (comma-separated).",
    )
    @discord.app_commands.describe(
        amount="The number of messages to delete.",
        channel="The channel to purge messages from (defaults to current channel).",
        keywords="Comma-separated list of keywords to filter by.",
    )
    @commands.has_guild_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def purgekeywords(self, context: Context, amount: int, channel: Optional[discord.TextChannel] = None, *, keywords: str) -> None:
        target_channel = channel or context.channel
        is_same_channel = target_channel == context.channel
        embed = discord.Embed(title="Deleting messages...", description="Please wait...")
        reply_msg = await context.reply(embed=embed)
        
        keywords_list = [k.strip().lower() for k in keywords.split(',') if k.strip()]

        def check(message):
            if is_same_channel:
                if context.message and message.id == context.message.id:
                    return True
                if reply_msg and message.id == reply_msg.id:
                    return True
            return any(keyword in message.content.lower() for keyword in keywords_list)

        limit = amount + 2 if is_same_channel else amount
        purged_messages = await target_channel.purge(limit=limit, check=check)
        
        if is_same_channel:
            deleted_count = len([m for m in purged_messages if m.id not in (getattr(context.message, 'id', None), getattr(reply_msg, 'id', None))])
        else:
            deleted_count = len(purged_messages)
        embed = discord.Embed(description=f"**{context.author}** cleared **{deleted_count}** messages in {target_channel.mention}!")
        await context.reply(embed=embed)

    @commands.hybrid_command(
        name="preemptban",
        description="Pre-emptively bans a user before they join the server.",
    )
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def preemptban(self, context: Context, user_id: str, *, reason: str = "Not specified") -> None:
        try:
            await self.bot.http.ban(user_id, context.guild.id, reason=reason)
            user = self.bot.get_user(int(user_id)) or await self.bot.fetch_user(
                int(user_id)
            )
            embed = discord.Embed(description=f"**{user}** (ID: {user_id}) was banned by **{context.author}**!")
            embed.add_field(name="Reason:", value=reason)
            await context.reply(embed=embed)
        except Exception:
            embed = discord.Embed(description="An error occurred while trying to ban the user. Make sure ID is an existing ID that belongs to a user.")
            await context.reply(embed=embed)

    @commands.hybrid_command(
        name="archive",
        description="Archives in a text file the last messages with a chosen limit of messages.",
    )
    @commands.has_permissions(manage_messages=True)
    async def archive(self, context: Context, limit: int = 10) -> None:
        log_file = f"{context.channel.id}.log"
        with open(log_file, "w", encoding="UTF-8") as f:
            f.write(
                f'Archived messages from: #{context.channel} ({context.channel.id}) in the guild "{context.guild}" ({context.guild.id}) at {datetime.now().strftime("%d.%m.%Y %H:%M:%S")}\n'
            )
            async for message in context.channel.history(
                limit=limit, before=context.message
            ):
                attachments = []
                for attachment in message.attachments:
                    attachments.append(attachment.url)
                attachments_text = (
                    f"[Attached File{'s' if len(attachments) >= 2 else ''}: {', '.join(attachments)}]"
                    if len(attachments) >= 1
                    else ""
                )
                f.write(
                    f"{message.created_at.strftime('%d.%m.%Y %H:%M:%S')} {message.author} {message.id}: {message.clean_content} {attachments_text}\n"
                )
        f = discord.File(log_file)
        await context.reply(file=f)
        os.remove(log_file)

async def setup(bot) -> None:
    await bot.add_cog(Moderation(bot))
