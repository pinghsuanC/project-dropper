import hashlib
import mimetypes
import os
import re
from pathlib import Path

import dotenv

dotenv.load_dotenv()
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR")
_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


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
        # TODO: add ai agent to rename the files to a certain format
        base = Path(Path(name).name)  # strip any folder parts
        ext = base.suffix.lower().lstrip(".")  # ".PNG" → "png"
        folder = directory / FileHelper._safe_folder_name(ext or "other")
        folder.mkdir(parents=True, exist_ok=True)

        candidate = folder / base.name
        counter = 1

        if (candidate).exists():
            counter = 1
            while candidate.exists():
                candidate = directory / folder / f"{base.stem}-{counter}{base.suffix}"
                counter += 1

        return candidate

    @staticmethod
    def _safe_folder_name(name: str, replacement: str = "_") -> str:
        """Make a string safe to use as a file or folder name on Windows, macOS, and Linux."""
        name = re.sub(
            r'[<>:"/\\|?*\x00-\x1f]', replacement, name
        )  # forbidden + control characters
        name = name.strip().rstrip(".")  # no trailing dots or spaces
        if name.split(".")[0].upper() in _RESERVED:  # CON, CON.txt, ...
            name = f"{replacement}{name}"
        if name in {"", ".", ".."}:  # nothing usable left
            name = "unnamed"
        return name[:200]
