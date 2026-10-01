# School and Mobility

School owns confirmed school facts: school days, end times, pickup rules and
school events. Mobility owns routes, departures and travel status. The VVS API
provides transport data. Real people, school records, stop preferences and
credentials stay in SQLite or environment files outside this repository.

Names resolve through the existing PeopleManager, scoped to the current
speaker. Unknown or duplicate names require clarification. A pickup journey
uses the adult speaker's mobility profile; the child's existing `person_id`
selects School records. School does not store bus lines or route preferences.

Supported German text/voice questions include:

- `Wann hat <Name> heute aus?`
- `Muss ich <Name> heute abholen?`
- `Wann muss ich los, um <Name> abzuholen?`
- `Wann muss <Name> heute zur Schule los?`

The first two need no route request. Pickup planning requires an explicit
pickup rule, destination and arrival deadline. School-arrival planning uses a
School travel event; Mobility matches the event to configured route rules.
Unknown data stays unknown. Approximate school end remains approximate.

## Local configuration

Sleepy reads `WIMAEDV_VVS_BASE_URL` and optional `WIMAEDV_VVS_API_KEY` from its
environment. The local instance is `wimaedv-vvs-api.service` on
`http://127.0.0.1:8088`. School and Mobility database paths point to external
storage. Do not add private records, stop IDs, schedules or secrets here.
An unset URL returns `NOT_CONFIGURED`; connection failures return
`UNAVAILABLE`. The adapter refuses redirects.

The local API provides `/api/v1/stops/{id}/departures` and `/api/v1/journeys`.
Health checks use `/health` and `/ready`. Static stop mappings must be verified
against that API before use.

## Realtime demand and status

The existing ReminderManager scheduler derives demand windows from School
travel events and Mobility route rules. It owns no second polling thread.
No active journey demand means `DORMANT` and zero periodic Realtime requests.
Upcoming travel uses `WATCH` (vehicles and trip updates every 300 seconds,
alerts every 900 seconds). A near or active journey uses `ACTIVE` (vehicles
every 45 seconds, trip updates every 90 seconds, alerts every 300 seconds).
Direct lookups remain available in `DORMANT`. Demand leases expire after their
configured lifetime and are released when the existing scheduler stops.

`REALTIME` requires complete estimated departure and arrival times on every
transit leg. Partial estimates produce `DEGRADED`; no estimates produce
`SCHEDULE_ONLY`. Feed age and explicit canceled-trip records are derived from
the API feed schema. A stale Realtime feed degrades the route; cancellation is
reported only when the feed explicitly identifies the matched trip as canceled.
Missing GTFS-RT fields remain absent. `STATIC_DATA_STALE` is not implemented
because the API does not expose verified static-data age metadata.

## Real Sleepy E2E

Check the local API first:

```bash
systemctl is-active wimaedv-vvs-api.service
curl --fail http://127.0.0.1:8088/health
curl --fail http://127.0.0.1:8088/ready
```

Run Sleepy text mode with the real speaker identity, then enter the supported
questions using a configured person's name:

```bash
cd /mnt/c/Users/Alex/Projekte/JARVIS-Sleepy/Main
/home/alex/jarvis-venv/bin/python jarvis_console.py --text --user '<SPEAKER_USER_ID>'
```

Verify School answers against the external School database. Verify journeys
against current API responses. Unit-test fixtures are synthetic and do not
count as live evidence. Realtime feed states can differ by feed and age.

## Tests

Run the full Unit suite:

```bash
wsl.exe -d Ubuntu-24.04 --cd /mnt/c/Users/Alex/Projekte/JARVIS-Sleepy/Main -- env OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 HF_HUB_OFFLINE=1 /home/alex/jarvis-venv/bin/python -m pytest tests/unit -q
```

Mobile Routing and Router standalone tests require local model services. HTTP
fixtures in unit tests are synthetic. Separate live smoke checks should query
health, readiness, vehicles, alerts, departures and EFA journeys directly;
never report synthetic test results as live API verification.
