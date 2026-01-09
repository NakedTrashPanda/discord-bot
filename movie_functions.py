
import discord
from discord.ext import commands
import requests
import re

from config import (
    TMDB_API_KEY,
    MOVIES_CHANNEL_ID,
)


def setup(bot):
    @bot.command(name="rmovie")
    async def request_movie(ctx, *, movie_name: str):
        movie_channel = bot.get_channel(MOVIES_CHANNEL_ID)
        target = movie_channel if movie_channel else ctx.channel

        url = "https://api.themoviedb.org/3/search/movie"
        res = requests.get(url, params={"api_key": TMDB_API_KEY, "query": movie_name}).json()
        if not res.get("results"):
            await ctx.send(f"❌ No movie found for: {movie_name}")
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

        await target.send(embed=embed, view=view)
        if movie_channel and ctx.channel.id != MOVIES_CHANNEL_ID:
            await ctx.send(f"✅ Sent to <#{MOVIES_CHANNEL_ID}>")


    @bot.command(name="rshow")
    async def request_show(ctx, *, query: str):
        movie_channel = bot.get_channel(MOVIES_CHANNEL_ID)
        target = movie_channel if movie_channel else ctx.channel

        s_e_match = re.search(r" [Ss](\d+)[Ee](\d+)", query)
        if not s_e_match:
            await ctx.send("❌ Please use format: !rshow Show Name S01E01")
            return

        season = str(int(s_e_match.group(1)))
        episode = str(int(s_e_match.group(2)))
        search_query = query[: s_e_match.start()]

        url = "https://api.themoviedb.org/3/search/tv"
        res = requests.get(url, params={"api_key": TMDB_API_KEY, "query": search_query}).json()
        if not res.get("results"):
            await ctx.send(f"❌ No show found for: {search_query}")
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

        await target.send(embed=embed, view=view)
        if movie_channel and ctx.channel.id != MOVIES_CHANNEL_ID:
            await ctx.send(f"✅ Sent to <#{MOVIES_CHANNEL_ID}>")


    @bot.command(name="movie")
    async def movie_info(ctx, *, movie_name: str):
        url = "https://api.themoviedb.org/3/search/movie"
        res = requests.get(url, params={"api_key": TMDB_API_KEY, "query": movie_name}).json()
        if not res.get("results"):
            await ctx.send(f"❌ No movie found for: {movie_name}")
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

        await ctx.send(embed=embed)


    @bot.command(name="show")
    async def show_info(ctx, *, show_name: str):
        url = "https://api.themoviedb.org/3/search/tv"
        res = requests.get(url, params={"api_key": TMDB_API_KEY, "query": show_name}).json()
        if not res.get("results"):
            await ctx.send(f"❌ No show found for: {show_name}")
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

        await ctx.send(embed=embed)
