"""Pure synchronization logic, independent of Home Assistant."""

from copy import deepcopy
from datetime import date
import math

COLLECTIONS = ("foods", "meals", "nutritionEntries", "waterEntries", "dailyTotals")
SINGLETONS = ("account", "preferences", "goalProfile")
FIELDS = ("calories", "protein", "carbs", "fat", "fiber", "sugar", "waterMl")


def record_date(record):
    """The API's consumption date; ISO date IDs are also supported."""
    value = record.get("date", record.get("consumptionDate", record["id"]))
    return date.fromisoformat(str(value)).isoformat()


def daily_values(records):
    """Validate complete totals rather than silently accepting missing metrics."""
    result = {}
    for record in records.values():
        day = record_date(record)
        if day in result:
            raise ValueError("Duplicate daily total date")
        values = {}
        for field in FIELDS:
            raw = record[field]
            if isinstance(raw, bool):
                raise ValueError("Invalid nutrient value")
            value = float(raw)
            if not math.isfinite(value) or value < 0:
                raise ValueError("Invalid nutrient value")
            values[field] = value
        result[day] = values
    return result


def apply_response(previous, payload, *, initial):
    """Build a candidate transaction; never mutate the committed snapshot."""
    state = deepcopy(previous) if previous else {}
    section = payload["data" if initial else "changes"]
    if not isinstance(section, dict):
        raise ValueError("Invalid response data")
    old_days = set(state.get("known_days", []))
    if state.get("dailyTotals"):
        old_days.update(daily_values(state["dailyTotals"]))
    for name in COLLECTIONS:
        if initial:
            records = section[name]
            if not isinstance(records, list):
                raise ValueError("Invalid export collection")
            state[name] = {}
            for record in records:
                key = str(record["id"])
                if key in state[name]:
                    raise ValueError("Duplicate record ID")
                state[name][key] = record
        elif name in section:
            changes = section[name]
            for record in changes["upsert"]:
                state[name][str(record["id"])] = record
            for key in changes["deleted"]:
                state[name].pop(str(key), None)
    for name in SINGLETONS:
        if initial or name in section:
            state[name] = section[name]
    totals = daily_values(state["dailyTotals"])
    state["known_days"] = sorted(old_days | set(totals))
    state["cursor"] = payload["cursor"]
    state["generated_at"] = payload.get("generatedAt")
    return state
