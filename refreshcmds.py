#!/usr/bin/env python3
"""
Refresh (sync) Discord application commands for this bot.

Why this exists
---------------
This repo includes an owner-only `sync` command in `cogs/owner.py`, but sometimes you
just want a simple script you can run locally/CI to sync the bot's slash commands.

This script:
- Loads `TOKEN` from `.env` in the repo root (no third-party dotenv dependency).
- Ensures sane defaults for env vars that are accessed at import-time by some cogs.
- Loads all cogs from `./cogs` so `@commands.hybrid_command(...)` commands register.
- Syncs application commands either globally or to a specific guild.

Notes
-----
- Global sync can take a while to propagate (Discord-side). Guild sync is usually immediate.
- This script does NOT start the status rotation task from `bot.py`; it only logs in,
  loads cogs, syncs, then exits.
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
    Minimal .env loader.

    - Supports KEY=VALUE pairs
    - Ignores empty lines and lines starting with '#'
    - Strips surrounding single/double quotes from values
    - Does not expand variables
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
    Apply loaded .env values into os.environ without overwriting existing vars.
    """
    for k, v in overrides.items():
        os.environ.setdefault(k, v)


def ensure_env_defaults() -> None:
    """
    Some cogs read env vars at import time (module top-level).

    In particular, `cogs/ai.py` does:
      auto1111_hosts = json.loads(os.environ['AUTO1111_HOSTS'])
      lms_hosts = json.loads(os.environ['LMS_HOSTS'])

    So we provide safe defaults here to avoid KeyError/JSON errors when you only
    want to sync commands.
    """
    os.environ.setdefault("AUTO1111_HOSTS", "[]")
    os.environ.setdefault("LMS_HOSTS", "[]")
    os.environ.setdefault("GEMINI_KEYS", "[]")
    os.environ.setdefault("STATUSES", json.dumps(["Neurodivergence"]))


async def load_all_cogs(bot: commands.Bot, cogs_dir: Path) -> None:
    """
    Loads every `*.py` file inside the cogs directory as an extension.
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
        # Load cogs so hybrid commands register with the app command tree.
        await load_all_cogs(bot, REPO_ROOT / "cogs")

        if scope == "guild":
            if not guild_id:
                print("Error: --guild-id is required when --scope guild.")
                await bot.close()
                return

            guild = discord.Object(id=guild_id)
            # Copy global commands to the guild, then sync that guild.
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

