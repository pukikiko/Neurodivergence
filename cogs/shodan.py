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
    if not items:
        return "N/A"
    if isinstance(items, (list, tuple)):
        trimmed = [str(x) for x in items if x is not None and str(x).strip()]
        if not trimmed:
            return "N/A"
        if len(trimmed) > limit:
            return ", ".join(trimmed[:limit]) + f" (+{len(trimmed) - limit} more)"
        return ", ".join(trimmed)
    return str(items)

def _extract_screenshot(match: Dict[str, Any]) -> Optional[Tuple[bytes, str]]:
    """
    Shodan can include screenshots as base64 in `match["screenshot"]["data"]`.
    Returns (bytes, ext) or None.
    """
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

class RetryShodanButton(discord.ui.View):
    def __init__(
        self,
        user: discord.User,
        city: str,
        screenshot_matches: List[Dict[str, Any]],
        already_used_indices: Optional[List[int]] = None,
        timeout: float = 60.0,
    ):
        super().__init__(timeout=timeout)
        self.requester_id = getattr(user, 'id', None)
        self.city = city
        self.screenshot_matches = screenshot_matches
        self.already_used_indices = already_used_indices or []
        self.current_ip = None  # Will hold the IP of the *most recent* shown result
        self._add_shodan_button(initial_ip=None)  # Placeholder until first generate_embed_and_file()

    def _add_shodan_button(self, initial_ip=None):
        # Remove old link button(s) if any, then add the new one for the current IP.
        for child in list(self.children):
            # Remove only link buttons with custom_ids (leaves retry button present)
            if isinstance(child, discord.ui.Button) and getattr(child, 'custom_id', "").startswith("shodan_device_"):
                self.remove_item(child)
        ip = initial_ip or self.current_ip
        # Only provide a link button; don't supply a custom_id 
        if ip:
            shodan_url = f"{SHODAN_HOST_URL}/{ip}"
            # Per discord.py/lib: don't set custom_id when url is present!
            self.add_item(discord.ui.Button(label="Open in Shodan", url=shodan_url, style=discord.ButtonStyle.link))

    async def disable_all(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button) and not (child.style == discord.ButtonStyle.link):
                child.disabled = True

    async def generate_embed_and_file(self, random_index=None):
        matches = self.screenshot_matches
        total = len(matches)
        available_indices = list(set(range(total)) - set(self.already_used_indices))
        if not available_indices:
            embed = discord.Embed(
                title="Shodan",
                description="No more unique results left for retry.",
            )
            return embed, None, None
        if random_index is None:
            idx = random.choice(available_indices)
        else:
            idx = random_index
        match = matches[idx]
        extracted = _extract_screenshot(match)
        if not extracted:
            embed = discord.Embed(
                title="Shodan",
                description="Failed to decode screenshot.",
            )
            return embed, None, None
        image_bytes, ext = extracted
        filename = f"shodan_{self.city.lower().replace(' ', '_')}.{ext}"
        file = discord.File(io.BytesIO(image_bytes), filename=filename)

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

        embed = discord.Embed(
            title=f"Shodan screenshot — {self.city}",
            description=f'Query: `city:"{self.city}" has_screenshot:true`',
        )
        embed.add_field(name="IP:Port", value=f"`{ip}:{port}`", inline=True)
        embed.add_field(name="Org/ISP", value=str(org), inline=True)
        if asn and asn != "N/A":
            mxtoolbox_url = f"https://mxtoolbox.com/SuperTool.aspx?action=asn%3a{asn}&run=toolpage"
            asn_value = f"[{asn}]({mxtoolbox_url})"
        else:
            asn_value = "N/A"
        embed.add_field(name="ASN", value=asn_value, inline=True)
        embed.add_field(name="Country/Region", value=f"{country} / {region}", inline=True)
        embed.add_field(name="Product", value=str(product), inline=True)
        embed.add_field(name="Transport", value=str(transport), inline=True)
        embed.add_field(name="Hostnames", value=hostnames, inline=False)
        embed.add_field(name="Domains", value=domains, inline=False)
        embed.set_footer(text=f"Seen: {timestamp}")
        embed.set_image(url=f"attachment://{filename}")

        # Set up the correct Open in Shodan link button (no custom_id!)
        if ip and ip != "N/A":
            self.current_ip = ip
            self._add_shodan_button(initial_ip=ip)
        else:
            self.current_ip = None
            self._add_shodan_button(initial_ip=None)

        return embed, file, idx

    @discord.ui.button(label="Retry", style=discord.ButtonStyle.primary, custom_id="shodan_retry")
    async def retry(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Use the saved requester ID to compare instead of interaction.message.user.id.
        if self.requester_id is not None and interaction.user.id != self.requester_id:
            await interaction.response.send_message(
                "Only the original requester can use this button.", ephemeral=True
            )
            return

        embed, file, idx = await self.generate_embed_and_file()
        if file is None:
            await self.disable_all()
            await interaction.response.edit_message(embed=embed, view=self, attachments=[])
            return
        self.already_used_indices.append(idx)
        await interaction.response.edit_message(embed=embed, view=self, attachments=[file])

    async def on_timeout(self):
        await self.disable_all()
        try:
            pass
        except Exception:
            pass

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

        idx = random.randrange(len(screenshot_matches))
        match = screenshot_matches[idx]
        extracted = _extract_screenshot(match)
        if not extracted:
            embed = discord.Embed(
                title="Shodan",
                description="Failed to decode screenshot.",
            )
            await msg.edit(embed=embed)
            return

        image_bytes, ext = extracted
        filename = f"shodan_{city.lower().replace(' ', '_')}.{ext}"
        file = discord.File(io.BytesIO(image_bytes), filename=filename)

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

        embed = discord.Embed(
            title=f"Shodan screenshot — {city}",
            description=f'Query: `city:"{city}" has_screenshot:true`',
        )
        embed.add_field(name="IP:Port", value=f"`{ip}:{port}`", inline=True)
        embed.add_field(name="Org/ISP", value=str(org), inline=True)
        asn_link = f"https://mxtoolbox.com/SuperTool.aspx?action=asn%3a{asn}&run=toolpage" if asn != "N/A" else None
        if asn_link:
            embed.add_field(name="ASN", value=f"[{asn}]({asn_link})", inline=True)
        else:
            embed.add_field(name="ASN", value=str(asn), inline=True)
        embed.add_field(name="Country/Region", value=f"{country} / {region}", inline=True)
        embed.add_field(name="Product", value=str(product), inline=True)
        embed.add_field(name="Transport", value=str(transport), inline=True)
        embed.add_field(name="Hostnames", value=hostnames, inline=False)
        embed.add_field(name="Domains", value=domains, inline=False)
        embed.set_footer(text=f"Seen: {timestamp}")
        embed.set_image(url=f"attachment://{filename}")

        shodan_url = None
        if ip and ip != "N/A":
            shodan_url = f"{SHODAN_HOST_URL}/{ip}"

        view = RetryShodanButton(
            user=getattr(ctx, "author", getattr(ctx, "user", None)),
            city=city,
            screenshot_matches=screenshot_matches,
            already_used_indices=[idx],
        )
        # Do NOT provide custom_id for a link button!
        if shodan_url:
            view._add_shodan_button(initial_ip=ip)

        try:
            await msg.delete()
        except Exception:
            pass
        await ctx.reply(embed=embed, file=file, view=view)

async def setup(bot) -> None:
    await bot.add_cog(Shodan(bot))
