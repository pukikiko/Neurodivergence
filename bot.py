import json
import logging
import os
import platform
import random
import sys

import discord
from discord.ext import commands, tasks
from discord.ext.commands import Context

intents = discord.Intents.default()
intents.message_content = True

# 设置两个日志记录器


class LoggingFormatter(logging.Formatter):
    # 颜色
    black = "\x1b[30m"
    red = "\x1b[31m"
    green = "\x1b[32m"
    yellow = "\x1b[33m"
    blue = "\x1b[34m"
    gray = "\x1b[38m"
    # 样式
    reset = "\x1b[0m"
    bold = "\x1b[1m"

    COLORS = {
        logging.DEBUG: gray + bold,
        logging.INFO: blue + bold,
        logging.WARNING: yellow + bold,
        logging.ERROR: red,
        logging.CRITICAL: red + bold,
    }

    def format(self, record):
        log_color = self.COLORS[record.levelno]
        format = "(black){asctime}(reset) (levelcolor){levelname:<8}(reset) (green){name}(reset) {message}"
        format = format.replace("(black)", self.black + self.bold)
        format = format.replace("(reset)", self.reset)
        format = format.replace("(levelcolor)", log_color)
        format = format.replace("(green)", self.green + self.bold)
        formatter = logging.Formatter(format, "%Y-%m-%d %H:%M:%S", style="{")
        return formatter.format(record)


logger = logging.getLogger("Neurodivergence")
logger.setLevel(logging.INFO)

# 控制台处理器
console_handler = logging.StreamHandler()
console_handler.setFormatter(LoggingFormatter())
# 文件处理器
file_handler = logging.FileHandler(filename="discord.log", encoding="utf-8", mode="w")
file_handler_formatter = logging.Formatter(
    "[{asctime}] [{levelname:<8}] {name}: {message}", "%Y-%m-%d %H:%M:%S", style="{"
)
file_handler.setFormatter(file_handler_formatter)

# 添加处理器
logger.addHandler(console_handler)
logger.addHandler(file_handler)


class DiscordBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(
            command_prefix=commands.when_mentioned_or(),
            intents=intents,
            help_command=None,
        )
        """
        创建自定义机器人变量，以便在齿轮模块中更方便地访问这些变量。

        例如，配置可以通过以下代码访问：
        - self.config # 在此类中
        - bot.config # 在此文件中
        - self.bot.config # 在齿轮模块中
        """
        self.logger = logger

    async def load_cogs(self) -> None:
        """
        此函数中的代码在机器人启动时执行。
        """
        for file in os.listdir(f"{os.path.realpath(os.path.dirname(__file__))}/cogs"):
            if file.endswith(".py"):
                extension = file[:-3]
                try:
                    await self.load_extension(f"cogs.{extension}")
                    self.logger.info(f"Loaded extension '{extension}'")
                except Exception as e:
                    exception = f"{type(e).__name__}: {e}"
                    self.logger.error(
                        f"Failed to load extension {extension}\n{exception}"
                    )

    @tasks.loop(minutes=1.0)
    async def status_task(self) -> None:
        """
        设置机器人的游戏状态任务。
        """
        statuses = json.loads(os.environ['STATUSES'])
        await self.change_presence(activity=discord.CustomActivity(name=random.choice(statuses)))

    @status_task.before_loop
    async def before_status_task(self) -> None:
        """
        在启动状态切换任务之前，确保机器人已准备就绪
        """
        await self.wait_until_ready()

    async def setup_hook(self) -> None:
        """
        这段代码仅在机器人首次启动时执行。
        """
        self.logger.info(f"Logged in as {self.user.name}")
        self.logger.info(f"discord.py API version: {discord.__version__}")
        self.logger.info(f"Python version: {platform.python_version()}")
        self.logger.info(
            f"Running on: {platform.system()} {platform.release()} ({os.name})"
        )
        self.logger.info("-------------------")
        await self.load_cogs()
        self.status_task.start()

    async def on_message(self, message: discord.Message) -> None:
        """
        每当有人发送消息时（无论是否带有前缀），此事件中的代码都会执行

        :param message: 发送的消息。
        """
        if message.author == self.user or message.author.bot:
            return
        await self.process_commands(message)

    async def on_command_completion(self, context: Context) -> None:
        """
        每当普通命令*成功*执行时，此事件中的代码都会执行。

        :param context: 已执行命令的上下文。
        """
        full_command_name = context.command.qualified_name
        split = full_command_name.split(" ")
        executed_command = str(split[0])
        logging_channel_id = os.getenv("LOGGING_CHANNEL")
        log_channel = bot.get_channel(int(logging_channel_id)) if logging_channel_id else None
        if context.guild is not None:
            self.logger.info(
                f"Executed {executed_command} command in {context.guild.name} (ID: {context.guild.id}) by {context.author} (ID: {context.author.id})"
            )
            if log_channel:
                embed = discord.Embed(title=f"Command run by {context.author}")
                embed.add_field(name=f"in {context.guild.name}", value=context.message.content, inline=True)
                await log_channel.send(embed=embed)
        else:
            self.logger.info(
                f"Executed {executed_command} command by {context.author} (ID: {context.author.id}) in DMs"
            )
            if log_channel:
                embed = discord.Embed(title=f"Command run by {context.author}")
                embed.add_field(name="in DMs", value=context.message.content, inline=True)
                await log_channel.send(embed=embed)

    async def on_command_error(self, context: Context, error) -> None:
        """
        每当普通有效命令捕获到错误时，此事件中的代码都会执行。

        :param context: 执行失败的普通命令的上下文。
        :param error: 遇到的错误。
        """
        if isinstance(error, commands.CommandOnCooldown):
            minutes, seconds = divmod(error.retry_after, 60)
            hours, minutes = divmod(minutes, 60)
            hours = hours % 24
            embed = discord.Embed(
                description=f"**Please slow down** - You can use this command again in {f'{round(hours)} hours' if round(hours) > 0 else ''} {f'{round(minutes)} minutes' if round(minutes) > 0 else ''} {f'{round(seconds)} seconds' if round(seconds) > 0 else ''}.",
                color=0xE02B2B,
            )
            await context.send(embed=embed)
        elif isinstance(error, commands.NotOwner):
            logging_channel_id = os.getenv("LOGGING_CHANNEL")
            log_channel = bot.get_channel(int(logging_channel_id)) if logging_channel_id else None
            embed = discord.Embed(
                description="You are not the owner of the bot!", color=0xE02B2B
            )
            await context.send(embed=embed)
            if context.guild:
                self.logger.warning(
                    f"{context.author} (ID: {context.author.id}) tried to execute an owner only command in the guild {context.guild.name} (ID: {context.guild.id}), but the user is not an owner of the bot."
                )
                if log_channel:
                    embed = discord.Embed(title=f"Command run by {context.author}", description="tried to execute an owner only command, but the user is not an owner of the bot.")
                    embed.add_field(name=f"in {context.guild.name}", value=context.message.content, inline=True)
                    await log_channel.send(embed=embed)
            else:
                self.logger.warning(
                    f"{context.author} (ID: {context.author.id}) tried to execute an owner only command in the bot's DMs, but the user is not an owner of the bot."
                )
                if log_channel:
                    embed = discord.Embed(title=f"Command run by {context.author}", description="tried to execute an owner only command, but the user is not an owner of the bot.")
                    embed.add_field(name=f"in DMs", value=context.message.content, inline=True)
                    await log_channel.send(embed=embed)
        elif isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                description="You are missing the permission(s) `"
                + ", ".join(error.missing_permissions)
                + "` to execute this command!",
                color=0xE02B2B,
            )
            await context.send(embed=embed)
        elif isinstance(error, commands.BotMissingPermissions):
            embed = discord.Embed(
                description="I am missing the permission(s) `"
                + ", ".join(error.missing_permissions)
                + "` to fully perform this command!",
                color=0xE02B2B,
            )
            await context.send(embed=embed)
        elif isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                title="Error!",
                # 需要首字母大写，因为代码中的命令参数没有大写字母，而它们是错误消息中的第一个词。
                description=str(error).capitalize(),
                color=0xE02B2B,
            )
            await context.send(embed=embed)
        else:
            raise error

bot = DiscordBot()
bot.run(os.getenv("TOKEN"))