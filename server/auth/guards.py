from fastapi import HTTPException

from enums import DeviceStatus
from repositories import devices as device_repo


def require_valid_session(session: dict | None) -> dict:
    """Return the session's device, or raise 401/403. Use at the start of protected routes."""
    if session is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return require_valid_device(session["device_id"])


def require_valid_device(device_id: dict | None) -> dict:
    """Return the id's device, or raise 401/403. Use when need to check device id specifically."""

    device = device_repo.get_device_by_id(device_id)
    if device is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if device["status"] != DeviceStatus.ACTIVE:
        raise HTTPException(status_code=403, detail="Device revoked")

    return device
