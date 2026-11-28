"""
api_session tests: which requests get the Cloudflare Access headers.

No network: requests.Session.request (the parent method ApiSession calls) is mocked,
and the test reads the headers it was given.

Run from inside desktop/:
    python -m unittest discover -s tests -v
"""

import os
import unittest
from unittest import mock

import requests

# config.py requires API_BASE_URL; give tests a value if the env / .env has none.
os.environ.setdefault("API_BASE_URL", "http://127.0.0.1:8000")

import api_session

API = "https://dropper.example.dev"
CF_HEADERS = {
    "CF-Access-Client-Id": "desktop-id.access",
    "CF-Access-Client-Secret": "desktop-secret",
}


class ApiSessionTests(unittest.TestCase):
    def setUp(self):
        # Point the module at a fixed API origin and token, whatever .env says
        patches = [
            mock.patch.object(
                api_session, "_API_ORIGIN", ("https", "dropper.example.dev")
            ),
            mock.patch.object(api_session, "_CF_ACCESS_HEADERS", dict(CF_HEADERS)),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def sent_headers(self, method: str, url: str, **kwargs) -> dict:
        """Send through a fresh ApiSession; return the headers passed to requests."""
        with mock.patch.object(requests.Session, "request") as parent_request:
            getattr(api_session.ApiSession(), method)(url, **kwargs)
        parent_request.assert_called_once()
        return parent_request.call_args.kwargs.get("headers") or {}

    def test_api_request_gets_cloudflare_headers(self):
        headers = self.sent_headers("get", f"{API}/health")
        self.assertEqual(headers, CF_HEADERS)

    def test_post_keeps_callers_headers_and_adds_cloudflare(self):
        headers = self.sent_headers(
            "post",
            f"{API}/files/finish-download",
            headers={"Authorization": "Bearer tok"},
            json={"file_ids": []},
        )
        self.assertEqual(headers, {"Authorization": "Bearer tok", **CF_HEADERS})

    def test_callers_own_cloudflare_header_wins(self):
        headers = self.sent_headers(
            "get", f"{API}/health", headers={"CF-Access-Client-Id": "override"}
        )
        self.assertEqual(headers["CF-Access-Client-Id"], "override")
        self.assertEqual(headers["CF-Access-Client-Secret"], "desktop-secret")

    def test_callers_headers_dict_is_not_modified(self):
        mine = {"Authorization": "Bearer tok"}
        self.sent_headers("get", f"{API}/auth/me", headers=mine)
        self.assertEqual(mine, {"Authorization": "Bearer tok"})

    def test_r2_presigned_url_gets_no_cloudflare_headers(self):
        url = "https://acc.r2.cloudflarestorage.com/bucket/key?X-Amz-Signature=abc"
        headers = self.sent_headers("put", url, data=b"bytes")
        self.assertNotIn("CF-Access-Client-Id", headers)
        self.assertNotIn("CF-Access-Client-Secret", headers)

    def test_lookalike_host_gets_no_cloudflare_headers(self):
        """A plain string-prefix check would match this; the origin check doesn't."""
        headers = self.sent_headers("get", "https://dropper.example.dev.evil.com/x")
        self.assertEqual(headers, {})

    def test_other_scheme_gets_no_cloudflare_headers(self):
        headers = self.sent_headers("get", "http://dropper.example.dev/health")
        self.assertEqual(headers, {})

    def test_unset_token_sends_no_cloudflare_headers(self):
        """Local dev: no token configured -> no empty CF headers sent."""
        with mock.patch.object(
            api_session,
            "_CF_ACCESS_HEADERS",
            {"CF-Access-Client-Id": None, "CF-Access-Client-Secret": None},
        ):
            headers = self.sent_headers("get", f"{API}/health")
        self.assertEqual(headers, {})

    def test_module_exposes_one_shared_session(self):
        self.assertIsInstance(api_session.api, api_session.ApiSession)
        self.assertIsInstance(api_session.api, requests.Session)


if __name__ == "__main__":
    unittest.main()
