from __future__ import annotations

import asyncio
import logging
from typing import List, Optional, Union

import discord
from discord import StageChannel, VoiceChannel
from discord.ext import commands

from cogs.music.queue import GuildMusicState, QueueManager, Track
from cogs.music.sources import AudioSourceFactory

log = logging.getLogger("Neurodivergence.music")


class GuildPlayer:
    def __init__(
        self,
        bot: commands.Bot,
        queues: QueueManager,
        factory: AudioSourceFactory,
    ) -> None:
        self.bot = bot
        self.queues = queues
        self.factory = factory

    async def _play_next(self, guild_id: int) -> None:
        state = self.queues.get_state(guild_id)
        async with state.lock:
            vc = state.voice
            if not vc or not vc.is_connected():
                state.current = None
                return

            if state.queue:
                state.current = state.queue.popleft()
            else:
                state.current = None
                return

            track = state.current

        try:
            if track.source == "youtube":
                source = await asyncio.to_thread(self.factory.build_youtube, track)
            else:
                source = await asyncio.to_thread(self.factory.build_local, track)
        except Exception:
            log.exception("Failed to build audio source for guild %s", guild_id)
            await self._play_next(guild_id)
            return

        async with state.lock:
            vc = state.voice
            if not vc or not vc.is_connected():
                return

        def after(err: Optional[Exception]) -> None:
            if err:
                log.error("Voice play after error: %s", err, exc_info=err)
            self.bot.loop.create_task(self._play_next(guild_id))

        try:
            vc.play(source, after=after)
        except Exception:
            log.exception("vc.play failed for guild %s", guild_id)
            await self._play_next(guild_id)

    async def connect_or_move(
        self,
        guild: discord.Guild,
        channel: Union[VoiceChannel, StageChannel],
    ) -> discord.VoiceClient:
        state = self.queues.get_state(guild.id)
        perms = channel.permissions_for(guild.me)
        if not perms.connect or not perms.speak:
            raise RuntimeError("missing_voice_permissions")

        if state.voice and state.voice.is_connected():
            if state.voice.channel and state.voice.channel.id == channel.id:
                return state.voice
            await state.voice.move_to(channel)
            return state.voice

        vc = await channel.connect()
        state.voice = vc
        return vc

    async def enqueue_and_maybe_start(
        self,
        guild: discord.Guild,
        voice_channel: Union[VoiceChannel, StageChannel],
        tracks: List[Track],
    ) -> None:
        if not tracks:
            return
        state = self.queues.get_state(guild.id)
        async with state.lock:
            for t in tracks:
                state.queue.append(t)

        await self.connect_or_move(guild, voice_channel)

        async with state.lock:
            st = self.queues.get_state(guild.id)
            vc = st.voice
            playing = vc.is_playing() if vc else False
            paused = vc.is_paused() if vc else False

        if not playing and not paused:
            await self._play_next(guild.id)

    async def skip(self, guild_id: int) -> None:
        state = self.queues.get_state(guild_id)
        async with state.lock:
            vc = state.voice
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()

    async def pause(self, guild_id: int) -> bool:
        state = self.queues.get_state(guild_id)
        vc = state.voice
        if vc and vc.is_playing():
            vc.pause()
            return True
        return False

    async def resume(self, guild_id: int) -> bool:
        state = self.queues.get_state(guild_id)
        vc = state.voice
        if vc and vc.is_paused():
            vc.resume()
            return True
        return False

    async def clear_queue_only(self, guild_id: int) -> None:
        state = self.queues.get_state(guild_id)
        async with state.lock:
            state.queue.clear()

    async def disconnect_guild(self, guild_id: int, clear_queue: bool = True) -> None:
        state = self.queues.get_state(guild_id)
        if state.idle_disconnect_task and not state.idle_disconnect_task.done():
            state.idle_disconnect_task.cancel()
        state.idle_disconnect_task = None

        async with state.lock:
            vc = state.voice
            state.voice = None
            state.current = None
            if clear_queue:
                state.queue.clear()

        if vc and vc.is_connected():
            await vc.disconnect()

    def cancel_idle_disconnect(self, state: GuildMusicState) -> None:
        if state.idle_disconnect_task and not state.idle_disconnect_task.done():
            state.idle_disconnect_task.cancel()
        state.idle_disconnect_task = None
