import os
import socket

import dotenv
import requests
from app.auth.device_auth import DeviceAuth
from app.auth.device_fingerprint_processor import DeviceFingerprintProcessor
from app.helper.device_id_helper import DeviceIdHelper
from enums import Platform
from exceptions import ApiError

dotenv.load_dotenv("../../.env")

_BASE_URL = os.getenv("API_BASE_URL")


def get_challenge():
    response = requests.post(
        f"{_BASE_URL}/auth/challenge",
        json={"device_id": DeviceIdHelper.load_device_id()},
        timeout=5,
    )
    data = _check(response)
    print(data["message"])
    challenge = data["data"]["challenge"]
    return challenge


def verify_challenge(device_id: str, challenge: str, signature: str):
    response = requests.post(
        f"{_BASE_URL}/auth/verify_challenge",
        json={
            "device_id": device_id,
            "challenge": challenge,
            "signature": signature,
        },
        timeout=5,
    )
    data = _check(response)
    print(data["message"])
    token = data["data"]["token"]
    print(token)


def register_device():
    device_auth = DeviceAuth()
    device_fingerprint_processor = DeviceFingerprintProcessor()

    public_key = device_auth.get_public_key()
    device_fingerprint = device_fingerprint_processor.get_device_fingerprint()
    name = socket.gethostname()
    response = requests.post(
        f"{_BASE_URL}/auth/register",
        json={
            "name": name,
            "platform": Platform.DESKTOP,
            "public_key": public_key,
            "fingerprint": device_fingerprint,
        },
        timeout=5,
    )
    data = _check(response)

    device_id = data["data"]["device_id"]
    print(data["message"])
    DeviceIdHelper.save_device_id(device_id)
    return device_id


def _check(response):
    if response.ok:
        return response.json()
    try:
        detail = response.json().get("detail", response.text)
    except ValueError:  # body wasn't JSON (e.g. a crash page)
        detail = response.text
    raise ApiError(response.status_code, detail)
