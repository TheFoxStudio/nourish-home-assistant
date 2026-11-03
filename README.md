# Nourish for Home Assistant

A HACS custom integration for Nourish food and water tracking. Imports your existing history, then keeps it synchronized using the account-scoped Home Assistant pull API.

Author: **Sascha Fuchs**.
Licensed under MIT.

## Features

- Seven sensors for today's calories (kcal), protein, carbohydrates, fat, fiber, sugar (g), and water (mL).
- Seven long-term daily consumption statistics, including history from before installation.
- Configurable polling from 1 to 43,200 minutes; default 15 minutes.
- Persistent records and cursor, incremental updates, deletions, backdated corrections, and automatic full export after an expired cursor (HTTP 410).
- UI setup, polling options, token replacement, and authentication recovery. Multiple accounts on the same server are supported.
- HTTPS only, bearer authentication, no redirects, and no token or response-body logging.


## Install

After this repository has been uploaded to GitHub:

1. In HACS, open **Custom repositories**, add this repository's GitHub URL, and choose **Integration**.
2. Download **Nourish** and restart Home Assistant.
3. Open **Settings > Devices & services > Add integration > Nourish**.
4. Enter the server origin (default `https://food.orktork.space`), API token, and polling interval in minutes.

Manual installation: copy `custom_components/nourish` into your Home Assistant `config/custom_components` directory and restart Home Assistant. Requires Home Assistant 2026.3 or newer and Recorder enabled.

Use the integration's **Configure** option to change the interval. Use **Reconfigure** to replace a token for the same account and server. Invalid or revoked tokens trigger Home Assistant's reauthentication flow.

## Historical graphs

Today's sensor entities are measurements. Their automatically generated long-term statistics describe sampled values during the day. For **amounts consumed per day, week, or month, including imported history**, use the separate external statistics. Each sensor exposes its associated ID in the `daily_statistic_id` attribute, for example `nourish:YOUR_ENTRY_ID_calories`.

Example Lovelace card, replacing the IDs with the attributes from your sensors:

```yaml
type: statistics-graph
title: Nourish daily calories
chart_type: bar
period: day
days_to_show: 30
stat_types:
  - change
entities:
  - nourish:YOUR_ENTRY_ID_calories
```

Create a separate card for water and macros because their units differ. Use `change` with `day`, `week`, or `month` periods to show consumption totals. The daily statistic `state` is that day's total; its `sum` is a cumulative total used by Home Assistant to calculate changes.

The API supplies consumption dates, without an intraday breakdown or a specified account time zone. The integration interprets these dates in **Home Assistant's configured time zone**. Each daily statistic is labeled at local noon (rounded down to a UTC hour for Recorder, including fractional-offset time zones). This is a daily total, not an hourly intake measurement. The current day's point can therefore have a timestamp later than the current time. Use matching time zones in Nourish and Home Assistant. Today resets locally at midnight even between polls; new app records appear after the next successful pull.

A zero baseline precedes the first imported day so the first day's consumption counts. Missing dates are zero. Edits rebuild cumulative statistics, including subsequent days, so backdated records and deletions do not double count. Removed daily-total records are retained as zero-valued dates, including across a new initial export.

## Synchronization and storage

The first setup validates the API with an export. Integration startup then performs and commits its own initial export. Later polls request `/api/ha/updates` with the saved cursor. Setup therefore makes two initial API calls; no destructive server-side cursor is used.

All exported collections and singleton objects are stored by ID in Home Assistant's `.storage/nourish.<entry_id>` file. The records and cursor are saved as one snapshot only after validating the entire response. Statistics imports replace existing timestamps. After every restart, the snapshot's complete historical statistics are replayed, so an interruption between saving and Recorder processing can recover. If fetching or validation fails, the previous committed cursor remains usable. Unchanged pulls do not rebuild statistics during normal operation.

HTTP 429 respects both numeric and HTTP-date `Retry-After` headers; the next scheduled poll after the deadline retries. HTTP 401 starts reauthentication. Other errors leave entities unavailable until a successful poll. HTTP 410 triggers a fresh export. Changing the token also forces a fresh export, while retaining dates needed to zero deleted history. Very long intervals can expire the 30-day cursor and cause another export.

The token is stored in Home Assistant's standard config-entry storage. The local snapshot includes your food history and account/goal-profile information, including physical details provided by the API. Protect Home Assistant configuration files and backups accordingly. These details are not exposed as entity attributes. Removing the integration deletes its local synchronization snapshot. Recorder statistics remain until you remove them through Home Assistant's statistics management.

## Expected API record shape

The supplied API description specifies the protocol but does not provide a complete JSON example. The implementation expects these daily-total field names:

```json
{
  "id": "daily-total-id",
  "date": "2026-11-03",
  "calories": 2100,
  "protein": 130,
  "carbs": 250,
  "fat": 65,
  "fiber": 30,
  "sugar": 45,
  "waterMl": 2200
}
```

`consumptionDate` or an ISO-date `id` also work instead of `date`. Metrics must be complete, finite, nonnegative numbers. All five collection keys must be present as arrays in an initial export, and `account` must contain `id`. The API client accepts schema version 1 only. Confirm these field names against a real backend response before release; adjust `model.py` if the backend uses different names. No live account token was supplied for end-to-end testing.

## Development

```sh
python -m pip install pytest pytest-asyncio aiohttp ruff
python -m pytest -q
ruff check .
ruff format --check custom_components tests
python scripts/build_release.py
```

Tests exercise full exports, incremental replacement, deletion, idempotent retries, validation, authentication, rate limits, and historical cumulative statistics. The Linux GitHub Actions workflow additionally imports the integration against an installed Home Assistant runtime and runs HACS validation. Local tests do not start a full Home Assistant instance.
