from urllib.parse import urlsplit

import requests

import config

# One shared HTTP session for the whole desktop client. It adds the desktop's
# Cloudflare Access service-token headers to every request sent to our API server,
# so the client modules don't each have to build them.
#
# Only requests to API_BASE_URL get the headers. Presigned R2 URLs (uploads and
# downloads) go to a different host and must never receive the service token.

# Scheme + host + port of the API server, e.g. ("https", "dropper.example.dev")
_API_ORIGIN = urlsplit(config.API_BASE_URL)[:2]

# Cloudflare Access (optional: unset in local dev, where Cloudflare isn't in front)
_CF_ACCESS_HEADERS = {
    "CF-Access-Client-Id": config.CLOUDFLARE_SERVICE_TOKEN_CLIENT_ID,
    "CF-Access-Client-Secret": config.CLOUDFLARE_SERVICE_TOKEN_CLIENT_SECRET,
}


def _is_api_url(url: str) -> bool:
    """True only for our server. Compares the origin, not a string prefix, so a
    host like `<api host>.attacker.com` doesn't match."""
    return urlsplit(url)[:2] == _API_ORIGIN


class ApiSession(requests.Session):
    def request(self, method, url, **kwargs):
        if _is_api_url(url):
            # copy, so a headers dict the caller reuses isn't changed
            headers = dict(kwargs.get("headers") or {})
            for name, value in _CF_ACCESS_HEADERS.items():
                if value:  # skip when not configured (local dev)
                    headers.setdefault(name, value)
            kwargs["headers"] = headers
        return super().request(method, url, **kwargs)


api = ApiSession()
