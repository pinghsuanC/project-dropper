import uuid

from db.database_connection import DatabaseConnection
from enums import SessionStatus


def insert_session(token_hashed, device_id) -> None:
    """Store a working session for specific device."""
    session_id = str(uuid.uuid7())
    with DatabaseConnection() as conn:
        conn.execute(
            "INSERT INTO session (id, token_hashed, device_id, status) VALUES (?, ?, ?, ?)",
            (
                session_id,
                token_hashed,
                device_id,
                SessionStatus.ACTIVE,
            ),
        )


def get_device_active_session(token_hashed) -> dict | None:
    """Get active session row by device_id, hashed token."""
    row = None
    with DatabaseConnection() as conn:
        row = conn.execute(
            "SELECT * FROM session WHERE (token_hashed=? AND status=?)",
            (
                token_hashed,
                SessionStatus.ACTIVE,
            ),
        ).fetchone()

    return dict(row) if row else None


def revoke_stale_sessions() -> None:
    with DatabaseConnection() as conn:
        conn.execute(
            "UPDATE session SET status=? WHERE (status=? AND expires_at < unixepoch())",
            (SessionStatus.REVOKED, SessionStatus.ACTIVE),
        )
