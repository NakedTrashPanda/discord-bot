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
    USER_DATA_FILE,
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

def load_user_data():
    if USER_DATA_FILE.exists():
        with open(USER_DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_user_data(user_data):
    with open(USER_DATA_FILE, "w") as f:
        json.dump(user_data, f, indent=2)

class RemoveWatchlistItemView(discord.ui.View):
    def __init__(self, user_id, watchlist_items, timeout=180):
        super().__init__(timeout=timeout)
        self.user_id = str(user_id)
        self.watchlist_items = watchlist_items # Pass filenames

        # Add buttons for each item
        for i, filename in enumerate(watchlist_items):
            # Max 25 components per view, and 5 per row.
            # If there are many items, we might need pagination or select dropdown
            if i < 25: # Discord button limit
                self.add_item(discord.ui.Button(
                    label=f"Remove {i+1}",
                    custom_id=f"remove_wl_{filename}",
                    style=discord.ButtonStyle.red
                ))

    @discord.ui.button(label="Clear All", style=discord.ButtonStyle.red, custom_id="remove_wl_all")
    async def clear_all_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ You can only modify your own watchlist.", ephemeral=True)
            return
        
        user_data = load_user_data()
        user_data_for_user = user_data.get(self.user_id, {"watched": [], "watchlist": []})
        user_data_for_user["watchlist"] = []
        user_data[self.user_id] = user_data_for_user
        save_user_data(user_data)
        await interaction.response.edit_message(content="✅ Your watchlist has been cleared.", embed=None, view=None)


    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey, custom_id="remove_wl_cancel")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ You can only modify your own watchlist.", ephemeral=True)
            return
        
        await interaction.response.edit_message(content="Operation cancelled.", view=None)


    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.custom_id.startswith("remove_wl_"):
            if str(interaction.user.id) != self.user_id:
                await interaction.response.send_message("❌ You can only modify your own watchlist.", ephemeral=True)
                return False
            
            filename_to_remove = interaction.custom_id[len("remove_wl_"):]
            if filename_to_remove == "all" or filename_to_remove == "cancel":
                # Handled by specific buttons above
                return True

            user_data = load_user_data()
            user_data_for_user = user_data.get(self.user_id, {"watched": [], "watchlist": []})
            
            if filename_to_remove in user_data_for_user["watchlist"]:
                user_data_for_user["watchlist"].remove(filename_to_remove)
                user_data[self.user_id] = user_data_for_user
                save_user_data(user_data)

                await interaction.response.edit_message(content=f"✅ Removed '{filename_to_remove}' from your watchlist.", view=None)
                # You might want to refresh the watchlist embed here
            else:
                await interaction.response.send_message(f"❌ '{filename_to_remove}' not found in your watchlist.", ephemeral=True)
            return False # Interaction handled, no need for further processing

        return True

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
    """
    Select a batch of files prioritizing target counts while respecting size limits.
    This function attempts to maintain the target batch size by selecting the smallest files
    when the original ordering would exceed the size limit.
    """
    # First, try with the specified order
    ordered_images = order_files(images, order_type)
    ordered_videos = order_files(videos, order_type)

    # Take the first target_images and target_videos from the ordered lists
    # But only if we have enough files
    candidate_images = ordered_images[:min(target_images, len(ordered_images))]
    candidate_videos = ordered_videos[:min(target_videos, len(ordered_videos))]

    # Calculate total size of candidates
    total_size = sum(get_file_size_mb(f) for f in candidate_images + candidate_videos)

    # If within size limit and we have the target counts, return as is
    if total_size <= max_size_mb and len(candidate_images) == target_images and len(candidate_videos) == target_videos:
        return candidate_images + candidate_videos

    # Check if we could fit the target counts with the smallest files
    smallest_images = sorted(images, key=get_file_size_mb)[:min(target_images, len(images))]
    smallest_videos = sorted(videos, key=get_file_size_mb)[:min(target_videos, len(videos))]

    smallest_total_size = sum(get_file_size_mb(f) for f in smallest_images + smallest_videos)

    # If the smallest files meet our target counts and fit in the size limit, use them
    if (smallest_total_size <= max_size_mb and
        len(smallest_images) == target_images and
        len(smallest_videos) == target_videos):
        # Use the original order if it fits, otherwise use smallest files
        # But since original didn't fit, use smallest
        return smallest_images + smallest_videos

    # If we don't have enough files for targets or exceeding size limit,
    # try to optimize by selecting smallest files to meet targets if possible
    return prioritize_target_counts_over_size(images, videos, target_images, target_videos, max_size_mb)


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


def prioritize_target_counts_over_size(all_images, all_videos, target_images, target_videos, max_size_mb):
    """
    Attempts to maintain target counts by selecting smallest files when possible.
    If target counts cannot be maintained within size limits, falls back to size-first approach.
    """
    # Sort by size to get smallest files from all available
    sorted_images_by_size = sorted(all_images, key=get_file_size_mb)
    sorted_videos_by_size = sorted(all_videos, key=get_file_size_mb)

    # Try to take the smallest target_images and target_videos
    potential_images = sorted_images_by_size[:min(target_images, len(sorted_images_by_size))]
    potential_videos = sorted_videos_by_size[:min(target_videos, len(sorted_videos_by_size))]

    # Check if this combination fits within the size limit
    total_size = sum(get_file_size_mb(f) for f in potential_images + potential_videos)

    if total_size <= max_size_mb and len(potential_images) == target_images and len(potential_videos) == target_videos:
        # Great! We can maintain target counts with smallest files
        return potential_images + potential_videos
    elif total_size <= max_size_mb:
        # We're under the limit but don't have enough files for targets
        # Return what we have
        return potential_images + potential_videos
    else:
        # Even the smallest files exceed the limit, so we need to reduce the batch
        # Start by taking the smallest files and add as many as possible
        all_smallest = sorted(
            potential_images + potential_videos,
            key=get_file_size_mb
        )

        selected = []
        current_size = 0

        for file in all_smallest:
            file_size = get_file_size_mb(file)
            if current_size + file_size <= max_size_mb:
                selected.append(file)
                current_size += file_size

        # If we couldn't fit even a few files, fall back to the original smart_fit approach
        if len(selected) < 2:  # arbitrary threshold
            # Use the original smart_fit logic as fallback
            images_sorted = sorted(all_images, key=get_file_size_mb)
            videos_sorted = sorted(all_videos, key=get_file_size_mb)
            selected_images = []
            selected_videos = []
            total_size = 0

            for img in images_sorted:
                if len(selected_images) < min(target_images, len(all_images)):
                    size = get_file_size_mb(img)
                    if total_size + size <= max_size_mb:
                        selected_images.append(img)
                        total_size += size

            for vid in videos_sorted:
                if len(selected_videos) < min(target_videos, len(all_videos)):
                    size = get_file_size_mb(vid)
                    if total_size + size <= max_size_mb:
                        selected_videos.append(vid)
                        total_size += size

            return selected_images + selected_videos

        return selected

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
    """Core upload logic without automatic rating reactions."""
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

    print("Upload successful!")

    for f in pretty_tqdm(batch, "Archiving"):
        dest = ARCHIVE_FOLDER / f.name
        shutil.move(str(f), str(dest))
        uploaded_set.add(f.name)

        # Store upload metadata
        if "metadata" not in history:
            history["metadata"] = {}
        history["metadata"][f.name] = {
            "upload_date": datetime.now().isoformat(),
            "message_id": message.id
        }

    history["uploaded_files"] = list(uploaded_set)
    save_history(history)
    print(f"Completed: {len(batch)} files archived")

# ========== Scheduled Upload Task ========== 

@tasks.loop(minutes=1)
async def daily_upload():
    """Check schedule config and run upload if it\'s time."""
    config = load_schedule_config()

    if not config.get("enabled", True):
        return

    now = datetime.now()
    target_hour = config.get("hour", 12)
    target_minute = config.get("minute", 0)

    # Only run if we\'re in the target minute
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

    @tree.command(name="undo", description="Admin: Undo the most recent media post (delete message, restore files).")
    async def undocmd(interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You need administrator permissions to use this.", ephemeral=True)
            return
        
        # Initial ephemeral message
        await interaction.response.send_message("🔄 Attempting to undo the last media post...", ephemeral=True)
        status_messages = ["🔄 Initializing undo process..."]
        
        history = load_history()
        metadata = history.get('metadata', {})
        
        # Find the message_id of the most recent batch
        recent_entries = [(fname, data) for fname, data in metadata.items() if 'upload_date' in data and 'message_id' in data]
        if not recent_entries:
            await interaction.edit_original_response(content="❌ No posts found in history with 'upload_date' and 'message_id' to undo.")
            return
        
        recent_entries.sort(key=lambda x: x[1]['upload_date'], reverse=True)
        latest_message_id = recent_entries[0][1]['message_id']
        
        # Find all files associated with this latest message_id
        batch_files_to_undo = []
        for fname, data in metadata.items():
            if data.get('message_id') == latest_message_id:
                batch_files_to_undo.append((fname, data))
        
        if not batch_files_to_undo:
            await interaction.edit_original_response(content="❌ Could not identify files for the most recent batch.")
            return

        status_messages.append(f"Identified batch with message ID `{latest_message_id}` containing {len(batch_files_to_undo)} file(s).")
        await interaction.edit_original_response(content="\n".join(status_messages))

        # --- PRE-CHECK: Verify all files exist in archive before proceeding ---
        missing_archive_files = []
        for fname, _ in batch_files_to_undo:
            archive_path = ARCHIVE_FOLDER / fname
            if not archive_path.exists():
                missing_archive_files.append(fname)
        
        if missing_archive_files:
            error_msg = "❌ Aborting undo: The following archived file(s) are missing and cannot be restored:\n"
            error_msg += "\n".join([f"- `{f}`" for f in missing_archive_files])
            error_msg += "\n\nDiscord post will NOT be deleted."
            await interaction.edit_original_response(content=error_msg)
            print(f"Aborting undo due to missing archive files: {missing_archive_files}") # Server-side log
            return
        # --- END PRE-CHECK ---

        # Delete the Discord message for the batch
        try:
            channel = interaction.guild.get_channel(MEDIA_CHANNEL_ID)
            if channel and latest_message_id:
                message = await channel.fetch_message(latest_message_id)
                await message.delete()
                status_messages.append(f"✅ Original Discord message `{latest_message_id}` deleted.")
            else:
                status_messages.append(f"⚠️ Could not delete Discord message `{latest_message_id}` (channel not found or message_id missing).")
        except discord.errors.NotFound:
            status_messages.append(f"⚠️ Original Discord message `{latest_message_id}` not found, likely already deleted.")
        except Exception as e:
            status_messages.append(f"❌ Error deleting Discord message `{latest_message_id}`: {e}")
            print(f"Error deleting Discord message: {e}") # Server-side logging
        await interaction.edit_original_response(content="\n".join(status_messages))

        restored_files_count = 0
        errors_during_restoration = []

        for fname, data in batch_files_to_undo:
            # Restore single file
            archive_path = ARCHIVE_FOLDER / fname
            media_path = MEDIA_FOLDER / fname
            
            if archive_path.exists():
                try:
                    archive_path.rename(media_path)
                    restored_files_count += 1
                    status_messages.append(f"✅ Restored: `{fname}`")
                except Exception as e:
                    errors_during_restoration.append(f"❌ Error restoring `{fname}`: {e}")
                    print(f"Error renaming file '{fname}': {e}") # Server-side logging
            else:
                errors_during_restoration.append(f"❌ Archive file missing for `{fname}`.")
                print(f"Archive file '{fname}' not found at {archive_path}") # Server-side logging
            
            # Clean history for this file only
            if fname in metadata:
                del metadata[fname]
            history['uploaded_files'] = [f for f in history.get('uploaded_files', []) if f != fname]
            
            # Clear ratings
            ratings = load_media_ratings()
            if fname in ratings:
                ratings.pop(fname, None)
                save_media_ratings(ratings) # Save ratings after each file removal
            
            await interaction.edit_original_response(content="\n".join(status_messages + errors_during_restoration))
        
        history['metadata'] = metadata # Ensure updated metadata is assigned back
        save_history(history) # Save history once after processing all files in batch
        
        final_message = f"✅ Undo complete: Restored {restored_files_count} file(s) from the last batch."
        if errors_during_restoration:
            final_message += "\n\n**Errors encountered during restoration:**\n" + "\n".join(errors_during_restoration)
        
        await interaction.edit_original_response(content=final_message)

    @tree.context_menu(name="Add to Watchlist")
    async def add_to_watchlist_context_menu(interaction: discord.Interaction, message: discord.Message):
        history = load_history()
        metadata = history.get("metadata", {})
        user_data = load_user_data()

        # Find the filename associated with this message
        filename = None
        for fname, data in metadata.items():
            if data.get("message_id") == message.id:
                filename = fname
                break
        
        if not filename:
            await interaction.response.send_message("❌ This message does not correspond to an uploaded media item.", ephemeral=True)
            return

        user_id_str = str(interaction.user.id)
        if user_id_str not in user_data:
            user_data[user_id_str] = {"watched": [], "watchlist": []}

        if filename in user_data[user_id_str]["watchlist"]:
            await interaction.response.send_message(f"ℹ️ '{filename}' is already in your watchlist.", ephemeral=True)
        else:
            user_data[user_id_str]["watchlist"].append(filename)
            save_user_data(user_data)
            await interaction.response.send_message(f"✅ Added '{filename}' to your watchlist.", ephemeral=True)

    @tree.command(name="watched", description="Show media you have marked as watched.")
    async def watched_cmd(interaction: discord.Interaction):
        user_id_str = str(interaction.user.id)
        user_data = load_user_data()

        if user_id_str not in user_data or not user_data[user_id_str]["watched"]:
            await interaction.response.send_message("❌ You have not marked any media as watched yet.", ephemeral=True)
            return

        watched_list = user_data[user_id_str]["watched"]
        history = load_history()
        metadata = history.get("metadata", {})

        embed = discord.Embed(
            title=f"🎬 {interaction.user.display_name}'s Watched Media",
            color=0x2ECC71
        )

        description = []
        for i, filename in enumerate(watched_list[:20]): # Limit to 20 to prevent too large embeds
            # Try to get the original message link if available
            message_id = metadata.get(filename, {}).get("message_id")
            if message_id and interaction.guild:
                # Construct a jump URL for the original message
                message_link = f"https://discord.com/channels/{interaction.guild.id}/{MEDIA_CHANNEL_ID}/{message_id}"
                description.append(f"{i+1}. [{filename}]({message_link})")
            else:
                description.append(f"{i+1}. {filename}")
        
        if not description:
            await interaction.response.send_message("❌ Could not retrieve details for your watched media.", ephemeral=True)
            return

        embed.description = "\n".join(description)

        if len(watched_list) > 20:
            embed.set_footer(text=f"Showing 20 of {len(watched_list)} watched media items.")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @tree.command(name="watchlist", description="Show media you have added to your watchlist.")
    async def watchlist_cmd(interaction: discord.Interaction):
        user_id_str = str(interaction.user.id)
        user_data = load_user_data()

        if user_id_str not in user_data or not user_data[user_id_str]["watchlist"]:
            await interaction.response.send_message("❌ Your watchlist is empty.", ephemeral=True)
            return

        watchlist = user_data[user_id_str]["watchlist"]
        history = load_history()
        metadata = history.get("metadata", {})

        embed = discord.Embed(
            title=f"👀 {interaction.user.display_name}'s Watchlist",
            color=0x3498DB
        )

        description = []
        for i, filename in enumerate(watchlist[:5]): # Limit buttons to 5 to avoid too many components
            # Try to get the original message link if available
            message_id = metadata.get(filename, {}).get("message_id")
            if message_id and interaction.guild:
                message_link = f"https://discord.com/channels/{interaction.guild.id}/{MEDIA_CHANNEL_ID}/{message_id}"
                description.append(f"{i+1}. [{filename}]({message_link})")
            else:
                description.append(f"{i+1}. {filename}")
        
        if not description:
            await interaction.response.send_message("❌ Could not retrieve details for your watchlist.", ephemeral=True)
            return

        embed.description = "\n".join(description)

        if len(watchlist) > 5: # Show more if there are many items
            embed.set_footer(text=f"Showing 5 of {len(watchlist)} watchlist items. Use buttons to remove.")

        view = RemoveWatchlistItemView(interaction.user.id, watchlist[:5]) # Pass only the displayed items to the view

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        # ========== Event Handlers ========== 
    @bot.event
    async def on_raw_reaction_add(payload):
        """Track ANY reaction as a vote (one vote per user per message) and update user\'s watched list."""
        if payload.user_id == bot.user.id:
            return

        history = load_history()
        metadata = history.get("metadata", {})
        ratings = load_media_ratings()
        user_data = load_user_data() # Load user data

        # Find files from this message
        rated_files = [
            filename for filename, data in metadata.items()
            if data.get("message_id") == payload.message_id
        ]

        if not rated_files:
            return

        user_id_str = str(payload.user.id) # Convert to string for JSON keys

        # Ensure user entry exists in user_data
        if user_id_str not in user_data:
            user_data[user_id_str] = {"watched": [], "watchlist": []}

        # Check if the reaction is a rating emoji (1-5) for watched list
        rating_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
        if str(payload.emoji) in rating_emojis:
            for filename in rated_files:
                # Add to watched list if not already present
                if filename not in user_data[user_id_str]["watched"]:
                    user_data[user_id_str]["watched"].append(filename)
            save_user_data(user_data) # Save user data after updating watched list

        # Existing logic for reaction-based rating
        for filename in rated_files:
            if filename not in ratings:
                ratings[filename] = {"votes": 0, "voters": []}
            
            if user_id_str not in ratings[filename]["voters"]:
                ratings[filename]["votes"] += 1
                ratings[filename]["voters"].append(user_id_str)
        
        save_media_ratings(ratings)
