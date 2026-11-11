"""
File transfer tests: prepare-upload -> finish-upload -> check/prepare-download -> finish-download.

Run from inside server/:
    python -m unittest discover -s tests -v

Needs:  pip install httpx   (FastAPI's TestClient uses it)

Object storage (R2) is mocked: no network calls are made.
"""

import base64
import os
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

# --- Point the app at a throwaway database BEFORE importing it ---------------
# db/database_connection.py reads DB_PATH when it is imported. An absolute
# path wins over SERVER_DIR / DB_PATH, and load_dotenv() doesn't override it.
_TMP_DIR = tempfile.TemporaryDirectory()
_TEST_DB = Path(_TMP_DIR.name) / "test_file.db"
os.environ["DB_PATH"] = str(_TEST_DB)
os.environ.setdefault("HMAC_SECRET", "test-secret-not-for-production")

from fastapi.testclient import TestClient

import db.database_connection as db_conn
from db.database_connection import DatabaseConnection
from enums import DeviceStatus, FileStatus
from server import app

REGISTER = "/auth/register"
CHALLENGE = "/auth/challenge"
VERIFY = "/auth/verify-challenge"

PREPARE_UPLOAD = "/files/prepare-upload"
FINISH_UPLOAD = "/files/finish-upload"
CHECK_PENDING = "/files/check-pending-download"
PREPARE_DOWNLOAD = "/files/prepare-download"
FINISH_DOWNLOAD = "/files/finish-download"

FAKE_PUT_URL = "https://r2.example/put"
FAKE_GET_URL = "https://r2.example/get"


# --- Helpers ------------------------------------------------------------------
def public_pem(key: Ed25519PrivateKey) -> str:
    return (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )


def sign(key: Ed25519PrivateKey, challenge: str) -> str:
    return base64.b64encode(key.sign(challenge.encode())).decode()


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def db_file(file_id: str) -> dict | None:
    with DatabaseConnection() as conn:
        row = conn.execute("SELECT * FROM file WHERE id=?", (file_id,)).fetchone()
    return dict(row) if row else None


def set_device_status(device_id: str, status: str) -> None:
    with DatabaseConnection() as conn:
        conn.execute("UPDATE device_info SET status=? WHERE id=?", (status, device_id))


class FileFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # If another test module imported the db module first, DB_PATH points at
        # its database; force ours for the duration of this class.
        cls._orig_db_path = db_conn.DB_PATH
        db_conn.DB_PATH = _TEST_DB

        cls._client_cm = TestClient(app)
        cls.client = cls._client_cm.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._client_cm.__exit__(None, None, None)
        db_conn.DB_PATH = cls._orig_db_path
        _TMP_DIR.cleanup()

    def setUp(self):
        # Replace object storage with a mock for every test
        patcher = patch("files.routes.ObjectStorage")
        self.storage_cls = patcher.start()
        self.addCleanup(patcher.stop)
        self.storage = self.storage_cls.return_value
        self.storage.get_put_presigned_url.return_value = FAKE_PUT_URL
        self.storage.get_get_presigned_url.return_value = FAKE_GET_URL
        self.storage.delete_objects.return_value = set()

        # Fresh sender and receiver per test, so tests don't affect each other
        self.sender_id, self.sender_token = self.login_new_device()
        self.receiver_id, self.receiver_token = self.login_new_device()

    # --- Auth helpers -------------------------------------------------------------
    def login_new_device(self) -> tuple[str, str]:
        """Register a device and run challenge/verify. Returns (device_id, token)."""
        key = Ed25519PrivateKey.generate()
        response = self.client.post(
            REGISTER,
            json={
                "name": "test-device",
                "platform": "desktop",
                "public_key": public_pem(key),
                "fingerprint": uuid.uuid4().hex,
            },
        )
        self.assertIn(response.status_code, (200, 201), response.text)
        device_id = response.json()["data"]["device_id"]

        response = self.client.post(CHALLENGE, json={"device_id": device_id})
        self.assertEqual(response.status_code, 200, response.text)
        challenge = response.json()["data"]["challenge"]

        response = self.client.post(
            VERIFY,
            json={
                "device_id": device_id,
                "challenge": challenge,
                "signature": sign(key, challenge),
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        return device_id, response.json()["data"]["token"]

    # --- File helpers -------------------------------------------------------------
    def prepare_upload(self, token=None, receiver_id=None, size=123, **overrides):
        body = {
            "file_name": "hello.txt",
            "size": size,
            "content_type": "text/plain",
            "checksum": "abc123",
            "receiver_id": receiver_id or self.receiver_id,
            **overrides,
        }
        return self.client.post(
            PREPARE_UPLOAD, json=body, headers=auth(token or self.sender_token)
        )

    def finish_upload(self, file_id: str, token=None):
        return self.client.post(
            FINISH_UPLOAD,
            json={"file_id": file_id},
            headers=auth(token or self.sender_token),
        )

    def finish_download(self, file_ids: list[str], token=None):
        return self.client.post(
            FINISH_DOWNLOAD,
            json={"file_ids": file_ids},
            headers=auth(token or self.receiver_token),
        )

    def uploaded_file(self, size=123) -> str:
        """Create a file that has been fully uploaded. Returns its id."""
        response = self.prepare_upload(size=size)
        self.assertEqual(response.status_code, 200, response.text)
        file_id = response.json()["data"]["file_id"]

        self.storage.head_object.return_value = {"ContentLength": size}
        response = self.finish_upload(file_id)
        self.assertEqual(response.status_code, 200, response.text)
        return file_id

    # =============================================================================
    # prepare-upload
    # =============================================================================
    def test_prepare_upload_returns_presigned_url_and_pending_file(self):
        response = self.prepare_upload()

        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()["data"]
        self.assertEqual(data["upload_url"], FAKE_PUT_URL)

        row = db_file(data["file_id"])
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], FileStatus.PENDING)
        self.assertEqual(row["sender_id"], self.sender_id)
        self.assertEqual(row["receiver_id"], self.receiver_id)
        self.assertEqual(row["object_key"], f"{self.receiver_id}/{data['file_id']}")
        self.storage.get_put_presigned_url.assert_called_once_with(
            key=row["object_key"]
        )

    def test_prepare_upload_without_auth_header_is_401(self):
        response = self.client.post(
            PREPARE_UPLOAD,
            json={
                "file_name": "hello.txt",
                "size": 1,
                "content_type": "text/plain",
                "checksum": "abc",
                "receiver_id": self.receiver_id,
            },
        )
        self.assertEqual(response.status_code, 401, response.text)

    def test_prepare_upload_with_invalid_token_is_401(self):
        response = self.prepare_upload(token="not-a-real-token")
        self.assertEqual(response.status_code, 401, response.text)
        self.storage.get_put_presigned_url.assert_not_called()

    def test_prepare_upload_to_unknown_receiver_is_rejected(self):
        response = self.prepare_upload(receiver_id=str(uuid.uuid4()))
        self.assertEqual(response.status_code, 401, response.text)
        self.storage.get_put_presigned_url.assert_not_called()

    def test_prepare_upload_to_revoked_receiver_is_403(self):
        set_device_status(self.receiver_id, DeviceStatus.REVOKED)
        response = self.prepare_upload()
        self.assertEqual(response.status_code, 403, response.text)

    def test_prepare_upload_from_revoked_sender_is_403(self):
        set_device_status(self.sender_id, DeviceStatus.REVOKED)
        response = self.prepare_upload()
        self.assertEqual(response.status_code, 403, response.text)

    def test_prepare_upload_with_non_uuid_receiver_is_422(self):
        response = self.prepare_upload(receiver_id="not-a-uuid")
        self.assertEqual(response.status_code, 422, response.text)

    def test_prepare_upload_missing_fields_is_422(self):
        response = self.client.post(
            PREPARE_UPLOAD,
            json={"receiver_id": self.receiver_id},
            headers=auth(self.sender_token),
        )
        self.assertEqual(response.status_code, 422, response.text)

    # =============================================================================
    # finish-upload
    # =============================================================================
    def test_finish_upload_marks_file_uploaded(self):
        file_id = self.prepare_upload(size=42).json()["data"]["file_id"]
        self.storage.head_object.return_value = {"ContentLength": 42}

        response = self.finish_upload(file_id)

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["data"]["file_id"], file_id)
        self.assertEqual(db_file(file_id)["status"], FileStatus.UPLOADED)
        self.storage.head_object.assert_called_once_with(
            f"{self.receiver_id}/{file_id}"
        )

    def test_finish_upload_unknown_file_is_404(self):
        response = self.finish_upload(str(uuid.uuid4()))
        self.assertEqual(response.status_code, 404, response.text)

    def test_finish_upload_by_non_sender_is_403(self):
        file_id = self.prepare_upload().json()["data"]["file_id"]
        self.storage.head_object.return_value = {"ContentLength": 123}

        response = self.finish_upload(file_id, token=self.receiver_token)

        self.assertEqual(response.status_code, 403, response.text)
        self.assertEqual(db_file(file_id)["status"], FileStatus.PENDING)

    def test_finish_upload_twice_is_409(self):
        file_id = self.uploaded_file()

        response = self.finish_upload(file_id)

        self.assertEqual(response.status_code, 409, response.text)

    def test_finish_upload_when_object_missing_is_409(self):
        file_id = self.prepare_upload().json()["data"]["file_id"]
        self.storage.head_object.return_value = None

        response = self.finish_upload(file_id)

        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(db_file(file_id)["status"], FileStatus.PENDING)

    def test_finish_upload_with_size_mismatch_is_409(self):
        file_id = self.prepare_upload(size=100).json()["data"]["file_id"]
        self.storage.head_object.return_value = {"ContentLength": 99}

        response = self.finish_upload(file_id)

        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(db_file(file_id)["status"], FileStatus.PENDING)

    def test_finish_upload_with_invalid_token_is_401(self):
        file_id = self.prepare_upload().json()["data"]["file_id"]
        response = self.finish_upload(file_id, token="not-a-real-token")
        self.assertEqual(response.status_code, 401, response.text)

    def test_finish_upload_with_non_uuid_file_id_is_422(self):
        response = self.finish_upload("not-a-uuid")
        self.assertEqual(response.status_code, 422, response.text)

    # =============================================================================
    # check-pending-download
    # =============================================================================
    def test_check_pending_with_nothing_returns_empty_list(self):
        response = self.client.get(CHECK_PENDING, headers=auth(self.receiver_token))

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["data"]["files"], [])

    def test_check_pending_lists_uploaded_files_for_receiver(self):
        file_id = self.uploaded_file()

        response = self.client.get(CHECK_PENDING, headers=auth(self.receiver_token))

        self.assertEqual(response.status_code, 200, response.text)
        ids = [f["id"] for f in response.json()["data"]["files"]]
        self.assertEqual(ids, [file_id])

    def test_check_pending_ignores_files_not_yet_uploaded(self):
        self.prepare_upload()  # still pending

        response = self.client.get(CHECK_PENDING, headers=auth(self.receiver_token))

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["data"]["files"], [])

    def test_check_pending_does_not_show_files_to_sender(self):
        self.uploaded_file()

        response = self.client.get(CHECK_PENDING, headers=auth(self.sender_token))

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["data"]["files"], [])

    def test_check_pending_with_invalid_token_is_401(self):
        response = self.client.get(CHECK_PENDING, headers=auth("not-a-real-token"))
        self.assertEqual(response.status_code, 401, response.text)

    # =============================================================================
    # prepare-download
    # =============================================================================
    def test_prepare_download_returns_file_objects_with_urls(self):
        file_id = self.uploaded_file(size=77)

        response = self.client.get(PREPARE_DOWNLOAD, headers=auth(self.receiver_token))

        self.assertEqual(response.status_code, 200, response.text)
        objects = response.json()["data"]["file_objects"]
        self.assertEqual(len(objects), 1)
        self.assertEqual(
            objects[0],
            {
                "file_id": file_id,
                "file_name": "hello.txt",
                "size": 77,
                "content_type": "text/plain",
                "checksum": "abc123",
                "download_url": FAKE_GET_URL,
            },
        )
        self.storage.get_get_presigned_url.assert_called_once_with(
            f"{self.receiver_id}/{file_id}"
        )

    def test_prepare_download_with_no_files_returns_empty_list(self):
        response = self.client.get(PREPARE_DOWNLOAD, headers=auth(self.receiver_token))

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["data"]["file_objects"], [])

    def test_prepare_download_with_invalid_token_is_401(self):
        response = self.client.get(PREPARE_DOWNLOAD, headers=auth("not-a-real-token"))
        self.assertEqual(response.status_code, 401, response.text)

    # =============================================================================
    # finish-download
    # =============================================================================
    def test_finish_download_deletes_objects_and_marks_deleted(self):
        file_id = self.uploaded_file()

        response = self.finish_download([file_id])

        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()["data"]
        self.assertEqual(data["finished"], [file_id])
        self.assertEqual(data["failed_deletion_ids"], [])
        self.assertEqual(db_file(file_id)["status"], FileStatus.DELETED)
        self.storage.delete_objects.assert_called_once_with(
            [f"{self.receiver_id}/{file_id}"]
        )

    def test_finish_download_storage_failure_leaves_file_downloaded(self):
        ok_id = self.uploaded_file()
        bad_id = self.uploaded_file()
        self.storage.delete_objects.return_value = {f"{self.receiver_id}/{bad_id}"}

        response = self.finish_download([ok_id, bad_id])

        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()["data"]
        self.assertCountEqual(data["finished"], [ok_id, bad_id])
        self.assertEqual(data["failed_deletion_ids"], [bad_id])
        self.assertIn(bad_id, response.json()["message"])
        self.assertEqual(db_file(ok_id)["status"], FileStatus.DELETED)
        self.assertEqual(db_file(bad_id)["status"], FileStatus.DOWNLOADED)

    def test_finish_download_unknown_ids_is_404(self):
        response = self.finish_download([str(uuid.uuid4())])
        self.assertEqual(response.status_code, 404, response.text)
        self.storage.delete_objects.assert_not_called()

    def test_finish_download_by_non_receiver_is_404(self):
        file_id = self.uploaded_file()

        response = self.finish_download([file_id], token=self.sender_token)

        self.assertEqual(response.status_code, 404, response.text)
        self.assertEqual(db_file(file_id)["status"], FileStatus.UPLOADED)

    def test_finish_download_of_pending_file_is_404(self):
        file_id = self.prepare_upload().json()["data"]["file_id"]

        response = self.finish_download([file_id])

        self.assertEqual(response.status_code, 404, response.text)
        self.assertEqual(db_file(file_id)["status"], FileStatus.PENDING)

    def test_finish_download_twice_is_404(self):
        file_id = self.uploaded_file()
        self.assertEqual(self.finish_download([file_id]).status_code, 200)

        response = self.finish_download([file_id])

        self.assertEqual(response.status_code, 404, response.text)

    def test_finish_download_mixed_ids_only_finishes_known(self):
        file_id = self.uploaded_file()

        response = self.finish_download([file_id, str(uuid.uuid4())])

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["data"]["finished"], [file_id])

    def test_finish_download_empty_list_is_422(self):
        response = self.finish_download([])
        self.assertEqual(response.status_code, 422, response.text)

    def test_finish_download_with_invalid_token_is_401(self):
        file_id = self.uploaded_file()
        response = self.finish_download([file_id], token="not-a-real-token")
        self.assertEqual(response.status_code, 401, response.text)

    # =============================================================================
    # Full round trip
    # =============================================================================
    def test_full_transfer_round_trip(self):
        file_id = self.uploaded_file(size=10)

        pending = self.client.get(CHECK_PENDING, headers=auth(self.receiver_token))
        self.assertEqual([f["id"] for f in pending.json()["data"]["files"]], [file_id])

        download = self.client.get(PREPARE_DOWNLOAD, headers=auth(self.receiver_token))
        self.assertEqual(
            download.json()["data"]["file_objects"][0]["download_url"], FAKE_GET_URL
        )

        self.assertEqual(self.finish_download([file_id]).status_code, 200)

        pending = self.client.get(CHECK_PENDING, headers=auth(self.receiver_token))
        self.assertEqual(pending.json()["data"]["files"], [])


if __name__ == "__main__":
    unittest.main()
