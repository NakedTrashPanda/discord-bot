import discord
from discord.ext import commands

from config import DISCORD_TOKEN
import media_functions
import movie_functions

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

if __name__ == "__main__":
    media_functions.setup(bot)
    movie_functions.setup(bot)
    bot.run(DISCORD_TOKEN)
