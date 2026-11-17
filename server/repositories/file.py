import uuid

from db.database_connection import DatabaseConnection
from enums import FileStatus


def insert_multiple_files(
    sender_id: str, receiver_id: str, files: list[dict]
) -> list[dict]:
    """Insert several files in one transaction. Returns their ids and keys, in order."""
    rows = []
    for f in files:
        rows.append(
            {
                "id": f["id"],
                "object_key": f["object_key"],
                "file_name": f["file_name"],
                "size": f["size"],
                "content_type": f["content_type"],
                "checksum": f["checksum"],
                "status": f["status"],
            }
        )

    with DatabaseConnection() as conn:
        conn.executemany(
            "INSERT INTO file (id, sender_id, receiver_id, file_name, object_key, size, content_type, checksum, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    r["id"],
                    sender_id,
                    receiver_id,
                    r["file_name"],
                    r["object_key"],
                    r["size"],
                    r["content_type"],
                    r["checksum"],
                    r["status"],
                )
                for r in rows
            ],
        )

    return [
        {"file_id": r["id"], "object_key": r["object_key"], "file_name": r["file_name"]}
        for r in rows
    ]


def insert_file(
    sender_id: str,
    receiver_id: str,
    file_name: str,
    size: int,
    content_type: str,
    checksum: str,
    status: str,
) -> tuple[str, str]:
    """Insert a new file row. Returns (file_id, object_key)."""
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
                status,
            ),
        )

    return file_id, object_key


def update_multiple_files_to_same_status(file_ids: list[str], status: str) -> int:
    """Set the same status on several files. Returns how many rows changed."""
    if not file_ids:
        return 0

    placeholders = ", ".join("?" for _ in file_ids)
    with DatabaseConnection() as conn:
        cursor = conn.execute(
            f"UPDATE file SET status = ? WHERE id IN ({placeholders})",
            (status, *file_ids),
        )
        return cursor.rowcount


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
    ids: list[str], original_status: str, destination_status: str
) -> list[dict]:
    if not ids:
        return []
    """Update all the files in the list to Downloaded."""
    id_str = ", ".join("?" for _ in ids)
    with DatabaseConnection() as conn:
        rows = conn.execute(
            f"UPDATE file SET status=? "
            f"WHERE id IN ({id_str}) AND status=? "
            f"RETURNING id, object_key",
            (
                destination_status,
                *ids,
                original_status,
            ),
        ).fetchall()
    return [dict(r) for r in rows]


def update_files_status_for_receiver(
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


def get_pending_files_for_sender(sender_id: str, ids: list[str]) -> list[dict]:
    if not ids:
        return []
    """Get all the pending files in the list for sender."""
    id_str = ", ".join("?" for _ in ids)
    with DatabaseConnection() as conn:
        rows = conn.execute(
            f"SELECT * from file WHERE id in ({id_str}) AND sender_id=? AND status=?",
            (
                *ids,
                sender_id,
                FileStatus.PENDING,
            ),
        ).fetchall()
    return [dict(r) for r in rows]


def get_uploaded_files_for_receiver(receiver_id: str, ids: list[str]) -> list[dict]:
    if not ids:
        return []
    """Get all the files in the list to Downloaded."""
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


def get_sent_files_waiting(sender_id: str) -> list[dict]:
    """Files sent by sender_id the receiver hasn't downloaded yet (pending or uploaded), newest first."""
    with DatabaseConnection() as conn:
        rows = conn.execute(
            "SELECT f.id, f.file_name, f.size, f.status, f.created_at, "
            "d.name AS receiver_name "
            "FROM file f JOIN device_info d ON d.id = f.receiver_id "
            "WHERE f.sender_id=? AND f.status IN (?, ?) "
            "ORDER BY f.created_at DESC, f.id DESC",
            (
                sender_id,
                FileStatus.PENDING,
                FileStatus.UPLOADED,
            ),
        ).fetchall()
    return [dict(r) for r in rows]
