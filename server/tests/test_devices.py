"""
Device tests: GET /devices/paired.

Run from inside server/:
    python -m unittest discover -s tests -v
"""

import base64
import os
import tempfile
import unittest
import uuid
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

# --- Point the app at a throwaway database BEFORE importing it ---------------
_TMP_DIR = tempfile.TemporaryDirectory()
_TEST_DB = Path(_TMP_DIR.name) / "test_devices.db"
os.environ["DB_PATH"] = str(_TEST_DB)
os.environ.setdefault("HMAC_SECRET", "test-secret-not-for-production")

from fastapi.testclient import TestClient

import db.database_connection as db_conn
from db.database_connection import DatabaseConnection
from enums import DeviceStatus, PairStatus
from server import app

REGISTER = "/auth/register"
CHALLENGE = "/auth/challenge"
VERIFY = "/auth/verify-challenge"
PAIRED = "/devices/paired"


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


def insert_pair(
    a: str, b: str, status: str = PairStatus.ACTIVE, created_at: int | None = None
) -> None:
    """Insert a pair the way the server must: smaller id first."""
    device_1_id, device_2_id = sorted((a, b))
    with DatabaseConnection() as conn:
        conn.execute(
            "INSERT INTO device_pair (id, device_1_id, device_2_id, status, created_at) "
            "VALUES (?, ?, ?, ?, COALESCE(?, unixepoch()))",
            (str(uuid.uuid7()), device_1_id, device_2_id, status, created_at),
        )


def set_device_status(device_id: str, status: str) -> None:
    with DatabaseConnection() as conn:
        conn.execute("UPDATE device_info SET status=? WHERE id=?", (status, device_id))


class PairedDevicesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
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
        self.phone_id, self.phone_token = self.login_new_device("phone", "android")
        self.pc_id, self.pc_token = self.login_new_device("PC", "desktop")

    def login_new_device(self, name: str, platform: str) -> tuple[str, str]:
        """Register a device and run challenge/verify. Returns (device_id, token)."""
        key = Ed25519PrivateKey.generate()
        response = self.client.post(
            REGISTER,
            json={
                "name": name,
                "platform": platform,
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

    def paired_id(self, token: str) -> str | None:
        response = self.client.get(PAIRED, headers=auth(token))
        self.assertEqual(response.status_code, 200, response.text)
        device = response.json()["data"]["device"]
        return device["device_id"] if device else None

    # --- Tests --------------------------------------------------------------------
    def test_not_paired_returns_null(self):
        response = self.client.get(PAIRED, headers=auth(self.phone_token))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["message"], "Not paired.")
        self.assertIsNone(response.json()["data"]["device"])

    def test_pair_is_visible_from_both_sides(self):
        insert_pair(self.phone_id, self.pc_id)
        self.assertEqual(self.paired_id(self.phone_token), self.pc_id)
        self.assertEqual(self.paired_id(self.pc_token), self.phone_id)

    def test_response_shape(self):
        insert_pair(self.phone_id, self.pc_id)
        body = self.client.get(PAIRED, headers=auth(self.phone_token)).json()
        self.assertEqual(body["message"], "Paired device found.")
        device = body["data"]["device"]
        self.assertEqual(set(device), {"device_id", "name", "platform", "paired_at"})
        self.assertEqual(device["name"], "PC")
        self.assertEqual(device["platform"], "desktop")
        self.assertIsInstance(device["paired_at"], int)

    def test_only_newest_pair_is_returned(self):
        other_id, _ = self.login_new_device("laptop", "desktop")
        insert_pair(self.phone_id, self.pc_id, created_at=1000)
        insert_pair(self.phone_id, other_id, created_at=2000)
        self.assertEqual(self.paired_id(self.phone_token), other_id)

    def test_same_timestamp_picks_one_deterministically(self):
        other_id, _ = self.login_new_device("laptop", "desktop")
        insert_pair(self.phone_id, self.pc_id, created_at=1000)
        insert_pair(self.phone_id, other_id, created_at=1000)
        # uuid7 pair ids are time-ordered, so the later insert wins the tie
        self.assertEqual(self.paired_id(self.phone_token), other_id)

    def test_revoked_pair_is_hidden(self):
        insert_pair(self.phone_id, self.pc_id, status=PairStatus.REVOKED)
        self.assertIsNone(self.paired_id(self.phone_token))

    def test_revoked_newest_pair_falls_back_to_active_one(self):
        other_id, _ = self.login_new_device("laptop", "desktop")
        insert_pair(self.phone_id, self.pc_id, created_at=1000)
        insert_pair(self.phone_id, other_id, PairStatus.REVOKED, created_at=2000)
        self.assertEqual(self.paired_id(self.phone_token), self.pc_id)

    def test_revoked_partner_device_is_hidden(self):
        insert_pair(self.phone_id, self.pc_id)
        set_device_status(self.pc_id, DeviceStatus.REVOKED)
        self.assertIsNone(self.paired_id(self.phone_token))

    def test_other_devices_pairs_are_not_returned(self):
        a_id, _ = self.login_new_device("a", "android")
        b_id, _ = self.login_new_device("b", "desktop")
        insert_pair(a_id, b_id)
        self.assertIsNone(self.paired_id(self.phone_token))

    def test_without_auth_header_is_401(self):
        response = self.client.get(PAIRED)
        self.assertIn(response.status_code, (401, 403), response.text)

    def test_with_invalid_token_is_401(self):
        response = self.client.get(PAIRED, headers=auth("garbage"))
        self.assertEqual(response.status_code, 401, response.text)

    def test_revoked_caller_is_403(self):
        set_device_status(self.phone_id, DeviceStatus.REVOKED)
        response = self.client.get(PAIRED, headers=auth(self.phone_token))
        self.assertEqual(response.status_code, 403, response.text)


if __name__ == "__main__":
    unittest.main()
