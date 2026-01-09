import discord
from discord.ext import commands

from config import DISCORD_TOKEN
import media_functions
import movie_functions

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=None, intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

    # Setup modules
    media_functions.setup(bot)
    movie_functions.setup(bot)

    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

    # Start daily upload loop
    if not media_functions.daily_upload.is_running():
        media_functions.daily_upload.start()
        print("Started daily_upload loop.")

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
