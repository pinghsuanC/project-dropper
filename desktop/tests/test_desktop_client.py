"""
Desktop client tests: the two QR payloads shown to the phone.

Both QRs are part of the desktop <-> phone contract:
- config QR: the mobile Cloudflare Access service token, which the phone keeps in
  secure storage.
- pairing QR: `pairing_token`, which the phone sends unchanged to
  /pairing-request/claim.

Run from inside desktop/:
    python -m unittest discover -s tests -v
"""

import json
import os
import unittest
from unittest import mock

# config.py requires API_BASE_URL; give tests a value if the env / .env has none.
os.environ.setdefault("API_BASE_URL", "http://127.0.0.1:8000")

from app import desktop_client
from app.desktop_client import DesktopClient

CLIENT_ID_VAR = "CLOUDFLARE_SERVICE_TOKEN_CLIENT_ID_MOBILE"
SECRET_VAR = "CLOUDFLARE_SERVICE_TOKEN_CLIENT_SECRET_MOBILE"


def captured_qr_payload(print_qr) -> dict:
    """Run a _print_*_qr method with qrcode mocked out; return the JSON put into the QR."""
    with mock.patch("app.desktop_client.qrcode.QRCode") as qr_class:
        print_qr()

    qr = qr_class.return_value
    qr.add_data.assert_called_once()
    qr.print_ascii.assert_called_once()
    return json.loads(qr.add_data.call_args.args[0])


class ConfigQrTests(unittest.TestCase):
    def config_payload(self, client_id: str | None, access_key: str | None) -> dict:
        # desktop_client imported the values from config, so patch them there
        with (
            mock.patch.object(desktop_client, CLIENT_ID_VAR, client_id),
            mock.patch.object(desktop_client, SECRET_VAR, access_key),
        ):
            return captured_qr_payload(DesktopClient()._print_config_qr)

    def test_config_qr_contains_mobile_cloudflare_token(self):
        payload = self.config_payload("cf-id.access", "cf-secret")
        self.assertEqual(
            payload,
            {
                "cloudflare_client_id": "cf-id.access",
                "cloudflare_access_key": "cf-secret",
            },
        )

    def test_config_qr_has_no_pairing_token(self):
        payload = self.config_payload("id", "secret")
        self.assertNotIn("pairing_token", payload)

    def test_missing_env_gives_null_credentials(self):
        """Local dev without the env vars: keys are still present, values are null."""
        payload = self.config_payload(None, None)
        self.assertIsNone(payload["cloudflare_client_id"])
        self.assertIsNone(payload["cloudflare_access_key"])


class PairingQrTests(unittest.TestCase):
    def pairing_payload(self, pairing_token: str) -> dict:
        return captured_qr_payload(
            lambda: DesktopClient()._print_pairing_qr(pairing_token)
        )

    def test_pairing_qr_contains_only_the_token(self):
        payload = self.pairing_payload("abc123-token")
        self.assertEqual(payload, {"pairing_token": "abc123-token"})

    def test_pairing_qr_key_matches_claim_body(self):
        """Same key the server's claim endpoint expects, so the phone can pass it through."""
        payload = self.pairing_payload("tok")
        self.assertEqual(payload["pairing_token"], "tok")
        self.assertNotIn("pairing_code", payload)


if __name__ == "__main__":
    unittest.main()
