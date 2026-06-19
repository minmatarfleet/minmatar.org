# Activity Feed — Verification Cases Research

Research date: 2026-06-19  
Sources: zKillboard REST API (`/api/killID/`, `/api/kills/systemID/`), ESI killmail payloads  
Plan reference: Activity Feed Ingestion plan §9–10  
User-Agent: `minmatar.org-feed-verification-research/1.0`

---

## Executive summary

Live zKill + ESI pulls confirm the **golden anchor kill 136398967** sits inside a real Minmatar-dominant Vard engagement that exceeds both `fleet_active` (5+ kills, 8+ unique attacker pilots / 20 min) and `killmail_batch` (8+ kills / 15 min). The ±30 min backfill window contains **31 kills** and **21 unique attacker pilots**, with Minmatar militia (`500002`) as the clear dominant faction.

Four additional positive cases were identified in monitored FW systems (Huola, Kourmonen, Vard) from the last 48 hours. Three negative controls were confirmed (Jita allowlist discard, NPC discard, solo below-threshold). **No clean Amarr-dominant (`500001`) fleet case** was found in the 7-day API sample — implementation should use a synthetic fixture or widen the history backfill window.

**Critical fixture bug:** `fw_monitored_systems.json` lists Huola as `30002756` (ESI: Ishomilken) and Kourmonen as `30002757` (ESI: Nikkishina). Correct IDs are **Huola `30003067`** and **Kourmonen `30003068`** (verified via ESI `/universe/systems/` and legacy fleet data). ESI `/fw/systems/` seed should be authoritative; the fixture fallback is wrong for two headline systems.

---

## Threshold reference (from plan)

| Rollup | Window | Min kills | Min pilots | Other |
|--------|--------|-----------|------------|-------|
| `killmail_batch` (`kill_burst`) | 15 min | 8 | — | Monitored FW system, non-NPC |
| `fleet_active` (`fleet_engagement`) | 20 min | 5 | 8 unique attacker `character_id`s | Dominant militia ≥40% of militia-tagged attacker rows (`500001` / `500002`); else pirate accent |
| `militia_joins` | 1 h / 24 h | — | — | ≥5 / ≥15 **first-seen** militia chars per faction |
| Ingest discard | — | — | — | Non-allowlist system, `zkb.npc=true` |

### Verified FW system IDs (ESI)

| System | Correct `solar_system_id` | Wrong ID in fixture |
|--------|---------------------------|---------------------|
| Vard | 30002538 | — |
| Huola | **30003067** | 30002756 (Ishomilken) |
| Kourmonen | **30003068** | 30002757 (Nikkishina) |
| Jita (negative) | 30000142 | — |
| Tama (negative) | 30002813 | — |

---

## Verification cases table

| # | Case | Killmail ID(s) | System | Time (UTC) | Kills / pilots (window) | Expected event | Rationale |
|---|------|----------------|--------|------------|-------------------------|----------------|-----------|
| **P1** | **Golden Minmatar fleet** (anchor) | 136398967 + 30 siblings (see below) | Vard `30002538` | 2026-06-19 16:55–17:55 (±30 min) | **31 kills / 21 pilots** (±30 min); **27 / 20** (±20 min); **17** kills in best 15 min | `fleet_active` (minmatar) + `killmail_batch` | All thresholds exceeded; `500002` dominant; anchor linked |
| **P2** | **Huola Minmatar fleet** | 136383906, 136383910, 136383929, 136383981, 136384020, 136384105, 136384107, 136384114, 136384116, 136384130 | Huola `30003067` | 2026-06-19 00:48–01:08 | **10 kills / 22 pilots** (20 min) | `fleet_active` (minmatar) | 5+ kills, 8+ pilots; zKill `fw:minmatar` labels |
| **P3** | **Kourmonen Minmatar fleet** | 136385448–136385705 (23-mail cluster) | Kourmonen `30003068` | 2026-06-19 02:50–03:00 | **23 kills / 51 pilots** (20 min) | `fleet_active` (minmatar) + `killmail_batch` | Large sustained fight; strongest non-golden fleet in sample |
| **P4** | **Vard post-anchor spike** | 136400562–136400629 | Vard `30002538` | 2026-06-19 18:39–18:42 | **10 kills / 13 pilots** (3 min span) | `killmail_batch` + `fleet_active` (likely **pirate** accent) | Meets numeric thresholds; zKill `fw:amarr` labels but ESI `faction_id` mostly absent (see gaps) |
| **P5** | **Militia newly-active proxy** | chars from P1 window | Vard `30002538` | ±1 h around anchor | **10 unique Minmatar militia chars** in killmails | `militia_joins` (minmatar) *if first-seen* | Meets ≥5/1h count proxy; cannot confirm first-seen via API alone |
| **N1** | **Jita trade hub** | 136400936 | Jita `30000142` | 2026-06-19 18:58:31 | 1 kill | **none** | Outside `FeedMonitoredSystem` allowlist |
| **N2** | **NPC in FW system** | 136386594 | Kourmonen `30003068` | recent | 1 kill | **none** | `zkb.npc=true` → ingest discard |
| **N3** | **Solo below-threshold** | 136400805 | Vard `30002538` | 2026-06-19 18:51:27 | 1 kill / 1 pilot | **none** (alone) | Isolated solo cannot satisfy fleet/burst thresholds |
| **N4** | **Unlisted nullsec** | 136400880 | Tama `30002813` | recent | 1 kill | **none** | FW-region-adjacent but not in Amarr–Minmatar FW allowlist |

---

## Golden kill engagement analysis (136398967)

### Anchor mail (ESI + zKill)

| Field | Value |
|-------|-------|
| `killmail_id` | 136398967 |
| `hash` | `fa607eb45b4a88c891d422d10f79ff234ef72907` |
| `solar_system_id` | 30002538 (Vard) |
| `killmail_time` | 2026-06-19T17:25:08Z |
| Attackers (ESI) | 9 rows, **8 unique pilots** with `character_id` |
| Militia attackers (anchor) | **8× `500002`** (Minmatar) |
| zKill labels | `#:5+`, `pvp`, `fw:minmatar`, `fw:amamin`, `npc:false`, `solo:false` |
| [zKill page](https://zkillboard.com/kill/136398967/) | — |

Single-mail ingest of 136398967 alone is **insufficient** for `fleet_active` (plan §9). Verification requires engagement backfill.

### ±30 min Vard window (ESI-verified, non-NPC)

All killmails from zKill Vard 24h feed with ESI times in `[16:55:08, 17:55:08]` UTC:

```
136398538, 136398548, 136398556, 136398640, 136398647, 136398672, 136398679,
136398682, 136398691, 136398781, 136398789, 136398792, 136398801, 136398806,
136398805, 136398812, 136398967, 136398970, 136398972, 136398973, 136398976,
136398981, 136398988, 136398992, 136398996, 136399016, 136399100, 136399113,
136399201, 136399207, 136399424
```

| Metric | ±30 min | ±20 min | ±15 min | Threshold | Pass? |
|--------|---------|---------|---------|-----------|-------|
| Kills | **31** | **27** | **21** | ≥5 (`fleet_active`), ≥8 (`killmail_batch`) | ✓ / ✓ |
| Unique attacker pilots | **21** | **20** | **20** | ≥8 (`fleet_active`) | ✓ |
| Unique Minmatar militia pilots | **10** | **10** | **10** | — | — |
| Unique Amarr militia pilots | **0** | **0** | **0** | — | — |
| Dominant militia faction | **500002** (Minmatar) | same | same | ≥40% militia rows | ✓ |
| Best 15-min burst | **17 kills** (starting 17:14:20 UTC) | — | — | ≥8 | ✓ |
| Anchor in set | yes | yes | yes | required | ✓ |

**Conclusion:** `backfill_engagement --anchor-killmail 136398967 --window-minutes 30` should produce a `FeedCluster` `fleet_engagement` for Vard + `500002`, and both `fleet_active` and `killmail_batch` `FeedEvent`s. Pilot deduplication must union `character_id` across mails (21 unique, not per-mail sum).

### Engagement timeline (sample)

| Killmail ID | Time (UTC) | Δ from anchor | Pilots (mail) | Militia on mail |
|-------------|------------|---------------|---------------|-----------------|
| 136398538 | 16:59:41 | −25.4 min | — | Minmatar-tagged |
| 136398967 | 17:25:08 | **0** (anchor) | 8 | 8× Minmatar |
| 136399207 | 17:33:xx | +8 min | — | Minmatar-tagged |
| 136399424 | 17:50:23 | +25.2 min | — | Mixed / solo labels |

---

## System activity spot-checks (last 7 days, zKill)

| System | ID | 7d kills (zKill) | PVP | Notes |
|--------|-----|------------------|-----|-------|
| Vard | 30002538 | 912 | 904 | Heavy EU-tz FW fighting 2026-06-19; golden engagement |
| Huola | 30003067 | 254 | 243 | Fleet fight ~00:48 UTC; good secondary positive |
| Kourmonen | 30003068 | 754 | 749 | Highest volume; large Minmatar fleet ~02:50 UTC |
| Jita | 30000142 | 2000+ | 1850+ | High-volume negative control |
| Tama | 30002813 | 1600+ | 1596+ | Unlisted negative control |

zKill `pastSeconds` is capped at **7 days**. zKill History API (`/api/history/systemID/...`) returned Cloudflare challenge pages during research — `backfill_engagement` should fall back to systemID pagination + ESI (as plan notes).

---

## Recommended CI fixture set

Current bundle: `backend/feed/tests/fixtures/engagement_vard_136398967/killmail_136398967.json` (anchor only).

### `engagement_vard_136398967/` — required siblings

Import full R2Z2/ESI JSON for these killmails (priority order):

| Priority | Killmail ID | Hash (zKill) | Why include |
|----------|-------------|--------------|-------------|
| **Required** | 136398967 | `fa607eb45b4a88c891d422d10f79ff234ef72907` | Anchor; 8 Minmatar militia attackers |
| **High** | 136398973 | (fetch via zKill) | Core gang kill, `#:5+` |
| **High** | 136398992 | — | 6+ pilots on mail |
| **High** | 136398981 | — | Fills 15-min burst density |
| **High** | 136398976 | — | Adjacent to anchor |
| **Medium** | 136398970, 136398972 | — | Mixed attackers (realistic noise) |
| **Medium** | 136398640, 136398647 | — | Early ±20 min window kills |
| **Medium** | 136399016, 136399100 | — | Late ±20 min window kills |
| **Optional** | 136399201, 136399207, 136399424 | — | Extend toward ±30 min edge |

**Minimum viable set (8 mails):** 136398967, 136398973, 136398981, 136398992, 136398976, 136398970, 136398640, 136399100 — sufficient for offline cluster tests when combined with synthetic padding in unit tests.

### Additional fixture bundles (recommended)

| Bundle | Anchor killmail | Purpose |
|--------|-----------------|---------|
| `fleet_huola_136383906/` | 136383906 + 9 siblings | Secondary `fleet_active` (minmatar) |
| `fleet_kourmonen_136385705/` | 136385705 + subset of 23-mail cluster | Large fleet + burst |
| `spike_vard_pirate_136400562/` | 136400562–136400629 | Pirate-accent `fleet_active` ambiguity |
| `negative_jita_136400936/` | 136400936 | Allowlist discard |
| `negative_npc_136386594/` | 136386594 | NPC discard (`npc:true`) |
| `negative_solo_136400805/` | 136400805 | Below-threshold solo |
| `negative_tama_136400880/` | 136400880 | Unlisted system discard |

### Synthetic gaps

| Case | Recommendation |
|------|----------------|
| Amarr `fleet_active` (`500001` dominant) | No real 7d case found. Add `fleet_amarr_synthetic.json` with 6+ kills, 8+ pilots, all attackers `faction_id=500001`. |
| `militia_joins` | Seed `FeedMilitiaFirstSeen` rows in test DB; API cannot prove first-seen. |

---

## Gaps and ambiguities for implementation

1. **Fixture system IDs wrong for Huola/Kourmonen.** `fw_monitored_systems.json` uses `30002756` / `30002757`. ESI names: Ishomilken / Nikkishina. Correct: `30003067` / `30003068`. CI using `--fixture-only` seed will monitor the wrong systems until fixed. **ESI `/fw/systems/` seed is authoritative.**

2. **zKill FW labels ≠ ESI `faction_id`.** Vard cluster `136400562–136400629` has zKill `fw:amarr` labels on most mails, but ESI shows **no** `faction_id` on attackers for 9/10 mails. Only `136400579` has 6× `500002`. Dominant faction logic must use ESI militia tags, not zKill labels. Accent will likely be **pirate**, not Amarr yellow.

3. **No Amarr-dominant fleet in 7d sample.** Huola 120-kill ESI sample: 0 mails with Amarr militia `faction_id`. Kourmonen `fw:amarr` zKill filter returned only 3 kills in 48h. Plan requires Amarr `fleet_active` verification — use synthetic fixture or extend history backfill beyond 7 days.

4. **`militia_joins` not API-verifiable.** Golden window has 10 unique Minmatar militia characters in ±1 h, but first-seen requires `FeedMilitiaFirstSeen` state. Test with seeded rows, not killmail replay alone.

5. **zKill History API blocked.** Cloudflare challenge on `/api/history/systemID/...` during research. `backfill_engagement` must tolerate history 404/CF and fall back to `kills/systemID/{id}/pastSeconds/604800/` pagination + ESI time filter.

6. **Pilot deduplication.** Golden ±30 min: **21 unique pilots** across 31 kills. Do not sum per-mail attacker counts (would over-count).

7. **Overlap rule.** Same kills may produce both `killmail_batch` and `fleet_active` events (plan §3). Golden engagement should emit **both**.

8. **Solo kills in monitored systems.** Vard 24h sample had 43 solo PVP kills. These are valid `FeedKillmail` rows but must not alone trigger fleet/burst rollups (N3).

9. **ESI rate limits.** Bulk ESI enrichment hit HTTP 429 without backoff. `backfill_engagement` needs retry/backoff (plan risk table mentions 100ms between zKill hits).

10. **Cluster window alignment.** Plan uses sliding windows per system + dominant faction. Verify whether ±30 backfill is centered on anchor time vs. fixed 20-min buckets — affects which sibling kills are included at window edges (e.g. 136399424 at +25 min is inside ±30 but outside ±20).

---

## Data sources and methodology

- zKill REST: `GET /api/killID/{id}/`, `GET /api/kills/systemID/{id}/pastSeconds/604800/page/{n}/`, label modifiers `fw:amarr`, `fw:minmatar`
- ESI: `GET /latest/killmails/{id}/{hash}/`, `GET /latest/universe/systems/{id}/`, `GET /latest/fw/systems/`
- Rate limiting: ≥1.1s between zKill pages; ≥0.15–0.2s between ESI calls; retry on 429
- Classification: thresholds from plan §3; dominant faction inferred from ESI `faction_id` on attacker rows
- Negative controls: confirmed `zkb.npc` and `solar_system_id` via zKill + ESI

---

## Quick pass/fail checklist (for implementation sign-off)

| Check | Expected | Research result |
|-------|----------|-----------------|
| Anchor ingest | `FeedKillmail` for 136398967 | zKill + ESI payload available |
| Engagement backfill ±30 min | ≥5 kills, ≥8 pilots, includes anchor | **31 kills, 21 pilots** ✓ |
| `fleet_active` golden | Minmatar accent, anchor linked | **PASS** (500002 dominant) |
| `killmail_batch` golden | ≥8 kills in 15 min | **PASS** (17 kills peak) |
| Jita discard | No `FeedKillmail` | 136400936 in Jita ✓ |
| NPC discard | No `FeedKillmail` | 136386594 `npc:true` ✓ |
| Solo discard (rollup) | No fleet/burst event | 136400805 solo ✓ |
| Unlisted discard | No `FeedKillmail` | 136400880 in Tama ✓ |
| Amarr fleet positive | `fleet_active` yellow | **NOT FOUND** in 7d — synthetic needed |
