import discord
import asyncio
import random
from discord import app_commands
from discord.ext import commands
import config
import datetime

def format_time(seconds: int) -> str:
    """Format seconds into human-readable countdown (e.g. 1h 23m 10s)."""
    delta = datetime.timedelta(seconds=seconds)
    days, remainder = divmod(delta.total_seconds(), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts = []
    if days > 0:
        parts.append(f"{int(days)}d")
    if hours > 0:
        parts.append(f"{int(hours)}h")
    if minutes > 0:
        parts.append(f"{int(minutes)}m")
    if seconds > 0:
        parts.append(f"{int(seconds)}s")

    return " ".join(parts) if parts else "0s"


class GiveawayView(discord.ui.View):
    def __init__(self, host: discord.Member, prize: str, winners: int, seconds: int, prize_link: str | None = None):
        super().__init__(timeout=seconds)
        self.host = host
        self.prize = prize
        self.prize_link = prize_link
        self.winners = winners
        self.entries = set()
        self.message: discord.Message | None = None
        self.end_time = discord.utils.utcnow().timestamp() + seconds
        self.update_task: asyncio.Task | None = None

        self.add_item(self.EnterButton(self))
        self.add_item(self.LeaveButton(self))

    class EnterButton(discord.ui.Button):
        def __init__(self, parent_view: "GiveawayView"):
            super().__init__(label="Enter Giveaway", style=discord.ButtonStyle.green)
            self.parent_view = parent_view

        async def callback(self, interaction: discord.Interaction):
            view = self.parent_view

            if interaction.user.bot:
                await interaction.response.send_message("Bots cannot enter giveaways!", ephemeral=True)
                return

            if interaction.user.id in view.entries:
                await interaction.response.send_message("You are already entered!", ephemeral=True)
                return

            view.entries.add(interaction.user.id)
            remaining = int(view.end_time - discord.utils.utcnow().timestamp())
            await view.update_embed(remaining)
            await interaction.response.send_message("You have entered the giveaway!", ephemeral=True)

    class LeaveButton(discord.ui.Button):
        def __init__(self, parent_view: "GiveawayView"):
            super().__init__(label="Leave Giveaway", style=discord.ButtonStyle.red)
            self.parent_view = parent_view

        async def callback(self, interaction: discord.Interaction):
            view = self.parent_view

            if interaction.user.bot:
                await interaction.response.send_message("Bots cannot leave giveaways!", ephemeral=True)
                return

            if interaction.user.id not in view.entries:
                await interaction.response.send_message("You are not in the giveaway!", ephemeral=True)
                return

            view.entries.remove(interaction.user.id)
            remaining = int(view.end_time - discord.utils.utcnow().timestamp())
            await view.update_embed(remaining)
            await interaction.response.send_message("You have left the giveaway.", ephemeral=True)

    async def start_updating(self):
        """Background task to update countdown at safe intervals and finish the giveaway."""
        while True:
            if not self.message:
                await asyncio.sleep(5)
                continue

            remaining = int(self.end_time - discord.utils.utcnow().timestamp())
            if remaining <= 0:
                await self.end_giveaway()
                break

            await self.update_embed(remaining)

            if remaining > 86400:
                await asyncio.sleep(900)
            elif remaining > 3600:
                await asyncio.sleep(300)
            elif remaining > 600:
                await asyncio.sleep(60)
            elif remaining > 60:
                await asyncio.sleep(15)
            else:
                await asyncio.sleep(5)

    async def update_embed(self, remaining: int | None = None):
        """Update the giveaway embed dynamically with countdown and entries."""
        if remaining is None:
            remaining = int(self.end_time - discord.utils.utcnow().timestamp())

        prize_text = f"[{self.prize}]({self.prize_link})" if self.prize_link else self.prize

        embed = discord.Embed(
            title="🎉 New Giveaway Alert! 🥳",
            description=(
                f"**Prize:** {prize_text}\n"
                f"**Hosted by:** {self.host.mention}\n"
                f"**Time remaining:** {format_time(remaining)}\n"
                f"**Number of winners:** {self.winners}\n\n"
                f"**Entries so far:** {len(self.entries)}"
            ),
            color=config.EMBED_COLOR
        )
        embed.set_footer(text="The giveaway has not ended yet.")
        if self.message:
            try:
                await self.message.edit(embed=embed, view=self)
            except discord.HTTPException:
                pass

    async def end_giveaway(self):
        """End the giveaway, pick winners, and update the embed."""
        if not self.message:
            return

        prize_text = f"[{self.prize}]({self.prize_link})" if self.prize_link else self.prize

        if not self.entries:
            description = (
                f"**Prize:** {prize_text}\n"
                f"**Hosted by:** {self.host.mention}\n\n"
                "**No one entered the giveaway.**"
            )
            embed = discord.Embed(title="Giveaway Ended", description=description, color=discord.Color.red())
            await self.message.edit(embed=embed, view=None)
            return

        winners = random.sample(list(self.entries), min(self.winners, len(self.entries)))
        winner_mentions = ", ".join(f"<@{user_id}>" for user_id in winners)

        description = (
            f"**Prize:** {prize_text}\n"
            f"**Hosted by:** {self.host.mention}\n"
            f"**Winners:** {winner_mentions}\n\n"
            "Congratulations!"
        )

        embed = discord.Embed(title="Giveaway Ended", description=description, color=discord.Color.green())
        await self.message.edit(embed=embed, view=None)

        await self.message.reply(
            f"Congratulations {winner_mentions}! You won **{prize_text}**!",
            mention_author=False
        )

class Giveaways(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="giveaway", description="Start a giveaway in a selected channel.")
    @app_commands.guilds(discord.Object(id=config.GUILD_ID))
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.describe(
        channel="The channel to host the giveaway in",
        prize="The prize for the giveaway",
        prize_link="Optional link for the prize",
        duration="Duration of the giveaway (e.g. 1m, 10m, 2h, 3d)",
        winners="Number of winners (default: 1)",
    )
    async def giveaway(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        prize: str,
        duration: str,
        winners: int = 1,
        prize_link: str | None = None
    ):
        """Start a giveaway in the chosen channel with flexible duration format."""

        try:
            unit = duration[-1].lower()
            time = int(duration[:-1])

            if unit == "m":
                seconds = time * 60
            elif unit == "h":
                seconds = time * 3600
            elif unit == "d":
                seconds = time * 86400
            else:
                await interaction.response.send_message(
                    "Invalid duration format! Use `m` for minutes, `h` for hours, or `d` for days. Example: `10m`, `2h`, `1d`.",
                    ephemeral=True
                )
                return
        except (ValueError, IndexError):
            await interaction.response.send_message(
                "Invalid duration format! Example: `10m`, `2h`, `1d`.",
                ephemeral=True
            )
            return

        if winners < 1:
            await interaction.response.send_message("There must be at least **1 winner**.", ephemeral=True)
            return

        view = GiveawayView(interaction.user, prize, winners, seconds, prize_link)

        prize_text = f"[{prize}]({prize_link})" if prize_link else prize

        embed = discord.Embed(
            title="🎉 New Giveaway Alert! 🥳",
            description=(
                f"**Prize:** {prize_text}\n"
                f"**Hosted by:** {interaction.user.mention}\n"
                f"**Time remaining:** {format_time(seconds)}\n"
                f"**Number of winners:** {winners}\n\n"
                f"**Entries so far:** 0"
            ),
            color=config.EMBED_COLOR
        )
        embed.set_footer(text="The giveaway has not ended yet.")

        giveaway_message = await channel.send(embed=embed, view=view)
        view.message = giveaway_message

        # Start background updater
        view.update_task = asyncio.create_task(view.start_updating())

        await interaction.response.send_message(
            f"Giveaway for **{prize}** started in {channel.mention}!",
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Giveaways(bot))