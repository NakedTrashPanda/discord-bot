import discord
from discord.ext import commands
import threading
import argparse

from config import DISCORD_TOKEN
import media_functions
import movie_functions
import help_functions
import tui_interface
#import factcheck_functions
#import gemini_functions

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=commands.when_mentioned, intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

    # Setup modules
    media_functions.setup(bot)
    movie_functions.setup(bot)
    help_functions.setup_help_commands(bot)
    #factcheck_functions.setup(bot)
    #gemini_functions.setup(bot)

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

def run_tui():
    """Run the TUI in a separate thread"""
    tui_interface.simple_tui_main(bot)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Discord Media Bot')
    parser.add_argument('--tui', action='store_true', help='Launch with TUI interface')
    args = parser.parse_args()

    if args.tui:
        # Start TUI in a separate thread
        tui_thread = threading.Thread(target=run_tui, daemon=True)
        tui_thread.start()

    # Run the bot
    bot.run(DISCORD_TOKEN)
