from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import List, Optional, Union

import discord
from discord import StageChannel, VoiceChannel
from discord import app_commands
from discord.ext import commands

from cogs.music.embeds import headline_for_batch, music_track_embed, now_playing_embed
from cogs.music.player import GuildPlayer
from cogs.music.queue import QueueManager, Track
from cogs.music.sources import (
    LOCAL_LIBRARY_EXTENSIONS,
    AudioSourceFactory,
    iter_library_folder_paths,
    resolve_library_subdir,
    resolve_local_audio_path,
)
from cogs.music.ytdlp_helper import extract_tracks_sync

log = logging.getLogger("Neurodivergence.music")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _local_music_root() -> Path:
    env = os.environ.get("MUSIC_LOCAL_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return (REPO_ROOT / "music_library").resolve()


def _invoker_voice(
    interaction: discord.Interaction,
) -> Optional[Union[VoiceChannel, StageChannel]]:
    if interaction.guild is None or not isinstance(interaction.user, discord.Member):
        return None
    voice = interaction.user.voice
    if not voice or not voice.channel:
        return None
    ch = voice.channel
    if isinstance(ch, (VoiceChannel, StageChannel)):
        return ch
    return None


class MusicCog(commands.Cog, name="music"):
    """Voice music playback: YouTube, local library audio (MP3/FLAC), per-guild queue."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.local_root = _local_music_root()
        self.factory = AudioSourceFactory(self.local_root)
        self.queues = QueueManager()
        self.player = GuildPlayer(bot, self.queues, self.factory)

    async def cog_load(self) -> None:
        # Re-resolve after bot startup .env load so MUSIC_LOCAL_DIR applies.
        self.local_root = _local_music_root()
        self.factory.local_root = self.local_root
        try:
            self.local_root.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            # Docker read-only mounts, missing parents, or sync-only runs without a library.
            log.warning(
                "Could not ensure music library directory %s exists (%s). "
                "/play_local still works if this path is readable.",
                self.local_root,
                e,
            )

        audio_count = 0
        allowed = {e.lower() for e in LOCAL_LIBRARY_EXTENSIONS}
        if self.local_root.is_dir():
            try:
                audio_count = sum(
                    1
                    for f in self.local_root.iterdir()
                    if f.is_file() and f.suffix.lower() in allowed
                )
            except OSError as e:
                log.warning("Could not scan music library %s: %s", self.local_root, e)
        else:
            log.warning(
                "Music library path is not a directory (yet): %s",
                self.local_root,
            )

        log.info(
            "Music library path: %s (top-level audio files: %s)",
            self.local_root,
            audio_count,
        )

    def _schedule_idle_disconnect(self, guild_id: int) -> None:
        state = self.player.queues.get_state(guild_id)
        self.player.cancel_idle_disconnect(state)

        async def countdown() -> None:
            try:
                await asyncio.sleep(300)
                guild = self.bot.get_guild(guild_id)
                if guild is None:
                    return
                vc = guild.voice_client
                if vc is None or not vc.is_connected():
                    return
                ch = vc.channel
                if ch is None:
                    return
                humans = sum(1 for m in ch.members if not m.bot)
                if humans > 0:
                    return
                await self.player.disconnect_guild(guild_id, clear_queue=True)
                self.player.queues.remove_state(guild_id)
            except asyncio.CancelledError:
                pass

        state.idle_disconnect_task = asyncio.create_task(countdown())

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        guild = member.guild
        vc = guild.voice_client
        if vc is None or not vc.is_connected():
            st = self.player.queues.get_state(guild.id)
            self.player.cancel_idle_disconnect(st)
            return

        channel = vc.channel
        if channel is None:
            return

        humans = sum(1 for m in channel.members if not m.bot)
        state = self.player.queues.get_state(guild.id)
        if humans == 0:
            self._schedule_idle_disconnect(guild.id)
        else:
            self.player.cancel_idle_disconnect(state)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        await self.player.disconnect_guild(guild.id, clear_queue=True)
        self.player.queues.remove_state(guild.id)

    @app_commands.command(name="play", description="Play from YouTube (URL or search) or add a playlist to the queue.")
    @app_commands.describe(query="YouTube link or search text")
    @app_commands.guild_only()
    async def play(self, interaction: discord.Interaction, query: str) -> None:
        assert interaction.guild is not None
        channel = _invoker_voice(interaction)
        if channel is None:
            await interaction.response.send_message(
                "Join a voice channel first.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True)
        self.player.cancel_idle_disconnect(self.player.queues.get_state(interaction.guild.id))

        try:
            tracks = await asyncio.to_thread(
                extract_tracks_sync,
                query,
                interaction.user.id,
            )
        except Exception:
            log.exception("yt-dlp extract failed for query=%r", query)
            await interaction.followup.send("Could not play this link or search.", ephemeral=True)
            return

        if not tracks:
            await interaction.followup.send("No results found.", ephemeral=True)
            return

        try:
            await self.player.enqueue_and_maybe_start(
                interaction.guild,
                channel,
                tracks,
            )
        except RuntimeError as e:
            if str(e) == "missing_voice_permissions":
                await interaction.followup.send(
                    "I need **Connect** and **Speak** in that voice channel.",
                    ephemeral=True,
                )
                return
            raise

        state = self.player.queues.get_state(interaction.guild.id)
        vc = interaction.guild.voice_client
        hl = headline_for_batch(
            tracks=tracks,
            state_current=state.current,
            voice_client=vc,
        )
        also = tracks[1:] if len(tracks) > 1 else None
        embed = music_track_embed(
            track=tracks[0],
            requester_mention=interaction.user.mention,
            headline=hl,
            also_queued=also,
        )
        await interaction.followup.send(embed=embed, ephemeral=False)

    @app_commands.command(
        name="play_local",
        description="Play a local MP3 or FLAC from the music library. Pick a folder (optional), then a file.",
    )
    @app_commands.describe(
        folder="Subfolder inside the library (autocomplete). Leave empty for files in the library root.",
        filename="Audio file (.mp3 / .flac) in that folder (autocomplete)",
    )
    @app_commands.guild_only()
    async def play_local(
        self,
        interaction: discord.Interaction,
        folder: str = "",
        filename: str = "",
    ) -> None:
        assert interaction.guild is not None
        channel = _invoker_voice(interaction)
        if channel is None:
            await interaction.response.send_message(
                "Join a voice channel first.",
                ephemeral=True,
            )
            return

        if not (filename or "").strip():
            await interaction.response.send_message(
                "Choose an audio file (use autocomplete).",
                ephemeral=True,
            )
            return

        self.player.cancel_idle_disconnect(self.player.queues.get_state(interaction.guild.id))

        folder_key = (folder or "").strip()
        try:
            path = resolve_local_audio_path(
                filename.strip(),
                self.local_root,
                folder_key,
            )
        except (FileNotFoundError, ValueError) as e:
            await interaction.response.send_message(str(e) or "File not found.", ephemeral=True)
            return

        rel_display: Optional[str] = None
        try:
            rel_display = path.resolve().relative_to(self.local_root.resolve()).as_posix()
        except ValueError:
            rel_display = path.name

        track = Track(
            title=path.stem,
            source="local",
            uri=str(path),
            requester_id=interaction.user.id,
            duration=None,
            thumbnail_url=None,
        )

        try:
            await self.player.enqueue_and_maybe_start(
                interaction.guild,
                channel,
                [track],
            )
        except RuntimeError as e:
            if str(e) == "missing_voice_permissions":
                await interaction.response.send_message(
                    "I need **Connect** and **Speak** in that voice channel.",
                    ephemeral=True,
                )
                return
            raise

        state = self.player.queues.get_state(interaction.guild.id)
        vc = interaction.guild.voice_client
        hl = headline_for_batch(
            tracks=[track],
            state_current=state.current,
            voice_client=vc,
        )
        embed = music_track_embed(
            track=track,
            requester_mention=interaction.user.mention,
            headline=hl,
            local_path_display=rel_display,
        )
        await interaction.response.send_message(embed=embed, ephemeral=False)

    @play_local.autocomplete("folder")
    async def play_local_folder_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> List[app_commands.Choice[str]]:
        root = self.local_root
        if not root.is_dir():
            return []
        choices: List[app_commands.Choice[str]] = [
            app_commands.Choice(name="Library root (top-level files)", value=""),
        ]
        cur = (current or "").strip().lower()
        for rel in iter_library_folder_paths(root):
            if cur and cur not in rel.lower():
                continue
            display = rel if len(rel) <= 80 else f"{rel[:77]}..."
            choices.append(app_commands.Choice(name=display[:100], value=rel))
            if len(choices) >= 25:
                break
        return choices[:25]

    @play_local.autocomplete("filename")
    async def play_local_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> List[app_commands.Choice[str]]:
        root = self.local_root
        if not root.is_dir():
            return []
        folder_key = ""
        ns = interaction.namespace
        if hasattr(ns, "folder") and ns.folder is not None:
            folder_key = str(ns.folder).strip()
        try:
            dir_path = resolve_library_subdir(root, folder_key)
        except (FileNotFoundError, ValueError, OSError):
            return []
        allowed = {e.lower() for e in LOCAL_LIBRARY_EXTENSIONS}
        try:
            names = sorted(
                f.name
                for f in dir_path.iterdir()
                if f.is_file() and f.suffix.lower() in allowed
            )
        except OSError:
            return []
        if current:
            cur = current.lower()
            names = [n for n in names if cur in n.lower()]
        out: List[app_commands.Choice[str]] = []
        for n in names[:25]:
            out.append(app_commands.Choice(name=n[:100], value=n))
        return out

    @app_commands.command(name="skip", description="Skip the current track.")
    @app_commands.guild_only()
    async def skip(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        vc = interaction.guild.voice_client
        if vc is None or not vc.is_connected():
            await interaction.response.send_message("Not playing anything here.", ephemeral=True)
            return
        if not vc.is_playing() and not vc.is_paused():
            await interaction.response.send_message("Nothing to skip.", ephemeral=True)
            return
        await self.player.skip(interaction.guild.id)
        await interaction.response.send_message("Skipped.", ephemeral=True)

    @app_commands.command(name="pause", description="Pause playback.")
    @app_commands.guild_only()
    async def pause(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        ok = await self.player.pause(interaction.guild.id)
        if ok:
            await interaction.response.send_message("Paused.", ephemeral=True)
        else:
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)

    @app_commands.command(name="resume", description="Resume playback.")
    @app_commands.guild_only()
    async def resume(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        ok = await self.player.resume(interaction.guild.id)
        if ok:
            await interaction.response.send_message("Resumed.", ephemeral=True)
        else:
            await interaction.response.send_message("Nothing is paused.", ephemeral=True)

    @app_commands.command(name="queue", description="Show the current queue.")
    @app_commands.guild_only()
    async def queue_cmd(
        self,
        interaction: discord.Interaction,
        page: app_commands.Range[int, 1, 50] = 1,
    ) -> None:
        assert interaction.guild is not None
        state = self.player.queues.get_state(interaction.guild.id)
        per_page = 10
        lines: List[str] = []
        if state.current:
            lines.append(f"**Now:** {state.current.title}")
        else:
            lines.append("**Now:** —")

        qlist = list(state.queue)
        if not qlist and not state.current:
            embed = discord.Embed(title="Queue", description="The queue is empty.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        start = (page - 1) * per_page
        chunk = qlist[start : start + per_page]
        for i, t in enumerate(chunk, start=start + 1):
            lines.append(f"`{i}.` {t.title}")

        more = len(qlist) - (start + len(chunk))
        if more > 0:
            lines.append(f"*…and {more} more*")

        embed = discord.Embed(title="Queue", description="\n".join(lines))
        embed.set_footer(text=f"Page {page}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="now_playing", description="Show the current track.")
    @app_commands.guild_only()
    async def now_playing(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        state = self.player.queues.get_state(interaction.guild.id)
        cur = state.current
        if not cur:
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)
            return

        embed = now_playing_embed(guild=interaction.guild, track=cur)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    @app_commands.command(
        name="clear",
        description="Remove all upcoming tracks from the queue (does not stop the current song).",
    )
    @app_commands.guild_only()
    async def clear(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        await self.player.clear_queue_only(interaction.guild.id)
        await interaction.response.send_message("Cleared the queue.", ephemeral=True)

    @app_commands.command(name="disconnect", description="Stop playback and disconnect from voice.")
    @app_commands.guild_only()
    async def disconnect(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        vc = interaction.guild.voice_client
        if vc is None or not vc.is_connected():
            await interaction.response.send_message("I'm not in a voice channel.", ephemeral=True)
            return
        await self.player.disconnect_guild(interaction.guild.id, clear_queue=True)
        self.player.queues.remove_state(interaction.guild.id)
        await interaction.response.send_message("Disconnected.", ephemeral=True)
