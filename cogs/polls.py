import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import config
import datetime
import re

def format_time(seconds: int) -> str:
    """Convert seconds into a human-readable time format (Xd Xh Xm Xs)."""
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

def is_url(text: str) -> bool:
    """Check if the given text is a valid URL."""
    url_pattern = re.compile(r"^https?://[^\s]+$")
    return bool(url_pattern.match(text))

class PollView(discord.ui.View):
    def __init__(self, question: str, options: list[str], links: dict[str, str], author: discord.User, seconds: int, message: discord.Message = None):
        super().__init__(timeout=seconds)
        self.question = question
        self.options = options
        self.links = links
        self.votes = {option: [] for option in options}
        self.author = author
        self.end_time = discord.utils.utcnow().timestamp() + seconds
        self.message = message

        for i, option in enumerate(options, start=1):
            self.add_item(PollButton(label=option, option=option, row=(i - 1) // 5))

    def build_results_embed(self) -> discord.Embed:
        total_votes = sum(len(voters) for voters in self.votes.values())
        remaining = int(self.end_time - discord.utils.utcnow().timestamp())
        embed = discord.Embed(
            title="SiliconRP Poll",
            description=self.question,
            color=config.EMBED_COLOR
        )
        if remaining > 0:
            timer_text = f"Time left: {format_time(remaining)}"
        else:
            timer_text = "Poll ended"
        embed.set_footer(text=f"{timer_text}\nPoll created by {self.author}")

        if total_votes == 0:
            results_text = "No votes yet."
        else:
            results_text = ""
            for option, voters in self.votes.items():
                count = len(voters)
                percent = (count / total_votes) * 100 if total_votes > 0 else 0
                bar = "█" * int(percent // 10)
                results_text += f"**{option}** — {count} votes ({percent:.1f}%)\n`{bar:<10}`\n"
        embed.add_field(name="Results", value=results_text, inline=False)

        if any(self.links.values()):
            link_text = "\n".join([
                f"[{opt}]({self.links[opt]})" for opt in self.options if self.links.get(opt)
            ])
            if link_text:
                embed.add_field(name="Links", value=link_text, inline=False)

        return embed

    async def start_timer(self):
        while True:
            remaining = int(self.end_time - discord.utils.utcnow().timestamp())
            if remaining <= 0:
                await self.message.edit(embed=self.build_results_embed(), view=None)
                break
            await self.message.edit(embed=self.build_results_embed(), view=self)
            await asyncio.sleep(1)

class PollButton(discord.ui.Button):
    def __init__(self, label: str, option: str, row: int):
        super().__init__(label=label, style=discord.ButtonStyle.primary, row=row)
        self.option = option

    async def callback(self, interaction: discord.Interaction):
        view: PollView = self.view
        for voters in view.votes.values():
            if interaction.user.id in voters:
                voters.remove(interaction.user.id)
        if interaction.user.id not in view.votes[self.option]:
            view.votes[self.option].append(interaction.user.id)
        await interaction.response.edit_message(embed=view.build_results_embed(), view=view)

class Polls(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="poll",
        description="Create a poll with up to 5 options (with optional links)."
    )
    @app_commands.guilds(discord.Object(id=config.GUILD_ID))
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.describe(
        question="The poll question",
        option1="First option",
        option1_link="Optional link for option 1",
        option2="Second option",
        option2_link="Optional link for option 2",
        option3="Third option (optional)",
        option3_link="Optional link for option 3",
        option4="Fourth option (optional)",
        option4_link="Optional link for option 4",
        option5="Fifth option (optional)",
        option5_link="Optional link for option 5",
        duration="Poll duration (e.g. 1m, 10m, 2h, 3d)"
    )
    async def poll(
        self,
        interaction: discord.Interaction,
        question: str,
        option1: str,
        option2: str,
        option1_link: str = None,
        option2_link: str = None,
        option3: str = None,
        option3_link: str = None,
        option4: str = None,
        option4_link: str = None,
        option5: str = None,
        option5_link: str = None,
        duration: str = "1m"
    ):
        if config.POLLONLYADMIN:
            perms = interaction.user.guild_permissions
            if not (perms.administrator or perms.manage_messages or perms.manage_guild):
                await interaction.response.send_message("Only admins or moderators can create polls on this server.", ephemeral=True)
                return

        options = [o for o in [option1, option2, option3, option4, option5] if o]
        if len(options) < 2:
            await interaction.response.send_message("You must provide at least two options for a poll.", ephemeral=True)
            return
        if len(options) > 5:
            await interaction.response.send_message("Button-based polls can only have up to 5 options.", ephemeral=True)
            return

        option_links = {
            option1: option1_link if option1_link and is_url(option1_link) else None,
            option2: option2_link if option2_link and is_url(option2_link) else None,
            option3: option3_link if option3 and option3_link and is_url(option3_link) else None,
            option4: option4_link if option4 and option4_link and is_url(option4_link) else None,
            option5: option5_link if option5 and option5_link and is_url(option5_link) else None,
        }

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

        view = PollView(question, options, option_links, interaction.user, seconds)
        embed = view.build_results_embed()
        await interaction.response.send_message(embed=embed, view=view)
        message = await interaction.original_response()
        view.message = message
        self.bot.loop.create_task(view.start_timer())

async def setup(bot: commands.Bot):
    await bot.add_cog(Polls(bot))