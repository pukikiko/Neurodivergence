import asyncio
import io
from pathlib import Path

import discord
from discord.ext import commands
from discord.ext.commands import Context
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from weasyprint import HTML


TEMPLATE_SUBDIR = Path("letters") / "templates"


def _html_to_pdf_bytes(*, html: str, base_url: str) -> bytes:
    # WeasyPrint returns PDF bytes directly.
    return HTML(string=html, base_url=base_url).write_pdf()


class Letters(commands.Cog, name="letters"):
    def __init__(self, bot) -> None:
        self.bot = bot

        repo_root = Path(__file__).resolve().parents[1]
        templates_dir = repo_root / TEMPLATE_SUBDIR
        self.templates_dir = templates_dir

        self.jinja_env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=select_autoescape(["html", "xml"]),
            undefined=StrictUndefined,
        )

    def _render_letter_html(self, *, template_name: str, variables: dict) -> str:
        template = self.jinja_env.get_template(template_name)
        return template.render(**variables)

    async def _render_and_convert_pdf(
        self, *, template_name: str, variables: dict
    ) -> bytes:
        rendered_html = self._render_letter_html(
            template_name=template_name, variables=variables
        )
        # Convert in a worker thread so the Discord event loop stays responsive.
        return await asyncio.to_thread(
            _html_to_pdf_bytes,
            html=rendered_html,
            base_url=str(self.templates_dir),
        )

    @commands.hybrid_command(
        name="birthday_letter",
        description="Generate a funny birthday letter PDF from an HTML template.",
    )
    async def birthday_letter(
        self,
        ctx: Context,
        recipient_name: str,
        sender_name: str,
        age: int,
    ) -> None:
        embed = discord.Embed(
            title="Birthday Letter",
            description="Generating your PDF... Please wait.",
        )
        msg = await ctx.reply(embed=embed)

        try:
            pdf_bytes = await self._render_and_convert_pdf(
                template_name="birthday_letter.html",
                variables={
                    "recipient_name": recipient_name,
                    "sender_name": sender_name,
                    "age": age,
                },
            )
        except Exception as e:
            # Log full error server-side; show short message to user.
            if hasattr(self.bot, "logger"):
                self.bot.logger.exception("Failed to generate birthday_letter PDF")
            await msg.edit(
                embed=discord.Embed(
                    title="Birthday Letter",
                    description="Could not generate the PDF (template/render error).",
                    color=0xE02B2B,
                )
            )
            return

        await msg.delete()
        filename = f"birthday_letter_{ctx.message.id}.pdf"
        await ctx.reply(file=discord.File(io.BytesIO(pdf_bytes), filename=filename))

    @commands.hybrid_command(
        name="apology_letter",
        description="Generate a funny apology letter PDF from an HTML template.",
    )
    async def apology_letter(
        self,
        ctx: Context,
        recipient_name: str,
        sender_name: str,
        *,
        reason: str,
    ) -> None:
        embed = discord.Embed(
            title="Apology Letter",
            description="Generating your PDF... Please wait.",
        )
        msg = await ctx.reply(embed=embed)

        try:
            pdf_bytes = await self._render_and_convert_pdf(
                template_name="apology_letter.html",
                variables={
                    "recipient_name": recipient_name,
                    "sender_name": sender_name,
                    "reason": reason,
                },
            )
        except Exception:
            if hasattr(self.bot, "logger"):
                self.bot.logger.exception("Failed to generate apology_letter PDF")
            await msg.edit(
                embed=discord.Embed(
                    title="Apology Letter",
                    description="Could not generate the PDF (template/render error).",
                    color=0xE02B2B,
                )
            )
            return

        await msg.delete()
        filename = f"apology_letter_{ctx.message.id}.pdf"
        await ctx.reply(file=discord.File(io.BytesIO(pdf_bytes), filename=filename))


async def setup(bot) -> None:
    await bot.add_cog(Letters(bot))

