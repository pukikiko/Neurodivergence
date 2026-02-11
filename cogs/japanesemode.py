import discord
from discord.ext import commands
from discord.ext.commands import Context
import aiohttp
import os

libretranslate_url = os.environ.get("LIBRETRANSLATE_URL", "http://localhost:5000")

# this is so jank but it makes it funnier
TRANSLATED_FOOTER = "🇯🇵 JAPAN JAPAN JAPAN IT'S GREAT"
TRANSLATED_MARKER = " 🇯🇵"

class JapaneseMode(commands.Cog, name="japanesemode"):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.toggled_channels = set()

    async def translate(self, text):
        if not text:
            return text
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{libretranslate_url}/translate", json={
                "q": text,
                "source": "en",
                "target": "ja",
            }) as response:
                if response.status != 200:
                    return text
                data = await response.json()
                return data.get("translatedText", text)

    async def translate_embed(self, embed):
        new_embed = discord.Embed(
            title=await self.translate(embed.title) if embed.title else embed.title,
            description=await self.translate(embed.description) if embed.description else embed.description,
            color=embed.color,
        )
        for field in embed.fields:
            new_embed.add_field(
                name=await self.translate(field.name),
                value=await self.translate(field.value),
                inline=field.inline,
            )
        new_embed.set_footer(text=TRANSLATED_FOOTER)
        return new_embed

    def is_already_translated(self, message):
        # jank 2
        if message.content and message.content.endswith(TRANSLATED_MARKER):
            return True
        for embed in message.embeds:
            if embed.footer and embed.footer.text == TRANSLATED_FOOTER:
                return True
        return False

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author != self.bot.user:
            return
        if message.channel.id not in self.toggled_channels:
            return
        if self.is_already_translated(message):
            return
        await self.translate_message(message)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if after.author != self.bot.user:
            return
        if after.channel.id not in self.toggled_channels:
            return
        if self.is_already_translated(after):
            return
        await self.translate_message(after)

    async def translate_message(self, message):
        try:
            new_content = None
            if message.content:
                new_content = await self.translate(message.content) + TRANSLATED_MARKER
            new_embeds = [await self.translate_embed(e) for e in message.embeds] if message.embeds else []
            await message.edit(content=new_content, embeds=new_embeds or [])
        except Exception:
            pass

    @commands.hybrid_command(
        name="becomejapanese",
        description="toggle japanese mode for this channel. all bot responses become japanese",
    )
    async def becomejapanese(self, ctx):
        if ctx.channel.id in self.toggled_channels:
            self.toggled_channels.discard(ctx.channel.id)
            embed = discord.Embed(title="japanese mode OFF", description="no longer japanese :(")
            await ctx.reply(embed=embed)
        else:
            self.toggled_channels.add(ctx.channel.id)
            embed = discord.Embed(title="japanese mode ON", description="all bot responses in this channel will now become japanese")
            embed.set_footer(text=TRANSLATED_FOOTER)
            await ctx.reply(embed=embed)

    @commands.hybrid_command(
        name="japanesemode",
        description="i takeuh your message, become japanese",
    )
    async def japanesemode(self, ctx, *, text: str):
        embed = discord.Embed(title="japanese mode ON", description="becoming japanese...")
        msg = await ctx.reply(embed=embed)

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(f"{libretranslate_url}/translate", json={
                    "q": text,
                    "source": "en",
                    "target": "ja",
                }) as response:
                    if response.status != 200:
                        embed = discord.Embed(title="japanesemode failed", description=f"could not become japanese :( ({response.status})")
                        await msg.edit(embed=embed)
                        return
                    data = await response.json()
            except aiohttp.ClientError:
                embed = discord.Embed(title="japanesemode is fucking dead :(", description="libretranslate IS FUCKING DEAD or something idk @174360161643659265 fix it")
                await msg.edit(embed=embed)
                return

        translated = data.get("translatedText", "idk what happened but i can't be japanese")
        embed = discord.Embed(title="日本人になる", description=translated)
        embed.set_footer(text=TRANSLATED_FOOTER)
        await msg.edit(embed=embed)

async def setup(bot) -> None:
    await bot.add_cog(JapaneseMode(bot))
