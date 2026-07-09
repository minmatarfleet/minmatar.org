---
name: academy-graduation
description: >-
  Identify Minmatar Fleet Academy (L3ARN) pilots ready to graduate, analyze
  Discord voice, fleet participation, and killmail behavior, route to alliance
  corps by ticker (FOSFO, TDT, SLTAR, A-RAT), and output a TSV for Google
  Sheets. Use when the user asks about academy graduation, L3ARN tenure, who
  should graduate, graduate routing, or academy pilot corp placement.
---

# Minmatar Fleet Academy Graduation

Find **L3ARN pilots who should graduate**, profile their behavior, suggest corp
tickers (multiple OK), and output a copy-paste TSV.

**Agent skill first.** Workflow and routing judgment live here and in
[examples.md](examples.md). `scripts/fetch_academy_pilots.py` only fetches
metrics from `production_readonly` — you own graduation gates, routing, and
summaries.

Reference alliance: [Minmatar Fleet Alliance](https://my.minmatar.org/).

## Quick start

```bash
cd backend
pipenv run python ../.cursor/skills/academy-graduation/scripts/fetch_academy_pilots.py --json
```

Also read [debug-production-readonly-db](../debug-production-readonly-db/SKILL.md) if DB access fails.

Refresh corp names/tickers from API before routing:

```
GET https://api.minmatar.org/api/eveonline/corporations/corporations?corporation_type=alliance
```

## Workflow

```
Task Progress:
- [ ] Fetch academy roster + 90d behavior (script or Django shell)
- [ ] Refresh graduate corp list from API (tickers in config.json)
- [ ] Apply graduation gate — drop pilots who should stay in L3ARN
- [ ] Route survivors to corp tickers (multi-corp OK)
- [ ] Write one-line pilot summaries (behavior, not routing justification)
- [ ] Present table; output TSV if user wants Google Sheets
```

## Data sources

| Signal | Source | Notes |
|--------|--------|-------|
| Tenure | `discord_discorduser.created_at` | Proxy only; mark unreliable dates |
| TZ preference | `eveonline_eveplayer.prime_time` | US / EU / AP / splits |
| SP | `eveonline_evecharacterskill` sum | Millions in output |
| Discord activity | `discord_discordchannelactivityrecord` | `voice_minute` rows, 90d |
| Fleet attendance | `fleets_evefleetinstancemember` | Count + avg instance size |
| Fleet roles | `fleets_evefleetrolevolunteer` | logi_anchor, cyno, links, scout |
| Kills | `eveonline_evecharacterkillmailattacker` | 30d and 90d |
| Gang size | Attacker count per killmail | small ≤10, medium 11–24, large 25–39, blob 40+ |
| Industry | `eveonline_evecharacterindustryjob` count | MFA path signal |

**Tenure unreliable:** Discord or character `created_at` on `2025-08-04` is a
site migration batch — prefix tenure with `~` and `*`. Do not graduate
migration-batch pilots on date alone.

**Corp join dates:** Not stored. ESI `track_members` may work if a director
re-auths; otherwise use behavior over calendar.

## Graduation gate

**Include** a pilot when they show real participation AND meet tenure rules.

**Exclude** (drop from output entirely):

- Under 180 days tenure with **reliable** dates and no exceptional activity
- Migration-batch date only, with weak 90d activity (voice-only, no fleets/kills)
- Industry-primary with no combat/fleet path unless explicitly MFA routing
- Obvious alts or exempt characters if flagged in data

**Include when:**

| Tenure | Requirement |
|--------|-------------|
| Reliable 180d+ | Fleets ≥4 OR kills_90d ≥8 OR (voice ≥10h AND kills_90d ≥3) OR (SP ≥80M AND kills_90d ≥1) |
| Unreliable (`~`) | Same activity bar AND (kills_90d ≥15 OR fleets ≥6 OR SP ≥40M) |

When borderline, leave them in Academy — this report is for clear graduates.

## Corp routing (tickers)

Use **tickers** from [config.json](config.json). **Multiple tickers per pilot is OK**
(`FOSFO / SLTAR`). Balance across corps — do not dump every USTZ PvPer into TDT.

| Ticker | Profile | Route when |
|--------|---------|------------|
| **FOSFO** | EUTZ skirmish/roam | EU/AP_EU TZ; small-gang dominant |
| **TDT** | USTZ killers | SP ≥30M, kills_30d ≥10, kills_90d ≥30, skirmish lean — **all** required |
| **SLTAR** | Fleet/comms FW | Fleet-heavy (8+ ops), under 30M SP, quiet last 30d, building pilots |
| **A-RAT** | All-TZ casual, scales up | Blob/large-gang kills, cyno volunteer, avg fleet ≥50 in combat, no TZ |
| **MFA** | Industry associates | 8+ industry jobs, kills_90d <5, fleets <3 — rare from L3ARN |

### Routing balance (learned)

- **TDT is selective.** 90d kill volume or high SP alone is not enough — need
  sustained **30-day killboard** and skirmish-dominant gang counts.
- **SLTAR** for JimLahey-types: many fleets, comms-first, still under 30M SP.
- **A-RAT** for Station-types: large-gang kills (25+ pilots), cyno, blob grind.
- **FOSFO** for all EUTZ graduates (replaced DHDR / Administrative Atrocities).
- Quiet veterans (high SP, 1 kill/30d) → **SLTAR / A-RAT**, not TDT.

Read [examples.md](examples.md) before routing.

## Pilot summary (Reason column)

One short sentence: **who they are**, not why they fit a corp.

- Lead with play style: skirmisher, fleet junkie, blob fighter, lapsed killer, building pilot
- Include one standout number: fleets/90d, kills/30d, voice hours, gang profile
- No corp names in the summary — tickers live in the Graduate to column

## Output

### Markdown table

| Pilot | TZ | SP | Kills (30d) | Tenure | Graduate to | Summary |
|-------|-----|-----|------------:|--------|-------------|---------|

- Tenure: `186d` or `~338d*` when unreliable
- Graduate to: tickers only, `PRIMARY / SECONDARY` when split

### Google Sheets TSV

When user wants copy-paste, output a **plain code block** with tab-separated values:

```
Pilot	TZ	SP	Kills (30d)	Tenure	Graduate to	Summary
C0ach Gar0f	EU	77M	118	~338d*	FOSFO / SLTAR	EUTZ skirmisher. 20 fleets, heavy small-gang output, regular voice.
```

Header row required. No markdown table pipes — tabs only.

## Optional script

| Script | Purpose |
|--------|---------|
| `scripts/fetch_academy_pilots.py` | JSON roster + 90d metrics from `production_readonly` |

```bash
cd backend
pipenv run python ../.cursor/skills/academy-graduation/scripts/fetch_academy_pilots.py --json
```

You interpret the JSON, apply gates, route, summarize.

## What improves over time

| Belongs in skill / examples | Should NOT live in Python |
|-----------------------------|---------------------------|
| Graduation gate judgment | Hardcoded graduate lists |
| Corp routing balance | Keyword scoring |
| Summary voice | Template paragraphs per corp |
| Tenure caveats | Static corp tables without API refresh |

Add routing learnings to [examples.md](examples.md) after graduation pushes.

## Additional resources

- Routing learnings: [examples.md](examples.md)
- Config (corp IDs, tickers): [config.json](config.json)
- Setup: [README.md](README.md)
- Production DB: [debug-production-readonly-db](../debug-production-readonly-db/SKILL.md)
- Recruitment scout (corp bios): [fl33t-recruitment-scout](../fl33t-recruitment-scout/SKILL.md)
