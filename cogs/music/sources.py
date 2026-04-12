from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

import discord
import yt_dlp

from cogs.music.queue import Track

# Basenames only; FFmpeg decodes these for local playback.
LOCAL_LIBRARY_EXTENSIONS: Tuple[str, ...] = (".mp3", ".flac")


def _is_allowed_library_audio_suffix(suffix: str) -> bool:
    return suffix.lower() in LOCAL_LIBRARY_EXTENSIONS


def _is_path_under_root(candidate: Path, root: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def resolve_library_subdir(library_root: Path, folder_relative: str) -> Path:
    """
    Resolve a subdirectory of the music library (posix-style relative path, no ..).
    Empty string means the library root itself.
    """
    root = library_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError("Local music directory does not exist.")

    rel = (folder_relative or "").strip().replace("\\", "/").strip("/")
    if not rel:
        return root

    cur = root
    for part in Path(rel).parts:
        if not part or part in (".", ".."):
            raise ValueError("Invalid folder.")
        nxt = (cur / part).resolve()
        if not _is_path_under_root(nxt, root):
            raise ValueError("Invalid folder path.")
        if not nxt.is_dir():
            raise FileNotFoundError("Folder not found.")
        cur = nxt
    return cur


def iter_library_folder_paths(library_root: Path, *, max_depth: int = 6) -> List[str]:
    """
    All subdirectory paths under library_root, as posix relative paths (e.g. Rock/Metal).
    Used for /play_local folder autocomplete.
    """
    root = library_root.resolve()
    if not root.is_dir():
        return []
    out: List[str] = []

    def walk(current: Path, rel: str, depth: int) -> None:
        if depth >= max_depth:
            return
        try:
            children = sorted(
                (p for p in current.iterdir() if p.is_dir()),
                key=lambda p: p.name.lower(),
            )
        except OSError:
            return
        for child in children:
            resolved = child.resolve()
            if not _is_path_under_root(resolved, root):
                continue
            new_rel = f"{rel}/{child.name}" if rel else child.name
            out.append(new_rel.replace("\\", "/"))
            walk(child, new_rel, depth + 1)

    walk(root, "", 0)
    return sorted(out, key=str.lower)


def resolve_local_audio_path(
    filename: str,
    library_root: Path,
    folder_relative: str = "",
) -> Path:
    """
    Resolve a basename-only .mp3 or .flac under library_root or folder_relative.
    Rejects traversal. Matching is case-insensitive on stem (and extension when ambiguous).
    """
    root = library_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError("Local music directory does not exist.")

    base_dir = resolve_library_subdir(root, folder_relative)

    safe_name = Path(filename).name
    suf = Path(safe_name).suffix.lower()
    if not _is_allowed_library_audio_suffix(suf):
        raise ValueError(
            f"Only {', '.join(LOCAL_LIBRARY_EXTENSIONS)} files are allowed."
        )

    desired_stem = Path(safe_name).stem

    def _finalize(candidate: Path) -> Path:
        resolved = candidate.resolve()
        if not _is_path_under_root(resolved, root):
            raise ValueError("Invalid file path.")
        if not resolved.is_file():
            raise FileNotFoundError("File not found.")
        return resolved

    direct = base_dir / safe_name
    if direct.is_file():
        return _finalize(direct)

    try:
        for f in sorted(base_dir.iterdir(), key=lambda p: p.name.lower()):
            if not f.is_file():
                continue
            if not _is_allowed_library_audio_suffix(f.suffix):
                continue
            if f.stem.lower() != desired_stem.lower():
                continue
            if f.suffix.lower() == suf:
                return _finalize(f)
        for f in sorted(base_dir.iterdir(), key=lambda p: p.name.lower()):
            if not f.is_file():
                continue
            if not _is_allowed_library_audio_suffix(f.suffix):
                continue
            if f.stem.lower() == desired_stem.lower():
                return _finalize(f)
    except OSError:
        pass

    raise FileNotFoundError("File not found.")


class AudioSourceFactory:
    """Builds discord AudioSource instances from Track objects."""

    FFMPEG_BEFORE = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"

    def __init__(self, local_root: Path) -> None:
        self.local_root = local_root

    def build_youtube(self, track: Track) -> discord.AudioSource:
        url = _extract_youtube_audio_url(track.uri)
        if not url:
            raise ValueError("Could not get audio stream for this track.")
        return discord.FFmpegOpusAudio(
            url,
            before_options=self.FFMPEG_BEFORE,
            options="-vn",
        )

    def build_local(self, track: Track) -> discord.AudioSource:
        path = Path(track.uri)
        if not path.is_file():
            raise FileNotFoundError("Local audio file is missing.")
        return discord.FFmpegOpusAudio(str(path), options="-vn")


def _extract_youtube_audio_url(webpage_url: str) -> Optional[str]:
    ydl_opts: dict = {
        "format": "bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(webpage_url, download=False)
    if not info:
        return None
    url = info.get("url")
    if url:
        return url
    formats = info.get("formats") or []
    for f in reversed(formats):
        if f.get("url") and f.get("acodec") != "none" and f.get("vcodec") == "none":
            return f.get("url")
    for f in reversed(formats):
        if f.get("url"):
            return f.get("url")
    return None
