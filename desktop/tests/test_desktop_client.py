"""
Desktop client tests: the pairing QR payload.

The QR is part of the desktop <-> phone contract (see API.md, Pairing): the phone
reads `pairing_token` and sends it unchanged to /pairing-request/claim, and stores
`client_id` / `access_key` (Cloudflare Access service token) in secure storage.

Run from inside desktop/:
    python -m unittest discover -s tests -v
"""

import json
import unittest
from unittest import mock

from app import desktop_client
from app.desktop_client import DesktopClient

CLIENT_ID_VAR = "_CLOUDFLARE_SERVICE_TOKEN_CLIENT_ID_MOBILE"
SECRET_VAR = "_CLOUDFLARE_SERVICE_TOKEN_CLIENT_SECRET_MOBILE"


class PairingQrTests(unittest.TestCase):
    def qr_payload(
        self, pairing_token: str, client_id: str | None, access_key: str | None
    ) -> dict:
        """Call _print_qr with qrcode mocked out; return the JSON put into the QR.

        The Cloudflare values are read from the env when the module is imported,
        so the module-level constants are patched instead of the env.
        """
        with (
            mock.patch.object(desktop_client, CLIENT_ID_VAR, client_id),
            mock.patch.object(desktop_client, SECRET_VAR, access_key),
            mock.patch("app.desktop_client.qrcode.QRCode") as qr_class,
        ):
            DesktopClient()._print_qr(pairing_token)

        qr = qr_class.return_value
        qr.add_data.assert_called_once()
        qr.print_ascii.assert_called_once()
        return json.loads(qr.add_data.call_args.args[0])

    def test_qr_contains_token_and_cloudflare_credentials(self):
        payload = self.qr_payload("abc123-token", "cf-id.access", "cf-secret")
        self.assertEqual(
            payload,
            {
                "pairing_token": "abc123-token",
                "client_id": "cf-id.access",
                "access_key": "cf-secret",
            },
        )

    def test_qr_key_matches_claim_body(self):
        """Same key the server's claim endpoint expects, so the phone can pass it through."""
        payload = self.qr_payload("tok", "id", "secret")
        self.assertEqual(payload["pairing_token"], "tok")
        self.assertNotIn("pairing_code", payload)

    def test_missing_env_gives_null_credentials(self):
        """Local dev without the env vars: keys are still present, values are null."""
        payload = self.qr_payload("tok", None, None)
        self.assertIsNone(payload["client_id"])
        self.assertIsNone(payload["access_key"])


if __name__ == "__main__":
    unittest.main()
