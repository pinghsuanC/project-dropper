from db.database_connection import DatabaseConnection


def get_challenge(challenge: str) -> dict | None:
    """Get challenge row by challenge value."""
    row = None
    with DatabaseConnection() as conn:
        row = conn.execute(
            "SELECT * FROM auth_challenge WHERE challenge=?",
            (challenge,),
        ).fetchone()
    return dict(row) if row else None


def insert_challenge(challenge: str, device_id: str) -> None:
    """Store a new login challenge for a device."""
    with DatabaseConnection() as conn:
        conn.execute(
            "INSERT INTO auth_challenge (challenge, device_id) VALUES (?, ?)",
            (challenge, device_id),
        )


def clear_stale_challenge(device_id: str):
    """Delete all expired challenges of a device"""
    with DatabaseConnection() as conn:
        conn.execute(
            "DELETE FROM auth_challenge WHERE (device_id = ? OR expires_at < unixepoch());",
            (device_id,),
        )
