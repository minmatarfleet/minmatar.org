---
name: spy-catch
description: >-
  Operational playbook for fleet-behavior intel reviews: selective attendance,
  low-effort ships, early exit before undock, fleet-without-voice. Produce a
  sensitive People/CEO case list with evidence packs for Watch/Talk/Escalate/Clear
  triage. Use when hunting spies, reviewing suspicious fleet patterns, intel
  hygiene, or low-effort fleet attendance anomalies.
---

# Fleet Behavior Intel (spy-catch)

Catch low-effort / selective fleet patterns that look like intel gathering —
including **join then leave early / before undock** — using tracked fleet +
Discord voice data. **Not** mails/wallets.

This is a **People / CEO ops playbook**. The agent **fetches and drafts** only.
Humans own triage and any action.

**Not** [on-leave](../on-leave/SKILL.md): that flags people who never show up.
This reviews people who **do** show up in a suspicious way.

Also read [debug-production-readonly-db](../debug-production-readonly-db/SKILL.md).

## Owners and clearance

| Role | Responsibility |
|------|----------------|
| **Runner** | People Team (or CEO designee) — owns the case list |
| **Reviewer** | Second People/CEO eyes before any Escalate corp action |
| **Agent** | Fetch + draft case list only |
| **Out of room** | Do not share in general Discord, FC lounges, or with directors by default |

Treat output as **sensitive**. Date it; keep it off public channels.

## When to run

- **Cadence:** monthly, or ad hoc after leak concern.
- **Window:** last **90 days** (override only from session context).
- **Roster:** active Alliance members with ≥**5** tracked attendances in window.
- Cross-check on-leave so pure inactivity is not re-litigated here.

## Preconditions

1. `production_readonly` access.
2. Run from `backend/` with Pipenv.
3. Session exempts (named CEOs, scouts who fly frigs on purpose).
4. Auto-exempt: `People Team`, `Technology Team`, `Tribe - Chief`.

## Quick start

```bash
cd backend
pipenv run python ../.cursor/skills/spy-catch/scripts/fetch_fleet_behavior.py --json
```

Defaults from [config.json](config.json): 90d, min 5 fleets, prefilter cutoffs.

## Workflow

```
Task Progress:
- [ ] Confirm window, exempts, trigger (monthly / ad hoc)
- [ ] Fetch (--json)
- [ ] Drop auto-exempts + named exempts; drop thin samples
- [ ] Draft case list (prefiltered candidates only)
- [ ] Runner triage → Watch / Talk / Escalate / Clear
- [ ] Escalate: second reviewer → action checklist
- [ ] File outcomes in examples.md; vault/destroy report
```

## Signals

| Pattern | Evidence | Triage weight |
|---------|----------|---------------|
| **SelectiveAttend** | FC concentration only (single Alliance audience is normal — not a signal) | Primary if extreme |
| **LowEffortShip** | Off-doctrine hulls and/or T1 frig; capsule after long stay ignored (usually podded) | Primary when doctrine set |
| **EarlyExit** | Short presence vs instance (`join_time`→`updated_at`); often still docked | Primary when habitual |
| **FleetNoVoice** | ~0 `voice_minute` in instance window | Supporting (coverage gaps) |
| **TzSkew** | `time_region` vs `prime_time` / same-TZ availability | Supporting — real TZ ≠ hit |
| **StayedDocked** | Final `station_id` set | Supporting; pairs with EarlyExit |

**EarlyExit:** join, disappear well before fleet ends — especially last-seen docked
(before undock). Approx leave = last ESI poll (`updated_at`). Habit > one night.
False positives: crash, alt swap, formup cancel, legit drop.

**Do not** use as core: mails, wallets, corp history, hostile-alt graphs, enemy-side KMs.

## Draft rules (agent hint only)

1. Exempt → omit.
2. Fleets &lt; min → omit (thin sample).
3. Prefer clear compounds; never Escalate on FleetNoVoice or StayedDocked alone.
4. Habitual EarlyExit (esp. docked) across ≥5 fleets → Talk or Escalate **candidate**.
5. SelectiveAttend + LowEffortShip, or EarlyExit + LowEffortShip → Escalate candidate.
6. “Only my TZ” with normal doctrine/voice/presence → Clear.
7. One early leave / formup cancel → Clear.
8. Conf is a **hint**; runner overrides freely.

Bias: prefer **miss a quiet spy** over false Escalate. Lazy/broke/new ≠ espionage.

## Triage outcomes (human required)

| Outcome | Meaning | Next |
|---------|---------|------|
| **Clear** | Explained / bad data | Close |
| **Watch** | Odd, not actionable | Re-check next run; do not ping |
| **Talk** | Soft concern | Private People/CEO conversation |
| **Escalate** | Strong pattern + evidence | Second reviewer → checklist |

### Escalate checklist

1. Spot-check evidence fleets.
2. Action: talk first if needed; strip sensitive access; corp handling per CEO; optional on-leave OPSEC via on-leave playbook.
3. Record decision privately.
4. Do **not** announce in alliance channels.

**No automated kicks or status writes from this skill.**

## Deliverable

```
Run: YYYY-MM-DD | Window: 90d | Min fleets: 5 | Trigger: monthly|ad-hoc
Summary: N candidates → draft only (Outcome blank for runner) | Exempt: E

| Username | Primary | Fleets | Key metrics | Story | Conf | Outcome | Owner |
```

Per Talk/Escalate candidate, attach evidence pack (3–8 fleets):

```
### username (primary)
Story: ... | Conf: ... | Outcome: (blank)
Metrics: ...
Evidence:
- YYYY-MM-DD | FC | audience | ship | doctrine? | present Xm / left early, docked? | voice Xm | note
Caveats: ...
```

Sort by Conf (high → medium → low). Short list only — not half the alliance.

See [examples.md](examples.md).

## Related

- [on-leave](../on-leave/SKILL.md) — inactivity / OPSEC leave
- [debug-production-readonly-db](../debug-production-readonly-db/SKILL.md)
- [tribe-member-audit](../tribe-member-audit/SKILL.md) — confirm-then-act
