import uuid

from db.database_connection import DatabaseConnection
from enums import DevicePairStatus, DeviceStatus


def get_paired_device(device_id: str) -> dict | None:
    """
    The active device that has an active pair with device_id, or None.
    A device pairs with one device for now; if more exist, the newest pair wins.
    A pair stores the smaller id in device_1_id, so the caller can be on either side.
    """
    with DatabaseConnection() as conn:
        row = conn.execute(
            """
            SELECT d.id, d.name, d.platform, p.created_at AS paired_at
            FROM device_pair p
            JOIN device_info d
              ON d.id = CASE WHEN p.device_1_id = :me
                             THEN p.device_2_id ELSE p.device_1_id END
            WHERE (p.device_1_id = :me OR p.device_2_id = :me)
              AND p.status = :pair_status
              AND d.status = :device_status
            ORDER BY p.created_at DESC, p.id DESC
            LIMIT 1
            """,
            {
                "me": device_id,
                "pair_status": DevicePairStatus.ACTIVE.value,
                "device_status": DeviceStatus.ACTIVE.value,
            },
        ).fetchone()
    return dict(row) if row else None


def create_device_pair(device_1_id: str, device_2_id: str, status: str) -> dict | None:
    device_pair_id = str(uuid.uuid7())
    first, second = sorted([device_1_id, device_2_id])
    with DatabaseConnection() as conn:
        row = conn.execute(
            "INSERT INTO device_pair (id, device_1_id, device_2_id, status) "
            "VALUES (?, ?, ?, ?) RETURNING *",
            (
                device_pair_id,
                first,
                second,
                status,
            ),
        ).fetchone()

        return dict(row) if row else None
