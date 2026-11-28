"""
The client modules in app/apis send the Cloudflare Access token to our server,
and never to R2.

No network: requests.Session.request is mocked. Both the shared `api` session and
plain `requests.put/get` end up there, so every request the code makes is recorded
with its URL and headers.

Run from inside desktop/:
    python -m unittest discover -s tests -v
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import requests

# config.py requires API_BASE_URL; give tests a value if the env / .env has none.
os.environ.setdefault("API_BASE_URL", "http://127.0.0.1:8000")

import api_session
from app.apis import auth_apis, file_apis, pairing_apis
from config import API_BASE_URL

R2_UPLOAD_URL = "https://acc.r2.cloudflarestorage.com/bucket/obj?X-Amz-Signature=up"
CF_HEADERS = {
    "CF-Access-Client-Id": "desktop-id.access",
    "CF-Access-Client-Secret": "desktop-secret",
}


def fake_response(body: dict) -> mock.Mock:
    response = mock.Mock(ok=True, status_code=200)
    response.json.return_value = body
    response.raise_for_status.return_value = None
    return response


class ApisUseSessionTests(unittest.TestCase):
    def setUp(self):
        self.calls = []  # (method, url, headers) for every request made

        def record(method, url, **kwargs):
            self.calls.append((method.upper(), url, kwargs.get("headers") or {}))
            if url.endswith("/files/prepare-upload"):
                return fake_response(
                    {
                        "message": "ok",
                        "data": {"file_id": "f1", "upload_url": R2_UPLOAD_URL},
                    }
                )
            if url.endswith("/files/finish-upload"):
                return fake_response({"message": "ok", "data": {"file_id": "f1"}})
            if url.endswith("/devices/paired"):
                return fake_response({"message": "ok", "data": {"device": None}})
            return fake_response({"status": "ok"})

        patches = [
            mock.patch.object(requests.Session, "request", side_effect=record),
            mock.patch.object(api_session, "_CF_ACCESS_HEADERS", dict(CF_HEADERS)),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def assert_has_cf_headers(self, headers: dict):
        for name, value in CF_HEADERS.items():
            self.assertEqual(headers.get(name), value)

    def assert_no_cf_headers(self, headers: dict):
        for name in CF_HEADERS:
            self.assertNotIn(name, headers)

    def test_health_check_sends_cloudflare_headers(self):
        auth_apis.check_health()

        method, url, headers = self.calls[0]
        self.assertEqual((method, url), ("GET", f"{API_BASE_URL}/health"))
        self.assert_has_cf_headers(headers)

    def test_authorized_call_sends_bearer_and_cloudflare_headers(self):
        pairing_apis.get_paired_device("tok")

        _, url, headers = self.calls[0]
        self.assertEqual(url, f"{API_BASE_URL}/devices/paired")
        self.assertEqual(headers["Authorization"], "Bearer tok")
        self.assert_has_cf_headers(headers)

    def test_upload_sends_token_to_server_but_not_to_r2(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "note.txt"
            path.write_text("hello")
            with mock.patch.object(
                file_apis.DeviceHelper, "load_device_id", return_value="me"
            ):
                file_apis.upload_file("tok", str(path))

        by_url = {url: headers for _, url, headers in self.calls}
        self.assertEqual(
            [url for _, url, _ in self.calls],
            [
                f"{API_BASE_URL}/files/prepare-upload",
                R2_UPLOAD_URL,
                f"{API_BASE_URL}/files/finish-upload",
            ],
        )
        self.assert_has_cf_headers(by_url[f"{API_BASE_URL}/files/prepare-upload"])
        self.assert_has_cf_headers(by_url[f"{API_BASE_URL}/files/finish-upload"])
        # the R2 PUT gets neither the Cloudflare token nor the session token
        self.assert_no_cf_headers(by_url[R2_UPLOAD_URL])
        self.assertNotIn("Authorization", by_url[R2_UPLOAD_URL])


if __name__ == "__main__":
    unittest.main()
