# Mining fleet tracking

A fleet with **Track mining** on records the ore each member mines while
they are in the in-game fleet, from their ESI mining ledger, and shows it on
the fleet's **Mining** tab.

## Turning it on

| Where | What |
|---|---|
| Fleet form | **Track mining** switch (`EveFleet.track_mining`). Create, edit and copy keep it. |
| Tribe group settings | **Track mining by default** (`TribeGroup.track_mining_by_default`). A new fleet hosted by the group starts with the switch on; the FC can turn it off. Changing the setting never touches existing fleets. |

An alliance fleet starts with it off. A create request that leaves
`track_mining` out takes the host group's default.

## The rule

Per pilot and ore type, the fleet's ore is the sum over the pilot's stints of
`latest_totals - start_totals`.

- A **stint** (`EveFleetMiningSegment`) opens when the 30-second member poll
  first lists the pilot, or lists them again after they left. It ends when a
  poll no longer lists them (`EveFleetInstanceMember.left_at`) or the fleet
  ends.
- A **reading** syncs the pilot's ESI mining ledger, then sums every ledger
  row dated on or after the stint's start day (EVE time), in any system. No
  system or ship filter: ore mined in a neighbouring system or after a reship
  still counts. Summing from the start day keeps a fleet that crosses EVE
  midnight whole.
- Readings: one at the start, one about every 15 minutes while the fleet
  runs (`poll_fleet_mining`, every 5 minutes, queues the due ones), and one
  about 11 minutes after the stint ends, so ore mined in the last minutes
  reaches the ledger.
- A reading lower than the last one is ignored (a stale ESI cache, not lost
  ore).

## Statuses

| Stint | Meaning |
|---|---|
| `pending` | Waiting for the start reading (retried) |
| `open` | Being read live |
| `closing` | Ended; waiting for the end reading |
| `closed` | Final |
| `closed_stale` | The end reading failed; closed on the last good poll |
| `no_scope` | The character isn't on the site or hasn't granted `esi-industry.read_character_mining.v1` |
| `failed` | No start reading ever landed; counts nothing |

A pilot is **Measuring** while any stint waits for a reading, **Partial** if
any stint is `closed_stale` or `failed`, **No mining scope** if every stint is
`no_scope`, else **Done**.

## API

`GET /api/fleets/{fleet_id}/mining` (anyone who can see the fleet):
per-pilot ore with units, m³ (`EveType.volume`) and an ISK estimate (Jita
history average, `market.helpers.pricing.get_history_averages_by_type_id`),
fleet totals, `measuring` and `updated_at`. When the fleet hides its roster,
only its FC and Strategic FCs see every name; others see their own pilots by
name and the rest without a name or id.

The response also carries a `timeline` for the dispatch view: ore per pilot
per 15-minute bucket, read from the ledger deltas every pull stores
(`EveCharacterMiningDelta`, from both the character-sync scheduler and this
feature's readings). A delta belongs to a stint when it was seen after the
stint's start reading and no later than its last reading. Each pilot's
cells are `ore`, `quiet` (in the fleet, nothing seen in that bucket yet),
`idle` (in the fleet, no ore for 2+ buckets in a row: one empty bucket can
just mean no pull landed in it) or `out`. `mining_pct` is buckets with ore
over buckets in the fleet. `events` is a newest-first log of joins, leaves
and deltas (at most 200).

Buckets start at the fleet's start (to the minute), not on a clock quarter
hour, and a last bucket under a minute long is folded into the one before.
Ore the readings counted but no delta row timed (pulls from before delta
rows were stored, or a worker running older code) is drawn where the timed
ore starts, or at the last reading when there is none, so the chart's total
always matches the readings'.

The dispatch view (`FleetMiningDispatch.astro`) shows ore, m³ per hour and
the ISK estimate, the fleet's running total, and one strip per pilot. Roster
changes are snapped to the nearest bucket boundary and merged into one
marker (▲ joins, ▼ leaves), so a multiboxer dropping five characters is one
marker. Hovering a marker lists the pilots; clicking it (or Enter/Space)
opens the list in a panel under the chart. Joins at the fleet's start and
leaves at its end get no marker.

Where it shows (`partials/fleet_mining_component`, refreshing every 60
seconds while `measuring` is true):

| Fleet | Where |
|---|---|
| Live | The **Mining** tab |
| Over | The **After Action Report** tab, above the fights. The fights stay when the fleet also had a fight. There is no Mining tab. |

## Known limits

- ESI caches the ledger for 10 minutes (`Expires` is 10 minutes after
  `Date` on `/characters/{id}/mining/`), so a start reading can be that
  stale: ore mined in the few minutes before joining can count.
- In `CHARACTER_SYNC_MODE=scheduled` the character-sync scheduler also pulls
  fleet pilots' ledgers (every 15 minutes, 10 for hot miners), so live
  readings are pulled twice. The deltas both store feed the same timeline.
- A scope granted after a pilot's stint opened is only picked up on their
  next stint.
- Turning Track mining off on a running fleet doesn't stop open stints.
- The ledger also counts ice and gas; they show as their own lines.
- ESI keeps 30 days of ledger, so readings must happen during or soon after
  the fleet.
