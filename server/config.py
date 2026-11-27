import os
from pathlib import Path

import dotenv

# Load .env once, for the whole server. Variables already set in the process
# environment win (no override), so tests / Docker can point at their own values.
SERVER_DIR = Path(__file__).resolve().parent
dotenv.load_dotenv(SERVER_DIR / ".env")

# App
ENABLE_DOCS = os.getenv("ENABLE_DOCS", "false").lower() == "true"

# Database (relative paths resolve against server/; absolute paths are kept as-is)
DB_PATH = SERVER_DIR / os.getenv("DB_PATH", "data/database.db")
# Used only by tests: they patch db.database_connection.DB_PATH to this.
# server/data/ and *.db are git-ignored.
TEST_DB_PATH = SERVER_DIR / "data" / "test.db"

# Auth
HMAC_SECRET = os.environ[
    "HMAC_SECRET"
]  # required: crashes at startup with a clear error if missing

# Cloudflare R2 (optional at import so tests/CI without R2 credentials still load)
R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")
R2_BUCKET = os.getenv("R2_BUCKET")
R2_S3_API = os.getenv("R2_S3_API")
R2_API_TOKEN = os.getenv("R2_API_TOKEN")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCRESS_KEY = os.getenv("R2_SECRET_ACCRESS_KEY")
