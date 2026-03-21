# THIS NEEDS TO BE REWRITTEN

# Neurodivergence

Freshly rewritten!

A Discord bot with an array of interesting features, this project was my excuse to learn Python.

have fun!

## Running your own instance

Before you begin, you will need git and Docker installed to run Neurodivergence, so make sure you have those installed.

https://git-scm.com/book/en/v2/Getting-Started-Installing-Git

https://docs.docker.com/engine/install/

Now, you will need to clone the repo and build the Docker image.

    git clone https://github.com/SWAGNET-Enterprises/Neurodivergence.git
    cd Neurodivergence
    docker build -t neurodivergence:latest .

### Now we can run the bot!

    docker run -d -e TOKEN=your_discord_token -e GEMINI_KEYS=["your_gemini_api_key", "your_other_gemini_api_key"] -e AUTO1111_HOSTS=["http://host1:7860", "http://host2:7860"] -e LMS_HOSTS=["http://host1:1234", "http://host2:1234"] -e LOGGING_CHANNEL=0123456789012345678 -e STATUSES=["68+% of people fail VORT", "CBT&A costs $3000"] -e GEOWIFI_URL=http://127.0.0.1:5000/geowifi -e HTTP_PROXY=http://100.65.0.1:8888 --restart unless-stopped neurodivergence:latest

Make sure that all environment variables are set up correctly before running the bot, things can go sideways if they are misconfigured.

### Environment Variables

| Variable        | Description                                                                                                |
| --------------- | ---------------------------------------------------------------------------------------------------------- |
| TOKEN           | Your Discord bot token, obtained here: https://discord.com/developers/applications                         |
| GEMINI_KEYS     | Your Google Gemini API Keys in list format: ["your_gemini_api_key", "your_other_gemini_api_key"]          |
| AUTO1111_HOSTS  | Your Automatic1111 Stable Diffusion WebUI hosts in list format: ["http://host1:7860", "http://host2:7860"] |
| LMS_HOSTS       | Your Automatic1111 LM Studio hosts in list format: ["http://host1:1234", "http://host2:1234"]              |
| LOGGING_CHANNEL | Your Discord channel used for logging: 0123456789012345678                                                 |
| STATUSES        | The statuses you want the bot to display in list format: ["68+% of people fail VORT", "CBT&A costs $3000"] |
| GEOWIFI_URL     | The URL for your GeoWifi API instance, more info: https://github.com/SWAGNET-Enterprises/geowifi-api       |
| HTTP_PROXY      | The URL of your HTTP proxy used for fetching data: http://100.65.0.1:8888                                  |
| SHODAN_KEY      | API key for shodan.io - provides API access for cogs/shodan.py                                             |

### The Sidepipe Cog

There is a cog inside the cogs folder (sidepipe.py) which contains functions specific to The Sidepipe discord server, this cog is only included for code reference and should be deleted before starting your own instance, unless you wish to modify it and use it for your own purposes ;)
