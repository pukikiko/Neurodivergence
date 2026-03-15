import json
import logging
import os

import discord
from discord.ext import commands, tasks
from mcstatus import JavaServer

logger = logging.getLogger("Neurodivergence")

POLL_INTERVAL = int(os.getenv("MINECRAFT_POLL_INTERVAL", "30"))


class Minecraft(commands.Cog, name="minecraft"):
    def __init__(self, bot):
        self.bot = bot
        self.servers = {}  # address -> set of player names
        self.server_online = {}  # address -> bool
        self._load_servers()

    def _load_servers(self):
        raw = os.getenv("MINECRAFT_SERVERS", "[]")
        addresses = json.loads(raw)
        for addr in addresses:
            self.servers[addr] = set()
            self.server_online[addr] = None

    def _get_channel(self):
        channel_id = os.getenv("MINECRAFT_CHANNEL")
        if channel_id:
            return self.bot.get_channel(int(channel_id))
        return None

    async def cog_load(self):
        if self.servers:
            self.poll_servers.start()

    async def cog_unload(self):
        self.poll_servers.cancel()

    @tasks.loop(seconds=POLL_INTERVAL)
    async def poll_servers(self):
        channel = self._get_channel()
        if not channel:
            return

        for address in self.servers:
            try:
                server = await JavaServer.async_lookup(address)
                status = await server.async_status()

                current_players = set()
                if status.players.sample:
                    current_players = {p.name for p in status.players.sample}

                previous_players = self.servers[address]

                # Skip notifications on first poll (initial state)
                if self.server_online[address] is not None:
                    joined = current_players - previous_players
                    left = previous_players - current_players

                    for player in joined:
                        embed = discord.Embed(
                            description=f"**{player}** joined **{address}**",
                            color=0x55FF55,
                        )
                        embed.set_footer(
                            text=f"Players online: {status.players.online}/{status.players.max}"
                        )
                        await channel.send(embed=embed)

                    for player in left:
                        embed = discord.Embed(
                            description=f"**{player}** left **{address}**",
                            color=0xFF5555,
                        )
                        embed.set_footer(
                            text=f"Players online: {status.players.online}/{status.players.max}"
                        )
                        await channel.send(embed=embed)

                if self.server_online[address] is False:
                    embed = discord.Embed(
                        description=f"**{address}** is back online",
                        color=0x55FF55,
                    )
                    await channel.send(embed=embed)

                self.servers[address] = current_players
                self.server_online[address] = True

            except Exception as e:
                if self.server_online[address] is True:
                    embed = discord.Embed(
                        description=f"**{address}** appears to be offline",
                        color=0xFF5555,
                    )
                    await channel.send(embed=embed)
                    self.server_online[address] = False
                    self.servers[address] = set()
                elif self.server_online[address] is None:
                    self.server_online[address] = False
                    self.servers[address] = set()

                logger.warning(f"Failed to poll Minecraft server {address}: {e}")

    @poll_servers.before_loop
    async def before_poll(self):
        await self.bot.wait_until_ready()

    @commands.hybrid_command(
        name="mcstatus",
        description="Check the status of a monitored Minecraft server",
    )
    async def mcstatus(self, ctx, address: str = None):
        if not self.servers:
            await ctx.send("No Minecraft servers are configured.")
            return

        targets = [address] if address else list(self.servers.keys())

        for addr in targets:
            try:
                server = await JavaServer.async_lookup(addr)
                status = await server.async_status()

                embed = discord.Embed(
                    title=addr,
                    color=0x55FF55,
                )
                embed.add_field(
                    name="Players",
                    value=f"{status.players.online}/{status.players.max}",
                    inline=True,
                )
                embed.add_field(
                    name="Latency",
                    value=f"{status.latency:.0f}ms",
                    inline=True,
                )
                embed.add_field(
                    name="Version",
                    value=status.version.name,
                    inline=True,
                )

                if status.players.sample:
                    player_names = ", ".join(p.name for p in status.players.sample)
                    embed.add_field(
                        name="Online",
                        value=player_names,
                        inline=False,
                    )

                if status.description:
                    motd = str(status.description)
                    embed.add_field(name="MOTD", value=motd, inline=False)

                await ctx.send(embed=embed)

            except Exception:
                embed = discord.Embed(
                    title=addr,
                    description="Server is offline or unreachable",
                    color=0xFF5555,
                )
                await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Minecraft(bot))
