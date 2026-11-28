import os
from pathlib import Path

import dotenv

# Load .env once, for the whole desktop client. Variables already set in the process
# environment win (no override), so tests / CI can point at their own values.
DESKTOP_DIR = Path(__file__).resolve().parent
dotenv.load_dotenv(DESKTOP_DIR / ".env")

# App
APP_ENV = os.getenv("APP_ENV")  # "local" | "dev" | "prod" (see enums.AppEnv)

# Server
API_BASE_URL = os.environ[
    "API_BASE_URL"
]  # required: crashes at startup with a clear error if missing

# Downloads (optional: falls back to ~/Downloads/file-dropper, see FileHelper)
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR")

# Cloudflare Access service tokens (optional at import so local dev without
# Cloudflare still loads).
# Desktop's own token: sent as CF-Access-* headers on the desktop's requests.
CLOUDFLARE_SERVICE_TOKEN_CLIENT_ID = os.getenv("CLOUDFLARE_SERVICE_TOKEN_CLIENT_ID")
CLOUDFLARE_SERVICE_TOKEN_CLIENT_SECRET = os.getenv(
    "CLOUDFLARE_SERVICE_TOKEN_CLIENT_SECRET"
)
# Mobile's token: never used by the desktop itself, only handed to the phone in the
# config QR.
CLOUDFLARE_SERVICE_TOKEN_CLIENT_ID_MOBILE = os.getenv(
    "CLOUDFLARE_SERVICE_TOKEN_CLIENT_ID_MOBILE"
)
CLOUDFLARE_SERVICE_TOKEN_CLIENT_SECRET_MOBILE = os.getenv(
    "CLOUDFLARE_SERVICE_TOKEN_CLIENT_SECRET_MOBILE"
)
