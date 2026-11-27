"""
Outbox tests: GET /files/sent.

Run from inside server/:
    python -m unittest discover -s tests -v
"""

import base64
import os
import unittest
import uuid
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

# CI has no .env; config.py requires HMAC_SECRET at import, so set a default
# BEFORE importing the app. The DB is patched to TEST_DB_PATH in setUpClass.
os.environ.setdefault("HMAC_SECRET", "test-secret-not-for-production")

from fastapi.testclient import TestClient

import db.database_connection as db_conn
from config import TEST_DB_PATH
from db.database_connection import DatabaseConnection
from enums import DeviceStatus, FileStatus
from server import app

REGISTER = "/auth/register"
CHALLENGE = "/auth/challenge"
VERIFY = "/auth/verify-challenge"
PREPARE_UPLOAD = "/files/prepare-upload"
SENT = "/files/sent"


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


def insert_file(
    sender_id: str,
    receiver_id: str,
    status: str = FileStatus.UPLOADED,
    created_at: int | None = None,
    file_name: str = "dog.png",
    size: int = 21800,
) -> str:
    file_id = str(uuid.uuid7())
    with DatabaseConnection() as conn:
        conn.execute(
            "INSERT INTO file (id, sender_id, receiver_id, file_name, object_key, size, "
            "content_type, checksum, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, unixepoch()))",
            (
                file_id,
                sender_id,
                receiver_id,
                file_name,
                f"{receiver_id}/{file_id}",
                size,
                "image/png",
                "0" * 64,
                status,
                created_at,
            ),
        )
    return file_id


def set_device_status(device_id: str, status: str) -> None:
    with DatabaseConnection() as conn:
        conn.execute("UPDATE device_info SET status=? WHERE id=?", (status, device_id))


class SentFilesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._orig_db_path = db_conn.DB_PATH
        TEST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        TEST_DB_PATH.unlink(missing_ok=True)  # start from an empty DB
        db_conn.DB_PATH = TEST_DB_PATH

        cls._client_cm = TestClient(app)
        cls.client = cls._client_cm.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._client_cm.__exit__(None, None, None)
        db_conn.DB_PATH = cls._orig_db_path
        TEST_DB_PATH.unlink(missing_ok=True)

    def setUp(self):
        self.phone_id, self.phone_token = self.login_new_device("phone", "android")
        self.pc_id, self.pc_token = self.login_new_device("PC", "desktop")

    def login_new_device(self, name: str, platform: str) -> tuple[str, str]:
        """Register a device and run challenge/verify. Returns (device_id, token)."""
        key = Ed25519PrivateKey.generate()
        fingerprint = uuid.uuid4().hex
        response = self.client.post(
            REGISTER,
            json={
                "name": name,
                "platform": platform,
                "public_key": public_pem(key),
                "fingerprint": fingerprint,
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
                "fingerprint": fingerprint,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        return device_id, response.json()["data"]["token"]

    def sent_ids(self, token: str) -> list[str]:
        response = self.client.get(SENT, headers=auth(token))
        self.assertEqual(response.status_code, 200, response.text)
        return [f["file_id"] for f in response.json()["data"]]

    # --- Tests --------------------------------------------------------------------
    def test_nothing_sent_returns_200_empty_list(self):
        response = self.client.get(SENT, headers=auth(self.phone_token))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["data"], [])
        self.assertEqual(response.json()["message"], "0 file(s) waiting.")

    def test_response_shape(self):
        file_id = insert_file(self.phone_id, self.pc_id, created_at=1794363378)
        body = self.client.get(SENT, headers=auth(self.phone_token)).json()
        self.assertEqual(body["message"], "1 file(s) waiting.")
        self.assertEqual(
            body["data"],
            [
                {
                    "file_id": file_id,
                    "file_name": "dog.png",
                    "size": 21800,
                    "status": "uploaded",
                    "receiver_name": "PC",
                    "created_at": 1794363378,
                }
            ],
        )

    def test_only_pending_and_uploaded_are_listed(self):
        pending = insert_file(self.phone_id, self.pc_id, FileStatus.PENDING, 1000)
        uploaded = insert_file(self.phone_id, self.pc_id, FileStatus.UPLOADED, 2000)
        insert_file(self.phone_id, self.pc_id, FileStatus.DOWNLOADED, 3000)
        insert_file(self.phone_id, self.pc_id, FileStatus.DELETED, 4000)
        self.assertEqual(self.sent_ids(self.phone_token), [uploaded, pending])

    def test_newest_first(self):
        old = insert_file(self.phone_id, self.pc_id, created_at=1000)
        new = insert_file(self.phone_id, self.pc_id, created_at=3000)
        mid = insert_file(self.phone_id, self.pc_id, created_at=2000)
        self.assertEqual(self.sent_ids(self.phone_token), [new, mid, old])

    def test_only_callers_files_not_files_sent_to_caller(self):
        mine = insert_file(self.phone_id, self.pc_id)
        insert_file(self.pc_id, self.phone_id)  # sent TO the phone
        self.assertEqual(self.sent_ids(self.phone_token), [mine])

    def test_other_devices_files_never_appear(self):
        a_id, a_token = self.login_new_device("a", "android")
        theirs = insert_file(a_id, self.pc_id)
        self.assertEqual(self.sent_ids(self.phone_token), [])
        self.assertEqual(self.sent_ids(a_token), [theirs])

    def test_file_started_through_prepare_upload_shows_as_pending(self):
        with patch("files.routes.ObjectStorage") as storage_cls:
            storage_cls.return_value.get_put_presigned_url.return_value = "https://x"
            response = self.client.post(
                PREPARE_UPLOAD,
                headers=auth(self.phone_token),
                json={
                    "file_name": "cat.jpg",
                    "size": 812,
                    "content_type": "image/jpeg",
                    "checksum": "a" * 64,
                    "receiver_id": self.pc_id,
                },
            )
        self.assertIn(response.status_code, (200, 201), response.text)
        file_id = response.json()["data"]["file_id"]

        data = self.client.get(SENT, headers=auth(self.phone_token)).json()["data"]
        self.assertEqual(
            [(f["file_id"], f["status"]) for f in data], [(file_id, "pending")]
        )

    def test_without_auth_header_is_401(self):
        response = self.client.get(SENT)
        self.assertIn(response.status_code, (401, 403), response.text)

    def test_with_invalid_token_is_401(self):
        response = self.client.get(SENT, headers=auth("garbage"))
        self.assertEqual(response.status_code, 401, response.text)

    def test_revoked_caller_is_403(self):
        set_device_status(self.phone_id, DeviceStatus.REVOKED)
        response = self.client.get(SENT, headers=auth(self.phone_token))
        self.assertEqual(response.status_code, 403, response.text)


if __name__ == "__main__":
    unittest.main()
