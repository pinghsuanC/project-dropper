"""
Desktop client tests: the pairing QR payload.

The QR is part of the desktop <-> phone contract (see API.md, Pairing): the phone
reads `pairing_token` from it and sends it unchanged to /pairing-request/claim.

Run from inside desktop/:
    python -m unittest discover -s tests -v
"""

import json
import unittest
from unittest import mock

from app.desktop_client import DesktopClient


class PairingQrTests(unittest.TestCase):
    def qr_payload(self, pairing_token: str) -> dict:
        """Call _show_qr with qrcode mocked out; return the JSON put into the QR."""
        with mock.patch("app.desktop_client.qrcode.QRCode") as qr_class:
            DesktopClient()._show_qr(pairing_token)

        qr = qr_class.return_value
        qr.add_data.assert_called_once()
        qr.print_ascii.assert_called_once()
        return json.loads(qr.add_data.call_args.args[0])

    def test_qr_contains_pairing_token(self):
        payload = self.qr_payload("abc123-token")
        self.assertEqual(payload, {"pairing_token": "abc123-token"})

    def test_qr_key_matches_claim_body(self):
        """Same key the server's claim endpoint expects, so the phone can pass it through."""
        payload = self.qr_payload("tok")
        self.assertIn("pairing_token", payload)
        self.assertNotIn("pairing_code", payload)


if __name__ == "__main__":
    unittest.main()
