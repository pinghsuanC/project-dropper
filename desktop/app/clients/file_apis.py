import hashlib
import os

import dotenv
import requests

from app.helper.device_helper import DeviceHelper
from app.helper.file_helper import FileHelper
from exceptions import ApiError

dotenv.load_dotenv("../../.env")

_BASE_URL = os.getenv("API_BASE_URL")


def upload_file(token: str, path: str):
    """Only used for development purpose. Desktop doesn't need a upload. This should happen inside the mobile app
    For now sending it to myself.
    """

    receiver_id = DeviceHelper.load_device_id()
    info = FileHelper.describe_file(path)  # name, size, content_type, checksum
    headers = {"Authorization": f"Bearer {token}"}

    # ask for presigned upload url
    response = requests.post(
        f"{_BASE_URL}/files/prepare-upload",
        json={**info, "receiver_id": receiver_id},
        headers=headers,
        timeout=5,
    )
    response = _check(response)
    data = response["data"]
    print(response["message"])

    # upload the bytes to R2
    with open(path, "rb") as f:
        requests.put(data["upload_url"], data=f, timeout=60).raise_for_status()

    # tell server it's done
    response = requests.post(
        f"{_BASE_URL}/files/finish-upload",
        json={"file_id": data["file_id"]},
        headers=headers,
        timeout=5,
    )
    response = _check(response)
    data = response["data"]
    print(response["message"])

    return data["file_id"]


def download_files(token: str):
    """Only used for development purpose. Desktop doesn't need a upload. This should happen inside the mobile app
    For now sending it to myself.
    """
    headers = {"Authorization": f"Bearer {token}"}

    # ask for presigned upload url
    response = requests.get(
        f"{_BASE_URL}/files/check-pending-download",
        headers=headers,
        timeout=5,
    )
    response = _check(response)
    data = response["data"]
    print(response["message"])

    if not data["files"]:
        return

    # get pre-signed download urls
    response = requests.get(
        f"{_BASE_URL}/files/prepare-download",
        headers=headers,
        timeout=5,
    )
    response = _check(response)
    data = response["data"]
    print(response["message"])

    if not data["file_objects"]:
        print("There's no file objects.")
        return

    # download the files to designated folder
    destination_path = FileHelper.get_safe_download_directory()

    finished_ids = []

    for file_obj in data["file_objects"]:
        file_path = FileHelper.get_safe_file_path(
            file_obj["file_name"], destination_path
        )
        temp_path = file_path.with_name(file_path.name + ".part")
        sha256 = hashlib.sha256()
        with requests.get(file_obj["download_url"], stream=True, timeout=60) as r:
            r.raise_for_status()

            with open(temp_path, "wb") as out:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    out.write(chunk)
                    sha256.update(chunk)

            if sha256.hexdigest() != file_obj["checksum"]:
                temp_path.unlink(missing_ok=True)  # throw away the bad copy
                print(
                    f"Checksum mismatch for {file_obj['file_name']}, will retry next time"
                )
                continue

            print(
                f"Successfully downloaded {file_obj['file_name']} {'' if file_obj['file_name'] == file_path.name else 'renamed to ' + file_path.name}"
            )
            temp_path.replace(file_path)
            finished_ids.append(file_obj["file_id"])

    if not finished_ids:
        print("Nothing finished")
        return

    # tell server it's done
    response = requests.post(
        f"{_BASE_URL}/files/finish-download",
        json={"file_ids": finished_ids},
        headers=headers,
        timeout=5,
    )
    response = _check(response)
    data = response["data"]
    print(response["message"])

    return


def _check(response):
    if response.ok:
        return response.json()
    try:
        detail = response.json().get("detail", response.text)
    except ValueError:  # body wasn't JSON (e.g. a crash page)
        detail = response.text
    raise ApiError(response.status_code, detail)
