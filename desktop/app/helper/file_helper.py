import hashlib
import mimetypes
import os
from pathlib import Path

import dotenv

dotenv.load_dotenv()
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR")


class FileHelper:
    def __init__(self):
        pass

    @staticmethod
    def describe_file(path: str) -> dict:
        """Everything the server needs to know about a file, before uploading it."""

        p = Path(path)
        with open(p, "rb") as f:
            checksum = hashlib.file_digest(f, "sha256").hexdigest()
        content_type, _ = mimetypes.guess_type(p.name)

        return {
            "file_name": p.name,
            "size": p.stat().st_size,
            "content_type": content_type or "application/octet-stream",
            "checksum": checksum,
        }

    @staticmethod
    def get_safe_download_directory() -> Path:
        dir = (
            Path(DOWNLOAD_DIR or Path.home() / "Downloads" / "file-dropper")
            .expanduser()
            .resolve()
        )

        # make sure there is a folder
        if dir.exists() and not dir.is_dir():
            raise RuntimeError(
                f"DOWNLOAD_DIR points to a file, not a folder: {DOWNLOAD_DIR}"
            )

        dir.mkdir(parents=True, exist_ok=True)

        return dir

    @staticmethod
    def get_safe_file_path(name: str, directory: Path) -> Path:

        # make sure there is a folder
        candidate = directory / name
        base = Path(Path(name).name)
        if (candidate).exists():
            counter = 1
            while candidate.exists():
                candidate = directory / f"{base.stem}-{counter}{base.suffix}"
                counter += 1

        return candidate
