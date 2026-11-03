"""Read-only Nourish API client. Never include credentials in exceptions."""

import asyncio
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

import aiohttp


class NourishError(Exception):
    """API or response error."""


class InvalidAuth(NourishError):
    """Token was rejected."""


class ExpiredCursor(NourishError):
    """A new export is required."""


class RateLimited(NourishError):
    """Rate limited, with a retry deadline."""

    def __init__(self, seconds):
        super().__init__("API rate limit reached")
        self.seconds = seconds


def normalize_url(value):
    """Require HTTPS, no embedded secrets, query, or fragment."""
    value = value.strip().rstrip("/")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
    ):
        raise ValueError("Enter an HTTPS server origin")
    return value


class NourishApi:
    """Use HA's shared session; reject redirects to protect the bearer token."""

    def __init__(self, session, url, token):
        self.session = session
        self.url = normalize_url(url)
        self.token = token

    async def fetch(self, cursor=None):
        path = "/api/ha/export" if cursor is None else "/api/ha/updates"
        try:
            async with self.session.get(
                self.url + path,
                params=None if cursor is None else {"cursor": cursor},
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=aiohttp.ClientTimeout(total=60),
                allow_redirects=False,
            ) as response:
                if response.status == 401:
                    raise InvalidAuth("API token rejected")
                if response.status == 410:
                    raise ExpiredCursor("Cursor expired")
                if response.status == 429:
                    retry = response.headers.get("Retry-After", "60")
                    try:
                        seconds = float(retry)
                    except ValueError:
                        try:
                            seconds = (
                                parsedate_to_datetime(retry) - datetime.now(timezone.utc)
                            ).total_seconds()
                        except ValueError, TypeError, OverflowError:
                            seconds = 60
                    raise RateLimited(max(1, seconds))
                if response.status != 200:
                    raise NourishError(f"API returned HTTP {response.status}")
                payload = await response.json()
        except aiohttp.ClientError, asyncio.TimeoutError, ValueError:
            raise NourishError("Unable to read Nourish response") from None
        if not isinstance(payload, dict) or payload.get("schemaVersion") != 1:
            raise NourishError("Unsupported API schema")
        if not isinstance(payload.get("cursor"), str) or not payload["cursor"]:
            raise NourishError("Response is missing its cursor")
        return payload
