import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
import pytz
import config
import platform

AEST = pytz.timezone("Australia/Sydney")
TIME_FORMAT = "%-I:%M%p" if platform.system() != "Windows" else "%#I:%M%p"

class ServerInfo(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="serverinfo", description="Shows information about this server.")
    @app_commands.guilds(discord.Object(id=config.GUILD_ID))
    async def serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild or self.bot.get_guild(config.GUILD_ID)
        if guild is None:
            await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )
            return

        role_list = [role.mention for role in guild.roles if role != guild.default_role]
        displayed_roles = ", ".join(role_list[:20]) or "No roles"
        if len(role_list) > 20:
            displayed_roles += f" … and {len(role_list) - 20} more"

        embed = discord.Embed(
            title=f"Server Info — {guild.name}",
            color=config.EMBED_COLOR,
            timestamp=datetime.now(AEST),
        )

        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        owner_value = "Unknown"
        if guild.owner:
            owner_value = guild.owner.mention
        elif guild.owner_id:
            owner_value = f"<@{guild.owner_id}>"

        embed.add_field(name="Members", value=str(guild.member_count), inline=True)
        embed.add_field(name="Roles", value=str(len(guild.roles)), inline=True)
        embed.add_field(name="Categories", value=str(len(guild.categories)), inline=True)
        embed.add_field(name="Text Channels", value=str(len(guild.text_channels)), inline=True)
        embed.add_field(name="Voice Channels", value=str(len(guild.voice_channels)), inline=True)
        embed.add_field(name="Role List", value=displayed_roles, inline=False)

        embed.add_field(name="Owner", value=owner_value, inline=True)
        embed.add_field(name="Server ID", value=str(guild.id), inline=True)
        embed.add_field(
            name="Created On",
            value=guild.created_at.astimezone(AEST).strftime(f"%B %d, %Y {TIME_FORMAT}"),
            inline=True,
        )

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(ServerInfo(bot))