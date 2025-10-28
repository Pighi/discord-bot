import discord
from discord.ext import commands
from discord import app_commands
import config

class Purge(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="purge",
        description="Delete messages in the channel with different filters."
    )
    @app_commands.guilds(discord.Object(id=config.GUILD_ID))
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.describe(
        user="Delete all messages from this user",
        after="Delete all messages after this message ID",
        amount="Delete a specific number of messages",
        all="Delete all messages in the channel (⚠️)"
    )
    async def purge(
        self,
        interaction: discord.Interaction,
        user: discord.User = None,
        after: str = None,
        amount: int = None,
        all: bool = False
    ):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message(
                "You don't have permission to manage messages.", ephemeral=True
            )
            return

        await interaction.response.defer(thinking=True, ephemeral=True)

        deleted = []
        channel = interaction.channel

        if all:
            deleted = await channel.purge(limit=None)
            await interaction.followup.send(
                f"Deleted **{len(deleted)}** messages (all in channel).",
                ephemeral=True
            )
            return

        if user:
            deleted = await channel.purge(limit=None, check=lambda m: m.author.id == user.id)
            await interaction.followup.send(
                f"Deleted **{len(deleted)}** messages from {user.mention}.",
                ephemeral=True
            )
            return

        if after:
            try:
                msg = await channel.fetch_message(int(after))
                deleted = await channel.purge(after=msg)
                await interaction.followup.send(
                    f"Deleted **{len(deleted)}** messages after message ID `{after}`.",
                    ephemeral=True
                )
                return
            except Exception:
                await interaction.followup.send("Invalid message ID.", ephemeral=True)
                return

        if amount:
            deleted = await channel.purge(limit=amount)
            await interaction.followup.send(
                f"Deleted **{len(deleted)}** messages.", ephemeral=True
            )
            return

        await interaction.followup.send(
            "You must specify at least one option (user, after, amount, or all).",
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(Purge(bot))