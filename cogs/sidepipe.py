import json
import logging
import os
import re

import discord
from discord.ext import commands, tasks
from discord.ext.commands import Context
import aiohttp
import io
from mcstatus import JavaServer

logger = logging.getLogger("Neurodivergence")

POLL_INTERVAL = int(os.getenv("MINECRAFT_POLL_INTERVAL", "30"))

# Minecraft § 格式代码到十六进制颜色的映射（Java 版）
MC_COLOR_MAP = {
    "0": 0x000000,  # 黑色
    "1": 0x0000AA,  # 深蓝
    "2": 0x00AA00,  # 深绿
    "3": 0x00AAAA,  # 深青
    "4": 0xAA0000,  # 深红
    "5": 0xAA00AA,  # 深紫
    "6": 0xFFAA00,  # 金色
    "7": 0xAAAAAA,  # 灰色
    "8": 0x555555,  # 深灰
    "9": 0x5555FF,  # 蓝色
    "a": 0x55FF55,  # 绿色
    "b": 0x55FFFF,  # 青色
    "c": 0xFF5555,  # 红色
    "d": 0xFF55FF,  # 浅紫
    "e": 0xFFFF55,  # 黄色
    "f": 0xFFFFFF,  # 白色
}

# 匹配任何 § 格式代码的正则表达式（颜色 + k/l/m/n/o/r）
MC_FORMAT_RE = re.compile(r"§[0-9a-fk-or]", re.IGNORECASE)


def strip_mc_formatting(text: str) -> str:
    """从字符串中移除所有 Minecraft § 格式代码。"""
    return MC_FORMAT_RE.sub("", text)


def get_motd_color(text: str) -> int | None:
    """返回找到的第一个 § 颜色代码的十六进制颜色值，或返回 None。"""
    match = re.search(r"§([0-9a-f])", text, re.IGNORECASE)
    if match:
        return MC_COLOR_MAP.get(match.group(1).lower())
    return None


class Sidepipe(commands.Cog, name="sidepipe"):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.whitelisted_guilds = [
            discord.Object(id=1161606292541014056)
        ]
        self.mc_servers = {}  # 地址 -> 玩家名称集合
        self.mc_server_online = {}  # 地址 -> 布尔值
        self._load_mc_servers()

    def _load_mc_servers(self):
        raw = os.getenv("MINECRAFT_SERVERS", "[]")
        addresses = json.loads(raw)
        for addr in addresses:
            self.mc_servers[addr] = set()
            self.mc_server_online[addr] = None

    def _get_mc_channel(self):
        channel_id = os.getenv("MINECRAFT_CHANNEL")
        if channel_id:
            return self.bot.get_channel(int(channel_id))
        return None

    async def cog_load(self):
        if self.mc_servers:
            self.poll_mc_servers.start()

    async def cog_unload(self):
        self.poll_mc_servers.cancel()

    async def cog_check(self, ctx: commands.Context) -> bool:
        if ctx.guild.id in [guild.id for guild in self.whitelisted_guilds]:
            return True
        else:
            await ctx.reply("This command can only be used inside The Sidepipe.")
            return False

    @commands.hybrid_command(
        name="cctvselfie",
        description="Take a selfie using my CCTV cameras",
    )
    async def cctvselfie(self, ctx, camera="2"):
        embed = discord.Embed(title=f"CCTV Selfie - Camera {camera}", description=f"Please wait...")
        msg = await ctx.reply(embed=embed)

        async with aiohttp.ClientSession() as session:
                url = os.getenv("HASS_URL")
                headers = {'Authorization': f'Bearer {os.getenv("HASS_TOKEN")}'}
                async with session.get(url=f"{url}/api/camera_proxy/camera.{camera}", headers=headers) as response:
                    if response.status != 200:
                        embed = discord.Embed(title=f"CCTV Selfie - Camera {camera}", description=f"Error fetching image. f{response.status}")
                        await msg.edit(embed=embed)
                        return
                    image_data = io.BytesIO(await response.read())
                    await ctx.reply(file=discord.File(image_data, filename=f"{ctx.message.id}.jpg"))
                    await msg.delete()

    @tasks.loop(seconds=POLL_INTERVAL)
    async def poll_mc_servers(self):
        channel = self._get_mc_channel()
        if not channel:
            return

        for address in self.mc_servers:
            try:
                server = await JavaServer.async_lookup(address)
                status = await server.async_status()

                current_players = set()
                if status.players.sample:
                    current_players = {p.name for p in status.players.sample}

                previous_players = self.mc_servers[address]

                # 首次轮询时跳过通知（初始状态）
                if self.mc_server_online[address] is not None:
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

                if self.mc_server_online[address] is False:
                    embed = discord.Embed(
                        description=f"**{address}** is back online",
                        color=0x55FF55,
                    )
                    await channel.send(embed=embed)

                self.mc_servers[address] = current_players
                self.mc_server_online[address] = True

            except Exception as e:
                if self.mc_server_online[address] is True:
                    embed = discord.Embed(
                        description=f"**{address}** appears to be offline",
                        color=0xFF5555,
                    )
                    await channel.send(embed=embed)
                    self.mc_server_online[address] = False
                    self.mc_servers[address] = set()
                elif self.mc_server_online[address] is None:
                    self.mc_server_online[address] = False
                    self.mc_servers[address] = set()

                logger.warning(f"Failed to poll Minecraft server {address}: {e}")

    @poll_mc_servers.before_loop
    async def before_mc_poll(self):
        await self.bot.wait_until_ready()

    @commands.hybrid_command(
        name="mcstatus",
        description="Check the status of a monitored Minecraft server",
    )
    async def mc_status(self, ctx, address: str = None):
        if not self.mc_servers and not address:
            await ctx.send("No Minecraft servers are configured.")
            return

        targets = [address] if address else list(self.mc_servers.keys())

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
        servers = list(self.mc_servers.keys())
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


async def setup(bot) -> None:
    await bot.add_cog(Sidepipe(bot))
