from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, Optional

import discord

if TYPE_CHECKING:
    pass


@dataclass
class Track:
    title: str
    source: Literal["youtube", "local"]
    uri: str
    requester_id: int
    duration: Optional[int] = None
    thumbnail_url: Optional[str] = None


@dataclass
class GuildMusicState:
    queue: deque[Track] = field(default_factory=deque)
    current: Optional[Track] = None
    voice: Optional[discord.VoiceClient] = None
    idle_disconnect_task: Optional[asyncio.Task] = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class QueueManager:
    def __init__(self) -> None:
        self._states: dict[int, GuildMusicState] = {}

    def get_state(self, guild_id: int) -> GuildMusicState:
        if guild_id not in self._states:
            self._states[guild_id] = GuildMusicState()
        return self._states[guild_id]

    def remove_state(self, guild_id: int) -> None:
        self._states.pop(guild_id, None)
