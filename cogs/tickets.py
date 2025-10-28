import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import asyncio
import json
import os
import io
import config

CONFIG_FILE = "ticket_config.json"

def slugify(name: str) -> str:
    return name.lower().replace(" ", "-")

def load_ticket_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump({}, f)
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_ticket_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)

class TicketReasonModal(discord.ui.Modal, title="Ticket Reason"):
    reason = discord.ui.TextInput(
        label="Reason for opening the ticket",
        placeholder="Describe your issue...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500
    )

    def __init__(self, ticket_type: str, settings: dict):
        super().__init__()
        self.ticket_type = ticket_type
        self.settings = settings

    async def on_submit(self, interaction: discord.Interaction):
        reason_text = str(self.reason)
        await create_ticket(interaction, self.ticket_type, self.settings, reason_text)

class CloseTicketReasonModal(discord.ui.Modal, title="Close Ticket"):
    reason = discord.ui.TextInput(
        label="Reason for closing the ticket",
        placeholder="Why are you closing this ticket?",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500
    )

    def __init__(self, channel: discord.TextChannel):
        super().__init__()
        self.channel = channel

    async def on_submit(self, interaction: discord.Interaction):
        user = interaction.user
        guild = interaction.guild

        await interaction.response.send_message("Closing ticket in 5 seconds...", ephemeral=True)
        await discord.utils.sleep_until(datetime.utcnow() + timedelta(seconds=5))

        transcript = io.StringIO()
        async for message in self.channel.history(limit=None, oldest_first=True):
            time = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
            author = f"{message.author} ({message.author.id})"
            content = message.content
            if message.attachments:
                content += " " + " ".join([att.url for att in message.attachments])
            transcript.write(f"[{time}] {author}: {content}\n")

        transcript.seek(0)
        file = discord.File(fp=transcript, filename=f"transcript-{self.channel.name}.txt")

        log_channel = guild.get_channel(config.TICKET_LOG_CHANNEL_ID)
        if log_channel:
            embed = discord.Embed(
            title="Ticket Closed",
            description=f"Ticket **{self.channel.name}** has been closed.",
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Closed By", value=user.mention, inline=True)
        embed.add_field(name="Reason", value=self.reason.value, inline=False)
        embed.add_field(name="Ticket Channel", value=self.channel.name, inline=True)
        embed.set_footer(text=f"User ID: {user.id}")

        await log_channel.send(embed=embed, file=file)

        await self.channel.delete()

async def create_ticket(interaction: discord.Interaction, ticket_type: str, settings: dict, reason_text: str | None):
    guild = interaction.guild
    user = interaction.user

    existing = discord.utils.get(guild.text_channels, name=f"{ticket_type}-{user.id}")
    if existing:
        return await interaction.response.send_message(
            f"You already have an open {ticket_type} ticket: {existing.mention}", ephemeral=True
        )

    category = guild.get_channel(settings["category_id"]) if settings["category_id"] else None

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
    }
    for role_id in settings["staff_roles"]:
        role = guild.get_role(role_id)
        if role:
            overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

    channel = await guild.create_text_channel(
        name=f"{slugify(ticket_type)}-{user.id}",
        overwrites=overwrites,
        category=category,
        reason=f"{ticket_type.capitalize()} ticket opened by {user}"
    )

    description = f"{user.mention} created a **{ticket_type}** ticket.\nA staff member will be with you shortly."
    if reason_text:
        description += f"\n\n**Reason:** {reason_text}"

    embed = discord.Embed(
        title=f"{ticket_type.capitalize()} Ticket",
        description=description,
        color=config.EMBED_COLOR
    )

    view = discord.ui.View()
    view.add_item(CloseTicketView().children[0])
    view.add_item(ClaimTicketView().children[0])

    await channel.send(content="@here", embed=embed, view=view)

    await interaction.response.send_message(
        f"Your **{ticket_type}** ticket has been created: {channel.mention}",
        ephemeral=True
    )

class TicketTypeDropdown(discord.ui.Select):
    def __init__(self):
        data = load_ticket_config()
        options = [
            discord.SelectOption(
                label=ticket_type.capitalize(),
                description=settings["description"],
                value=ticket_type
            )
            for ticket_type, settings in data.items()
        ]

        if not options:
            options = [discord.SelectOption(label="No ticket types configured!", value="none", description="Ask staff to configure.")]

        super().__init__(
            placeholder="Choose a ticket type...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_type_dropdown"
        )

    async def callback(self, interaction: discord.Interaction):
        ticket_type = self.values[0]
        if ticket_type == "none":
            return await interaction.response.send_message("No ticket types are available. Please ask staff.", ephemeral=True)

        data = load_ticket_config()
        settings = data[ticket_type]

        if settings.get("require_reason", False):
            modal = TicketReasonModal(ticket_type, settings)
            return await interaction.response.send_modal(modal)

        await create_ticket(interaction, ticket_type, settings, None)

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketTypeDropdown())

class ClaimTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claim Ticket", style=discord.ButtonStyle.green, custom_id="claim_ticket")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.channel
        guild = interaction.guild
        user = interaction.user

        data = load_ticket_config()
        ticket_type = None
        for ttype, settings in data.items():
            if channel.name.startswith(slugify(ttype)):
                ticket_type = ttype
                break

        if not ticket_type:
            return await interaction.response.send_message("Could not identify ticket type.", ephemeral=True)

        settings = data[ticket_type]

        staff_roles = [guild.get_role(r) for r in settings["staff_roles"]]
        if not any(r in user.roles for r in staff_roles if r):
            return await interaction.response.send_message("You don’t have permission to claim this ticket.", ephemeral=True)

        if channel.topic and "claimed_by:" in channel.topic:
            try:
                claimed_id = int(channel.topic.split("claimed_by:")[1].strip())
                claimed_user = guild.get_member(claimed_id)
            except ValueError:
                claimed_user = None

            return await interaction.response.send_message(
                f"This ticket is already claimed by {claimed_user.mention if claimed_user else 'someone'}.",
                ephemeral=True
            )

        await channel.edit(topic=f"claimed_by:{user.id}")

        embed = discord.Embed(
            title=f"{ticket_type.capitalize()} Ticket",
            description=f"{channel.mention} has been claimed by {user.mention}.",
            color=config.EMBED_COLOR
        )
        await channel.send(embed=embed)

        await interaction.response.send_message(f"You have claimed this ticket!", ephemeral=True)

class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.red, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.channel
        guild = interaction.guild
        user = interaction.user

        data = load_ticket_config()
        ticket_type = None
        for ttype, settings in data.items():
            if channel.name.startswith(slugify(ttype)):
                ticket_type = ttype
                break

        if not ticket_type:
            return await interaction.response.send_message("Could not identify ticket type.", ephemeral=True)

        settings = data[ticket_type]
        close_permission = settings.get("close_permission", "staff")

        if close_permission == "staff":
            staff_roles = [guild.get_role(r) for r in settings["staff_roles"]]
            if not any(r in user.roles for r in staff_roles if r):
                return await interaction.response.send_message("Only staff can close this ticket.", ephemeral=True)

        modal = CloseTicketReasonModal(channel)
        await interaction.response.send_modal(modal)

class TicketAdminView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Add Ticket Type", style=discord.ButtonStyle.green, custom_id="add_ticket_type")
    async def add_ticket_type(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("✏️ Enter the **name** of the new ticket type:", ephemeral=True)

        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel

        msg = await interaction.client.wait_for("message", check=check)
        ticket_name = msg.content.lower()

        data = load_ticket_config()
        if ticket_name in data:
            return await interaction.followup.send("That ticket type already exists!", ephemeral=True)

        data[ticket_name] = {
            "category_id": None,
            "staff_roles": [],
            "description": "New ticket type",
            "require_reason": False,
            "close_permission": "staff"
        }
        save_ticket_config(data)

        await interaction.followup.send(f"Ticket type `{ticket_name}` created!", ephemeral=True)

    @discord.ui.button(label="Remove Ticket Type", style=discord.ButtonStyle.red, custom_id="remove_ticket_type")
    async def remove_ticket_type(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_ticket_config()
        options = [
            discord.SelectOption(label=name, value=name) for name in data.keys()
        ]
        if not options:
            return await interaction.response.send_message("No ticket types available.", ephemeral=True)

        select = discord.ui.Select(placeholder="Select a ticket type to remove", options=options)

        async def select_callback(i: discord.Interaction):
            ticket = select.values[0]
            del data[ticket]
            save_ticket_config(data)
            await i.response.send_message(f"Removed ticket type `{ticket}`.", ephemeral=True)

        select.callback = select_callback
        view = discord.ui.View()
        view.add_item(select)
        await interaction.response.send_message("Select a ticket type to remove:", view=view, ephemeral=True)

    @discord.ui.button(label="Configure Ticket Type", style=discord.ButtonStyle.blurple, custom_id="config_ticket_type")
    async def configure_ticket_type(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_ticket_config()
        options = [
            discord.SelectOption(label=name, value=name) for name in data.keys()
        ]
        if not options:
            return await interaction.response.send_message("No ticket types available.", ephemeral=True)

        select = discord.ui.Select(placeholder="Select a ticket type to configure", options=options)

        async def select_callback(i: discord.Interaction):
            ticket = select.values[0]
            ticket_data = data[ticket]

            embed = discord.Embed(
                title=f"Config: {ticket.capitalize()}",
                description=f"**Description:** {ticket_data['description']}\n"
                            f"**Category:** {ticket_data['category_id']}\n"
                            f"**Staff Roles:** {', '.join([str(r) for r in ticket_data['staff_roles']]) or 'None'}",
                color=config.EMBED_COLOR
            )
            view = TicketConfigView(ticket)
            await i.response.send_message(embed=embed, view=view)

        select.callback = select_callback
        view = discord.ui.View()
        view.add_item(select)
        await interaction.response.send_message("Select a ticket type to configure:", view=view, ephemeral=True)

class TicketConfigView(discord.ui.View):
    def __init__(self, ticket_type: str):
        super().__init__(timeout=None)
        self.ticket_type = ticket_type

    @discord.ui.button(label="Set Category", style=discord.ButtonStyle.gray, custom_id="set_category")
    async def set_category(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_ticket_config()
        await interaction.response.send_message(
            "Please enter the **category ID** you want to set for this ticket type.\n"
            "To get a category ID: enable Developer Mode → right-click the category → Copy ID.",
            ephemeral=True
        )

        def check(m: discord.Message):
            return m.author == interaction.user and m.channel == interaction.channel

        msg = await interaction.client.wait_for("message", check=check)

        try:
            category_id = int(msg.content.strip())
            category = interaction.guild.get_channel(category_id)
            if not category or category.type != discord.ChannelType.category:
                return await interaction.followup.send("That ID does not belong to a valid category.", ephemeral=True)

            data[self.ticket_type]["category_id"] = category_id
            save_ticket_config(data)
            await interaction.followup.send(f"Category set to **{category.name}**", ephemeral=True)

        except ValueError:
            await interaction.followup.send("Please provide a valid numeric category ID.", ephemeral=True)

    @discord.ui.button(label="Set Staff Roles", style=discord.ButtonStyle.gray, custom_id="set_roles")
    async def set_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_ticket_config()
        await interaction.response.send_message("Mention the staff roles allowed to access this ticket type:", ephemeral=True)

        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel

        msg = await interaction.client.wait_for("message", check=check)
        role_ids = [role.id for role in msg.role_mentions]
        if not role_ids:
            return await interaction.followup.send("You must mention at least one role.", ephemeral=True)

        data[self.ticket_type]["staff_roles"] = role_ids
        save_ticket_config(data)
        await interaction.followup.send("Staff roles updated!", ephemeral=True)

    @discord.ui.button(label="Set Description", style=discord.ButtonStyle.gray, custom_id="set_description")
    async def set_description(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_ticket_config()
        await interaction.response.send_message("Enter a description for this ticket type:")

        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel

        msg = await interaction.client.wait_for("message", check=check)

        data[self.ticket_type]["description"] = msg.content
        save_ticket_config(data)

        ticket_data = data[self.ticket_type]
        embed = discord.Embed(
            title=f"Config: {self.ticket_type.capitalize()}",
            description=f"**Description:** {ticket_data['description']}\n"
                        f"**Category:** {ticket_data['category_id']}\n"
                        f"**Staff Roles:** {', '.join([str(r) for r in ticket_data['staff_roles']]) or 'None'}",
            color=config.EMBED_COLOR
        )

        await interaction.message.edit(embed=embed, view=self)
        await interaction.followup.send("Description updated!", ephemeral=True)

    @discord.ui.button(label="Toggle Close Permission", style=discord.ButtonStyle.gray, custom_id="toggle_close_permission")
    async def toggle_close_permission(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_ticket_config()
        current = data[self.ticket_type].get("close_permission", "staff")

        new_value = "anyone" if current == "staff" else "staff"
        data[self.ticket_type]["close_permission"] = new_value
        save_ticket_config(data)

        await interaction.response.send_message(
            f"Close permission set to **{new_value}** for `{self.ticket_type}`.",
            ephemeral=True
        )

    @discord.ui.button(label="Toggle Require Reason", style=discord.ButtonStyle.gray, custom_id="toggle_reason")
    async def toggle_reason(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_ticket_config()
        current = data[self.ticket_type].get("require_reason", False)
        data[self.ticket_type]["require_reason"] = not current
        save_ticket_config(data)

        state = "enabled" if not current else "disabled"
        await interaction.response.send_message(f"Require reason has been **{state}** for `{self.ticket_type}`.", ephemeral=True)

class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print("Ticket system loaded.")
        self.bot.add_view(TicketView())
        self.bot.add_view(CloseTicketView())
        self.bot.add_view(TicketAdminView())
        self.bot.add_view(ClaimTicketView())

    @app_commands.command(name="ticketpanel", description="Send the ticket creation panel")
    async def ticket_panel(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("You don't have permission to use this.", ephemeral=True)

        await interaction.response.send_message("Ticket panel has been sent.", ephemeral=True)

        embed = discord.Embed(
            title="SiliconRP Tickets",
            description="Welcome to the ticket channel.\n\n This is your gateway to obtaining assistance from staff. \n\n Below you will find numerous buttons to assist with getting you in touch with the correct support members. \n\n - **General Ticket**: This is used for general staff assistance. Essentially use this option if the other options below don't fit your requirements. Example usage includes technical issues, general discussions with staff and inquiries. Furthermore, you may use this option if you are after Tebex support.\n\n - **Donator**: Used to get help with purchases from our Tebex store. (Allowlist Priority, Custom Items/Liveries/Peds, Token Issues, Giveaways, or other donation inquiries) \n\n - **Player Report**: Please use this option to report a player. You may also use this option to report a staff member, but request the ticket be restricted before doing so. \n\n - **Application Inquiries**: Only accessible by our Application Team. These tickets will be used if there is a concern about your application. \n\n Choose a type of ticket below to get started.",
            color=config.EMBED_COLOR
        )
        await interaction.channel.send(embed=embed, view=TicketView())

    @app_commands.command(name="ticketadmin", description="Open the ticket admin panel")
    async def ticket_admin(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("You don't have permission to use this.", ephemeral=True)

        data = load_ticket_config()
        embed = discord.Embed(
            title="Ticket Admin Panel",
            description="Use the buttons below to manage ticket types, staff roles, and categories.",
            color=config.EMBED_COLOR
        )
        await interaction.response.send_message(embed=embed, view=TicketAdminView())


async def setup(bot: commands.Bot):
    guild = discord.Object(id=config.GUILD_ID)
    await bot.add_cog(Tickets(bot), guilds=[guild])