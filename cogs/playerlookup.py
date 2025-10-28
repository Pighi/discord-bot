import discord
from discord.ext import commands
from discord import app_commands
import aiomysql
import json
import config

class PlayerLookup(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def fetch_player(self, license_id: str):
        """Fetch player info from the Qbox players table."""
        conn = await aiomysql.connect(
            host=config.DB_HOST,
            user=config.DB_USER,
            password=config.DB_PASS,
            db=config.DB_NAME
        )
        async with conn.cursor() as cur:
            await cur.execute("SELECT money, charinfo FROM players WHERE license = %s", (license_id,))
            result = await cur.fetchone()
        await conn.ensure_closed()
        return result

    @app_commands.command(
        name="playerinfo",
        description="Look up a player's info by license ID"
    )
    @app_commands.guilds(discord.Object(id=config.GUILD_ID))
    async def playerinfo(self, interaction: discord.Interaction, license_id: str):
        await interaction.response.defer(ephemeral=True)

        data = await self.fetch_player(license_id)

        if not data:
            await interaction.followup.send("Player not found.", ephemeral=True)
            return

        money_json, charinfo_json = data
        money = json.loads(money_json)
        charinfo = json.loads(charinfo_json)

        embed = discord.Embed(
            title=f"👤 Player Info: {charinfo['firstname']} {charinfo['lastname']}",
            color=config.EMBED_COLOR
        )

        embed.add_field(name="💰 Cash", value=f"${money.get('cash', 0):,}", inline=True)
        embed.add_field(name="🏦 Bank", value=f"${money.get('bank', 0):,}", inline=True)
        embed.add_field(name="🪙 Crypto", value=f"${money.get('crypto', 0):,}", inline=True)

        embed.add_field(name="📅 Birthdate", value=charinfo.get("birthdate", "N/A"), inline=True)
        embed.add_field(name="🌍 Nationality", value=charinfo.get("nationality", "N/A"), inline=True)
        embed.add_field(name="📞 Phone", value=charinfo.get("phone", "N/A"), inline=True)

        embed.add_field(name="📖 Backstory", value=charinfo.get("backstory", "N/A"), inline=False)
        embed.set_footer(text=f"CID: {charinfo.get('cid')} | Account: {charinfo.get('account')}")

        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(PlayerLookup(bot))