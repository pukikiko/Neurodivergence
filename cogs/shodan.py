import base64
import io
import os
import random
from typing import Any, Dict, Optional, Tuple, List

import aiohttp
import discord
from discord.ext import commands

SHODAN_SEARCH_URL = "https://api.shodan.io/shodan/host/search"
SHODAN_HOST_URL = "https://www.shodan.io/host"

def _safe_join(items, limit: int = 3) -> str:
    if not items or not isinstance(items, (list, tuple)):
        return str(items) if items else "N/A"
    trimmed = [str(x) for x in items if x is not None and str(x).strip()]
    if not trimmed:
        return "N/A"
    if len(trimmed) > limit:
        return ", ".join(trimmed[:limit]) + f" (+{len(trimmed) - limit} more)"
    return ", ".join(trimmed)

def _extract_screenshot(match: Dict[str, Any]) -> Optional[Tuple[bytes, str]]:
    screenshot = match.get("screenshot")
    if not isinstance(screenshot, dict):
        return None
    data_b64 = screenshot.get("data")
    if not data_b64:
        return None
    mime = screenshot.get("mime") or "image/jpeg"
    ext = mime.split("/")[-1].lower()
    try:
        return base64.b64decode(data_b64), ext
    except Exception:
        return None

def _get_data_str(match: Dict[str, Any]) -> Optional[str]:
    """Returns the raw data as a string if available, else None."""
    data = match.get("data")
    if not data:
        return None
    if isinstance(data, bytes):
        try:
            data = data.decode(errors="replace")
        except Exception:
            data = str(data)
    if not isinstance(data, str):
        data = str(data)
    return data

def _get_concatenated_raw_data_file(matches: List[Dict[str, Any]], base_filename: str, start_idx: int) -> Optional[discord.File]:
    """
    Returns a discord.File with the concatenated 'data' fields from the given matches.
    """
    contents = []
    for idx, match in enumerate(matches, start=start_idx + 1):
        ip = match.get("ip_str") or "N/A"
        port = match.get("port") or "N/A"
        banner = _get_data_str(match)
        header = f"========== [{idx}] {ip}:{port} ==========\n"
        if banner:
            contents.append(header + banner + "\n")
    if not contents:
        return None
    joined = "\n".join(contents)
    data_bytes = joined.encode("utf-8", errors="replace")
    # Discord (2024) allows up to 25MB per file, up to 10 attachments.
    # Let's cap raw data size to a few MB to be safe.
    MAX_SIZE = 8 * 1024 * 1024
    truncated = False
    if len(data_bytes) > MAX_SIZE:
        data_bytes = data_bytes[:MAX_SIZE]
        data_bytes += b"\n... (truncated)\n"
        truncated = True
    filename_root = base_filename.replace(" ", "_").lower()
    filename = f"{filename_root}_raw_data.txt"
    fileobj = io.BytesIO(data_bytes)
    return discord.File(fileobj, filename=filename)

class ShodanPageView(discord.ui.View):
    def __init__(
        self,
        *,
        requester: discord.User,
        matches: List[Dict[str, Any]],
        page_size: int = 10,
        page: int = 0,
        screenshots: bool = False,
        query: str = "",
        timeout: float = 120.0,
    ):
        super().__init__(timeout=timeout)
        self.requester_id = getattr(requester, "id", None)
        self.matches = matches
        self.page_size = page_size
        self.page = page
        self.screenshots = screenshots
        self.query = query

        self.total_pages = max(1, (len(matches) + page_size - 1) // page_size)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.requester_id is not None and interaction.user.id != self.requester_id:
            await interaction.response.send_message(
                "Only the original requester can use this button.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="◀ Previous Page", style=discord.ButtonStyle.primary, row=0, custom_id="shodan_prev")
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page -= 1
        await self._update_message(interaction)
    
    @discord.ui.button(label="Next Page ▶", style=discord.ButtonStyle.primary, row=0, custom_id="shodan_next")
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page += 1
        await self._update_message(interaction)

    async def _update_message(self, interaction: discord.Interaction):
        for item in self.children:
            item.disabled = False
        if self.page <= 0:
            self.previous_page.disabled = True
        if self.page >= self.total_pages - 1:
            self.next_page.disabled = True

        embed, files = await self.format_embed_and_files()
        await interaction.response.edit_message(
            embed=embed,
            attachments=files if files else [],
            view=self
        )

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

    async def format_embed_and_files(self) -> Tuple[discord.Embed, Optional[List[discord.File]]]:
        """
        Returns a tuple of (discord.Embed, Optional[List[discord.File]]) for current page.
        Files can be screenshot image and/or raw data .txt.
        """
        start = self.page * self.page_size
        end = min(len(self.matches), start + self.page_size)
        current_matches = self.matches[start:end]

        if not self.screenshots:
            desc_lines = []
            files = []
            # Prepare single concatenated raw data file for this page
            # Use the city/first IP of page for filename root, otherwise fallback.
            if current_matches:
                sample_ip = current_matches[0].get("ip_str") or "page"
            else:
                sample_ip = "page"
            raw_file = _get_concatenated_raw_data_file(current_matches, f"{sample_ip}_{start+1}-{end}", start)
            for idx, m in enumerate(current_matches, start=start + 1):
                ip = m.get("ip_str") or "N/A"
                port = m.get("port") or "N/A"
                org = m.get("org") or m.get("isp") or "N/A"
                product = m.get("product") or "N/A"
                asn = m.get("asn") or "N/A"
                hostnames = _safe_join(m.get("hostnames"))
                domains = _safe_join(m.get("domains"))
                location = m.get("location") if isinstance(m.get("location"), dict) else {}
                country = location.get("country_name") or location.get("country_code") or "N/A"
                region = location.get("region_code") or location.get("region_name") or "N/A"
                row = (
                    f"**{idx}.** [`{ip}:{port}`]({SHODAN_HOST_URL}/{ip}) | {org}, {product}\n"
                    f"ASN: {asn} | {country}/{region}\n"
                    f"Hostnames: {hostnames}\nDomains: {domains}\n"
                )
                # Link to single data file if it exists and this row has data
                if raw_file and _get_data_str(m):
                    row += f"[Download raw data](attachment://{raw_file.filename})\n"
                desc_lines.append(row)
            embed = discord.Embed(
                title=f"Shodan Results ({start+1}-{end} of {len(self.matches)})",
                description="\n".join(desc_lines) if desc_lines else "No results.",
                color=discord.Color.blue()
            )
            embed.set_footer(text=f"Page {self.page + 1}/{self.total_pages} | Query: {self.query}")

            for item in self.children:
                if isinstance(item, discord.ui.Button):
                    if item.label.startswith("◀"):
                        item.disabled = self.page <= 0
                    elif item.label.startswith("Next"):
                        item.disabled = self.page >= self.total_pages - 1

            files = [raw_file] if raw_file else []
            return embed, files if files else None
        else:
            match = current_matches[0] if current_matches else None
            files = []
            if not match:
                embed = discord.Embed(title="Shodan", description="No screenshot results on this page.")
                embed.set_footer(text=f"Page {self.page + 1}/{self.total_pages}")
                for item in self.children:
                    if isinstance(item, discord.ui.Button):
                        if item.label.startswith("◀"):
                            item.disabled = self.page <= 0
                        elif item.label.startswith("Next"):
                            item.disabled = self.page >= self.total_pages - 1
                return embed, None
            extracted = _extract_screenshot(match)
            if not extracted:
                embed = discord.Embed(title="Shodan", description="Failed to decode screenshot.")
                embed.set_footer(text=f"Page {self.page + 1}/{self.total_pages}")
                for item in self.children:
                    if isinstance(item, discord.ui.Button):
                        if item.label.startswith("◀"):
                            item.disabled = self.page <= 0
                        elif item.label.startswith("Next"):
                            item.disabled = self.page >= self.total_pages - 1
                return embed, None
            image_bytes, ext = extracted
            hint = match.get('city') or match.get('org') or 'custom'
            filename = f"shodan_{str(hint).lower().replace(' ', '_')}_{start+1}.{ext}"
            image_file = discord.File(io.BytesIO(image_bytes), filename=filename)
            files.append(image_file)

            ip = match.get("ip_str") or "N/A"
            port = match.get("port") or "N/A"
            org = match.get("org") or match.get("isp") or "N/A"
            asn = match.get("asn") or "N/A"
            hostnames = _safe_join(match.get("hostnames"))
            domains = _safe_join(match.get("domains"))
            product = match.get("product") or "N/A"
            transport = match.get("transport") or "N/A"
            timestamp = match.get("timestamp") or "N/A"

            location = match.get("location") if isinstance(match.get("location"), dict) else {}
            country = (location.get("country_name") or location.get("country_code") or "N/A") if location else "N/A"
            region = (location.get("region_code") or location.get("region_name") or "N/A") if location else "N/A"

            # For screenshot mode, keep current behavior: attach corresponding raw data file for the row
            single_raw_file = None
            if _get_data_str(match):
                single_raw_file = _get_concatenated_raw_data_file([match], f"{ip}_{port}", start)
                if single_raw_file:
                    files.append(single_raw_file)
            datalink = f"[Download raw data](attachment://{single_raw_file.filename})\n" if single_raw_file else ""

            embed = discord.Embed(
                title=f'Shodan Screenshot {start+1} of {len(self.matches)}',
                description=(
                    f"Query: `{self.query}`\n[`{ip}:{port}`]({SHODAN_HOST_URL}/{ip}) | {org}\n"
                    f"Product: {product} | Transport: {transport}\n"
                    f"ASN: {asn} | {country}/{region}\n"
                    f"Hostnames: {hostnames}\nDomains: {domains}\n"
                    f"{datalink}"
                ),
            )
            embed.set_footer(text=f"Seen: {timestamp} | Page {self.page + 1}/{self.total_pages}")
            embed.set_image(url=f"attachment://{filename}")

            for item in self.children:
                if isinstance(item, discord.ui.Button):
                    if item.label.startswith("◀"):
                        item.disabled = self.page <= 0
                    elif item.label.startswith("Next"):
                        item.disabled = self.page >= self.total_pages - 1

            return embed, files if files else None

class Shodan(commands.Cog, name="shodan"):
    def __init__(self, bot) -> None:
        self.bot = bot

    @commands.hybrid_command(
        name="shodan",
        description='Search Shodan for a city screenshot (query: city:"<city>" has_screenshot:true)',
    )
    async def shodan(self, ctx, city: str = ""):
        key = os.getenv("SHODAN_KEY")
        if not key:
            embed = discord.Embed(
                title="Shodan",
                description="`SHODAN_KEY` is not set on this bot.",
            )
            await ctx.reply(embed=embed)
            return

        city = (city or "").strip()
        if not city:
            embed = discord.Embed(
                title="Shodan",
                description="Please provide a city name. Example: `/shodan Adelaide`",
            )
            await ctx.reply(embed=embed)
            return

        query = f'city:"{city}" has_screenshot:true'
        embed = discord.Embed(title="Shodan", description=f"Searching: `{query}`\nPlease wait...")
        msg = await ctx.reply(embed=embed)

        params = {
            "key": key,
            "query": query,
            "limit": 100,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(SHODAN_SEARCH_URL, params=params) as resp:
                    if resp.status != 200:
                        try:
                            err = await resp.json()
                            err_msg = err.get("error") or err.get("message") or str(err)
                        except Exception:
                            err_msg = await resp.text()
                        embed = discord.Embed(
                            title="Shodan",
                            description=f"Error from Shodan: `{resp.status}`\n{err_msg}",
                        )
                        await msg.edit(embed=embed)
                        return
                    payload = await resp.json()
        except Exception as e:
            embed = discord.Embed(title="Shodan", description=f"Request failed: `{type(e).__name__}`")
            await msg.edit(embed=embed)
            return

        matches = payload.get("matches") if isinstance(payload, dict) else None
        if not isinstance(matches, list) or not matches:
            embed = discord.Embed(title="Shodan", description="No results.")
            await msg.edit(embed=embed)
            return

        screenshot_matches = [m for m in matches if _extract_screenshot(m)]
        if not screenshot_matches:
            embed = discord.Embed(
                title="Shodan",
                description="Results found, but none included screenshot data.",
            )
            await msg.edit(embed=embed)
            return

        view = ShodanPageView(
            requester=getattr(ctx, "author", getattr(ctx, "user", None)),
            matches=screenshot_matches,
            page_size=1,
            page=0,
            screenshots=True,
            query=query,
        )
        embed, files = await view.format_embed_and_files()
        await msg.edit(embed=embed, attachments=files if files else [], view=view)

    @commands.hybrid_command(
        name="mcserver",
        description='Search Shodan for public Minecraft servers in a given city (query: city:"<city>" port:25565)',
    )
    async def mcserver(self, ctx, city: str = ""):
        key = os.getenv("SHODAN_KEY")
        if not key:
            embed = discord.Embed(
                title="Shodan",
                description="`SHODAN_KEY` is not set on this bot.",
            )
            await ctx.reply(embed=embed)
            return

        city = (city or "").strip()
        if not city:
            embed = discord.Embed(
                title="Minecraft Server Finder",
                description="Please provide a city name. Example: `/mcserver Paris`",
            )
            await ctx.reply(embed=embed)
            return

        query = f'city:"{city}" port:25565'
        embed = discord.Embed(title="Minecraft Server Finder", description=f"Searching: `{query}`\nPlease wait...")
        msg = await ctx.reply(embed=embed)

        params = {
            "key": key,
            "query": query,
            "limit": 100,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(SHODAN_SEARCH_URL, params=params) as resp:
                    if resp.status != 200:
                        try:
                            err = await resp.json()
                            err_msg = err.get("error") or err.get("message") or str(err)
                        except Exception:
                            err_msg = await resp.text()
                        embed = discord.Embed(
                            title="Minecraft Server Finder",
                            description=f"Error from Shodan: `{resp.status}`\n{err_msg}",
                        )
                        await msg.edit(embed=embed)
                        return
                    payload = await resp.json()
        except Exception as e:
            embed = discord.Embed(title="Minecraft Server Finder", description=f"Request failed: `{type(e).__name__}`")
            await msg.edit(embed=embed)
            return

        matches = payload.get("matches") if isinstance(payload, dict) else None
        if not isinstance(matches, list) or not matches:
            embed = discord.Embed(title="Minecraft Server Finder", description="No Minecraft servers found.")
            await msg.edit(embed=embed)
            return

        page_size = 10
        view = ShodanPageView(
            requester=getattr(ctx, "author", getattr(ctx, "user", None)),
            matches=matches,
            page_size=page_size,
            page=0,
            screenshots=False,
            query=query,
        )
        embed, files = await view.format_embed_and_files()
        await msg.edit(embed=embed, attachments=files if files else [], view=view)

    @commands.hybrid_command(
        name="shodan_query",
        description="Search Shodan with a custom query.",
    )
    async def shodan_query(self, ctx, *, query: str = ""):
        key = os.getenv("SHODAN_KEY")
        if not key:
            embed = discord.Embed(
                title="Shodan",
                description="`SHODAN_KEY` is not set on this bot.",
            )
            await ctx.reply(embed=embed)
            return

        query_orig = (query or "").strip()
        screenshots = False
        lower_query = query_orig.lower()
        if "show:screenshot" in lower_query:
            screenshots = True
            base_query = query_orig.replace("show:screenshot", "").replace("SHOW:SCREENSHOT", "")
        elif "show:list" in lower_query:
            screenshots = False
            base_query = query_orig.replace("show:list", "").replace("SHOW:LIST", "")
        else:
            screenshots = "has_screenshot:true" in lower_query
            base_query = query_orig

        query = base_query.strip()
        if screenshots and "has_screenshot:true" not in query.lower():
            query = (query + " has_screenshot:true").strip()

        embed = discord.Embed(title="Shodan", description=f"Searching: `{query}`\nPlease wait...")
        msg = await ctx.reply(embed=embed)

        params = {
            "key": key,
            "query": query,
            "limit": 100,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(SHODAN_SEARCH_URL, params=params) as resp:
                    if resp.status != 200:
                        try:
                            err = await resp.json()
                            err_msg = err.get("error") or err.get("message") or str(err)
                        except Exception:
                            err_msg = await resp.text()
                        embed = discord.Embed(
                            title="Shodan",
                            description=f"Error from Shodan: `{resp.status}`\n{err_msg}",
                        )
                        await msg.edit(embed=embed)
                        return
                    payload = await resp.json()
        except Exception as e:
            embed = discord.Embed(title="Shodan", description=f"Request failed: `{type(e).__name__}`")
            await msg.edit(embed=embed)
            return

        matches = payload.get("matches") if isinstance(payload, dict) else None
        if not isinstance(matches, list) or not matches:
            embed = discord.Embed(title="Shodan", description="No results.")
            await msg.edit(embed=embed)
            return

        if screenshots:
            screenshot_matches = [m for m in matches if _extract_screenshot(m)]
            if not screenshot_matches:
                embed = discord.Embed(
                    title="Shodan",
                    description="Results found, but none included screenshot data.",
                )
                await msg.edit(embed=embed)
                return

            view = ShodanPageView(
                requester=getattr(ctx, "author", getattr(ctx, "user", None)),
                matches=screenshot_matches,
                page_size=1,
                page=0,
                screenshots=True,
                query=query_orig,
            )
            embed, files = await view.format_embed_and_files()
            await msg.edit(embed=embed, attachments=files if files else [], view=view)
        else:
            page_size = 10
            view = ShodanPageView(
                requester=getattr(ctx, "author", getattr(ctx, "user", None)),
                matches=matches,
                page_size=page_size,
                page=0,
                screenshots=False,
                query=query_orig,
            )
            embed, files = await view.format_embed_and_files()
            await msg.edit(embed=embed, attachments=files if files else [], view=view)

async def setup(bot) -> None:
    await bot.add_cog(Shodan(bot))
