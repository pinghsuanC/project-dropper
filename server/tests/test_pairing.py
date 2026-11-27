"""
Pairing tests: POST /pairing-request/start, POST /pairing-request/claim,
GET /pairing-request/{pairing_request_id}/get.

Run from inside server/:
    python -m unittest discover -s tests -v
"""

import base64
import hashlib
import os
import time
import unittest
import uuid

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

# CI has no .env; config.py requires HMAC_SECRET at import, so set a default
# BEFORE importing the app. The DB is patched to TEST_DB_PATH in setUpClass.
os.environ.setdefault("HMAC_SECRET", "test-secret-not-for-production")

from fastapi.testclient import TestClient

import db.database_connection as db_conn
import repositories.pairing_request as pairing_request_repo
from config import TEST_DB_PATH
from db.database_connection import DatabaseConnection
from enums import DevicePairStatus, DeviceStatus, PairingRequestStatus
from exceptions import PairingRequestAlreadyUsedError
from server import app

REGISTER = "/auth/register"
CHALLENGE = "/auth/challenge"
VERIFY = "/auth/verify-challenge"
PAIRED = "/devices/paired"
START = "/pairing-request/start"
CLAIM = "/pairing-request/claim"


def status_url(pairing_request_id: str) -> str:
    return f"/pairing-request/{pairing_request_id}/get"


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


def insert_pair(a: str, b: str) -> None:
    """Insert an active pair directly, smaller id first."""
    device_1_id, device_2_id = sorted((a, b))
    with DatabaseConnection() as conn:
        conn.execute(
            "INSERT INTO device_pair (id, device_1_id, device_2_id, status) "
            "VALUES (?, ?, ?, ?)",
            (str(uuid.uuid7()), device_1_id, device_2_id, DevicePairStatus.ACTIVE),
        )


def set_device_status(device_id: str, status: str) -> None:
    with DatabaseConnection() as conn:
        conn.execute("UPDATE device_info SET status=? WHERE id=?", (status, device_id))


def db_pairing_request(pairing_request_id: str) -> dict | None:
    with DatabaseConnection() as conn:
        row = conn.execute(
            "SELECT * FROM pairing_request WHERE id=?", (pairing_request_id,)
        ).fetchone()
    return dict(row) if row else None


def db_pairs_of(device_id: str) -> list[dict]:
    with DatabaseConnection() as conn:
        rows = conn.execute(
            "SELECT * FROM device_pair WHERE device_1_id=? OR device_2_id=?",
            (device_id, device_id),
        ).fetchall()
    return [dict(r) for r in rows]


def expire(pairing_request_id: str) -> None:
    with DatabaseConnection() as conn:
        conn.execute(
            "UPDATE pairing_request SET expires_at = 0 WHERE id=?",
            (pairing_request_id,),
        )


class PairingRequestTests(unittest.TestCase):
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
        # Fresh devices per test, so pairs/requests from other tests never interfere
        self.pc_id, self.pc_token = self.login_new_device("PC", "desktop")
        self.phone_id, self.phone_token = self.login_new_device("phone", "android")

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

    def start(self, token: str | None = None) -> dict:
        """PC starts a pairing request. Returns the response `data`."""
        response = self.client.post(START, headers=auth(token or self.pc_token))
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["data"]

    def claim(self, pairing_token: str, token: str | None = None):
        return self.client.post(
            CLAIM,
            headers=auth(token or self.phone_token),
            json={"pairing_token": pairing_token},
        )

    def get_status(self, pairing_request_id: str, token: str | None = None):
        return self.client.get(
            status_url(pairing_request_id), headers=auth(token or self.pc_token)
        )

    # --- POST /pairing-request/start ----------------------------------------------
    def test_start_returns_id_token_and_expiry(self):
        before = int(time.time())
        response = self.client.post(START, headers=auth(self.pc_token))

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["message"], "Pairing started.")
        data = body["data"]
        self.assertEqual(
            set(data), {"pairing_request_id", "pairing_token", "expires_at"}
        )
        uuid.UUID(data["pairing_request_id"])  # raises if not a uuid
        self.assertTrue(data["pairing_token"])
        self.assertIsInstance(data["expires_at"], int)
        # schema default: created + 180 s
        self.assertAlmostEqual(data["expires_at"], before + 180, delta=5)

    def test_start_stores_only_the_token_hash(self):
        data = self.start()
        row = db_pairing_request(data["pairing_request_id"])

        self.assertIsNotNone(row)
        self.assertEqual(row["device_1_id"], self.pc_id)
        self.assertIsNone(row["device_2_id"])
        self.assertEqual(row["status"], PairingRequestStatus.PENDING)
        self.assertNotEqual(row["token_hashed"], data["pairing_token"])
        self.assertEqual(
            row["token_hashed"],
            hashlib.sha256(data["pairing_token"].encode()).hexdigest(),
        )

    def test_start_twice_replaces_older_pending_request(self):
        first = self.start()
        second = self.start()

        self.assertNotEqual(first["pairing_token"], second["pairing_token"])
        self.assertIsNone(db_pairing_request(first["pairing_request_id"]))
        self.assertEqual(
            self.claim(first["pairing_token"]).status_code, 404
        )  # old QR is dead
        self.assertEqual(self.claim(second["pairing_token"]).status_code, 200)

    def test_start_does_not_touch_other_devices_requests(self):
        _, laptop_token = self.login_new_device("laptop", "desktop")
        mine = self.start()
        self.start(laptop_token)

        self.assertIsNotNone(db_pairing_request(mine["pairing_request_id"]))

    def test_start_without_auth_header_is_401(self):
        response = self.client.post(START)
        self.assertIn(response.status_code, (401, 403), response.text)

    def test_start_with_invalid_token_is_401(self):
        response = self.client.post(START, headers=auth("garbage"))
        self.assertEqual(response.status_code, 401, response.text)

    def test_start_from_revoked_device_is_403(self):
        set_device_status(self.pc_id, DeviceStatus.REVOKED)
        response = self.client.post(START, headers=auth(self.pc_token))
        self.assertEqual(response.status_code, 403, response.text)

    # --- POST /pairing-request/claim ----------------------------------------------
    def test_claim_pairs_the_two_devices(self):
        data = self.start()

        response = self.claim(data["pairing_token"])

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["message"], "Pairing successfully claimed.")
        self.assertEqual(
            body["data"],
            {
                "paired_with": {
                    "device_id": self.pc_id,
                    "name": "PC",
                    "platform": "desktop",
                }
            },
        )

    def test_claim_updates_request_and_creates_sorted_pair(self):
        data = self.start()
        self.assertEqual(self.claim(data["pairing_token"]).status_code, 200)

        row = db_pairing_request(data["pairing_request_id"])
        self.assertEqual(row["status"], PairingRequestStatus.ACCEPTED)
        self.assertEqual(row["device_2_id"], self.phone_id)

        pairs = db_pairs_of(self.pc_id)
        self.assertEqual(len(pairs), 1)
        pair = pairs[0]
        self.assertEqual(pair["status"], DevicePairStatus.ACTIVE)
        self.assertEqual(
            [pair["device_1_id"], pair["device_2_id"]],
            sorted([self.pc_id, self.phone_id]),
        )

    def test_claim_makes_devices_visible_in_devices_paired(self):
        data = self.start()
        self.assertEqual(self.claim(data["pairing_token"]).status_code, 200)

        for token, other_id in (
            (self.phone_token, self.pc_id),
            (self.pc_token, self.phone_id),
        ):
            response = self.client.get(PAIRED, headers=auth(token))
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["data"]["device"]["device_id"], other_id)

    def test_claim_unknown_token_is_404(self):
        self.start()
        response = self.claim("not-a-real-token")
        self.assertEqual(response.status_code, 404, response.text)
        self.assertNotIn("data", response.json())

    def test_claim_own_token_is_404(self):
        data = self.start()
        response = self.claim(data["pairing_token"], token=self.pc_token)
        self.assertEqual(response.status_code, 404, response.text)
        self.assertEqual(db_pairs_of(self.pc_id), [])

    def test_claim_expired_token_is_404(self):
        data = self.start()
        expire(data["pairing_request_id"])

        response = self.claim(data["pairing_token"])

        self.assertEqual(response.status_code, 404, response.text)
        self.assertEqual(db_pairs_of(self.pc_id), [])

    def test_claim_same_token_twice_is_404(self):
        data = self.start()
        self.assertEqual(self.claim(data["pairing_token"]).status_code, 200)

        # a third device scans the same (already used) QR
        _, laptop_token = self.login_new_device("laptop", "desktop")
        response = self.claim(data["pairing_token"], token=laptop_token)

        self.assertEqual(response.status_code, 404, response.text)
        self.assertEqual(len(db_pairs_of(self.pc_id)), 1)

    def test_claim_when_initiator_revoked_is_404(self):
        data = self.start()
        set_device_status(self.pc_id, DeviceStatus.REVOKED)

        response = self.claim(data["pairing_token"])

        self.assertEqual(response.status_code, 404, response.text)
        self.assertEqual(db_pairs_of(self.phone_id), [])

    def test_claim_when_claimer_already_paired_is_409(self):
        laptop_id, _ = self.login_new_device("laptop", "desktop")
        insert_pair(self.phone_id, laptop_id)
        data = self.start()

        response = self.claim(data["pairing_token"])

        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(
            response.json()["detail"],
            "Already paired with other device. Unpair first.",
        )
        # the request is still pending, nothing was created for the PC
        row = db_pairing_request(data["pairing_request_id"])
        self.assertEqual(row["status"], PairingRequestStatus.PENDING)
        self.assertEqual(db_pairs_of(self.pc_id), [])

    def test_claim_when_initiator_already_paired_is_409(self):
        tablet_id, _ = self.login_new_device("tablet", "android")
        insert_pair(self.pc_id, tablet_id)
        data = self.start()

        response = self.claim(data["pairing_token"])

        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(
            response.json()["detail"],
            "That device is already paired. Unpair it first.",
        )
        self.assertEqual(db_pairs_of(self.phone_id), [])

    def test_claim_missing_pairing_token_is_422(self):
        response = self.client.post(CLAIM, headers=auth(self.phone_token), json={})
        self.assertEqual(response.status_code, 422, response.text)

    def test_claim_without_auth_header_is_401(self):
        data = self.start()
        response = self.client.post(
            CLAIM, json={"pairing_token": data["pairing_token"]}
        )
        self.assertIn(response.status_code, (401, 403), response.text)

    def test_claim_from_revoked_device_is_403(self):
        data = self.start()
        set_device_status(self.phone_id, DeviceStatus.REVOKED)

        response = self.claim(data["pairing_token"])

        self.assertEqual(response.status_code, 403, response.text)

    def test_accept_twice_raises_already_used(self):
        """The race guard: if the request stopped being pending between the check
        and the update, accept_pairing_request raises instead of pairing again."""
        data = self.start()
        request_id = data["pairing_request_id"]
        pairing_request_repo.accept_pairing_request(
            request_id, claimer_id=self.phone_id, initiator_id=self.pc_id
        )

        laptop_id, _ = self.login_new_device("laptop", "desktop")
        with self.assertRaises(PairingRequestAlreadyUsedError):
            pairing_request_repo.accept_pairing_request(
                request_id, claimer_id=laptop_id, initiator_id=self.pc_id
            )
        self.assertEqual(db_pairs_of(laptop_id), [])

    # --- GET /pairing-request/{id}/get --------------------------------------------
    def test_get_pending_request(self):
        data = self.start()

        response = self.get_status(data["pairing_request_id"])

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["message"], "Valid pairing request found.")
        request = body["data"]
        self.assertEqual(
            set(request), {"id", "paired_with", "status", "created_at", "expires_at"}
        )
        self.assertEqual(request["id"], data["pairing_request_id"])
        self.assertIsNone(request["paired_with"])  # nobody has claimed it yet
        self.assertEqual(request["status"], PairingRequestStatus.PENDING)
        self.assertIsInstance(request["created_at"], int)
        self.assertEqual(request["expires_at"], data["expires_at"])

    def test_get_after_claim_is_accepted(self):
        data = self.start()
        self.assertEqual(self.claim(data["pairing_token"]).status_code, 200)

        response = self.get_status(data["pairing_request_id"])

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.json()["data"]["status"], PairingRequestStatus.ACCEPTED
        )
        # the claimer's device name
        self.assertEqual(response.json()["data"]["paired_with"], "phone")

    def test_get_does_not_leak_token_hash(self):
        data = self.start()
        body = self.get_status(data["pairing_request_id"]).json()
        self.assertNotIn("token_hashed", body["data"])
        self.assertNotIn("pairing_token", body["data"])

    def test_get_by_other_device_is_404(self):
        data = self.start()
        response = self.get_status(data["pairing_request_id"], token=self.phone_token)
        self.assertEqual(response.status_code, 404, response.text)

    def test_get_unknown_id_is_404(self):
        response = self.get_status(str(uuid.uuid4()))
        self.assertEqual(response.status_code, 404, response.text)

    def test_get_non_uuid_id_is_422(self):
        response = self.get_status("not-a-uuid")
        self.assertEqual(response.status_code, 422, response.text)

    def test_get_without_auth_header_is_401(self):
        data = self.start()
        response = self.client.get(status_url(data["pairing_request_id"]))
        self.assertIn(response.status_code, (401, 403), response.text)


if __name__ == "__main__":
    unittest.main()
