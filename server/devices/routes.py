from fastapi import APIRouter

import repositories.device_pair as pair_repo
from auth import guards
from auth.dependencies import CurrentSession
from schemas.devices import PairedDeviceResponse

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("/paired", response_model=PairedDeviceResponse)
def get_paired_device(deviceSession: CurrentSession):
    """The device the caller is paired with, or null if not paired."""

    device = guards.require_valid_session(deviceSession)
    paired = pair_repo.get_paired_device(device["id"])

    if paired is None:
        return {"message": "Not paired.", "data": {"device": None}}

    return {
        "message": "Paired device found.",
        "data": {
            "device": {
                "device_id": paired["id"],
                "name": paired["name"],
                "platform": paired["platform"],
                "paired_at": paired["paired_at"],
            }
        },
    }
