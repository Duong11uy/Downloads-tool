import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = BASE_DIR / "config"
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", BASE_DIR / "downloads"))
STATIC_DIR = BASE_DIR / "src" / "static"

# Ensure directories exist
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

# App Settings
APP_NAME = "Web Novel Downloader"
APP_VERSION = "1.0.0"
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))

# Scraper Settings
DEFAULT_CONCURRENCY = int(os.getenv("CONCURRENCY", 5))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 25))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", 5))

# Default User-Agent simulating modern browser
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Sites config path
SITES_CONFIG_PATH = CONFIG_DIR / "sites_config.json"
