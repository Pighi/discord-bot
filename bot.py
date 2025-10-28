import discord
from discord.ext import commands
import config

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

COGS = {
    "welcome": "cogs.welcome",
    "verify": "cogs.verify",
    "admin": "cogs.admin",
    "stickynote": "cogs.stickynote",
    "tickets": "cogs.tickets",
    "playerlookup": "cogs.playerlookup",
    "purge": "cogs.purge",
    "serverinfo": "cogs.serverinfo",
    "giveaways": "cogs.giveaways",
    "polls": "cogs.polls",
    "help": "cogs.help",
}

async def load_cogs():
    for feature, enabled in config.FEATURES.items():
        if enabled:
            try:
                await bot.load_extension(COGS[feature])
                print(f"Loaded {feature} cog")
            except Exception as e:
                print(f"Failed to load {feature} cog: {e}")
        else:
            print(f"Skipped {feature} cog (disabled in config)")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    await load_cogs()

    try:
        bot.tree.clear_commands(guild=None)
        await bot.tree.sync()
        print("Cleared ALL global commands")
    except Exception as e:
        print(f"Failed to clear global commands: {e}")

    try:
        guild = discord.Object(id=config.GUILD_ID)
        synced = await bot.tree.sync(guild=guild)
        print(f"Synced {len(synced)} commands to guild {guild.id}")
    except Exception as e:
        print(f"Failed to sync guild commands: {e}")

bot.run(config.TOKEN)