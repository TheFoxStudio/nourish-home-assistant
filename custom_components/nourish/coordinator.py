"""Persistent cursor synchronization and statistics replay."""

from datetime import timedelta
from hashlib import sha256
import logging
import time

from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.util import dt as dt_util

from .api import ExpiredCursor, InvalidAuth, NourishError, RateLimited
from .const import DOMAIN, CONF_INTERVAL, DEFAULT_INTERVAL
from .model import apply_response, daily_values
from .statistics import import_statistics

_LOGGER = logging.getLogger(__name__)


class NourishCoordinator(DataUpdateCoordinator):
    """Store a transaction before publishing it; replay statistics after restart."""

    def __init__(self, hass, entry, api):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(
                minutes=entry.options.get(
                    CONF_INTERVAL, entry.data.get(CONF_INTERVAL, DEFAULT_INTERVAL)
                )
            ),
        )
        self.entry = entry
        self.api = api
        self.store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")
        self.snapshot = None
        self.retry_at = 0
        self.replay = True
        self.statistics_day = None
        self.daily_totals = {}
        self.token_fingerprint = sha256(api.token.encode()).hexdigest()

    async def async_load(self):
        self.snapshot = await self.store.async_load()

    async def _async_update_data(self):
        if time.monotonic() < self.retry_at:
            raise UpdateFailed("Waiting for Nourish Retry-After")
        try:
            initial = (
                not self.snapshot
                or not self.snapshot.get("cursor")
                or self.snapshot.get("token_fingerprint") != self.token_fingerprint
            )
            try:
                payload = await self.api.fetch(None if initial else self.snapshot["cursor"])
            except ExpiredCursor:
                initial = True
                payload = await self.api.fetch()
            candidate = apply_response(self.snapshot, payload, initial=initial)
            candidate["token_fingerprint"] = self.token_fingerprint
            today = dt_util.now().date()
            changed = (
                self.replay
                or self.statistics_day != today
                or not self.snapshot
                or candidate["dailyTotals"] != self.snapshot["dailyTotals"]
                or candidate["known_days"] != self.snapshot["known_days"]
            )
            # Persist records and cursor together. If interrupted before Recorder
            # finishes, the next startup replays the complete stored snapshot.
            await self.store.async_save(candidate)
            if changed:
                import_statistics(self.hass, self.entry.entry_id, candidate)
            self.snapshot = candidate
            self.daily_totals = daily_values(candidate["dailyTotals"])
            self.statistics_day = today
            self.replay = False
            return candidate
        except InvalidAuth as err:
            raise ConfigEntryAuthFailed("Nourish token rejected") from err
        except RateLimited as err:
            self.retry_at = time.monotonic() + err.seconds
            raise UpdateFailed("Nourish rate limited the request") from err
        except NourishError, KeyError, TypeError, ValueError, OSError:
            # Do not expose server payloads, account details, URLs, or tokens.
            raise UpdateFailed("Unable to synchronize Nourish data") from None
