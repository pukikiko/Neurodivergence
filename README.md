# Neurodivergence

Neurodivergence is a [discord.py](https://github.com/Rapptz/discord.py) bot with a modular cog layout: AI helpers, utilities, moderation, fun commands, and optional Shodan integration.

Full command and configuration reference: [documentation/BOT_DOCUMENTATION.md](documentation/BOT_DOCUMENTATION.md).

## Requirements

- Python 3.10+
- Discord bot token and any optional API keys you enable (see docs)
- Docker and Docker Compose (recommended for deployment)

## Deployment

The application should be deployed using Docker.

### Docker Compose (Recommended)

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```
2. Fill out `.env` with your `TOKEN` and other necessary variables.
3. Start the bot in the background:
   ```bash
   docker compose up -d
   ```

### Manual Docker Build & Run

If you prefer to build the image yourself or use `docker run` manually:

```bash
docker build -t neurodivergence:latest .
docker run -d \
  --env-file .env \
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
| `GEMINI_KEYS` | JSON array of Gemini API keys (AI features) |
| `AUTO1111_HOSTS` | JSON array of Stable Diffusion WebUI URLs |
| `LMS_HOSTS` | JSON array of LM Studio URLs |
| `LOGGING_CHANNEL` | Channel ID for command logging |
| `SHODAN_KEY` | Shodan API key (Shodan cog) |
| `HASS_*` | Optional integrations (see full docs) |

The **Sidepipe** cog (`cogs/sidepipe.py`) is server-specific; remove or replace it for your own deployment.
