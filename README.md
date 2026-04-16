# Neurodivergence

Neurodivergence is a [discord.py](https://github.com/Rapptz/discord.py) bot with a modular cog layout: AI helpers, utilities, moderation, fun commands, optional Shodan integration, and **voice music** (YouTube and local MP3/FLAC with a per-server queue).

Full command and configuration reference: [documentation/BOT_DOCUMENTATION.md](documentation/BOT_DOCUMENTATION.md).

## Requirements

- Python 3.10+
- **FFmpeg** on the host (required for voice decoding; included in the Docker image)
- **`davey`** (PyPI) — required by current **discord.py** for voice connections (Discord DAVE), alongside **PyNaCl**. Without it, voice connect raises `davey library needed in order to use voice`.
- Discord bot token and any optional API keys you enable (see docs)

## Running locally

```bash
pip install -r requirements.txt
# Configure environment (at minimum TOKEN and STATUSES JSON for bot.py)
export TOKEN='your_bot_token'
export STATUSES='["Hello"]'
python bot.py
```

Install FFmpeg (e.g. `brew install ffmpeg` on macOS, or your distro’s `ffmpeg` package).

## Docker

Build and run:

```bash
docker build -t neurodivergence:latest .
docker run -d \
  -e TOKEN=your_discord_token \
  -e STATUSES='["Neurodivergence"]' \
  -e SHODAN_KEY=your_shodan_api_key \
  --restart unless-stopped \
  neurodivergence:latest
```

Add other variables from the documentation as needed (`GEMINI_KEYS`, `AUTO1111_HOSTS`, `MUSIC_LOCAL_DIR`, etc.).

### Music library volume (optional)

To use `/play_local` with files on the host, mount a directory and point the bot at it:

```bash
docker run -d \
  -e TOKEN=your_discord_token \
  -e STATUSES='["Neurodivergence"]' \
  -e MUSIC_LOCAL_DIR=/data/music_library \
  -v /path/on/host/mp3s:/data/music_library:ro \
  --restart unless-stopped \
  neurodivergence:latest
```

## Slash commands

After changing commands, sync the application command tree (owner `sync` in the bot, or `python refreshcmds.py`). See [documentation/BOT_DOCUMENTATION.md](documentation/BOT_DOCUMENTATION.md).

## Environment variables (summary)

| Variable | Description |
|----------|-------------|
| `TOKEN` | Discord bot token ([Discord Developer Portal](https://discord.com/developers/applications)) |
| `STATUSES` | JSON array of status strings for rotation |
| `MUSIC_LOCAL_DIR` | Optional. Root directory for `/play_local` (`.mp3` / `.flac`, subfolders supported; default: `./music_library`) |
| `GEMINI_KEYS` | JSON array of Gemini API keys (AI features) |
| `AUTO1111_HOSTS` | JSON array of Stable Diffusion WebUI URLs |
| `LMS_HOSTS` | JSON array of LM Studio URLs |
| `LOGGING_CHANNEL` | Channel ID for command logging |
| `SHODAN_KEY` | Shodan API key (Shodan cog) |
| `GEOWIFI_URL`, `HTTP_PROXY`, `LIBRETRANSLATE_URL`, `HASS_*` | Optional integrations (see full docs) |

The **Sidepipe** cog (`cogs/sidepipe.py`) is server-specific; remove or replace it for your own deployment.
