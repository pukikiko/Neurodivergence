import discord
from discord.ext import commands
from discord.ext.commands import Context
import aiohttp
from bs4 import BeautifulSoup
import re
import os
import urllib.parse

headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0'}

class Utility(commands.Cog, name="utility"):
    def __init__(self, bot) -> None:
        self.bot = bot

    @commands.hybrid_command(
        name="weather",
        description="See the current weather (Australia)",
    )
    async def weather(self, ctx, town="adelaide", state="sa"):
        embed = discord.Embed(title=f"BOM Weather - {town.capitalize()}", description="Please wait...")
        msg = await ctx.send(embed=embed)

        async with aiohttp.ClientSession() as session:
            url = f"http://reg.bom.gov.au/{state}/forecasts/{town}.shtml"
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    embed = discord.Embed(title="Weather", description=f"Failed to retrieve weather. {response.status}")
                    await msg.edit(embed=embed)
                    return
                soup = BeautifulSoup(await response.text(), "html.parser")

                # Find the main weather div
                div_element = soup.find("div", class_="day main")
                if not div_element:
                    embed = discord.Embed(title="Weather", description="No weather information found for this location.")
                    await msg.edit(embed=embed)
                    return

                # Extract weather information
                summary = div_element.find('dd', class_="summary").text
                max_temp = div_element.find('em', class_="max").text
                rainfall_chance = div_element.find('em', class_="pop").text
                description = div_element.find('p').text

                # Create and send the embed with weather information
                embed = discord.Embed(title=f"BOM Weather - {town.capitalize()}")
                embed.add_field(name="Max Temp", value=f"{max_temp}°C", inline=True)
                embed.add_field(name="Chance of any rain", value=f"{rainfall_chance}", inline=True)
                embed.add_field(name=f"{summary}", value=f"{description}", inline=False)
                await msg.edit(embed=embed)

    @commands.hybrid_command(
        name="pl",
        description="Find contact details using Person Lookup (Australia)",
    )
    async def pl(self, ctx, query="", suburb="", state=""):
        embed = discord.Embed(title=f"Person Lookup - {query.capitalize()}", description="Please wait...")
        msg = await ctx.reply(embed=embed)

        async with aiohttp.ClientSession() as session:
            url = f"https://personlookup.com.au/search?page=1&q={query}&suburb={suburb}&state={state}"
            async with session.get(url, headers=headers, proxy=os.getenv("HTTP_PROXY")) as response:
                if response.status != 200:
                    embed = discord.Embed(title=f"Person Lookup - {query.capitalize()}", description=f"Error fetching results. {response.status}")
                    await msg.edit(embed=embed)
                    return
                soup = BeautifulSoup(await response.text(), "html.parser")

                # Find all profile divs
                profile_divs = soup.find("div", class_="col-12 col-md-8 order-first order-md-last mb-4 mb-md-0").find_all("div", class_="buttons-fix")
                if not profile_divs:
                    embed = discord.Embed(title=f"Person Lookup - {query.capitalize()}", description="No results found.")
                    await msg.edit(embed=embed)
                    return

                # Iterate over each profile div and extract the relevant information then add to embed
                embed = discord.Embed(title=f"Person Lookup - {query.capitalize()}")
                for profile in profile_divs:
                    name = profile.find("a", class_="stretched-link").text.strip()
                    address = profile.find("div", class_="col-12 col-sm-6 col-md-8 col-lg-9 col-xl-6 mb-2 mb-sm-0").text.strip()
                    phone = profile.find("div", class_="col-12 offset-0 col-sm-6 offset-sm-0 col-md-8 offset-md-4 col-lg-9 offset-lg-3 col-xl-3 offset-xl-0").text.strip()
                    embed.add_field(name=name, value=f"{address}\n{phone}", inline=False)
                await msg.edit(embed=embed)

    @commands.hybrid_command(
        name="fuel",
        description="Retrieve fuel prices (Australia)",
    )
    async def fuel(self, ctx, town="adelaide", state="sa"):
        embed = discord.Embed(title=f"Fuel Prices - {town.capitalize()}", description="Please wait...")
        msg = await ctx.reply(embed=embed)

        async with aiohttp.ClientSession() as session:
            url = f"https://fuelprice.io/{state}/{town}"
            async with session.get(url, headers=headers, proxy=os.getenv("HTTP_PROXY")) as response:
                if response.status != 200:
                    embed = discord.Embed(title=f"Fuel Prices - {town.capitalize()}", description=f"Error fetching fuel prices. {response.status}")
                    await msg.edit(embed=embed)
                    return
            soup = BeautifulSoup(await response.text(), "html.parser")

            # Find all price divs
            results_box = soup.find("ul", class_="cheapest-stations")
            servo_divs = results_box.find_all("li")
            if not servo_divs:
                embed = discord.Embed(title=f"Fuel Prices - {town.capitalize()}", description="No results found.")
                await msg.edit(embed=embed)
                return

            # Iterate over each price div and extract the relevant information then add to embed
            embed = discord.Embed(title=f"Fuel Prices - {town.capitalize()}", description="low to high")
            for servo in servo_divs:
                name = servo.find("strong").text.strip()
                price_text = servo.get_text(strip=True)
                price = re.search(r'(\d+(?:\.\d+)?)', price_text).group()
                embed.add_field(name=name, value=price, inline=False)
            await msg.edit(embed=embed)

    @commands.hybrid_command(
        name="openports",
        description="Retrieve open ports on a host from Shodan",
    )
    async def openports(self, ctx, ip="168.138.9.168"):
        embed = discord.Embed(title=f"Open ports - {ip}", description="Please wait...")
        msg = await ctx.reply(embed=embed)

        async with aiohttp.ClientSession() as session:
            url = f"https://internetdb.shodan.io/{ip}"
            async with session.get(url) as response:
                if response.status == 404:
                    embed = discord.Embed(title=f"Open ports - {ip}", description="No information available for this IP address.")
                    await msg.edit(embed=embed)
                    return
                elif response.status != 200:
                    # Handle other potential errors
                    embed = discord.Embed(title=f"Open ports - {ip}", description=f"An error occurred while fetching data. {response.status}")
                    await msg.edit(embed=embed)
                    return
                shodan_json = await response.json()

        if "detail" in shodan_json and shodan_json["detail"] == "No information available":
            embed = discord.Embed(title=f"Open ports - {ip}", description="No information available for this IP address.")
        else:
            embed = discord.Embed(title=f"Open ports - {ip}")
            embed.add_field(name="Hostnames", value=shodan_json["hostnames"], inline=False)
            embed.add_field(name="Open Ports", value=shodan_json["ports"], inline=False)
            embed.add_field(name="Tags", value=shodan_json["tags"], inline=False)
            embed.add_field(name="CPEs", value=shodan_json["cpes"], inline=False)
            embed.add_field(name="Vulns", value=shodan_json["vulns"], inline=False)
        await msg.edit(embed=embed)
            
    @commands.hybrid_command(
        name="rego",
        description="Check a vehicles registration (South Australia)",
    )
    async def rego(self, ctx, plate="wgz422"):
        embed = discord.Embed(title=f"Check Registration - {plate}", description="Please wait...")
        msg = await ctx.reply(embed=embed)

        async with aiohttp.ClientSession() as session:
            url = "https://account.ezyreg.sa.gov.au/r/veh/an/checkRegistration"
            data = {"plateNumber": plate, "registrationType": "VEHICLE"}
            async with session.post(url, json=data) as response:
                if response.status != 200:
                    embed = discord.Embed(title=f"Check Registration - {plate}", description="No results found.")
                    await msg.edit(embed=embed)
                    return
                ezyreg_json = await response.json()

        embed = discord.Embed(title=f"Check Registration - {plate}")
        embed.add_field(name="Expiry Date", value=ezyreg_json["checkRegistrationDetails"][0]["expiryDate"], inline=False)
        embed.add_field(name="Make", value=ezyreg_json["checkRegistrationDetails"][0]["vehicleMake"], inline=False)
        embed.add_field(name="Body Type", value=ezyreg_json["checkRegistrationDetails"][0]["vehicleBodyType"], inline=False)
        embed.add_field(name="Primary Colour", value=ezyreg_json["checkRegistrationDetails"][0]["primaryColour"], inline=False)
        embed.add_field(name="CTP Insurer", value=ezyreg_json["checkRegistrationDetails"][0]["ctpInsurer"], inline=False)
        embed.add_field(name="CTP Ins. Premium Class", value=ezyreg_json["checkRegistrationDetails"][0]["insuranceClass"], inline=False)
        embed.add_field(name="VIN", value=ezyreg_json["checkRegistrationDetails"][0]["vinChassis"], inline=False)
        await msg.edit(embed=embed)
         
    @commands.hybrid_command(
        name="geowifi",
        description="Retrieve geolocation info for a BSSID or SSID",
    )
    async def geowifi(self, ctx, bssid="", ssid=""):
        embed = discord.Embed(title=f"Wifi Geolocation - {bssid} {ssid}", description="Please wait...")
        msg = await ctx.reply(embed=embed)

        async with aiohttp.ClientSession() as session:
            url = os.getenv("GEOWIFI_URL")
            data = {"bssid": bssid, "ssid": ssid}
            async with session.post(url, json=data) as response:
                if response.status != 200:
                    embed = discord.Embed(title=f"Wifi Geolocation - {bssid} {ssid}", description=f"An error occurred while fetching data. {response.status}")
                    await msg.edit(embed=embed)
                    return
                geowifi_json = await response.json()

        embed = discord.Embed(title=f"Wifi Geolocation - {bssid} {ssid}")
        count = 0
        for item in geowifi_json:
            if count == 25:
                break
            if not all(key in item for key in ["bssid", "latitude", "longitude", "module"]):
                continue  # Skip entries with missing data

            bssid = item["bssid"]
            latitude = item["latitude"]
            longitude = item["longitude"]
            module = item["module"]
            location_url = f"https://www.google.com/maps/search/?q={latitude},{longitude}"
            ssid = item.get("ssid", None)  # Get ssid if available
            if ssid:
                count += 1
                embed.add_field(name=f"{module} - {bssid} - {ssid}", value=f"[{latitude}, {longitude}]({location_url})", inline=False)
                continue
            count += 1
            embed.add_field(name=f"{module} - {bssid}", value=f"[{latitude}, {longitude}]({location_url})", inline=False)
        await msg.edit(embed=embed)
         
    @commands.hybrid_command(
        name="ppsearch",
        description="Reverse search a phone number to see if it's a payphone.",
    )
    async def ppsearch(self, ctx, phone_number="0429510007"):
        embed = discord.Embed(title=f"Payphone Search - {phone_number}", description="Please wait...")
        msg = await ctx.reply(embed=embed)

        async with aiohttp.ClientSession() as session:
            encoded = urllib.parse.quote_plus(phone_number)
            url = f"http://telstratools.sn.mfc.pw/api/search?cli={encoded}"
            async with session.get(url) as response:
                if response.status != 200:
                    embed = discord.Embed(title=f"Payphone Search - {phone_number}", description=f"Error fetching payphone API ({response.status})")
                    await msg.edit(embed=embed)
                    return
                try:
                    data = await response.json()
                except Exception:
                    embed = discord.Embed(title=f"Payphone Search - {phone_number}", description="Error parsing API response.")
                    await msg.edit(embed=embed)
                    return

        # Process response
        if not isinstance(data, dict):
            embed = discord.Embed(title=f"Payphone Search - {phone_number}", description="Unexpected API response format.")
            await msg.edit(embed=embed)
            return

        if data.get("found"):
            item = data.get("item", {})
            cli = item.get("cli") or "N/A"
            address = item.get("address") or "N/A"

            embed = discord.Embed(title=f"Payphone Search - {cli}", description=f"Address: {address}")
        else:
            embed = discord.Embed(title=f"Payphone Search - {phone_number}", description="Not a payphone.")

        await msg.edit(embed=embed)

async def setup(bot) -> None:
    await bot.add_cog(Utility(bot))