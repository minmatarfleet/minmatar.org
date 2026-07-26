---
name: tribe-member-audit
description: >-
  Assess active tribe group members for missing qualifications (assets/skills)
  and/or low activity, then produce a targeted production shell one-liner to
  mark them inactive. Use when auditing Capitals, Industry (mining/PI), or
  other tribes for members without hulls, without colonies, zero mining, inactive
  roster cleanup, or scripts to remove tribe members from prod.
---

# Tribe Member Audit

Find **active tribe group members who fail qualifications and/or activity**,
present a clear list for human review, then hand a **targeted** prod removal
script (explicit usernames — never a blind bulk filter).

Also read [debug-production-readonly-db](../debug-production-readonly-db/SKILL.md)
for assessment queries. For mining/PI town-hall metrics, see
[town-hall-summary](../town-hall-summary/SKILL.md).

## Quick start

1. Confirm which tribe group codes and criteria (assets, skills, activity, colonies, or combo).
2. Assess on `production_readonly` from `backend/` with `pipenv run`.
3. Present candidates + notes (other hulls, zero linked chars, sync gaps).
4. **Exclude tribe chiefs and group chiefs** from removal targets.
5. After user confirms, give a prod `docker compose … shell -c` that targets **only** those usernames.

## Workflow

```
Task Progress:
- [ ] Confirm tribe group code(s) and audit criteria
- [ ] Load requirement type IDs / activity defs from prod (do not hardcode fixtures)
- [ ] Query active memberships + linked characters on production_readonly
- [ ] Flag gaps; note caveats (ESI sync, alts, wrong hull class)
- [ ] Drop tribe.chief and TribeGroup.chief usernames from the removal list
- [ ] Present table for review
- [ ] On approval: emit targeted prod removal one-liner
```

## Models

| Piece | Model / helper | Notes |
|-------|----------------|-------|
| Group | `TribeGroup.code` | e.g. `capitals.dreads`, `supply.mining`, `supply.planetary-interaction` |
| Membership | `TribeGroupMembership` | `status` = `active` / `inactive` / `pending`; user-scoped |
| Committed chars | `TribeGroupMembershipCharacter` | Optional; hulls/colonies may live on any linked alt |
| Hulls | `EveCharacterAsset` | Ships only, ESI-synced; not full asset dump |
| Mining ledger | `EveCharacterMiningEntry` | Per-character daily ore; used by mining reports |
| PI colonies | `EveCharacterPlanet` | ESI-synced colonies; prefer over tax ISK for “has PI” audits |
| Requirements | `TribeGroupRequirement` → `TribeGroupRequirementAssetType` / `…Skill` | OR across requirements; AND within one |
| Batch check | `characters_meeting_requirements_batch(..., using=DB)` | Full reqs (assets **and** skills) |
| Activity | `TribeGroupActivity` + `TribeGroupActivityRecord` | `occurred_at`; filter by group + window |
| Chiefs | `Tribe.chief`, `TribeGroup.chief` | Never mark inactive via audit scripts |

**Asset-only vs full requirements:** For “no matching hull,” filter `EveCharacterAsset` by requirement type IDs (or `asset_met`). Do not use the full batch helper alone — skill gaps fail `met` even when a hull exists.

**User vs character:** Membership is per user; assets/colonies/mining are per character. Default: member fails if **no linked character** has the qualifying data. Call out committed chars vs all alts when useful.

**Primary name → username:** Town hall / member reports key on primary character name. Removal scripts must use `user.username`. Map via `EvePlayer.primary_character` (or membership `user`) before emitting targets.

## Assessment (readonly)

From `backend/`:

```bash
pipenv run python manage.py shell -c '...'
```

Use `DB = "production_readonly"` and `.using(DB)` on every queryset.

### Missing qualifying assets (template)

```python
from collections import defaultdict
from tribes.models import (
    TribeGroup,
    TribeGroupMembership,
    TribeGroupRequirementAssetType,
)
from eveonline.models import EveCharacter, EveCharacterAsset

DB = "production_readonly"
CODES = ["capitals.dreads"]  # or carriers / faxes / others

for code in CODES:
    tg = TribeGroup.objects.using(DB).get(code=code)
    type_ids = list(
        TribeGroupRequirementAssetType.objects.using(DB)
        .filter(requirement__tribe_group=tg, eve_type_id__isnull=False)
        .values_list("eve_type_id", flat=True)
        .distinct()
    )
    active = list(
        TribeGroupMembership.objects.using(DB)
        .filter(tribe_group=tg, status="active")
        .select_related("user")
    )
    chars = list(
        EveCharacter.objects.using(DB)
        .filter(user_id__in=[m.user_id for m in active])
        .values_list("id", "user_id", "character_name")
    )
    by_user = defaultdict(list)
    for cid, uid, name in chars:
        by_user[uid].append((cid, name))
    have = set(
        EveCharacterAsset.objects.using(DB)
        .filter(character_id__in=[c[0] for c in chars], type_id__in=type_ids)
        .values_list("character_id", flat=True)
    )
    for m in active:
        if not any(cid in have for cid, _ in by_user.get(m.user_id, [])):
            print(m.user.username, code, [n for _, n in by_user.get(m.user_id, [])])
```

Optionally check other capital groups (`EveType` / `EveGroup` names `Dreadnought`, `Carrier`, `Force Auxiliary`) so the report can say “has Archon, no dread” vs “no capitals synced.”

### Activity gaps

**Generic:** Use `TribeGroupActivityRecord` for the group’s configured activities over a window (e.g. 30/90d). Flag active members with zero (or below-threshold) records. Combine with qualification gaps only when the user asks for both.

**Mining (`supply.mining`):** Prefer the member report (includes zero-activity roster rows; town hall truncates top-N):

```bash
pipenv run python manage.py town_hall_report \
  --group supply.mining --view member --period 30d \
  --database production_readonly --format json
```

Zero mining = `volume_m3 == 0`. Map primary names → usernames before targeting.

**PI (`supply.planetary-interaction`):** Ask which criterion:

| Criterion | Source | Use when |
|-----------|--------|----------|
| Colonies | `EveCharacterPlanet` on any linked character | Default for “has PI set up” / inactive cleanup |
| Tax ISK | Member report `isk_pi_30d_estimate` | “No PI tax in window” (corp wallet; can miss private/alt activity) |

Colony check (any linked char, not only committed):

```python
from tribes.models import TribeGroup, TribeGroupMembership
from eveonline.models import EveCharacter, EveCharacterPlanet

DB = "production_readonly"
tg = TribeGroup.objects.using(DB).get(code="supply.planetary-interaction")
active = list(
    TribeGroupMembership.objects.using(DB)
    .filter(tribe_group=tg, status="active")
    .select_related("user")
)
chars = list(
    EveCharacter.objects.using(DB)
    .filter(user_id__in=[m.user_id for m in active])
    .values_list("id", "user_id")
)
have = set(
    EveCharacterPlanet.objects.using(DB)
    .filter(character_id__in=[c[0] for c in chars])
    .values_list("character_id", flat=True)
)
by_user = {}
for cid, uid in chars:
    by_user.setdefault(uid, set()).add(cid)
for m in active:
    if not (by_user.get(m.user_id, set()) & have):
        print(m.user.username)
```

## Present results

Table per tribe group: username, committed characters, linked char count, notes.

Caveats to mention when relevant:

- Missing assets can mean no hull **or** never synced / missing ESI scopes / location not tracked.
- Zero linked characters = broken account link.
- Capitals requirements are a **doctrine subset** (e.g. Rev/RNI/Zir, not every dread). Owning Naglfar does not satisfy `capitals.dreads` unless configured in prod.
- Missing PI colonies can mean no colony **or** planets never synced (ESI scopes / sync lag).
- Mining zeros are ledger-based for the period; alts not linked to the user are invisible.

### Exclude chiefs

Before presenting a removal list, drop anyone who is `Tribe.chief` or `TribeGroup.chief` (any tribe/group, not only the audited one). Chiefs are auto-ensured as active members via `ensure_tribe_chiefs_have_group_memberships` and must not be soft-removed by audit scripts.

```python
from tribes.models import Tribe, TribeGroup
chief_uids = set(
    Tribe.objects.using(DB).exclude(chief_id=None).values_list("chief_id", flat=True)
) | set(
    TribeGroup.objects.using(DB).exclude(chief_id=None).values_list("chief_id", flat=True)
)
# skip memberships where m.user_id in chief_uids
```

## Removal (prod write)

**Never** remove from assessment alone. Wait for user confirmation, then give a one-liner that lists **exact usernames** per `TribeGroup.code`.

Run on the **prod host** (not local readonly):

```bash
docker compose -f docker-compose-prod.yml exec app python3 manage.py shell -c '
from django.utils import timezone
from tribes.models import TribeGroupMembership
now = timezone.now()
targets = {
    "capitals.dreads": ["user1", "user2"],
    "supply.mining": ["user3"],
    "supply.planetary-interaction": ["user4"],
}
for code, users in targets.items():
    for m in TribeGroupMembership.objects.filter(
        tribe_group__code=code, status="active", user__username__in=users
    ).select_related("user"):
        m.status = "inactive"
        m.left_at = now
        m.history_inactive_reason = "removed"
        m.save()
        print(f"removed {m.user.username} from {code}")
'
```

### Removal rules

| Do | Don't |
|----|-------|
| Target explicit `user__username__in=...` | Re-run the asset/activity filter as the write path |
| Set `status="inactive"`, `left_at=now` | Hard-delete membership rows |
| Use `history_inactive_reason = "removed"` (≤32 chars) | Long reason strings — `TribeGroupMembershipHistory.reason` is `max_length=32` |
| Exclude tribe + group chiefs from `targets` | Remove chiefs (they get re-added / break leadership) |
| Rely on post_save to drop auth/Discord groups | Delete committed characters unless the user asks |

Signals write history and call `remove_tribe_auth_groups_for_inactive_membership` on inactive. Same path as leave/chief remove when reason is `"removed"`. Clearing `TribeGroupMembershipCharacter` rows is optional for this soft-remove path; status + `left_at` is enough.

If a prior attempt failed on `Data too long for column 'reason'`, re-run with `"removed"` only; check which usernames are still `active` before retrying.

## Capitals reference

| Code | Typical qualifying hulls (confirm in prod) |
|------|--------------------------------------------|
| `capitals.dreads` | Revelation, Revelation Navy Issue, Zirnitra |
| `capitals.carriers` | Archon, Nidhoggur, Thanatos |
| `capitals.faxes` | Apostle, Lif, Ninazu |

Always load type IDs from `TribeGroupRequirementAssetType` on the DB you query.

## Industry reference

| Code | Default audit signal | Notes |
|------|----------------------|-------|
| `supply.mining` | Zero `volume_m3` in member report (30d) | `--view member` for full roster; map names → usernames |
| `supply.planetary-interaction` | No `EveCharacterPlanet` on any linked char | Prefer colonies over tax ISK unless user asks for tax |

## Related

- Town hall metrics (mining volume, PI tax, kills/fleets): [town-hall-summary](../town-hall-summary/SKILL.md)
- Readonly DB: [debug-production-readonly-db](../debug-production-readonly-db/SKILL.md)
