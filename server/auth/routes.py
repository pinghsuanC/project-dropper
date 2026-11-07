from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from auth import crypto
from enums import Platform
from exceptions import DeviceAlreadyExists, InvalidPublicKey
from repositories.devices import insert_device

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    name: str
    public_key: str
    platform: Platform
    fingerprint: str


@router.get("/challenge")
def get_challenge():
    return {"message": "Challenge reached"}


@router.post("/register")
def register_device(body: RegisterRequest):
    try:
        key = crypto.load_ed25519_public_key(body.public_key)
    except InvalidPublicKey as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        fingerprint_hashed = crypto.hash_input(body.fingerprint)
        device_id = insert_device(body.name, key, fingerprint_hashed, body.platform)
        return {
            "message": "Successfully registered device.",
            "data": {"device_id": device_id},
        }
    except DeviceAlreadyExists as e:
        raise HTTPException(status_code=409, detail=str(e))
