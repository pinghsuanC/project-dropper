import os
import sqlite3
from pathlib import Path

import dotenv

SERVER_DIR = Path(__file__).resolve().parent.parent  # db/ → server/
dotenv.load_dotenv(SERVER_DIR / ".env")
db_path = SERVER_DIR / os.getenv("DB_PATH")
if not db_path:
    raise RuntimeError("DB_PATH is not set (check server/.env)")
DB_PATH = SERVER_DIR / db_path
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


class DatabaseConnection:
    def __init__(self):
        self.db_path = DB_PATH

        self.schema_path = SCHEMA_PATH
        self.conn = None

    def __enter__(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
            self.conn.close()
            self.conn = None

    def init_db(self):
        with self as conn:
            conn.executescript(self.schema_path.read_text())
