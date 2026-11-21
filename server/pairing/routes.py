from uuid import UUID

from fastapi import (
    APIRouter,
    HTTPException,
)
from fastapi.security import HTTPBearer

import repositories.device_pair as device_pair_repo
import repositories.devices as device_repo
import repositories.pairing_request as pairing_request_repo
from auth import crypto, guards
from auth.dependencies import CurrentSession
from enums import DeviceStatus, PairingRequestStatus
from exceptions import PairingRequestAlreadyUsedError
from schemas.devices import (
    GetPairingRequestResponse,
    PairingRequestClaim,
    PairingRequestClaimResponse,
    PairingRequestStartResponse,
)

router = APIRouter(prefix="/pairing-request", tags=["pairing-request"])
bearer = HTTPBearer()

# TODO: enable websocket
# @router.websocket("/ws")
# async def pairing_status_wb(websocket: WebSocket):
#    await websocket.accpet()
#    try:
#        auth = await websocket.receive_json()
#        device = guards.require_device_from_token(auth.get("token"))
#        if device is None:
#            await websocket.close(code=4401)  # custom "unauthorized" close code
#            return
#
#        while True:
#            status = await asyncio.to_thread(
#                pairing_request_repo.get_latest_status, device["id"]
#            )
#            if status["status"] != "pending":
#                await websocket.send_json(
#                    status
#                )  # accepted / expired, with paired_with
#                break
#            await asyncio.sleep(1)
#    except WebSocketDisconnect:
#        pass  # the desktop went away, nothing to do
#    finally:
#        await websocket.close()


@router.post("/start", response_model=PairingRequestStartResponse)
def pairing_request_start(deviceSession: CurrentSession):
    """Initiate a pairing request and send back the pairing token."""

    sender = guards.require_valid_session(deviceSession)

    pairing_token = crypto.generate_pairing_request_token()

    row = pairing_request_repo.create_pairing_request(
        sender_id=sender["id"],
        status=PairingRequestStatus.PENDING,
        token_hashed=crypto.hash_pairing_request_token(pairing_token),
    )

    return {
        "message": "Pairing started.",
        "data": {
            "pairing_request_id": row["id"],
            "pairing_token": pairing_token,
            "expires_at": row["expires_at"],
        },
    }


@router.post("/claim", response_model=PairingRequestClaimResponse)
def pairing_request_claim(deviceSession: CurrentSession, body: PairingRequestClaim):
    """Device that claimed the pairing token, finish the pairing process"""

    claimer = guards.require_valid_session(deviceSession)
    token_hashed = crypto.hash_pairing_request_token(body.pairing_token)

    pairing_request = pairing_request_repo.get_claimable_pairing_request(
        claimer_id=claimer["id"],
        token_hashed=token_hashed,
    )

    if not pairing_request:
        raise HTTPException(
            status_code=404, detail="Pairing code is invalid or expired."
        )

    initiator = device_repo.get_device_by_id(pairing_request["device_1_id"])

    if not initiator or initiator["status"] != DeviceStatus.ACTIVE:
        raise HTTPException(
            status_code=404, detail="Pairing code is invalid or expired."
        )

    # restrict to unique pairings (1-to-1)

    if device_pair_repo.get_paired_device(claimer["id"]) is not None:
        raise HTTPException(
            status_code=409, detail="Already paired with other device. Unpair first."
        )

    if device_pair_repo.get_paired_device(initiator["id"]) is not None:
        raise HTTPException(
            status_code=409, detail="That device is already paired. Unpair it first."
        )

    # checks done, update the pair request to be approved, and create a pairing row
    try:
        pairing_request_repo.accept_pairing_request(
            pairing_request["id"],
            claimer_id=claimer["id"],
            initiator_id=initiator["id"],
        )
    except PairingRequestAlreadyUsedError:
        raise HTTPException(
            status_code=404, detail="Pairing code is invalid or expired."
        ) from None

    return {
        "message": "Pairing successfully claimed.",
        "data": {
            "paired_with": {
                "device_id": initiator["id"],
                "name": initiator["name"],
                "platform": initiator["platform"],
            }
        },
    }


@router.get("/{pairing_request_id}/get", response_model=GetPairingRequestResponse)
def get_pairing_request(pairing_request_id: UUID, deviceSession: CurrentSession):
    """Get the device pairing, if the code has been claimed."""
    initiator = guards.require_valid_session(deviceSession)

    pairing_request = pairing_request_repo.get_pairing_request_for_initiator(
        initiator_id=initiator["id"], pairing_request_id=str(pairing_request_id)
    )

    if not pairing_request:
        raise HTTPException(status_code=404, detail="Pairing request not found.")

    pairing_device = device_repo.get_device_by_id(pairing_request["device_2_id"])

    return {
        "message": "Valid pairing request found.",
        "data": {
            "id": pairing_request["id"],
            "paired_with": pairing_device["name"] if pairing_device else None,
            "status": pairing_request["status"],
            "created_at": pairing_request["created_at"],
            "expires_at": pairing_request["expires_at"],
        },
    }
