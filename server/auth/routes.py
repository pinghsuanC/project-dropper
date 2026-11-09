import time

from fastapi import (
    APIRouter,
    HTTPException,
)
from fastapi.security import HTTPBearer

import repositories.auth_challenge as challenge_repo
import repositories.devices as device_repo
import repositories.session as session_repo
from auth import crypto
from auth.dependencies import CurrentSession
from enums import DeviceStatus
from exceptions import DeviceAlreadyExists, InvalidPublicKey
from schemas.auth import (
    ChallengeRequest,
    ChallengeVerifyRequest,
    MeResponse,
    RegisterRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])


bearer = HTTPBearer()


@router.get("/me", response_model=MeResponse)
def me(deviceSession: CurrentSession):

    if deviceSession is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session",
            headers={"WWW-Authenticate": "Bearer"},
        )

    device_id = deviceSession["device_id"]
    device = device_repo.get_device(device_id)

    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    if device["status"] != DeviceStatus.ACTIVE:
        raise HTTPException(status_code=403, detail="Device revoked")

    return {
        "message": "Your session is confirmed active.",
        "data": {
            "isActive": True,
            "device_id": device_id,
            "name": device["name"],
            "platform": device["platform"],
        },
    }


@router.post("/verify-challenge")
def verify_challeng(body: ChallengeVerifyRequest):
    unauthorized = HTTPException(
        status_code=401, detail="Invalid challenge or signature"
    )
    device_id = body.device_id
    challenge = body.challenge
    signature = body.signature

    device = device_repo.get_device(device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    if device["status"] != DeviceStatus.ACTIVE:
        raise HTTPException(status_code=403, detail="Device revoked")

    challenge_row = challenge_repo.get_challenge(challenge)
    challenge_repo.clear_stale_challenge(device_id)
    if challenge_row is None:
        raise unauthorized
    if challenge_row["device_id"] != body.device_id:
        raise unauthorized
    if challenge_row["expires_at"] < time.time():
        raise unauthorized

    if not crypto.verify_signature(device["public_key"], challenge, signature):
        raise unauthorized

    # generate session and send token to desktop
    session_token = crypto.generate_session_token()
    session_repo.insert_session(crypto.hash_session_token(session_token), device_id)

    return {
        "message": ":D Congratulations. Challenge succeeded.",
        "data": {"token": session_token},
    }


@router.post("/challenge")
def invoke_challenge_request(body: ChallengeRequest):
    device_id = body.device_id

    device = device_repo.get_device(device_id)

    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    if device["status"] != DeviceStatus.ACTIVE:
        raise HTTPException(status_code=403, detail="Device revoked")

    challenge = crypto.geenrate_challenge()
    challenge_repo.clear_stale_challenge(device_id)
    challenge_repo.insert_challenge(challenge, device_id)
    return {
        "message": "Challenge generated.",
        "data": {"challenge": challenge},
    }


@router.post("/register")
def register_device(body: RegisterRequest):
    try:
        key = crypto.load_ed25519_public_key(body.public_key)
    except InvalidPublicKey as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        fingerprint_hashed = crypto.hash_input(body.fingerprint)
        device_id = device_repo.insert_device(
            body.name, key, fingerprint_hashed, body.platform
        )
        return {
            "message": "Successfully registered device.",
            "data": {"device_id": device_id},
        }
    except DeviceAlreadyExists as e:
        raise HTTPException(status_code=409, detail=str(e))
