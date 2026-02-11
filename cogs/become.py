import discord
from discord import app_commands
from discord.ext import commands
from discord.ext.commands import Context
import aiohttp
import os

libretranslate_url = os.environ.get("LIBRETRANSLATE_URL", "http://localhost:5000")

MODES = {
    "arabic": {"target": "ar", "marker": " 🇸🇦"},
    "azerbaijani": {"target": "az", "marker": " 🇦🇿"},
    "bengali": {"target": "bn", "marker": " 🇧🇩"},
    "bulgarian": {"target": "bg", "marker": " 🇧🇬"},
    "catalan": {"target": "ca", "marker": " 🏴"},
    "chinese": {"target": "zh", "marker": " 🇨🇳"},
    "chinese (traditional)": {"target": "zt", "marker": " 🇹🇼"},
    "czech": {"target": "cs", "marker": " 🇨🇿"},
    "danish": {"target": "da", "marker": " 🇩🇰"},
    "dutch": {"target": "nl", "marker": " 🇳🇱"},
    "esperanto": {"target": "eo", "marker": " 🟢"},
    "estonian": {"target": "et", "marker": " 🇪🇪"},
    "finnish": {"target": "fi", "marker": " 🇫🇮"},
    "french": {"target": "fr", "marker": " 🇫🇷"},
    "galician": {"target": "gl", "marker": " 🏴"},
    "german": {"target": "de", "marker": " 🇩🇪"},
    "greek": {"target": "el", "marker": " 🇬🇷"},
    "hebrew": {"target": "he", "marker": " 🇮🇱"},
    "hindi": {"target": "hi", "marker": " 🇮🇳"},
    "hungarian": {"target": "hu", "marker": " 🇭🇺"},
    "indonesian": {"target": "id", "marker": " 🇮🇩"},
    "irish": {"target": "ga", "marker": " 🇮🇪"},
    "italian": {"target": "it", "marker": " 🇮🇹"},
    "japanese": {"target": "ja", "marker": " 🇯🇵"},
    "korean": {"target": "ko", "marker": " 🇰🇷"},
    "kyrgyz": {"target": "ky", "marker": " 🇰🇬"},
    "latvian": {"target": "lv", "marker": " 🇱🇻"},
    "lithuanian": {"target": "lt", "marker": " 🇱🇹"},
    "malay": {"target": "ms", "marker": " 🇲🇾"},
    "norwegian": {"target": "nb", "marker": " 🇳🇴"},
    "persian": {"target": "fa", "marker": " 🇮🇷"},
    "polish": {"target": "pl", "marker": " 🇵🇱"},
    "portuguese": {"target": "pt", "marker": " 🇵🇹"},
    "portuguese-brazil": {"target": "pb", "marker": " 🇧🇷"},
    "romanian": {"target": "ro", "marker": " 🇷🇴"},
    "russian": {"target": "ru", "marker": " 🇷🇺"},
    "slovak": {"target": "sk", "marker": " 🇸🇰"},
    "slovenian": {"target": "sl", "marker": " 🇸🇮"},
    "spanish": {"target": "es", "marker": " 🇪🇸"},
    "albanian": {"target": "sq", "marker": " 🇦🇱"},
    "swedish": {"target": "sv", "marker": " 🇸🇪"},
    "tagalog": {"target": "tl", "marker": " 🇵🇭"},
    "thai": {"target": "th", "marker": " 🇹🇭"},
    "turkish": {"target": "tr", "marker": " 🇹🇷"},
    "ukrainian": {"target": "uk", "marker": " 🇺🇦"},
    "urdu": {"target": "ur", "marker": " 🇵🇰"},
    "vietnamese": {"target": "vi", "marker": " 🇻🇳"},
    "basque": {"target": "eu", "marker": " 🏴"},
}

ALL_MARKERS = [m["marker"] for m in MODES.values()]

class Become(commands.Cog, name="become"):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.morphed_channels = {}

    async def translate(self, text, target):
        if not text:
            return text
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{libretranslate_url}/translate", json={
                "q": text,
                "source": "en",
                "target": target,
            }) as response:
                if response.status != 200:
                    return text
                data = await response.json()
                return data.get("translatedText", text)

    async def translate_embed(self, embed, mode):
        marker = MODES[mode]["marker"]
        target = MODES[mode]["target"]
        new_embed = discord.Embed(
            title=await self.translate(embed.title, target) if embed.title else embed.title,
            description=await self.translate(embed.description, target) if embed.description else embed.description,
            color=embed.color,
        )
        for field in embed.fields:
            new_embed.add_field(
                name=await self.translate(field.name, target),
                value=await self.translate(field.value, target),
                inline=field.inline,
            )
        new_embed.set_footer(text=f"i'm {mode}{marker}")
        return new_embed

    def is_already_translated(self, message):
        for marker in ALL_MARKERS:
            if message.content and message.content.endswith(marker):
                return True
        for embed in message.embeds:
            if embed.footer and embed.footer.text and embed.footer.text.startswith("i'm "):
                return True
        return False

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author != self.bot.user:
            return
        if message.channel.id not in self.morphed_channels:
            return
        if self.is_already_translated(message):
            return
        await self.translate_message(message)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if after.author != self.bot.user:
            return
        if after.channel.id not in self.morphed_channels:
            return
        if self.is_already_translated(after):
            return
        await self.translate_message(after)

    async def translate_message(self, message):
        try:
            mode = self.morphed_channels[message.channel.id]
            target = MODES[mode]["target"]
            marker = MODES[mode]["marker"]
            new_content = None
            if message.content:
                new_content = await self.translate(message.content, target) + marker
            new_embeds = [await self.translate_embed(e, mode) for e in message.embeds] if message.embeds else []
            await message.edit(content=new_content, embeds=new_embeds or [])
        except Exception:
            pass

    async def mode_autocomplete(self, interaction: discord.Interaction, current: str):
        choices = [app_commands.Choice(name="Neuro (default)", value="neuro")]
        choices += [
            app_commands.Choice(name=f"{name.title()} {MODES[name]['marker'].strip()}", value=name)
            for name in sorted(MODES.keys())
            if current.lower() in name
        ]
        return choices[:25]

    @commands.hybrid_command(
        name="become",
        description="become a language in this channel",
    )
    @app_commands.autocomplete(mode=mode_autocomplete)
    async def become(self, ctx, mode: str):
        mode = mode.lower()
        if mode == "neuro":
            self.morphed_channels.pop(ctx.channel.id, None)
            embed = discord.Embed(title="become OFF", description="back to normal neuro brain")
            await ctx.reply(embed=embed)
        elif mode in MODES:
            self.morphed_channels[ctx.channel.id] = mode
            marker = MODES[mode]["marker"]
            embed = discord.Embed(title=f"become → {mode}{marker}", description=f"all bot responses in this channel will now be {mode}")
            await ctx.reply(embed=embed)
        else:
            embed = discord.Embed(title="become failed", description=f"'{mode}' isn't a language dummy")
            await ctx.reply(embed=embed)

    @commands.hybrid_command(
        name="becomelist",
        description="list all available languages to become",
    )
    async def becomelist(self, ctx):
        lines = [f"{MODES[name]['marker'].strip()} {name.title()}" for name in sorted(MODES.keys())]
        embed = discord.Embed(title="become languages", description="\n".join(lines))
        await ctx.reply(embed=embed)

async def setup(bot) -> None:
    await bot.add_cog(Become(bot))
