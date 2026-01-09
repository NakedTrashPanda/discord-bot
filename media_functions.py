import discord
from discord.ext import tasks
import json
import shutil
import random
import asyncio
from datetime import datetime, timedelta, time
from tqdm import tqdm
from config import (
    MEDIA_CHANNEL_ID,
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
    SCHEDULE_CONFIG_FILE,
    MEDIA_RATINGS_FILE,
    BOT_OWNER_ID,
)

# ========== JSON Data Management ==========

def load_history():
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return {"uploaded_files": []}

def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

def load_schedule_config():
    if SCHEDULE_CONFIG_FILE.exists():
        with open(SCHEDULE_CONFIG_FILE, "r") as f:
            return json.load(f)
    return {"enabled": True, "hour": 12, "minute": 0}

def save_schedule_config(config):
    with open(SCHEDULE_CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

def load_media_ratings():
    if MEDIA_RATINGS_FILE.exists():
        with open(MEDIA_RATINGS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_media_ratings(ratings):
    with open(MEDIA_RATINGS_FILE, "w") as f:
        json.dump(ratings, f, indent=2)

def load_caption_and_tags(media_path):
    """Load caption and tags from a .txt file with the same basename as the media file."""
    txt_path = media_path.with_suffix('.txt')
    if txt_path.exists():
        with open(txt_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            # Extract hashtags
            tags = [word[1:] for word in content.split() if word.startswith('#')]
            # Caption is everything except hashtags
            caption = ' '.join([word for word in content.split() if not word.startswith('#')])
            return caption, tags
    return None, []

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

# ========== Upload Logic ==========

async def perform_upload(channel, batch, batch_label="Daily Batch Upload"):
    """Core upload logic with rating reactions."""
    history = load_history()
    uploaded_set = set(history["uploaded_files"])

    files = []
    for f in pretty_tqdm(batch, "Preparing"):
        files.append(discord.File(str(f)))

    print("Uploading to Discord...")
    message = await channel.send(
        f"📤 **{batch_label}** ({len(batch)} files)",
        files=files,
    )

    # Add rating reactions
    rating_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
    for emoji in rating_emojis:
        await message.add_reaction(emoji)

    print("Upload successful!")

    for f in pretty_tqdm(batch, "Archiving"):
        dest = ARCHIVE_FOLDER / f.name
        shutil.move(str(f), str(dest))
        uploaded_set.add(f.name)

        # Store upload metadata with tags
        caption, tags = load_caption_and_tags(f)
        if "metadata" not in history:
            history["metadata"] = {}
        history["metadata"][f.name] = {
            "upload_date": datetime.now().isoformat(),
            "tags": tags,
            "caption": caption,
            "message_id": message.id
        }

    history["uploaded_files"] = list(uploaded_set)
    save_history(history)
    print(f"Completed: {len(batch)} files archived")

# ========== Scheduled Upload Task ==========

@tasks.loop(minutes=1)
async def daily_upload():
    """Check schedule config and run upload if it's time."""
    config = load_schedule_config()

    if not config.get("enabled", True):
        return

    now = datetime.now()
    target_hour = config.get("hour", 12)
    target_minute = config.get("minute", 0)

    # Only run if we're in the target minute
    if now.hour != target_hour or now.minute != target_minute:
        return

    channel = daily_upload.bot.get_channel(MEDIA_CHANNEL_ID)
    if not channel:
        print("Error: Channel not found")
        return

    print("=" * 60)
    print("Starting Scheduled Upload Process")
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
        await perform_upload(channel, batch)
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
                print(f"Smart fit: {len(smart_batch)} files ({smart_size:.2f} MB)")
                try:
                    await perform_upload(channel, smart_batch)
                    return
                except Exception as e2:
                    print(f"Smart fit failed: {e2}")

            print("Trying reduced batch...")
            reduced_batch = reduced_batch_selection(
                images, videos, MAX_UPLOAD_SIZE_MB * 0.6
            )

            if reduced_batch:
                reduced_size = sum(get_file_size_mb(f) for f in reduced_batch)
                print(f"Reduced batch: {len(reduced_batch)} files ({reduced_size:.2f} MB)")
                await perform_upload(channel, reduced_batch, "Reduced Batch Upload")
            else:
                print("No viable reduced batch.")
        else:
            print(f"Upload failed: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

    print("=" * 60)

# ========== Bot Setup ==========

def setup(bot: discord.Client):
    daily_upload.bot = bot
    tree = bot.tree

    # ========== Existing Commands ==========

    @tree.command(
        name="check_media",
        description="Check queued media and next batch details.",
    )
    async def check_media(interaction: discord.Interaction):
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
        embed.add_field(name="Images Ready", value=str(total_images), inline=True)
        embed.add_field(name="Videos Ready", value=str(total_videos), inline=True)
        embed.add_field(name="Archived Files", value=str(archived_count), inline=True)

        next_batch_text = (
            f"{images_in_batch} images + {videos_in_batch} videos "
            f"({round(batch_size_mb, 2)} MB)"
        )
        embed.add_field(name="Next Batch", value=next_batch_text, inline=False)
        embed.add_field(name="Order", value=SELECTION_ORDER, inline=False)

        await interaction.response.send_message(embed=embed)

    @tree.command(
        name="clear_history",
        description="Admin: clear upload history so all files are eligible again.",
    )
    async def clear_history_cmd(interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ You need administrator permissions to use this.",
                ephemeral=True,
            )
            return

        history = {"uploaded_files": [], "metadata": {}}
        save_history(history)
        await interaction.response.send_message(
            "✅ Upload history cleared! All media files will be eligible for upload again."
        )

    @tree.command(
        name="upload_now",
        description="Admin: trigger the daily media upload immediately.",
    )
    async def upload_now_cmd(interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ You need administrator permissions to use this.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            "🚀 Starting manual batch upload...", ephemeral=True
        )

        # Temporarily disable schedule check
        await perform_manual_upload()

    async def perform_manual_upload():
        channel = bot.get_channel(MEDIA_CHANNEL_ID)
        if not channel:
            print("Error: Channel not found")
            return

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

        batch = select_batch(
            images,
            videos,
            IMAGES_PER_BATCH,
            VIDEOS_PER_BATCH,
            MAX_UPLOAD_SIZE_MB,
            SELECTION_ORDER,
        )

        if batch:
            await perform_upload(channel, batch, "Manual Upload")

    # ========== New Commands ==========

    @tree.command(
        name="schedule",
        description="Configure daily upload schedule (format: HH:MM or 'off')",
    )
    async def schedule_cmd(interaction: discord.Interaction, time_str: str):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ You need administrator permissions to use this.",
                ephemeral=True,
            )
            return

        config = load_schedule_config()

        if time_str.lower() == "off":
            config["enabled"] = False
            save_schedule_config(config)
            await interaction.response.send_message("✅ Daily uploads disabled.")
            return

        try:
            hour, minute = map(int, time_str.split(":"))
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError

            config["enabled"] = True
            config["hour"] = hour
            config["minute"] = minute
            save_schedule_config(config)

            await interaction.response.send_message(
                f"✅ Daily upload scheduled for {hour:02d}:{minute:02d}"
            )
        except:
            await interaction.response.send_message(
                "❌ Invalid format. Use HH:MM (e.g., 14:30) or 'off'",
                ephemeral=True
            )

    @tree.command(
        name="dry_run",
        description="Preview the next N batches without uploading",
    )
    async def dry_run_cmd(interaction: discord.Interaction, count: int = 1):
        if count < 1 or count > 10:
            await interaction.response.send_message(
                "❌ Count must be between 1 and 10",
                ephemeral=True
            )
            return

        history = load_history()
        uploaded_set = set(history["uploaded_files"])

        images = [
            f for f in MEDIA_FOLDER.iterdir()
            if f.suffix.lower() in IMAGE_EXTENSIONS and f.name not in uploaded_set
        ]
        videos = [
            f for f in MEDIA_FOLDER.iterdir()
            if f.suffix.lower() in VIDEO_EXTENSIONS and f.name not in uploaded_set
        ]

        embed = discord.Embed(
            title=f"🔍 Dry Run - Next {count} Batch(es)",
            color=0xE67E22
        )

        for i in range(count):
            batch = select_batch(
                images, videos,
                IMAGES_PER_BATCH, VIDEOS_PER_BATCH,
                MAX_UPLOAD_SIZE_MB, SELECTION_ORDER
            )

            if not batch:
                embed.add_field(
                    name=f"Batch {i+1}",
                    value="No more files available",
                    inline=False
                )
                break

            batch_size = sum(get_file_size_mb(f) for f in batch)
            file_list = "\n".join([f"• {f.name} ({get_file_size_mb(f):.2f} MB)" for f in batch[:5]])
            if len(batch) > 5:
                file_list += f"\n... and {len(batch)-5} more"

            embed.add_field(
                name=f"Batch {i+1} ({len(batch)} files, {batch_size:.2f} MB)",
                value=file_list,
                inline=False
            )

            # Remove from available pool
            images = [f for f in images if f not in batch]
            videos = [f for f in videos if f not in batch]

        await interaction.response.send_message(embed=embed)

    
    @tree.command(
            name="test_tqdm", 
            description="[ADMIN] Test tqdm")
    async def test_tqdm_cmd(interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        
        await interaction.response.send_message("🧪 Testing...", ephemeral=True)
        
        test_files = list(MEDIA_FOLDER.iterdir())[:15]
        if not test_files:
            await interaction.followup.send("No files.", ephemeral=True)
            return
        
        print("Tqdm Test")
        pbar = pretty_tqdm(test_files[:10], "TEST")
        for f in pbar:
            await asyncio.sleep(0.03)
        print("✅ Done!")   
    
    @tree.command(
        name="search_media",
        description="Search archived media by tag",
    )
    async def search_media_cmd(interaction: discord.Interaction, tag: str):
        history = load_history()
        metadata = history.get("metadata", {})

        matches = [
            (filename, data) for filename, data in metadata.items()
            if tag.lower() in [t.lower() for t in data.get("tags", [])]
        ]

        if not matches:
            await interaction.response.send_message(
                f"❌ No media found with tag: #{tag}",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"🔍 Media Tagged #{tag}",
            description=f"Found {len(matches)} file(s)",
            color=0x1ABC9C
        )

        for filename, data in matches[:10]:
            caption = data.get("caption", "No caption")
            upload_date = data.get("upload_date", "Unknown")[:10]
            embed.add_field(
                name=filename,
                value=f"{caption}\nUploaded: {upload_date}",
                inline=False
            )

        if len(matches) > 10:
            embed.set_footer(text=f"Showing 10 of {len(matches)} results")

        await interaction.response.send_message(embed=embed)

    @tree.command(
            name="top_media", 
            description="Top voted media (past week)")
    async def top_media_cmd(interaction: discord.Interaction):
        ratings = load_media_ratings()
        history = load_history()
        metadata = history.get("metadata", {})

        week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        recent_files = [
            filename for filename, data in metadata.items()
            if data.get("upload_date", "") >= week_ago
        ]

        top_files = []
        for filename in recent_files:
            if filename in ratings:
                votes = ratings[filename].get("votes", 0)
                voters = len(ratings[filename].get("voters", []))
                top_files.append((filename, votes, voters))

        top_files.sort(key=lambda x: x[1], reverse=True)

        if not top_files:
            await interaction.response.send_message(
                "📊 No voted media from past week.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="🏆 Top Voted Media (Past 7 Days)",
            description="Any reaction = 1 vote per user",
            color=0xF39C12
        )

        for i, (filename, votes, voters) in enumerate(top_files[:10], 1):
            embed.add_field(
                name=f"{i}. {filename}",
                value=f"**{votes} votes** from {voters} user{'s' if voters != 1 else ''}",
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)
    @tree.command(
        name="help",
        description="Show all available commands with examples",
    )
    async def help_cmd(interaction: discord.Interaction):
        embed = discord.Embed(
            title="📚 Bot Commands Help",
            description="Complete guide to all available commands",
            color=0x3498DB
        )

        embed.add_field(
            name="📊 /check_media",
            value="View queue status and next batch details\nExample: `/check_media`",
            inline=False
        )

        embed.add_field(
            name="🔍 /dry_run [count]",
            value="Preview next batches without uploading\nExample: `/dry_run 3`",
            inline=False
        )

        embed.add_field(
            name="🔍 /search_media [tag]",
            value="Search archived media by hashtag\nExample: `/search_media wallpaper`",
            inline=False
        )

        embed.add_field(
            name="⭐ /top_media",
            value="View top-rated media from the past week\nExample: `/top_media`",
            inline=False
        )

        embed.add_field(
            name="🎬 /rmovie [name]",
            value="Get watch/download links for a movie\nExample: `/rmovie Inception`",
            inline=False
        )

        embed.add_field(
            name="📺 /rshow [query]",
            value="Get links for a TV episode\nExample: `/rshow Breaking Bad S01E01`",
            inline=False
        )

        embed.add_field(
            name="ℹ️ /movie [name]",
            value="Get detailed movie information\nExample: `/movie The Matrix`",
            inline=False
        )

        embed.add_field(
            name="ℹ️ /show [name]",
            value="Get detailed TV show information\nExample: `/show The Office`",
            inline=False
        )

        embed.add_field(
            name="🎥 /moviepoll [titles]",
            value="Create a poll to vote on movies to watch\nExample: `/moviepoll Inception, Interstellar, The Matrix`",
            inline=False
        )

        admin_embed = discord.Embed(
            title="🔧 Admin Commands",
            color=0xE74C3C
        )

        admin_embed.add_field(
            name="⏰ /schedule [time]",
            value="Set upload time (HH:MM) or disable (off)\nExample: `/schedule 14:30` or `/schedule off`",
            inline=False
        )

        admin_embed.add_field(
            name="🚀 /upload_now",
            value="Trigger immediate upload\nExample: `/upload_now`",
            inline=False
        )

        admin_embed.add_field(
            name="🗑️ /clear_history",
            value="Reset upload history\nExample: `/clear_history`",
            inline=False
        )

        await interaction.response.send_message(embeds=[embed, admin_embed], ephemeral=True)

        # ========== Event Handlers ==========
    @bot.event
    async def 
    on_raw_reaction_add(payload):
        """Track ANY reaction as a vote (one vote per user per message)."""
        if payload.user_id == bot.user.id:
        return

    history = load_history()
    metadata = history.get("metadata", {})
    ratings = load_media_ratings()

    # Find files from this message
    rated_files = [
        filename for filename, data in metadata.items()
        if data.get("message_id") == payload.message_id
    ]

    if not rated_files:
        return

    # Count unique voters per message (not per emoji)
    for filename in rated_files:
        if filename not in ratings:
            ratings[filename] = {"votes": 0, "voters": []}
        
        user_id = str(payload.user_id)
        if user_id not in ratings[filename]["voters"]:
            ratings[filename]["votes"] += 1
            ratings[filename]["voters"].append(user_id)
    
    save_media_ratings(ratings)
