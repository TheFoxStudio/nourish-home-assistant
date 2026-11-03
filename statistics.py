"""Import deterministic, correctable daily cumulative statistics."""

from datetime import date, datetime, time, timedelta

from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.components.recorder.statistics import async_add_external_statistics
from homeassistant.util import dt as dt_util

from .const import DOMAIN, METRICS
from .model import daily_values


def import_statistics(hass, entry_id, state):
    """Rebuild cumulative sums so backdated edits also repair subsequent days.

    Daily totals have no intraday precision. Label them at local noon, rounded
    down to a UTC hour to satisfy Recorder, including fractional-offset zones.
    A zero baseline on the previous day preserves the first day's change.
    """
    totals = daily_values(state["dailyTotals"])
    days = state["known_days"]
    if not days:
        return
    first = date.fromisoformat(days[0]) - timedelta(days=1)
    last = max(date.fromisoformat(days[-1]), dt_util.now().date())
    for key, (name, unit, _, unit_class) in METRICS.items():
        rows = []
        cumulative = 0.0
        day = first
        while day <= last:
            value = totals.get(day.isoformat(), {}).get(key, 0.0)
            cumulative += value
            start = dt_util.as_utc(
                datetime.combine(day, time(12), tzinfo=dt_util.DEFAULT_TIME_ZONE)
            )
            start = start.replace(minute=0, second=0, microsecond=0)
            rows.append({"start": start, "state": value, "sum": cumulative})
            day += timedelta(days=1)
        metadata = {
            "statistic_id": f"{DOMAIN}:{entry_id}_{key.lower()}",
            "source": DOMAIN,
            "name": f"Nourish {name} (daily)",
            "unit_of_measurement": unit,
            "unit_class": unit_class,
            "mean_type": StatisticMeanType.NONE,
            "has_sum": True,
        }
        for offset in range(0, len(rows), 1000):
            async_add_external_statistics(hass, metadata, rows[offset : offset + 1000])
