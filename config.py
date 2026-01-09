import os
from pathlib import Path


def load_secrets_from_file():
    secrets = {}
    try:
        with open('secrets.txt', 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    secrets[key.strip()] = value.strip()
    except FileNotFoundError:
        raise FileNotFoundError("secrets.txt file not found. Please create it based on the template.")
    return secrets


secrets = load_secrets_from_file()
DISCORD_TOKEN = secrets.get('DISCORD_TOKEN')
TMDB_API_KEY = secrets.get('TMDB_API_KEY')

if not DISCORD_TOKEN or DISCORD_TOKEN == "YOUR_REAL_DISCORD_TOKEN_WOULD_GO_HERE":
    raise ValueError("DISCORD_TOKEN not properly set in secrets.txt")
if not TMDB_API_KEY or TMDB_API_KEY == "YOUR_REAL_TMDB_API_KEY_WOULD_GO_HERE":
    raise ValueError("TMDB_API_KEY not properly set in secrets.txt")

MEDIA_CHANNEL_ID = int(os.getenv("MEDIA_CHANNEL_ID", 439072343285956618))
MOVIES_CHANNEL_ID = int(os.getenv("MOVIES_CHANNEL_ID", 370237203462488064))

IMAGES_PER_BATCH = int(os.getenv("IMAGES_PER_BATCH", 3))
VIDEOS_PER_BATCH = int(os.getenv("VIDEOS_PER_BATCH", 7))
ARCHIVE_RETENTION_DAYS = int(os.getenv("ARCHIVE_RETENTION_DAYS", 3))
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", 25))
SELECTION_ORDER = os.getenv("SELECTION_ORDER", "random")

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}

MEDIA_FOLDER = Path(os.getenv("MEDIA_FOLDER", "media"))
ARCHIVE_FOLDER = Path(os.getenv("ARCHIVE_FOLDER", "archive"))
HISTORY_FILE = Path(os.getenv("HISTORY_FILE", "upload_history.json"))

MEDIA_FOLDER.mkdir(exist_ok=True)
ARCHIVE_FOLDER.mkdir(exist_ok=True)

if not MEDIA_FOLDER.exists():
    raise FileNotFoundError(f"Media folder does not exist: {MEDIA_FOLDER}")
if not ARCHIVE_FOLDER.exists():
    raise FileNotFoundError(f"Archive folder does not exist: {ARCHIVE_FOLDER}")
