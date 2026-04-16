from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import discord

from cogs.music.queue import Track


def _format_duration(seconds: Optional[int]) -> str:
    if seconds is None or seconds < 0:
        return "—"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def music_track_embed(
    *,
    track: Track,
    requester_mention: str,
    headline: str,
    also_queued: Optional[List[Track]] = None,
    local_path_display: Optional[str] = None,
) -> discord.Embed:
    """
    Rich embed for a track: title, link (YouTube), requester, duration, thumbnail.
    """
    embed = discord.Embed(
        title=headline,
        description=f"**{track.title}**",
        color=0x5865F2,
    )

    if track.source == "youtube":
        embed.add_field(
            name="Video",
            value=f"[Open on YouTube]({track.uri})",
            inline=False,
        )
        if track.thumbnail_url:
            embed.set_thumbnail(url=track.thumbnail_url)
    else:
        disp = local_path_display or Path(track.uri).name
        embed.add_field(
            name="Source",
            value=f"Local library — `{disp}`",
            inline=False,
        )

    embed.add_field(
        name="Requested by",
        value=requester_mention,
        inline=True,
    )
    embed.add_field(
        name="Duration",
        value=_format_duration(track.duration),
        inline=True,
    )

    if also_queued:
        lines = []
        for t in also_queued[:15]:
            if t.source == "youtube":
                lines.append(f"• [{t.title}]({t.uri})")
            else:
                lines.append(f"• {t.title}")
        extra = len(also_queued) - 15
        if extra > 0:
            lines.append(f"*…and {extra} more*")
        embed.add_field(
            name=f"Also queued ({len(also_queued)})",
            value="\n".join(lines) if lines else "—",
            inline=False,
        )

    return embed


def now_playing_embed(*, guild: discord.Guild, track: Track) -> discord.Embed:
    """Embed for /now_playing (requester resolved from track.requester_id)."""
    req = guild.get_member(track.requester_id)
    mention = req.mention if req else f"<@{track.requester_id}>"
    return music_track_embed(
        track=track,
        requester_mention=mention,
        headline="Now playing",
    )


def headline_for_batch(
    *,
    tracks: List[Track],
    state_current: Optional[Track],
    voice_client: Optional[discord.VoiceClient],
) -> str:
    """Pick 'Now playing' vs 'Added to queue' for the first track of a batch."""
    if not tracks:
        return "Added to queue"
    first = tracks[0]
    vc = voice_client
    if (
        state_current is not None
        and state_current.uri == first.uri
        and vc is not None
        and (vc.is_playing() or vc.is_paused())
    ):
        return "Now playing"
    return "Added to queue"
