import uuid

from db.database_connection import DatabaseConnection
from enums import FileStatus


def insert_file(
    sender_id: str,
    receiver_id: str,
    file_name: str,
    size: int,
    content_type: str,
    checksum: str,
) -> tuple[str, str]:
    """Insert a new pending file row. Returns (file_id, object_key)."""
    file_id = str(uuid.uuid7())
    object_key = f"{receiver_id}/{file_id}"

    with DatabaseConnection() as conn:
        conn.execute(
            "INSERT INTO file (id, sender_id, receiver_id, file_name, object_key, size, content_type, checksum, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                file_id,
                sender_id,
                receiver_id,
                file_name,
                object_key,
                size,
                content_type,
                checksum,
                FileStatus.PENDING,
            ),
        )

    return file_id, object_key


def update_file_status(id: str, status: str) -> tuple[str, str]:
    """Update the file status to target"""

    with DatabaseConnection() as conn:
        conn.execute(
            "UPDATE file SET status=? WHERE id=?",
            (
                status,
                id,
            ),
        )


def get_uploaded_files(receiver_id: str) -> list[dict] | None:

    rows = None
    with DatabaseConnection() as conn:
        rows = conn.execute(
            "SELECT * FROM file WHERE receiver_id=? AND status=? ORDER BY created_at LIMIT 50",
            (
                receiver_id,
                FileStatus.UPLOADED,
            ),
        ).fetchall()

    return [dict(row) for row in rows] if rows else None


def update_files_status(
    receiver_id: str, ids: list[str], original_status: str, destination_status: str
) -> list[dict]:
    if not ids:
        return []
    """Update all the files in the list to Downloaded."""
    id_str = ", ".join("?" for _ in ids)
    with DatabaseConnection() as conn:
        rows = conn.execute(
            f"UPDATE file SET status=? "
            f"WHERE id IN ({id_str}) AND receiver_id=? AND status=? "
            f"RETURNING id, object_key",
            (
                destination_status,
                *ids,
                receiver_id,
                original_status,
            ),
        ).fetchall()
    return [dict(r) for r in rows]


def get_files_by_ids(receiver_id: str, ids: list[str]) -> list[dict]:
    if not ids:
        return []
    """Update all the files in the list to Downloaded."""
    id_str = ", ".join("?" for _ in ids)
    with DatabaseConnection() as conn:
        rows = conn.execute(
            f"SELECT * from file WHERE id in ({id_str}) AND receiver_id=? AND status=?",
            (
                *ids,
                receiver_id,
                FileStatus.UPLOADED,
            ),
        ).fetchall()
    return [dict(r) for r in rows]


def get_file_by_id(id: str) -> str | None:
    """Get file row by device id."""
    row = None
    with DatabaseConnection() as conn:
        row = conn.execute(
            "SELECT * FROM file WHERE id=?",
            (id,),
        ).fetchone()
    return dict(row) if row else None
