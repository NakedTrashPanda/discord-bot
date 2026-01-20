import discord
from discord.ext import commands

def setup_help_commands(bot):
    tree = bot.tree

    @tree.command(
        name="help",
        description="Show all available commands with examples",
    )
    async def help_cmd(interaction: discord.Interaction):
        general_embed = discord.Embed(
            title="📚 General Commands",
            description="Commands for everyone to use.",
            color=0x3498DB
        )
        general_embed.add_field(
            name="👀 /watchlist",
            value="Show media you have added to your watchlist, with options to remove.\nExample: `/watchlist`",
            inline=False
        )
        general_embed.add_field(
            name="🎬 /watched",
            value="Show media you have marked as watched.\nExample: `/watched`",
            inline=False
        )
        general_embed.add_field(
            name="➕ Right-click on message -> Apps -> Add to Watchlist",
            value="Add a media item from a message to your personal watchlist.\nExample: Right-click on a media message -> Apps -> Add to Watchlist",
            inline=False
        )
        general_embed.add_field(
            name="🏆 /top_media",
            value="View top-rated media from the past week.\nExample: `/top_media`",
            inline=False
        )
        general_embed.add_field(
            name="❓ /help",
            value="Show this help message.\nExample: `/help`",
            inline=False
        )

        media_embed = discord.Embed(
            title="🖼️ Media Commands",
            description="Commands related to media uploads.",
            color=0x1ABC9C
        )
        media_embed.add_field(
            name="📊 /check_media",
            value="View queue status and next batch details.\nExample: `/check_media`",
            inline=False
        )
        media_embed.add_field(
            name="🔍 /dry_run [count]",
            value="Preview the next N batches without uploading.\nExample: `/dry_run 3`",
            inline=False
        )

        movie_show_embed = discord.Embed(
            title="🍿 Movie & TV Show Commands",
            description="Commands for discovering movies and TV shows.",
            color=0x9B59B6
        )
        movie_show_embed.add_field(
            name="🎬 /rmovie [name]",
            value="Get watch/download links for a movie.\nExample: `/rmovie Inception`",
            inline=False
        )
        movie_show_embed.add_field(
            name="📺 /rshow [query]",
            value="Get watch/download links for a TV episode.\nExample: `/rshow Breaking Bad S01E01`",
            inline=False
        )
        movie_show_embed.add_field(
            name="ℹ️ /movie [name]",
            value="Get detailed movie information (release date, rating, overview, TMDB link).\nExample: `/movie The Matrix`",
            inline=False
        )
        movie_show_embed.add_field(
            name="ℹ️ /show [name]",
            value="Get detailed TV show information (first air date, rating, overview, TMDB link).\nExample: `/show The Office`",
            inline=False
        )
        movie_show_embed.add_field(
            name="🗓️ /seasons [show_name]",
            value="List seasons for a TV show with episode counts and air dates.\nExample: `/seasons The Mandalorian`",
            inline=False
        )
        movie_show_embed.add_field(
            name="📺 /episodes [show_name] [season_number]",
            value="List episodes for a specific TV show season.\nExample: `/episodes The Expanse 5`",
            inline=False
        )

        admin_embed = discord.Embed(
            title="🔧 Admin Commands",
            description="Commands for bot administrators only.",
            color=0xE74C3C
        )
        admin_embed.add_field(
            name="⏰ /schedule [time]",
            value="Set daily upload time (HH:MM) or disable (off).\nExample: `/schedule 14:30` or `/schedule off`",
            inline=False
        )
        admin_embed.add_field(
            name="🚀 /upload_now",
            value="Trigger immediate media upload.\nExample: `/upload_now`",
            inline=False
        )
        admin_embed.add_field(
            name="🗑️ /clear_history",
            value="Reset upload history so all media files are eligible again.\nExample: `/clear_history`",
            inline=False
        )
        admin_embed.add_field(
            name="↩️ /undo",
            value="Undo the most recent media post (deletes message, restores files).\nExample: `/undo`",
            inline=False
        )
        admin_embed.add_field(
            name="🧪 /test_tqdm",
            value="Test tqdm progress bar (Admin only).\nExample: `/test_tqdm`",
            inline=False
        )

        await interaction.response.send_message(embeds=[general_embed, media_embed, movie_show_embed, admin_embed], ephemeral=True)