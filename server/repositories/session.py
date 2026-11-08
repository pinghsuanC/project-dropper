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
