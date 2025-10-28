import discord
from discord import app_commands
from discord.ext import commands
import config

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="reload", description="Reload a cog (admin only).")
    @app_commands.guilds(discord.Object(id=config.GUILD_ID))
    async def reload(self, interaction: discord.Interaction, cog: str):
        """Reload a cog (admin only)."""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "You don't have permission to use this command.",
                ephemeral=True
            )
            return

        try:
            await self.bot.reload_extension(f"cogs.{cog}")
            await interaction.response.send_message(f"Reloaded {cog}.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Admin(bot))