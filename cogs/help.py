import discord
from discord.ext import commands
from discord import app_commands
import config

class Help(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="help",
        description="Shows all available commands and their descriptions."
    )
    @app_commands.guilds(discord.Object(id=config.GUILD_ID))
    @app_commands.checks.has_permissions(manage_messages=True)
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Help Menu",
            description="Here's a list of available commands:",
            color=config.EMBED_COLOR
        )

        embed.add_field(name="/playerinfo", value="Search up a players info.", inline=False)
        embed.add_field(name="/stickynote", value="Add a sticky note to a channel.", inline=False)
        embed.add_field(name="/clearnote", value="Clear stickynote from channel.", inline=False)
        embed.add_field(name="/setupverify", value="Send verify panel to the channel.", inline=False)
        embed.add_field(name="/ticketadmin", value="Modify ticket panel from the comfort of your discord.", inline=False)
        embed.add_field(name="/ticketpanel", value="Send ticket panel. (Configure ticket panel first)", inline=False)
        embed.add_field(name="/reload", value="Reload a feature for a real-time update.", inline=False)

        embed.set_footer(
            text=f"Requested by {interaction.user}",
            icon_url=interaction.user.avatar.url if interaction.user.avatar else None
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))