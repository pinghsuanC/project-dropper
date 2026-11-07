import os
import socket

import dotenv
import requests

from app.auth.device_auth import DeviceAuth
from app.auth.device_fingerprint_processor import DeviceFingerprintProcessor
from app.helper.device_helper import DeviceHelper
from enums import Platform
from exceptions import ApiError

dotenv.load_dotenv("../../.env")

_BASE_URL = os.getenv("API_BASE_URL")

DEVICE_TYPE = "desktop"


def test():
    response = requests.get(f"{_BASE_URL}/")
    print(response.status_code, response.json())


def test2():

    response = requests.post(
        f"{_BASE_URL}/",
        json={"name": "widget", "price": 9.99},
        timeout=5,
    )
    print(response.status_code, response.json())


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
    DeviceHelper.save_device_id(device_id)
    return device_id


def _check(response):
    if response.ok:
        return response.json()
    try:
        detail = response.json().get("detail", response.text)
    except ValueError:  # body wasn't JSON (e.g. a crash page)
        detail = response.text
    raise ApiError(response.status_code, detail)
