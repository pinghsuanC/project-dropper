import uuid

from db.database_connection import DatabaseConnection
from enums import DevicePairStatus, PairingRequestStatus
from exceptions import PairingRequestAlreadyUsedError


def clear_stale_pairings(sender_id: str):
    """Remove this device's pending requests and all expired ones."""
    with DatabaseConnection() as conn:
        conn.execute(
            "DELETE FROM pairing_request WHERE (device_1_id = ? AND status = 'pending') OR expires_at < unixepoch();",
            (sender_id,),
        )


def create_pairing_request(sender_id: str, status: str, token_hashed: str) -> dict:
    """Create a pending pairing request; returns the row."""

    clear_stale_pairings(sender_id)

    pairing_request_id = str(uuid.uuid7())
    with DatabaseConnection() as conn:
        row = conn.execute(
            "INSERT INTO pairing_request (id, device_1_id, status, token_hashed) "
            "VALUES (?, ?, ?, ?) RETURNING *",
            (
                pairing_request_id,
                sender_id,
                status,
                token_hashed,
            ),
        ).fetchone()

        return dict(row)


def get_claimable_pairing_request(claimer_id: str, token_hashed: str) -> dict | None:
    """Get the pairing request by token hashed"""
    with DatabaseConnection() as conn:
        row = conn.execute(
            "SELECT * FROM pairing_request WHERE device_1_id !=? AND token_hashed = ? AND status=? AND expires_at > unixepoch() LIMIT 1",
            (claimer_id, token_hashed, PairingRequestStatus.PENDING),
        ).fetchone()

        return dict(row) if row else None


def get_pairing_request_for_initiator(
    initiator_id: str, pairing_request_id: str
) -> dict | None:
    """Get the pairing request by request id"""
    with DatabaseConnection() as conn:
        row = conn.execute(
            "SELECT * FROM pairing_request WHERE id=? AND device_1_id=?",
            (
                pairing_request_id,
                initiator_id,
            ),
        ).fetchone()

        return dict(row) if row else None


def accept_pairing_request(request_id: str, claimer_id: str, initiator_id: str) -> dict:
    """Accept the request and create the pair in one transaction. Returns the new pair."""
    first, second = sorted([initiator_id, claimer_id])

    with DatabaseConnection() as conn:
        updated = conn.execute(
            "UPDATE pairing_request SET status = ?, device_2_id = ? "
            "WHERE id = ? AND status = ?",
            (
                PairingRequestStatus.ACCEPTED,
                claimer_id,
                request_id,
                PairingRequestStatus.PENDING,
            ),
        )
        if updated.rowcount == 0:
            raise PairingRequestAlreadyUsedError()  # someone claimed it a moment earlier

        pair = conn.execute(
            "INSERT INTO device_pair (id, device_1_id, device_2_id, status) "
            "VALUES (?, ?, ?, ?) RETURNING *",
            (str(uuid.uuid7()), first, second, DevicePairStatus.ACTIVE),
        ).fetchone()

    return dict(pair)
