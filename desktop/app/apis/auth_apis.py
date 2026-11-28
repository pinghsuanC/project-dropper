import socket

from api_session import api
from app.auth.device_crypto import DeviceCrypto
from app.auth.device_fingerprint_processor import DeviceFingerprintProcessor
from app.helper.device_helper import DeviceHelper
from app.helper.utility import _check
from config import API_BASE_URL
from enums import Platform


def check_health():
    response = api.get(
        f"{API_BASE_URL}/health",
        timeout=5,
    )
    status = response.json()["status"]
    return status


def get_challenge():
    response = api.post(
        f"{API_BASE_URL}/auth/challenge",
        json={"device_id": DeviceHelper.load_device_id()},
        timeout=5,
    )
    data = _check(response)
    # print(data["message"])
    challenge = data["data"]["challenge"]
    return challenge


def verify_challenge(device_id: str, challenge: str, signature: str):
    device_fingerprint_processor = DeviceFingerprintProcessor()
    device_fingerprint = device_fingerprint_processor.get_device_fingerprint()

    response = api.post(
        f"{API_BASE_URL}/auth/verify-challenge",
        json={
            "device_id": device_id,
            "challenge": challenge,
            "signature": signature,
            "fingerprint": device_fingerprint,
        },
        timeout=5,
    )
    data = _check(response)
    # print(data["message"])
    token = data["data"]["token"]
    return token


def register_device():
    device_auth = DeviceCrypto()
    device_fingerprint_processor = DeviceFingerprintProcessor()

    public_key = device_auth.get_public_key()
    device_fingerprint = device_fingerprint_processor.get_device_fingerprint()
    name = socket.gethostname()
    response = api.post(
        f"{API_BASE_URL}/auth/register",
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
    DeviceHelper.save_device_id(device_id)
    return device_id


def get_current_device_session(token: str):
    response = api.get(
        f"{API_BASE_URL}/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        timeout=5,
    )
    data = _check(response)
    print(data["message"])
    return data["data"]
