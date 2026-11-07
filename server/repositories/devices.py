import sqlite3
import uuid

from db.database_connection import DatabaseConnection
from enums import DeviceStatus
from exceptions import DeviceAlreadyExists


def insert_device(name, public_key, fingerprint, platform) -> str:
    """
    Inserts a new device into the devices table.
    public_key hashed
    """

    try:
        with DatabaseConnection() as conn:
            device_id = str(uuid.uuid7())
            conn.execute(
                "INSERT INTO device_info (id, name, public_key, fingerprint, platform, status) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    device_id,
                    name,
                    public_key,
                    fingerprint,
                    platform,
                    DeviceStatus.ACTIVE.value,
                ),
            )
    except sqlite3.IntegrityError as e:
        if "UNIQUE" in str(e):
            raise DeviceAlreadyExists() from e
        raise  # some other constraint: let it go up unchanged
    return device_id


def get_device(device_id: str) -> dict | None:
    """Get device row by device id."""
    row = None
    with DatabaseConnection() as conn:
        row = conn.execute(
            "SELECT * FROM device_info WHERE id=?",
            (device_id,),
        ).fetchone()
    return dict(row) if row else None


def get_device_by_public_key(public_key) -> dict | None:
    """
    Get device row by public key
    """
    row = None
    with DatabaseConnection() as conn:
        row = conn.execute(
            "SELECT * FROM device_info WHERE public_key=?",
            (public_key,),
        ).fetchone()
    return dict(row) if row else None
