# Neurodivergence Bot Documentation

## Overview

Neurodivergence is a feature-rich Discord bot built with Python using the `discord.py` library. The bot offers extensive features, including AI chat, image generation, server moderation, utilities, and fun/novelty commands. It uses a modular cog-based architecture to make features easy to extend or add.

## Architecture

### Core Components

- **Main Bot (`bot.py`)**: Handles initialization, command routing, cog loading, and logging
- **Cogs System**: Feature groups organized as Python modules in the `cogs/` folder
- **Logging**: Color-coded console logging and persistent file logging
- **Status Rotation**: Regularly updated Discord presence/status

---

## Cogs and Commands

### 1. General (`cogs/general.py`)

- `cmds` — Lists categorized commands

### 2. AI (`cogs/ai.py`)

- `gemini [prompt]` — Google Gemini chat (with attachments/context)
- `wizard [prompt]` — Wizard Vicuna (via LM Studio)
- `sd` — Generate images via Stable Diffusion

### 3. Utility (`cogs/utility.py`)

Includes Australian-centric utilities and information retrieval.

- `weather [town] [state]` — BOM weather
- `pl [query] [suburb] [state]` — Person Lookup (AU)
- `fuel [town] [state]` — Fuel prices
- `openports [ip]` — Scan open ports with Shodan InternetDB
- `rego [plate]` — Vehicle registration for South Australia
- `geowifi [bssid] [ssid]` — WiFi geolocation info
- `ppsearch [phone_number]` — Reverse payphone search

### 4. Shodan (`cogs/shodan.py`)

**Internet-wide device search and screenshots powered by Shodan.**

- `shodan <city>` — Searches Shodan for exposed devices with screenshots in a given city and returns an embedded image of the device, including detailed Shodan metadata (IP, port, org/ISP, ASN, product, country, region, hostname, domains, etc).
- **Retry** button: Allows users to fetch another random screenshot result from the queried city, only the original requester can use this.
- **Open in Shodan** button: Opens the live Shodan page for the shown IP.
- **Safety features**: Does not display the same screenshot twice per session, robustly handles API failures and missing data, ensures only the original invoking user can retry.
- **Requirements**:
  - `SHODAN_KEY` environment variable (your Shodan API key; required for all Shodan features).
  - Screenshot and device data collected securely using Shodan’s APIs.
- **Implementation details**:
  - Hybrid command (works as slash or text command).
  - Uses randomized results, avoids repeat images.
  - File uploads screenshots as Discord attachments for security/privacy and compatibility with embeds.

### 5. Fun (`cogs/fun.py`)

- `wanted` — Random SA Crime Stoppers wanted image
- `cctv` — Random open CCTV stream
- `redorblack` — Quantum random number generator

### 6. Moderation (`cogs/moderation.py`)

- `purge [amount]` — Bulk message deletion
- `preemptban [user_id] [reason]` — Ban user before joining
- `archive [limit]` — Archive recent messages

### 7. Become (`cogs/become.py`)

- `become [language]` — Bot translates all responses in a channel
- `becomelist` — List available languages

### 8. Owner (`cogs/owner.py`)

Management for the bot owner.

- `sync [scope]`, `unsync [scope]`, `load [cog]`, `unload [cog]`, `reload [cog]`

### 9. Sidepipe (`cogs/sidepipe.py`)

Server-specific functions (e.g. `cctvselfie`) for a particular server. **Remove or replace this for custom deployments.**

---

## Shodan Integration Details (`cogs/shodan.py`)

- **Command**: `/shodan <city>` or `shodan <city>`
- **Description**: Find and display random internet-exposed devices in a given city with a live screenshot. Includes all available device metadata.
- **Interactive features**:
  - Retry button—fetches more random results (unique per session).
  - "Open in Shodan" button—direct link to original device.
  - Only the command invoker can use retry to avoid abuse.
- **Screenshot handling**: Image is decoded from API, sent as a secure Discord attachment, and included in embed; failures and missing images are handled gracefully.
- **Metadata shown**: IP, port, organization, ASN, product, country/region, hostnames, domains, and more.
- **Config required**: `SHODAN_KEY` environment variable. (API key for Shodan.)
- **Permissions**: No elevated Discord permissions required.

---

## Configuration

### Environment Variables

| Variable             | Required | Description                                    |
|----------------------|----------|------------------------------------------------|
| `TOKEN`              | Yes      | Discord bot token                              |
| `GEMINI_KEYS`        | Yes*     | [AI] Gemini API keys (JSON array string)       |
| `AUTO1111_HOSTS`     | No       | [AI] Stable Diffusion host URLs                |
| `LMS_HOSTS`          | No       | [AI] LM Studio URL list                        |
| `LOGGING_CHANNEL`    | No       | Command log channel                            |
| `STATUSES`           | No       | Status rotation list                           |
| `GEOWIFI_URL`        | No       | GeoWifi API URL                                |
| `HTTP_PROXY`         | No       | HTTP proxy URL (for outgoing requests)         |
| `LIBRETRANSLATE_URL` | No       | LibreTranslate server URL                      |
| `SHODAN_KEY`         | Yes      | Shodan API key (required for Shodan features)  |
| `HASS_URL`           | No       | [Sidepipe] Home Assistant server URL           |
| `HASS_TOKEN`         | No       | [Sidepipe] Home Assistant API token            |

*AI features (gemini/wizard/sd) need `GEMINI_KEYS`, but rest of the bot will run without; Shodan command requires `SHODAN_KEY`.

### Dependencies

- `discord.py` — Discord API wrapper
- `aiohttp` — Async HTTP requests
- `beautifulsoup4` — HTML parsing utilities
- `pillow` — Image decoding
- See `requirements.txt`

---

## Deployment

### Docker

```
docker build -t neurodivergence:latest .
docker run -d \
  -e TOKEN=your_discord_token \
  -e SHODAN_KEY=your_shodan_api_key \
  ...[other options]...
  --restart unless-stopped \
  neurodivergence:latest
```

### Local

```
pip install -r requirements.txt
# set env vars, e.g. in .env
python bot.py
```

---

## Logging

- **Console**: Color-coded output, with timestamps and severity.
- **File**: Plain logs in `discord.log`
- **Discord Channel**: Command log to channel if enabled.

---

## Error Handling

- User-facing errors for cooldowns, Discord permission problems, missing arguments, owner-only commands
- API failures (AI, Shodan, etc) yield useful explanations and safe fallback

---

## Extending and Cogs

Create new cogs by subclassing `commands.Cog` and exposing `commands.hybrid_command` or decorator-based command handlers. See any cog (e.g., `cogs/shodan.py`) for examples of:
- Custom `discord.ui.View` for rich interactions (see Shodan for button + retry logic)
- Robust handling for user permissions, API failures, and async workflow

---

## Security

- Never commit/live Share bot tokens or private API keys
- Shodan screenshot content is sandboxed as Discord attachments, not exposed via public links
- Mod commands are permission-gated

---

## Troubleshooting

- **Bot not responding**: Check permissions, intents, and logs
- **Shodan command fails**: Ensure `SHODAN_KEY` is set and valid, bot has embed/file/upload permissions, and Shodan API is not rate-limited; check logs
- **AI/Image generation**: Ensure `GEMINI_KEYS`, `AUTO1111_HOSTS`, or other relevant config is present and valid

---

## License and Contribution

See repo for details. PRs and forks are welcome for learning or self-hosting!

