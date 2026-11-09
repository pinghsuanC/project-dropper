import os

import dotenv
import requests

from exceptions import ApiError

dotenv.load_dotenv("../../.env")

_BASE_URL = os.getenv("API_BASE_URL")


def get_current_device_session(token: str):
    response = requests.get(
        f"{_BASE_URL}/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        timeout=5,
    )
    data = _check(response)
    print(data["message"])
    return data["data"]


def _check(response):
    if response.ok:
        return response.json()
    try:
        detail = response.json().get("detail", response.text)
    except ValueError:  # body wasn't JSON (e.g. a crash page)
        detail = response.text
    raise ApiError(response.status_code, detail)
