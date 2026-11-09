"""
Auth flow tests: register -> challenge -> verify.

Run from inside server/:
    python -m unittest discover -s tests -v

Needs:  pip install httpx   (FastAPI's TestClient uses it)
"""

import base64
import os
import secrets
import tempfile
import unittest
import uuid
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

# --- Point the app at a throwaway database BEFORE importing it ---------------
# db/connection.py reads DB_LOCATION when it is imported, so this must come
# first. load_dotenv() does not override variables that are already set, so
# your real .env can't sneak the real database back in.
_TMP_DIR = tempfile.TemporaryDirectory()
os.environ["DB_LOCATION"] = str(Path(_TMP_DIR.name) / "test.db")
os.environ.setdefault("HMAC_SECRET", "test-secret-not-for-production")
# ↑ use whatever name your crypto.py reads; CI has no .env, so it needs a value

from fastapi.testclient import TestClient

from db.database_connection import DatabaseConnection
from server import app

# Adjust these if your routes are named differently
REGISTER = "/auth/register"
CHALLENGE = "/auth/challenge"
VERIFY = "/auth/verify-challenge"
ME = "auth/me"


# --- Helpers ------------------------------------------------------------------
def new_key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.generate()


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


class AuthFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # `with` makes TestClient run the lifespan, so init_db() creates the tables
        cls._client_cm = TestClient(app)
        cls.client = cls._client_cm.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._client_cm.__exit__(None, None, None)
        _TMP_DIR.cleanup()

    # Each test registers its own fresh device, so tests don't affect each other
    def register(self, key: Ed25519PrivateKey) -> str:
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
        return response.json()["data"]["device_id"]

    def get_challenge(self, device_id: str) -> str:
        response = self.client.post(CHALLENGE, json={"device_id": device_id})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["data"]["challenge"]

    def verify(self, device_id: str, challenge: str, signature: str):
        return self.client.post(
            VERIFY,
            json={
                "device_id": device_id,
                "challenge": challenge,
                "signature": signature,
            },
        )

    # --- Worked example: the happy path ------------------------------------------
    def test_valid_signature_returns_session_token(self):
        # Arrange: a registered device with a fresh challenge
        key = new_key()
        device_id = self.register(key)
        challenge = self.get_challenge(device_id)

        # Act: sign it with the right key and verify
        response = self.verify(device_id, challenge, sign(key, challenge))

        # Assert: success, and a token came back
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["data"]["token"])

    def test_valid_me(self):
        """Happy path calling /me with a valid header -> 200."""

        key = new_key()
        device_id = self.register(key)
        challenge = self.get_challenge(device_id)

        # Act: sign it with the right key and verify
        response = self.verify(device_id, challenge, sign(key, challenge))

        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["data"]["token"])

        token = response.json()["data"]["token"]

        response = self.client.get(
            ME,
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )

        data = response.json()["data"]

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["data"]["device_id"], device_id)
        self.assertNotIn("token_hashed", data)

    # Each one: Arrange -> Act -> Assert, like the example above.
    # Delete the skipTest line when you start filling one in.
    def test_register_rejects_invalid_public_key(self):
        """POST a register body whose public_key is garbage -> expect 400."""
        body = {
            "name": "bad-key-device",
            "platform": "desktop",
            "public_key": "not a key",
            "fingerprint": uuid.uuid4().hex,
        }
        response = self.client.post(REGISTER, json=body)
        self.assertEqual(response.status_code, 400, response.text)

    def test_register_rejects_unknown_platform(self):
        """platform="toaster" -> expect 422 (Pydantic/enum validation)."""
        body = {
            "name": "bad-platform-device",
            "platform": "not a valid platform",
            "public_key": public_pem(new_key()),
            "fingerprint": uuid.uuid4().hex,
        }
        response = self.client.post(REGISTER, json=body)
        self.assertEqual(response.status_code, 422, response.text)

    def test_register_same_key_twice_conflicts(self):
        """Register the same key twice -> second response is 409."""
        key = new_key()
        self.register(key)

        body = {
            "name": "device",
            "platform": "desktop",
            "public_key": public_pem(key),
            "fingerprint": uuid.uuid4().hex,
        }
        response = self.client.post(REGISTER, json=body)
        self.assertEqual(response.status_code, 409, response.text)

    def test_challenge_for_unknown_device_is_404(self):
        """Request a challenge for a random uuid that was never registered -> 404."""
        response = self.client.post(CHALLENGE, json={"device_id": str(uuid.uuid4())})
        self.assertEqual(response.status_code, 404, response.text)
        self.assertNotIn("data", response.json())

    def test_signature_from_wrong_key_is_rejected(self):
        """Valid device and challenge, but signed with a different key → 401"""
        key = new_key()
        device_id = self.register(key)
        challenge = self.get_challenge(device_id)

        response = self.verify(device_id, challenge, sign(new_key(), challenge))
        self.assertEqual(response.status_code, 401, response.text)
        self.assertNotIn("data", response.json())

    def test_challenge_cannot_be_reused(self):
        """Verify once (200), then send the exact same request again -> 401."""
        key = new_key()
        device_id = self.register(key)
        challenge = self.get_challenge(device_id)
        signature = sign(key, challenge)

        first = self.verify(device_id, challenge, signature)
        second = self.verify(device_id, challenge, signature)

        # successfully verified the challenge
        self.assertEqual(first.status_code, 200, first.text)

        # the challenge should have been deleted after usage
        self.assertEqual(second.status_code, 401, second.text)

    def test_expired_challenge_is_rejected(self):
        """Get a challenge, set its expires_at to 0 in the database, verify -> 401.
        Hint: `with DatabaseConnection() as conn:` + an UPDATE statement."""
        key = new_key()
        device_id = self.register(key)
        challenge = self.get_challenge(device_id)
        signature = sign(key, challenge)

        with DatabaseConnection() as conn:
            cursor = conn.execute(
                "UPDATE auth_challenge SET expires_at = 0 WHERE challenge = ?",
                (challenge,),
            )
            self.assertEqual(cursor.rowcount, 1)

        response = self.verify(device_id, challenge, signature)

        # challenge expired
        self.assertEqual(response.status_code, 401, response.text)

    def test_challenge_for_other_device_is_rejected(self):
        """Register A and B. Get a challenge for A. Submit it as B, signed with B's key -> 401."""
        key_a = new_key()
        device_id_a = self.register(key_a)
        challenge_a = self.get_challenge(device_id_a)

        key_b = new_key()
        device_id_b = self.register(key_b)

        signature = sign(key_b, challenge_a)
        response = self.verify(device_id_b, challenge_a, signature)

        self.assertEqual(response.status_code, 401, response.text)

    def test_garbage_signature_is_401_not_500(self):
        """Signature that isn't valid base64 -> 401, not a server crash."""
        key = new_key()
        device_id = self.register(key)

        for bad in ["%%% not base64 %%%", "", base64.b64encode(b"short").decode()]:
            with self.subTest(signature=bad):
                challenge = self.get_challenge(device_id)
                response = self.verify(device_id, challenge, bad)
                self.assertEqual(response.status_code, 401, response.text)

    def test_made_up_challenge_is_rejected(self):
        """A challenge the server never issued, correctly signed -> 401."""

        key = new_key()
        device_id = self.register(key)
        fake_challenge = base64.b64encode(secrets.token_bytes(32)).decode()
        signature = sign(key, fake_challenge)
        response = self.verify(device_id, fake_challenge, signature)

        self.assertEqual(response.status_code, 401, response.text)

    def test_me_invalid_authorization_header(self):
        """Garbage Bearer token → 401."""
        response = self.client.get(
            ME,
            headers={"Authorization": "Bearer some-random-token"},
        )

        self.assertEqual(response.status_code, 401, response.text)

    def test_me_no_authorization_header(self):
        """No Authorization header → 401."""
        response = self.client.get(
            ME,
        )

        self.assertEqual(response.status_code, 401, response.text)


if __name__ == "__main__":
    unittest.main()
