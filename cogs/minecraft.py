import json
import logging
import os
import re

import discord
from discord.ext import commands, tasks
from mcstatus import JavaServer

logger = logging.getLogger("Neurodivergence")

POLL_INTERVAL = int(os.getenv("MINECRAFT_POLL_INTERVAL", "30"))

# Minecraft § formatting code to hex color mapping (Java Edition)
MC_COLOR_MAP = {
    "0": 0x000000,  # black
    "1": 0x0000AA,  # dark_blue
    "2": 0x00AA00,  # dark_green
    "3": 0x00AAAA,  # dark_aqua
    "4": 0xAA0000,  # dark_red
    "5": 0xAA00AA,  # dark_purple
    "6": 0xFFAA00,  # gold
    "7": 0xAAAAAA,  # gray
    "8": 0x555555,  # dark_gray
    "9": 0x5555FF,  # blue
    "a": 0x55FF55,  # green
    "b": 0x55FFFF,  # aqua
    "c": 0xFF5555,  # red
    "d": 0xFF55FF,  # light_purple
    "e": 0xFFFF55,  # yellow
    "f": 0xFFFFFF,  # white
}

# Regex matching any § formatting code (colors + k/l/m/n/o/r)
MC_FORMAT_RE = re.compile(r"§[0-9a-fk-or]", re.IGNORECASE)


def strip_mc_formatting(text: str) -> str:
    """Remove all Minecraft § formatting codes from a string."""
    return MC_FORMAT_RE.sub("", text)


def get_motd_color(text: str) -> int | None:
    """Return the hex color of the first § color code found, or None."""
    match = re.search(r"§([0-9a-f])", text, re.IGNORECASE)
    if match:
        return MC_COLOR_MAP.get(match.group(1).lower())
    return None


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
    async def mc_status(self, ctx, address: str = None):
        if not self.servers and not address:
            await ctx.send("No Minecraft servers are configured.")
            return

        targets = [address] if address else list(self.servers.keys())

        for addr in targets:
            try:
                server = await JavaServer.async_lookup(addr)
                status = await server.async_status()

                motd_raw = str(status.description) if status.description else ""
                motd_color = get_motd_color(motd_raw)
                motd_clean = strip_mc_formatting(motd_raw).strip()

                embed = discord.Embed(
                    title=addr,
                    color=motd_color or 0x55FF55,
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

                if motd_clean:
                    embed.add_field(name="MOTD", value=motd_clean, inline=False)

                await ctx.send(embed=embed)

            except Exception:
                embed = discord.Embed(
                    title=addr,
                    description="Server is offline or unreachable",
                    color=0xFF5555,
                )
                await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="joinminecraft",
        description="How to join the Minecraft server",
    )
    async def join_minecraft(self, ctx):
        embed = discord.Embed(
            title="How to join the Minecraft server",
            color=0x55FF55,
        )
        embed.add_field(
            name="1. Download Prism Launcher",
            value="Grab it from [prismlauncher.org](https://prismlauncher.org/) and install it.",
            inline=False,
        )
        embed.add_field(
            name="2. Download the modpack",
            value="Download [CABIN 2.1.2](https://github.com/ThePansmith/CABIN/releases/download/2.1.2/CABIN-2.1.2-curseforge.zip).",
            inline=False,
        )
        embed.add_field(
            name="3. Import the modpack",
            value="Drag and drop the `.zip` file into Prism Launcher and it will import automatically.",
            inline=False,
        )
        servers = list(self.servers.keys())
        if servers:
            server_list = ", ".join(f"`{s}`" for s in servers)
        else:
            server_list = "`vm01.mfc.pw`"

        embed.add_field(
            name="4. Join the server",
            value=f"Launch the modpack and connect to {server_list}.",
            inline=False,
        )
        embed.add_field(
            name="5. Not whitelisted?",
            value="Ping <@174360161643659265> to get whitelisted.",
            inline=False,
        )
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Minecraft(bot))
