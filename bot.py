import discord
from discord.ext import commands, tasks
import json
import shutil
import requests
import re
from datetime import datetime, time, timedelta
import random
from tqdm import tqdm

from config import (
    DISCORD_TOKEN,
    TMDB_API_KEY,
    MEDIA_CHANNEL_ID,
    MOVIES_CHANNEL_ID,
    IMAGES_PER_BATCH,
    VIDEOS_PER_BATCH,
    ARCHIVE_RETENTION_DAYS,
    MAX_UPLOAD_SIZE_MB,
    SELECTION_ORDER,
    IMAGE_EXTENSIONS,
    VIDEO_EXTENSIONS,
    MEDIA_FOLDER,
    ARCHIVE_FOLDER,
    HISTORY_FILE,
)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


def load_history():
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return {"uploaded_files": []}


def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def cleanup_old_archives():
    cutoff = datetime.now() - timedelta(days=ARCHIVE_RETENTION_DAYS)
    for file in ARCHIVE_FOLDER.iterdir():
        if file.is_file() and datetime.fromtimestamp(file.stat().st_mtime) < cutoff:
            file.unlink()


def get_file_size_mb(file_path):
    return file_path.stat().st_size / (1024 * 1024)


def order_files(files, order_type):
    if order_type == "random":
        shuffled = list(files)
        random.shuffle(shuffled)
        return shuffled
    if order_type == "name":
        return sorted(files, key=lambda x: x.name)
    return list(files)


def select_batch(images, videos, target_images, target_videos, max_size_mb, order_type="random"):
    ordered_images = order_files(images, order_type)
    ordered_videos = order_files(videos, order_type)
    selected_images = []
    selected_videos = []
    total_size = 0

    for img in ordered_images[:target_images]:
        size = get_file_size_mb(img)
        if total_size + size <= max_size_mb:
            selected_images.append(img)
            total_size += size

    for vid in ordered_videos[:target_videos]:
        size = get_file_size_mb(vid)
        if total_size + size <= max_size_mb:
            selected_videos.append(vid)
            total_size += size

    return selected_images + selected_videos


def smart_fit_batch(images, videos, target_images, target_videos, max_size_mb):
    images_sorted = sorted(images, key=get_file_size_mb)
    videos_sorted = sorted(videos, key=get_file_size_mb)
    selected_images = []
    selected_videos = []
    total_size = 0

    for img in images_sorted:
        if len(selected_images) < target_images:
            size = get_file_size_mb(img)
            if total_size + size <= max_size_mb:
                selected_images.append(img)
                total_size += size

    for vid in videos_sorted:
        if len(selected_videos) < target_videos:
            size = get_file_size_mb(vid)
            if total_size + size <= max_size_mb:
                selected_videos.append(vid)
                total_size += size

    return selected_images + selected_videos


def reduced_batch_selection(images, videos, max_size_mb):
    all_files = list(images) + list(videos)
    all_files.sort(key=get_file_size_mb)
    selected = []
    total_size = 0

    for file_path in all_files:
        size = get_file_size_mb(file_path)
        if total_size + size <= max_size_mb:
            selected.append(file_path)
            total_size += size

    return selected


def pretty_tqdm(iterable, desc):
    return tqdm(
        iterable,
        desc=desc,
        unit="file",
        ncols=70,
        bar_format="[{desc:^10}] {l_bar}{bar} | {n_fmt}/{total_fmt} ({elapsed}<{remaining})",
    )


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    if not daily_upload.is_running():
        daily_upload.start()


@tasks.loop(time=time(hour=12, minute=0))
async def daily_upload():
    channel = bot.get_channel(MEDIA_CHANNEL_ID)
    if not channel:
        print("Error: Channel not found")
        return

    print("=" * 60)
    print("Starting Daily Upload Process")
    print("=" * 60)

    cleanup_old_archives()
    history = load_history()
    uploaded_set = set(history["uploaded_files"])

    images = [
        f
        for f in MEDIA_FOLDER.iterdir()
        if f.suffix.lower() in IMAGE_EXTENSIONS and f.name not in uploaded_set
    ]
    videos = [
        f
        for f in MEDIA_FOLDER.iterdir()
        if f.suffix.lower() in VIDEO_EXTENSIONS and f.name not in uploaded_set
    ]

    print(f"Available: {len(images)} images, {len(videos)} videos")
    print(f"Selection order: {SELECTION_ORDER}")

    batch = select_batch(
        images,
        videos,
        IMAGES_PER_BATCH,
        VIDEOS_PER_BATCH,
        MAX_UPLOAD_SIZE_MB,
        SELECTION_ORDER,
    )

    if not batch:
        print("No files to upload")
        return

    batch_size = sum(get_file_size_mb(f) for f in batch)
    print(f"Initial batch: {len(batch)} files ({batch_size:.2f} MB)")

    try:
        files = []
        for f in pretty_tqdm(batch, "Preparing"):
            files.append(discord.File(str(f)))

        print("Uploading to Discord...")
        await channel.send(
            f"📤 **Daily Batch Upload** ({len(batch)} files)", files=files
        )
        print("Upload successful!")

        for f in pretty_tqdm(batch, "Archiving"):
            dest = ARCHIVE_FOLDER / f.name
            shutil.move(str(f), str(dest))
            uploaded_set.add(f.name)

        history["uploaded_files"] = list(uploaded_set)
        save_history(history)
        print(f"Completed: {len(batch)} files archived")

    except discord.HTTPException as e:
        if e.status == 413:
            print("⚠️ Upload too large! Trying smart fit...")
            smart_batch = smart_fit_batch(
                images,
                videos,
                IMAGES_PER_BATCH,
                VIDEOS_PER_BATCH,
                MAX_UPLOAD_SIZE_MB * 0.8,
            )

            if smart_batch and len(smart_batch) >= len(batch) * 0.5:
                smart_size = sum(get_file_size_mb(f) for f in smart_batch)
                print(
                    f"Smart fit: {len(smart_batch)} files ({smart_size:.2f} MB)"
                )
                try:
                    files = []
                    for f in pretty_tqdm(smart_batch, "Preparing"):
                        files.append(discord.File(str(f)))

                    await channel.send(
                        f"📤 **Adjusted Batch Upload** ({len(smart_batch)} files)",
                        files=files,
                    )
                    print("Smart fit successful!")

                    for f in pretty_tqdm(smart_batch, "Archiving"):
                        dest = ARCHIVE_FOLDER / f.name
                        shutil.move(str(f), str(dest))
                        uploaded_set.add(f.name)

                    history["uploaded_files"] = list(uploaded_set)
                    save_history(history)
                except Exception as e2:
                    print(f"Smart fit failed: {e2}")
                    print("Trying reduced batch...")
                    reduced_batch = reduced_batch_selection(
                        images, videos, MAX_UPLOAD_SIZE_MB * 0.6
                    )
                    if reduced_batch:
                        reduced_size = sum(
                            get_file_size_mb(f) for f in reduced_batch
                        )
                        print(
                            f"Reduced batch: {len(reduced_batch)} files ({reduced_size:.2f} MB)"
                        )
                        files = []
                        for f in pretty_tqdm(reduced_batch, "Preparing"):
                            files.append(discord.File(str(f)))

                        await channel.send(
                            f"📤 **Reduced Batch Upload** ({len(reduced_batch)} files)",
                            files=files,
                        )
                        print("Reduced batch successful!")

                        for f in pretty_tqdm(reduced_batch, "Archiving"):
                            dest = ARCHIVE_FOLDER / f.name
                            shutil.move(str(f), str(dest))
                            uploaded_set.add(f.name)

                        history["uploaded_files"] = list(uploaded_set)
                        save_history(history)
            else:
                print("Skipping smart fit, trying reduced batch...")
                reduced_batch = reduced_batch_selection(
                    images, videos, MAX_UPLOAD_SIZE_MB * 0.6
                )
                if reduced_batch:
                    reduced_size = sum(
                        get_file_size_mb(f) for f in reduced_batch
                    )
                    print(
                        f"Reduced batch: {len(reduced_batch)} files ({reduced_size:.2f} MB)"
                    )
                    files = []
                    for f in pretty_tqdm(reduced_batch, "Preparing"):
                        files.append(discord.File(str(f)))

                    await channel.send(
                        f"📤 **Reduced Batch Upload** ({len(reduced_batch)} files)",
                        files=files,
                    )
                    print("Reduced batch successful!")

                    for f in pretty_tqdm(reduced_batch, "Archiving"):
                        dest = ARCHIVE_FOLDER / f.name
                        shutil.move(str(f), str(dest))
                        uploaded_set.add(f.name)

                    history["uploaded_files"] = list(uploaded_set)
                    save_history(history)
        else:
            print(f"Upload failed: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

    print("=" * 60)


@bot.command(name="check_media")
async def check_media(ctx):
    history = load_history()
    uploaded_set = set(history["uploaded_files"])

    images = [
        f
        for f in MEDIA_FOLDER.iterdir()
        if f.suffix.lower() in IMAGE_EXTENSIONS and f.name not in uploaded_set
    ]
    videos = [
        f
        for f in MEDIA_FOLDER.iterdir()
        if f.suffix.lower() in VIDEO_EXTENSIONS and f.name not in uploaded_set
    ]

    total_images = len(images)
    total_videos = len(videos)
    archived_count = len(list(ARCHIVE_FOLDER.iterdir()))

    next_batch = select_batch(
        images,
        videos,
        IMAGES_PER_BATCH,
        VIDEOS_PER_BATCH,
        MAX_UPLOAD_SIZE_MB,
        SELECTION_ORDER,
    )

    batch_size_mb = sum(get_file_size_mb(f) for f in next_batch)
    images_in_batch = sum(
        1 for f in next_batch if f.suffix.lower() in IMAGE_EXTENSIONS
    )
    videos_in_batch = sum(
        1 for f in next_batch if f.suffix.lower() in VIDEO_EXTENSIONS
    )

    embed = discord.Embed(title="📊 Media Queue Status", color=0x3498DB)
    embed.add_field(
        name="Images Ready", value=str(total_images), inline=True
    )
    embed.add_field(
        name="Videos Ready", value=str(total_videos), inline=True
    )
    embed.add_field(
        name="Archived Files", value=str(archived_count), inline=True
    )

    next_batch_text = (
        f"{images_in_batch} images + {videos_in_batch} videos "
        f"({round(batch_size_mb, 2)} MB)"
    )
    embed.add_field(name="Next Batch", value=next_batch_text, inline=False)
    embed.add_field(name="Order", value=SELECTION_ORDER, inline=False)

    await ctx.send(embed=embed)


@bot.command(name="clear_history")
@commands.has_permissions(administrator=True)
async def clear_history(ctx):
    history = {"uploaded_files": []}
    save_history(history)
    await ctx.send(
        "✅ Upload history cleared! All media files will be eligible for upload again."
    )


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


@bot.command()
@commands.has_permissions(administrator=True)
async def upload_now(ctx):
    await ctx.send("🚀 Starting manual batch upload...")
    await daily_upload()


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
