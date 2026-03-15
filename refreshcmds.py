#!/usr/bin/env python3
"""
刷新（同步）此机器人的 Discord 应用命令。

为什么需要这个
---------------
此仓库在 `cogs/owner.py` 中包含一个仅限所有者使用的 `sync` 命令，但有时你
只是想要一个可以在本地/CI 中运行的简单脚本来同步机器人的斜杠命令。

此脚本：
- 从仓库根目录的 `.env` 加载 `TOKEN`（无需第三方 dotenv 依赖）。
- 为某些齿轮模块在导入时访问的环境变量设置安全默认值。
- 加载 `./cogs` 中的所有齿轮模块，以便注册 `@commands.hybrid_command(...)` 命令。
- 全局或向特定服务器同步应用命令。

注意事项
-----
- 全局同步可能需要一段时间才能生效（Discord 端）。服务器同步通常是即时的。
- 此脚本不会启动 `bot.py` 中的状态轮换任务；它只会登录、加载齿轮模块、同步，然后退出。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Dict, Iterable, Optional

import discord
from discord.ext import commands


REPO_ROOT = Path(__file__).resolve().parent


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and ((value[0] == value[-1] == '"') or (value[0] == value[-1] == "'")):
        return value[1:-1]
    return value


def load_env_file(env_path: Path) -> Dict[str, str]:
    """
    最小化 .env 加载器。

    - 支持 KEY=VALUE 键值对
    - 忽略空行和以 '#' 开头的行
    - 去除值两端的单引号/双引号
    - 不展开变量
    """
    if not env_path.exists():
        return {}

    loaded: Dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = _strip_quotes(value)
        if not key:
            continue
        loaded[key] = value
    return loaded


def apply_env(overrides: Dict[str, str]) -> None:
    """
    将加载的 .env 值应用到 os.environ 中，不覆盖已有变量。
    """
    for k, v in overrides.items():
        os.environ.setdefault(k, v)


def ensure_env_defaults() -> None:
    """
    某些齿轮模块在导入时（模块顶层）读取环境变量。

    特别是 `cogs/ai.py` 中有：
      auto1111_hosts = json.loads(os.environ['AUTO1111_HOSTS'])
      lms_hosts = json.loads(os.environ['LMS_HOSTS'])

    因此我们在此提供安全默认值，以避免在只想同步命令时出现 KeyError/JSON 错误。
    """
    os.environ.setdefault("AUTO1111_HOSTS", "[]")
    os.environ.setdefault("LMS_HOSTS", "[]")
    os.environ.setdefault("GEMINI_KEYS", "[]")
    os.environ.setdefault("STATUSES", json.dumps(["Neurodivergence"]))
    os.environ.setdefault("MINECRAFT_SERVERS", "[]")


async def load_all_cogs(bot: commands.Bot, cogs_dir: Path) -> None:
    """
    加载齿轮模块目录中的每个 `*.py` 文件作为扩展。
    """
    if not cogs_dir.exists():
        raise FileNotFoundError(f"cogs directory not found: {cogs_dir}")

    for file in sorted(cogs_dir.iterdir()):
        if file.is_file() and file.suffix == ".py" and not file.name.startswith("_"):
            ext = f"cogs.{file.stem}"
            await bot.load_extension(ext)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="refreshcmds.py",
        description="Sync (refresh) Discord slash commands for Neurodivergence.",
    )
    parser.add_argument(
        "--scope",
        choices=["global", "guild"],
        default="global",
        help="Sync scope. Use 'guild' for near-instant updates.",
    )
    parser.add_argument(
        "--guild-id",
        type=int,
        default=None,
        help="Required when --scope guild. The target Discord server (guild) ID.",
    )
    parser.add_argument(
        "--env-file",
        default=str(REPO_ROOT / ".env"),
        help="Path to a .env file containing TOKEN (default: ./.env).",
    )
    return parser


async def run(scope: str, guild_id: Optional[int], env_file: Path) -> int:
    env_values = load_env_file(env_file)
    apply_env(env_values)
    ensure_env_defaults()

    token = os.getenv("TOKEN")
    if not token:
        print(f"Error: TOKEN was not found. Expected it in {env_file} or your environment.")
        return 2

    intents = discord.Intents.none()
    bot = commands.Bot(command_prefix="!", intents=intents)

    @bot.event
    async def setup_hook() -> None:
        # 加载齿轮模块，以便混合命令注册到应用命令树中。
        await load_all_cogs(bot, REPO_ROOT / "cogs")

        if scope == "guild":
            if not guild_id:
                print("Error: --guild-id is required when --scope guild.")
                await bot.close()
                return

            guild = discord.Object(id=guild_id)
            # 将全局命令复制到服务器，然后同步该服务器。
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            print(f"Synced {len(synced)} commands to guild {guild_id}.")
        else:
            synced = await bot.tree.sync()
            print(f"Synced {len(synced)} commands globally.")

        await bot.close()

    try:
        await bot.start(token)
        return 0
    except discord.LoginFailure:
        print("Error: Discord login failed. Is TOKEN correct?")
        return 3


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    return asyncio.run(run(args.scope, args.guild_id, Path(args.env_file)))


if __name__ == "__main__":
    raise SystemExit(main())

