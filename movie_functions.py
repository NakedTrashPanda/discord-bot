
import discord
from discord.ext import commands
import discord.app_commands
import requests
import re

from config import (
    TMDB_API_KEY,
    MOVIES_CHANNEL_ID,
)


async def request_movie(interaction: discord.Interaction, movie_name: str):
    movie_channel = interaction.client.get_channel(MOVIES_CHANNEL_ID)
    target = movie_channel if movie_channel else interaction.channel

    url = "https://api.themoviedb.org/3/search/movie"
    res = requests.get(url, params={"api_key": TMDB_API_KEY, "query": movie_name}).json()
    if not res.get("results"):
        await interaction.response.send_message(f"❌ No movie found for: {movie_name}")
        return

    item = res["results"][0]
    tmdb_id = item["id"]
    title = item.get("title")
    watch_url = f"https://rivestream.org/embed?type=movie&id={tmdb_id}"
    download_url = f"https://rivestream.org/download?type=movie&id={tmdb_id}"

    overview = item.get("overview", "")
    if len(overview) > 300:
        overview = overview[:300] + "..."

    embed = discord.Embed(title=title, description=overview, color=0x9B59B6)
    if item.get("poster_path"):
        embed.set_thumbnail(
            url=f"https://image.tmdb.org/t/p/w500{item['poster_path']}"
        )

    view = discord.ui.View()
    view.add_item(
        discord.ui.Button(
            label="Watch Now",
            url=watch_url,
            style=discord.ButtonStyle.link,
            emoji="🎬",
        )
    )
    view.add_item(
        discord.ui.Button(
            label="Download",
            url=download_url,
            style=discord.ButtonStyle.link,
            emoji="📥",
        )
    )

    await interaction.response.send_message(embed=embed, view=view)
    if movie_channel and interaction.channel_id != MOVIES_CHANNEL_ID:
        await interaction.followup.send(f"✅ Sent to <#{MOVIES_CHANNEL_ID}>")


async def request_show(interaction: discord.Interaction, query: str):
    movie_channel = interaction.client.get_channel(MOVIES_CHANNEL_ID)
    target = movie_channel if movie_channel else interaction.channel

    s_e_match = re.search(r" [Ss](\d+)[Ee](\d+)", query)
    if not s_e_match:
        await interaction.response.send_message("❌ Please use format: /rshow Show Name S01E01")
        return

    season = str(int(s_e_match.group(1)))
    episode = str(int(s_e_match.group(2)))
    search_query = query[: s_e_match.start()]

    url = "https://api.themoviedb.org/3/search/tv"
    res = requests.get(url, params={"api_key": TMDB_API_KEY, "query": search_query}).json()
    if not res.get("results"):
        await interaction.response.send_message(f"❌ No show found for: {search_query}")
        return

    item = res["results"][0]
    tmdb_id = item["id"]
    title = item.get("name")

    watch_url = (
        f"https://rivestream.org/embed?type=tv&id={tmdb_id}"
        f"&season={season}&episode={episode}"
    )
    download_url = (
        f"https://rivestream.org/download?type=tv&id={tmdb_id}"
        f"&season={season}&episode={episode}"
    )

    display_title = f"{title} (S{season.zfill(2)}E{episode.zfill(2)})"
    overview = item.get("overview", "")
    if len(overview) > 300:
        overview = overview[:300] + "..."

    embed = discord.Embed(title=display_title, description=overview, color=0x9B59B6)
    if item.get("poster_path"):
        embed.set_thumbnail(
            url=f"https://image.tmdb.org/t/p/w500{item['poster_path']}"
        )

    view = discord.ui.View()
    view.add_item(
        discord.ui.Button(
            label="Watch Now",
            url=watch_url,
            style=discord.ButtonStyle.link,
            emoji="🎬",
        )
    )
    view.add_item(
        discord.ui.Button(
            label="Download",
            url=download_url,
            style=discord.ButtonStyle.link,
            emoji="📥",
        )
    )

    await interaction.response.send_message(embed=embed, view=view)
    if movie_channel and interaction.channel_id != MOVIES_CHANNEL_ID:
        await interaction.followup.send(f"✅ Sent to <#{MOVIES_CHANNEL_ID}>")


async def movie_info(interaction: discord.Interaction, movie_name: str):
    url = "https://api.themoviedb.org/3/search/movie"
    res = requests.get(url, params={"api_key": TMDB_API_KEY, "query": movie_name}).json()
    if not res.get("results"):
        await interaction.response.send_message(f"❌ No movie found for: {movie_name}")
        return

    item = res["results"][0]
    tmdb_id = item["id"]
    title = item.get("title")
    release_date = item.get("release_date", "Unknown")
    rating = item.get("vote_average", "N/A")
    votes = item.get("vote_count", "N/A")
    overview = item.get("overview", "No description available.")

    embed = discord.Embed(title=title, description=overview, color=0x00FF00)
    if item.get("poster_path"):
        embed.set_thumbnail(
            url=f"https://image.tmdb.org/t/p/w500{item['poster_path']}"
        )

    embed.add_field(name="Release Date", value=release_date, inline=True)
    embed.add_field(name="Rating", value=f"{rating}/10", inline=True)
    embed.add_field(name="Votes", value=votes, inline=True)
    embed.add_field(
        name="TMDB Link",
        value=f"https://www.themoviedb.org/movie/{tmdb_id}",
        inline=False,
    )

    await interaction.response.send_message(embed=embed)


async def show_info(interaction: discord.Interaction, show_name: str):
    url = "https://api.themoviedb.org/3/search/tv"
    res = requests.get(url, params={"api_key": TMDB_API_KEY, "query": show_name}).json()
    if not res.get("results"):
        await interaction.response.send_message(f"❌ No show found for: {show_name}")
        return

    item = res["results"][0]
    tmdb_id = item["id"]
    title = item.get("name")
    first_air = item.get("first_air_date", "Unknown")
    rating = item.get("vote_average", "N/A")
    votes = item.get("vote_count", "N/A")
    overview = item.get("overview", "No description available.")

    embed = discord.Embed(title=title, description=overview, color=0x00FF00)
    if item.get("poster_path"):
        embed.set_thumbnail(
            url=f"https://image.tmdb.org/t/p/w500{item['poster_path']}"
        )

    embed.add_field(name="First Air Date", value=first_air, inline=True)
    embed.add_field(name="Rating", value=f"{rating}/10", inline=True)
    embed.add_field(name="Votes", value=votes, inline=True)
    embed.add_field(
        name="TMDB Link",
        value=f"https://www.themoviedb.org/tv/{tmdb_id}",
        inline=False,
    )

    await interaction.response.send_message(embed=embed)


async def list_seasons(interaction: discord.Interaction, show_name: str):
    search_url = "https://api.themoviedb.org/3/search/tv"
    search_res = requests.get(search_url, params={"api_key": TMDB_API_KEY, "query": show_name}).json()
    
    if not search_res.get("results"):
        await interaction.response.send_message(f"❌ No show found for: {show_name}")
        return
    
    show_id = search_res["results"][0]["id"]
    show_title = search_res["results"][0]["name"]

    details_url = f"https://api.themoviedb.org/3/tv/{show_id}"
    details_res = requests.get(details_url, params={"api_key": TMDB_API_KEY}).json()

    if not details_res.get("seasons"):
        await interaction.response.send_message(f"❌ Could not retrieve season information for {show_title}.")
        return

    embed = discord.Embed(
        title=f"Seasons for {show_title}",
        color=0x3498DB
    )

    for season in details_res["seasons"]:
        season_number = season.get("season_number")
        name = season.get("name", f"Season {season_number}")
        episode_count = season.get("episode_count", "N/A")
        air_date = season.get("air_date", "Unknown")

        value = f"Episodes: {episode_count}\nAir Date: {air_date}"
        embed.add_field(name=name, value=value, inline=False)
    
    await interaction.response.send_message(embed=embed)


async def list_episodes(interaction: discord.Interaction, show_name: str, season_number: int):
    search_url = "https://api.themoviedb.org/3/search/tv"
    search_res = requests.get(search_url, params={"api_key": TMDB_API_KEY, "query": show_name}).json()

    if not search_res.get("results"):
        await interaction.response.send_message(f"❌ No show found for: {show_name}")
        return

    show_id = search_res["results"][0]["id"]
    show_title = search_res["results"][0]["name"]

    season_url = f"https://api.themoviedb.org/3/tv/{show_id}/season/{season_number}"
    season_res = requests.get(season_url, params={"api_key": TMDB_API_KEY}).json()

    if not season_res.get("episodes"):
        await interaction.response.send_message(f"❌ Could not retrieve episodes for {show_title} Season {season_number}.")
        return

    embed = discord.Embed(
        title=f"Episodes for {show_title} - Season {season_number}",
        color=0x1ABC9C
    )

    for episode in season_res["episodes"]:
        episode_number = episode.get("episode_number")
        name = episode.get("name", f"Episode {episode_number}")
        air_date = episode.get("air_date", "Unknown")
        overview = episode.get("overview", "No description available.")

        value = f"Air Date: {air_date}\n{overview[:150]}..." if overview else f"Air Date: {air_date}"
        embed.add_field(name=f"E{str(episode_number).zfill(2)} - {name}", value=value, inline=False)
    
    await interaction.response.send_message(embed=embed)


def setup(bot):
    tree = bot.tree

    @tree.command(name="rmovie", description="Get watch/download links for a movie.")
    @discord.app_commands.describe(movie_name="The name of the movie")
    async def rmovie_slash(interaction: discord.Interaction, movie_name: str):
        await request_movie(interaction, movie_name=movie_name)
    
    @tree.command(name="rshow", description="Get watch/download links for a TV episode.")
    @discord.app_commands.describe(query="The TV show name and episode (e.g., 'Breaking Bad S01E01')")
    async def rshow_slash(interaction: discord.Interaction, query: str):
        await request_show(interaction, query=query)

    @tree.command(name="movie", description="Get detailed movie information.")
    @discord.app_commands.describe(movie_name="The name of the movie")
    async def movie_slash(interaction: discord.Interaction, movie_name: str):
        await movie_info(interaction, movie_name=movie_name)

    @tree.command(name="show", description="Get detailed TV show information.")
    @discord.app_commands.describe(show_name="The name of the TV show")
    async def show_slash(interaction: discord.Interaction, show_name: str):
        await show_info(interaction, show_name=show_name)

    @tree.command(name="seasons", description="List seasons for a TV show.")
    @discord.app_commands.describe(show_name="The name of the TV show")
    async def seasons_slash(interaction: discord.Interaction, show_name: str):
        await list_seasons(interaction, show_name=show_name)

    @tree.command(name="episodes", description="List episodes for a specific TV show season.")
    @discord.app_commands.describe(show_name="The name of the TV show", season_number="The season number")
    async def episodes_slash(interaction: discord.Interaction, show_name: str, season_number: int):
        await list_episodes(interaction, show_name=show_name, season_number=season_number)
