import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import config

sticky_notes = {}
locks = {}

class StickyNote(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="stickynote", description="Set a sticky note in this channel")
    @app_commands.guilds(discord.Object(id=config.GUILD_ID))
    @app_commands.checks.has_permissions(manage_messages=True)
    async def stickynote(self, interaction: discord.Interaction, content: str):
        channel = interaction.channel
        locks[channel.id] = asyncio.Lock()

        async with locks[channel.id]:
            if channel.id in sticky_notes and sticky_notes[channel.id]["msg_obj"]:
                try:
                    await sticky_notes[channel.id]["msg_obj"].delete()
                except discord.NotFound:
                    pass

            formatted_note = f"**⚠ Important Message Please Read ⚠**\n\n{content}"
            msg = await channel.send(formatted_note)
            sticky_notes[channel.id] = {"message": content, "msg_obj": msg}

        await interaction.response.send_message("Sticky note set!", ephemeral=True)

    @app_commands.command(name="clearnote", description="Clear the sticky note in this channel")
    @app_commands.guilds(discord.Object(id=config.GUILD_ID))
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clearnote(self, interaction: discord.Interaction):
        channel = interaction.channel

        if channel.id not in sticky_notes:
            await interaction.response.send_message("No sticky note set in this channel.", ephemeral=True)
            return

        async with locks.get(channel.id, asyncio.Lock()):
            note = sticky_notes[channel.id]
            if note["msg_obj"]:
                try:
                    await note["msg_obj"].delete()
                except discord.NotFound:
                    pass

            del sticky_notes[channel.id]

        await interaction.response.send_message("Sticky note cleared!", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        channel_id = message.channel.id

        if channel_id in sticky_notes:
            locks.setdefault(channel_id, asyncio.Lock())

            async with locks[channel_id]:
                note = sticky_notes[channel_id]

                if note["msg_obj"]:
                    try:
                        await note["msg_obj"].delete()
                    except discord.NotFound:
                        pass

                formatted_note = f"**⚠ Important Message Please Read ⚠**\n\n{note['message']}"
                new_msg = await message.channel.send(formatted_note)
                sticky_notes[channel_id]["msg_obj"] = new_msg

async def setup(bot):
    await bot.add_cog(StickyNote(bot))