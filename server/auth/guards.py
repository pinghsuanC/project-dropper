from fastapi import HTTPException

from auth import crypto
from enums import DeviceStatus
from repositories import devices as device_repo
from repositories import session as session_repo


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


def device_from_token(token: str | None) -> dict:
    """The active device for this session token, or None. For WebSockets, which can't use HTTP errors."""
    if not token:
        return None

    session = session_repo.get_device_active_session(crypto.hash_session_token(token))
    if session is None:  # unknown, expired, or ended
        return None

    device = device_repo.get_device_by_id(session["device_id"])
    if device is None or device["status"] != DeviceStatus.ACTIVE:
        return None

    return device


def require_device_from_token(token: str) -> dict:
    device = device_from_token(token)
    if device is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return device
