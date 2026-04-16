from __future__ import annotations

from typing import Any, List, Optional

import yt_dlp

from cogs.music.queue import Track


def _entry_to_track(entry: Any, requester_id: int) -> Optional[Track]:
    if not entry:
        return None
    title = entry.get("title") or "Unknown track"
    video_id = entry.get("id")
    webpage = entry.get("webpage_url") or entry.get("url")
    if webpage and isinstance(webpage, str) and not webpage.startswith("http"):
        webpage = None
    if not webpage and video_id:
        webpage = f"https://www.youtube.com/watch?v={video_id}"
    if not webpage:
        return None
    duration = entry.get("duration")
    if duration is not None and not isinstance(duration, int):
        try:
            duration = int(duration)
        except (TypeError, ValueError):
            duration = None
    thumb = entry.get("thumbnail")
    if not thumb and entry.get("thumbnails"):
        thumbs = entry["thumbnails"]
        if thumbs:
            thumb = thumbs[-1].get("url")
    return Track(
        title=title[:200],
        source="youtube",
        uri=webpage,
        requester_id=requester_id,
        duration=duration,
        thumbnail_url=thumb,
    )


def extract_tracks_sync(query: str, requester_id: int) -> List[Track]:
    """
    Resolve a YouTube URL or search query into one or more Track objects (synchronous).
    Intended to be run via asyncio.to_thread.
    """
    search_query = query.strip()
    if not search_query:
        return []

    if not search_query.startswith(("http://", "https://")):
        search_query = f"ytsearch1:{search_query}"

    ydl_opts: dict = {
        "format": "bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True,
        "extract_flat": "in_playlist",
        "noplaylist": False,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(search_query, download=False)

    if not info:
        return []

    tracks: List[Track] = []
    entries = info.get("entries")

    if entries is not None:
        for entry in entries:
            if entry is None:
                continue
            if entry.get("ie_key") == "YoutubePlaylist" and not entry.get("url"):
                continue
            t = _entry_to_track(entry, requester_id)
            if t:
                tracks.append(t)
        if tracks:
            return tracks

    t = _entry_to_track(info, requester_id)
    return [t] if t else []
