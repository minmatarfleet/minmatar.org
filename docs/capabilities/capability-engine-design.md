# Character capability engine: design (Phase 0)

Status: **built** (Oct 2026) in `backend/capabilities/`. Phase 0 of the
[Pilot Capability Plan](https://claude.ai/artifact/HiFMWqwHU3qmJTHhk38qY2).
Backend only: no UI or API yet.

The numbers in §9, §10 and the appendix come from a prototype run on 24 Oct
2026 against prod (`production_readonly`, SELECT only) and CCP SDE build
**3646012**. That was before the fit check (R17) existed; §13 has the built
engine's numbers. Every rule below is a named constant in
`backend/capabilities/engine/rules.py`.

Code map:

| Path | What |
|---|---|
| `capabilities/engine/sde.py` | Builds and reads the SDE snapshot (pure Python) |
| `capabilities/engine/dogma.py` | The fit check: CPU, grid, calibration and drones with a character's skills |
| `capabilities/engine/fit.py` | EFT to typed items: modules, loadable ammo, required drones, kit |
| `capabilities/engine/requirements.py` | Requirement rows per fitting (R1–R13, R17) |
| `capabilities/engine/readiness.py` | One character against one fitting, and "train next" |
| `capabilities/services.py` | Loads inputs from the database and stores results |
| `capabilities/tasks.py`, `signals.py` | When it all runs (§8) |

## 1. Summary

- Every requirement row is computed, so nobody has to keep a list by hand.
  **All four golden checks pass** on the real prod fittings, and all 51
  doctrine fittings resolve.
- **Core rule (H):** core = the fit's hard requirements, raised to mastery
  III for each skill that dogma shows touching this fit, and raised again to
  the level that **90% of Proven pilots already have**. The raise is capped
  at mastery V. Only the stat buckets that matter for the fit's capability
  count toward core.
- **Doctrine-ready depends on the doctrine type.** Strategic doctrines need
  hard + core. Non-strategic doctrines need hard only, with core shown as
  progress.
- **Levels:** Unlocked → Doctrine-ready → Proven. There is no Anchor: this
  phase is about training characters.
- **The player view shows every character, grouped by account.** Two
  characters online in the same fleet at the same time must be on different
  accounts, so fleet seats already reveal most account groupings (§7).
- How strict is core? Summed over all fittings, active players go from
  **30,234** fitting-player pairs Unlocked to **23,331** hard-ready to
  **17,371** core-ready (−26% against hard-only). The median fitting passes
  **71%** of its own Proven pilots.

## 2. What the engine produces

| Level | Rule |
|---|---|
| **Unlocked** | The hull's required skills and their prerequisites, recursively. |
| **Hard-ready** | `required` tier: the hull, fitted modules (offline ones too), loaded charges, loadable cargo ammo, and combat drones on drone hulls, plus all prerequisites. A substitute module satisfies its slot (R4). |
| **Core-ready** | `required` + `core` tiers. |
| **Doctrine-ready** | Core-ready for a fitting in a **strategic** doctrine. Hard-ready for a fitting that is only in non-strategic or experimental doctrines. A fitting in both kinds (the 10mn Exequror is in TFIs and Plexing) stores both flags, and each doctrine reads its own. |
| **Proven** | 3+ distinct alliance fleets in the last 365 days, in a hull that maps to this capability (§7). |

Alongside those levels there is a **support score** (0–100) per character
and fitting, which measures progress toward the `optimal` tier, and a ranked
"train next" list. Training time uses a flat default rate; character
attributes aren't synced (your answer to Q7).

## 3. SDE source: kept current automatically

The engine needs three things ESI never publishes:

- **`skillTypeID` on effect modifiers.** 113 modifiers on 53 skills
  (Surgical Strike, Rapid Firing, the drone and Command Specialist skills,
  and so on). Hull and module bonuses use it too.
- **Masteries and certificates.**
- **Hull traits.**

**eveuniverse is also stale in prod.** `eveuniverse_evetype.last_updated` is
19 Feb 2026 for every doctrine type, and nothing refreshes it. Against SDE
3646012, 4 values differ across the 960 doctrine and skill types checked:
the Cold-Gas Enduring MWDs' capacitor need, Einherji I shield HP, and the
Capital Jump Portal Generation skill level. That is small today, but the
exact fit check (R17) adds up CPU and grid, so it needs one consistent,
current copy of dogma.

**Proposal:** prod keeps its own SDE snapshot and updates it without anyone
looking.

1. **Daily check.** `capabilities.check_sde_build` reads
   `developers.eveonline.com/static-data/tranquility/latest.jsonl`, which is
   a few bytes.
2. **Download only on a new build.** It streams the JSONL zip (about 99 MB)
   to a temp file and extracts the slice the engine uses:
   - type attributes and effects for ships, modules, charges, drones,
     fighters, skills and subsystems;
   - every effect's modifiers;
   - certificates, masteries and traits.

   It stores the slice as an `SdeSnapshot` row (build, release date,
   compressed JSON, a few MB) and keeps the last 3 builds.
3. **Recompute.** It switches the engine to the new snapshot and recomputes
   every fitting, then all readiness.
4. **What changed.** It stores a summary: which fittings' requirements
   changed and how many characters gained or lost Doctrine-ready. Admin shows
   it per build.
5. **Failures are loud, never silent.** The job is a Sentry cron monitor.
   A failed download or parse keeps the previous snapshot in use.

For dev, `python manage.py load_sde_snapshot` runs the same code
(`--path` takes a CCP zip or unpacked folder instead of downloading).
Tests use a small fixture snapshot (a few hulls, modules and skills) and
never touch the network. eveuniverse stays the source for everything else on
the site. Optional follow-up: a new build could also queue an eveuniverse
refresh of the types it changed, which fixes the stale values site-wide.

## 4. Data model (new app `capabilities`)

Static inputs: `SdeSnapshot` (`build`, `release_date`, `loaded_at`,
`is_current`, `data` compressed JSON, `changes` JSON summary), loaded in
memory per task run.

Computed per fitting, one set per (fitting version, SDE build, rules version).

| Table | Columns |
|---|---|
| `FittingRequirementSet` | `fitting` FK, `fitting_version` (= `EveFitting.latest_version`), `sde_build`, `rules_version`, `capability`, `capability_source` (auto/override), `tank_layers`, `proven_pilots`, `proven_pass_rate`, `computed_at`, `is_current` |
| `FittingSkillRequirement` | `requirement_set` FK, `skill_id`, `skill_name`, `required_level`, `core_level`, `optimal_level`, `sources` JSON per tier, e.g. `{"required": ["hard"], "core": ["mastery", "empirical"]}`, `bucket`, `per_level_bonus`, `weight`, `reason` (e.g. "damageMultiplier of Dual Giga Pulse Laser II"), `mastery_levels` ("13455"), `empirical_level`, `proven_meeting_core` (share of Proven pilots who meet it; feeds the over-ask flag) |

One row per skill, holding three levels with required ≤ core ≤ optimal, is
simpler to query than one row per tier, and it still records a tier and a
source for each level. A row's **tier** is the lowest one with a non-zero
level.

Doctrine-team overrides, versioned with the fitting.

| Table | Columns |
|---|---|
| `EveFittingSkillOverride` (in `fittings`) | `fitting` FK, `skill` (EveType FK), `action` (pin / exclude / set_level), `tier`, `level`, `note`, `created_by`, `updated_at` |
| `EveFitting.capability` (new nullable field) | Override for the auto-classified capability. It lives on the fitting (your answer to Q5). |

Saving an override goes through the existing versioning path. It writes an
`EveFittingHistory` row and bumps `latest_version`. A new
`EveFittingHistory.skill_overrides` JSON field snapshots the previous
overrides, the way `tags` is snapshotted today. Overrides are applied last
and record `override` as the source.

**Admin experience.** Normally nobody touches anything. The fitting's
existing admin page gets a **Skill requirements** panel listing the computed
rows: skill, required / core / optimal level, and why. To correct one, pick
**Remove** or a different level on that row, or **Add skill** at the bottom,
then save the fitting as usual. Each row shows "computed" or "changed by
<name>", and the change lands in the fitting's history. Anyone who can edit
fittings can do this.

Per character, refreshed after each skill sync and nightly.

| Table | Columns |
|---|---|
| `CharacterFittingReadiness` | `character` FK, `requirement_set` FK, `unlocked`, `hard_ready`, `core_ready`, `missing_core` JSON [[skill, have, need]], `days_to_core`, `support_score`, `computed_at`. About 3.4k active-player characters × 51 fittings ≈ 175k narrow rows. |
| `CharacterCapability` | `character` FK, `capability`, `level` (0 none, 1 unlocked, 2 doctrine_ready, 3 proven), `best_fitting` FK, `ready_fittings`, `fleets_365d`, `strategic_fleets_365d`, `last_flown`, `computed_at` |
| `CharacterAccountLink` | `user` FK, `character_a`, `character_b`, `fleets_together`, `last_seen_together`. A pair of the same player's characters seen online in one fleet at the same time, which proves they are on different accounts (§7). |
| `CharacterAccount` | `user` FK, `number` (Account 1, 2, ...), `source` (inferred / pilot). `CharacterAccountMember` puts a character in one. Filled by the grouping in §7; inferred accounts are rebuilt nightly, and a user with a pilot-placed account keeps theirs. |

## 5. The requirement algorithm

Each rule has an ID so it can be tuned by name. The constants (in
brackets, prototype names) live in `capabilities/engine/rules.py`.

**Parsing**

- **R1. Items.** Parse the EFT with `fittings.eft` and resolve names with
  the SDE snapshot's type names. The items are the hull, every fitted module (online or
  offline), loaded charges, drones and fighters. Cargo is ignored, except
  ammo that loads into a fitted module (`chargeGroup1..5` plus `chargeSize`)
  [`cargo_charges_required=True`]. Spare modules in cargo are ignored, which
  matches `fit_roles.py`.
- **R2. Utility drones are optional.** On a hull whose traits bonus drones or
  fighters, combat drones count toward hard requirements. Repair, mining and
  EWAR drones, and every drone on a non-drone hull, go to the `optimal` tier
  with the reason "utility drones" [`drones_required="drone_hulls"`].
  Without this, a Napoc's Hornet EC-300s or an Apostle's Heavy Hull
  Maintenance Bots blocked half of the Proven pilots.

**Required tier**

- **R3. Required.** For every item in R1, take `requiredSkill1..6`
  (attributes 182/183/184/1285/1289/1290 with levels in 277/278/279/1286/1287/1288),
  then close over each skill's own prerequisites. Tier `required`, source
  `hard`.
- **R4. Substitutions** (answer 2: on). A slot whose preferred module
  has substitutes is satisfied by the easiest option: the requirement is the
  minimum over the alternatives.

**Candidates and the dogma filter**

- **R5. Candidates.** The union of:
  - the hull's mastery skills, levels I–V, taken cumulatively from
    `masteries` → `certificates`;
  - the hull's trait skills (`typeBonus`);
  - the R3 skills.
- **R6. Dogma filter.** A candidate skill survives if one of its effect
  modifiers touches this fit:
  - `LocationRequiredSkillModifier` or `OwnerRequiredSkillModifier` with
    `skillTypeID` S: some fitted item requires S and has a **non-zero**
    value for the modified attribute. The non-zero check keeps Controlled
    Bursts off projectile fits.
  - `LocationGroupModifier`: a fitted item in that group has the attribute.
  - `ItemModifier` on `shipID`: the hull attribute is in a tracked bucket,
    and the hull has it. Jump attributes exist only on jump-capable hulls.
  - `ItemModifier` on `charID`: allow-listed character attributes (max
    locked targets; max active drones only when drones are fitted).
  - Trait skills always survive.
- **R7. Tank layers.** Fitted modules decide the layer: more "armor" groups
  than "shield" groups means armor, and a tie means both. Hull-HP modifiers
  on the other layer don't survive. That is how Shield Management drops off
  the Revelation even though every hull has shield HP.

**Core tier**

- **R8. Core floor.** For each survivor:
  `core = max(hard level, mastery III level)` [`core_mastery_level=3`].
  Trait skills get at least level 3 [`trait_core_level=3`], because CCP's
  masteries leave hull skills out (the Revelation's mastery V has no Amarr
  Dreadnought).
- **R9. Empirical raise (rule H).** Take the characters with 3+ fleets in
  the hull [`empirical_min_fleets=3`] who also meet this fit's R3
  requirements, so a DPS Prophecy pilot doesn't calibrate the links
  Prophecy. If there are at least 8 of them [`empirical_min_pilots=8`],
  raise core to the level that 90% of them already have
  [`empirical_quantile=0.1`], capped at mastery V [`empirical_cap`]. Source
  `empirical`.
- **R10. Capability buckets.** Every surviving modifier gets a stat bucket:
  damage, tank, capacitor, navigation, targeting, fitting, jump, support or
  drones. A core row whose bucket isn't in the capability's core buckets
  drops back to its hard level, and its core level becomes `optimal`.

  | Capability | Core buckets |
  |---|---|
  | DPS | damage, tank, capacitor, navigation, targeting, fitting, drones |
  | Logistics | support, tank, capacitor, navigation, targeting, fitting |
  | Links | support, tank, capacitor, navigation, fitting |
  | Support | support, tank, capacitor, navigation, targeting, fitting |
  | Tackle | support, tank, navigation, targeting, fitting, capacitor |
  | Recon | navigation, jump, targeting, fitting, support |
  | Dreads | damage, tank, capacitor, targeting, jump, fitting, navigation |
  | Carriers | drones, tank, capacitor, targeting, jump, fitting, navigation, support |

  That keeps gunnery support off the tackle Punisher and drone skills off
  the links Prophecy. I added a **support** bucket to your seven: remote
  reps, bursts and EWAR strength. Logi, links and EWAR fits need it.

**Optimal tier and overrides**

- **R11. Optimal.** The mastery V level for every survivor. For trait skills
  and dogma-only skills with a bonus of at least 2% per level, it is V.
- **R12. Over-ask flag.** For each core row, store the share of Proven
  pilots who meet it. Below 70%, the admin view flags the row for the
  doctrine team. The engine never lowers a level on its own.
- **R13. Overrides last.** "Require this level" (`set_level`) sets one
  tier's level, adding the skill if it wasn't there; "Remove this skill"
  (`exclude`) drops the row. Source `override`.

**Fit check**

- **R17. Exact fit check (part of hard-ready).** For each character and
  fitting, compute fitted CPU and powergrid usage against output, and rig
  calibration, with that character's skill levels. The calculation applies
  dogma modifiers from:
  - skills, with each bonus multiplied by the skill level;
  - the hull's trait effects, multiplied by the hull skill level;
  - fitted online modules and rigs (Co-Processors, Reactor Controls, ACRs,
    role bonuses), with stacking penalties where the attribute is stackable.

  The calculation is limited to the fitting attributes (cpuOutput,
  powerOutput, cpu, power, upgradeCapacity, upgradeCost), so it is a small
  dogma pass, not a full simulator. It also checks that the character can
  launch the fit's drones: max active drones from the Drones skill. A
  character who doesn't fit is not hard-ready, and `missing` explains why,
  e.g. "12.4 tf CPU short: CPU Management IV (1.2 d) or Weapon Upgrades V
  (4.9 d)".

  The requirement table also gets the cheapest set of fitting-skill levels
  that makes the fit work, assuming no other support skills, so a new pilot
  sees the exact plan. Validation:
  - every doctrine fit must fit with all skills at V;
  - Proven pilots who meet the other hard requirements should almost all
    pass.

**Impact weight and support score**

- **R14. Impact weight.**
  `per_level_bonus` = |value of the modifying attribute on the skill|
  (Surgical Strike 3, Large Energy Turret 5, Jump Drive Calibration 20).
  `weight = per_level_bonus × bucket_weight[capability][bucket]`.
  "Train next" ranks the missing levels by
  `weight × levels gained / max(training days, 1)`. The one-day floor stops
  level-I skills, which train in minutes, from always ranking first.
- **R15. Training time.** SP for a level = `rank × (250, 1415, 8000, 45255, 256000)`,
  cumulative, with rank from attribute 275. The rate is a flat
  2,250 SP/h, labelled as an estimate. Character attributes aren't synced
  (answer 7).
- **R16. Support score.**
  `100 × Σ weight·min(have, optimal) / Σ weight·optimal` over all rows. It
  is shown next to the levels, never used as a gate.

Example: an active Napoc pilot who is hard-ready but not Doctrine-ready is
missing four armor compensations at level I, Armor Layering I and Controlled
Bursts IV. Ranked as R14 describes, the comps come first.

## 6. Capability per fitting

The auto-classifier reads the fit and the doctrine roles, and you can
override it per fitting (answer 5). The order of the checks matters:

1. Dreadnought → **Dreads**; Carrier → **Carriers**.
2. Logistics or FAX hull, or 2+ remote reps → **Logistics**.
3. An online command burst → **Links**.
4. Interdictor, HIC or interceptor → **Tackle**.
5. Black Ops, Covert Ops, or a cyno with no weapons → **Recon**.
6. A Force Recon picks between the two: a cloak or cyno makes it **Recon**,
   EWAR makes it **Support**.
7. 2+ EWAR modules (ECM, damps, TDs, webs, neuts, painters) on a support or
   secondary slot → **Support**.
8. A point on a support or secondary sub-battleship slot → **Tackle**.
9. Anything else → **DPS**.

On the 51 prod fittings that gives 14 DPS, 11 Logistics, 9 Links, 7 Tackle,
6 Support, 3 Carriers and 1 Dreads. Golden hulls all land correctly:
Revelation is Dreads, Napoc DPS, Guardian Logistics, Damnation Links,
Bhaalgorn and Vindicator Support, Devoter Tackle. These need a doctrine-team
look:

- the Pointrunner Vexor (DPS) and Pointrunner Dominix (Support);
- the Pointrunner Myrmidon, which has bursts online (Links);
- the AC Thrasher (Support, from its webs), and the AC Rifter, AC Thrasher
  Fleet Issue and Pulse Coercer Navy Issue (Tackle);
- the 50mn Osprey and 10mn Augoror (Logistics).

## 7. Proven, and characters grouped by account

**Proven** (thin first pass)

- A seat is a distinct (character, fleet instance, hull) from
  `EveFleetInstanceMember` plus `EveFleetInstanceMemberShipSnapshot`
  (90,466 rows in prod).
- A hull maps to the capability of its doctrine fittings. When a hull has
  more than one, it takes the capability of the fitting whose hard
  requirements the character meets, and then the one in the fleet's
  doctrine. Hulls outside every doctrine fall back to a hull-group map
  (Interdictor → Tackle, Combat Recon → Support, Covert Ops → Recon, and so
  on).
- Proven = 3+ distinct fleets in the capability over a rolling 365 days.
- Only about 10% of fleets have a doctrine set (113 of 812 strategic, 78 of
  1,163 non-strategic), so a fleet's doctrine can't be the main signal.

**Accounts.** EVE allows one character online per account, and three
characters per account. So:

- When two of a player's characters are in the same fleet with overlapping
  presence (`join_time` to the last poll update), they are on **different**
  accounts. Each such pair becomes a `CharacterAccountLink`.
- The **minimum number of accounts** is the largest group of characters that
  were all online together.
- Grouping: start one account per character in the largest such group (the
  "core" characters). Add each other character to an account none of whose
  characters it was ever online with, picking the account whose core
  character it shares the most skills profile with, and filling at most 3
  per account. A character with no possible home makes a new account.
  Characters with no seats stay unassigned until the pilot places them.
- **Validation on your characters (prod, read-only).**
  - Your user has 17 characters, 13 of them with fleet seats.
  - BearThatCares, Henri Chatelier, Emiliana Gaille, Sashii Ohmiras and Kaleb
    Snowden form a clear clique: every pair was in 171–287 fleets together.
    That is the 5 core accounts you described.
  - The next pair down has 11 fleets together.
  - The overlap peaks at 8 characters at once, which may be inflated by how
    the poller updates `updated_at`. The build will check that against ship
    snapshot timestamps before trusting the account count.
- **Out of scope for Phase 0:** soft detection from ESI online status. The
  Desktop scope has `esi-location.read_online`, so it can be added later as a
  second signal.

The player view in Phase 1 reads these tables. It shows every character with
its capabilities, grouped by account, so a pilot sees what they can bring at
once: one character per account.

## 8. How heavy is it, and when does it run

**Nothing here runs in a request**, and none of it is heavy. These are
measured on MySQL with prod-scale data (51 fittings, about 3,400 characters,
530k skill rows, a year of fleet seats):

| Work | When | Measured |
|---|---|---|
| Re-rate one character | After `update_character` syncs skills **and a level changed** (an unchanged sync queues nothing) | 15 ms median, 21 ms worst; 0.5 s on a worker's first task while it loads the fitting contexts |
| One fitting changed | 15 s after a fitting, correction, substitution, doctrine link or doctrine type change | About 4 s: recompute plus every character on that fitting |
| Nightly pass | 03:15 UTC | 12 s when nothing changed; about 30 s when everything changed, e.g. after a new SDE build |
| Weekly | Inside the nightly pass | Each fitting is recomputed at least every 7 days, so the empirical levels follow pilots' training |
| New SDE build | 12:40 UTC check, when CCP publishes one | About 100 MB download; parsing takes 1.2 s and peaks at 50 MB |

Writes:

- Readiness and capability rows are written only when a value changed, so
  an unchanged night writes no rows.
- At prod scale (about 4,700 characters) the readiness table is about
  100 MB.
- Rows of fittings that are no longer rated are dropped only by full
  passes, never by a one-character refresh.
- `computed_at` on a readiness or capability row means when its values
  last changed.

Memory: a worker process that runs these tasks keeps the SDE (37 MB) and
the fitting contexts in memory. A full pass peaks at about 260 MB for that
process, and repeated passes stay there.

ESI: none. The engine reads the skills the existing sync already stores.

**Why store readiness instead of computing it on read?** One player's page
alone could be computed live: 5–20 characters against 51 fittings is cheap.
But the FC and alliance questions can't be: "who can fly Guardian tonight",
"how many core-ready logi do we have", and the Readiness tribe cards. Those
scan every character, so they read the stored `CharacterFittingReadiness`
rows with a plain indexed SQL filter. Precomputing also follows the corp-page
lesson: prod is far bigger than dev.

**Queue:** no new queue or worker. The tasks live in the new `capabilities`
app, routed as `"capabilities.": "community"` next to `fittings.`. The
per-character refresh is chained from the skill sync on `eveonline`. They are
`AppTask`s queued with a short countdown, so a burst of edits collapses
into one queued copy. The nightly job is `exclusive`, and
every task is safe to run twice.

## 9. Golden checks (prod fittings, rule H)

Levels are hard / core / optimal.

**Revelation (TFIs), Dreads: 21 required + 23 core rows**

- Jump Drive Calibration 0/**5**/5 (mastery III alone asks only I; the R9
  raise brings it to V). Jump Fuel Conservation 0/4/5.
- Capital Energy Turret 5/5/5.
- Surgical Strike, Rapid Firing and Controlled Bursts 0/4/5.
- Armor compensations 0/4/5.
- Long Range Targeting 0/4/5, Signature Analysis 0/5/5.
- Amarr Dreadnought 1/4/5.
- No drone specialisation or shield skill appears. ✅

**Pulse Apocalypse Navy Issue (Napocs), DPS: 11 required + 28 core + 6 optimal**

- Surgical Strike 0/4/5, Rapid Firing 0/5/5, Controlled Bursts 0/4/5,
  Sharpshooter 0/5/5.
- Motion Prediction 5/5/5 and Trajectory Analysis 4/4/5 are already hard.
- Navigation 3/5/5, Evasive Maneuvering 0/4/5, Acceleration Control 0/3/5.
- No jump skills. The utility-drone skills are `optimal`. ✅

**Guardian, Logistics: 8 required + 19 core + 3 optimal**

- Logistics Cruisers 1/4/5, Remote Armor Repair Systems 4/4/5.
- Capacitor Management 0/5/5, Capacitor Systems Operation 0/5/5,
  Capacitor Emission Systems 1/4/5. ✅

**3X/4X Damnation, Links: 15 required + 21 core + 8 optimal**

- Armored, Skirmish and Information Command 5/5/5.
- Armored, Skirmish and Information Command Specialist 1/5/5.
- Command Burst Specialist 4/4/5, Command Ships 1/4/5.
- Leadership 5, Wing Command 4. ✅

(A row's tier is the lowest one with a non-zero level, so a skill such as
Mechanics, hard I and core V, counts as `required`.)

## 10. How strict is core?

Readiness is counted over active and trial players' characters with skills:
3,391 characters, about 911 players. The variants:

- **A** hard only.
- **B** mastery III ∩ dogma ∩ buckets.
- **H** B plus the p10 empirical raise (recommended).
- **D** B plus a median raise (the example in the brief).

| | Unlocked | Hard (A) | B | **H** | D |
|---|--:|--:|--:|--:|--:|
| Fitting-player pairs, all 51 fittings | 30,234 | 23,331 | 20,912 | **17,371** | 11,501 |
| Median share of Proven pilots who pass | — | 93% | 81% | **71%** | 35% |
| Revelation: players (characters) | 243 (398) | 181 (293) | 166 (254) | **145 (219)** | 65 (90) |
| Napoc: players (characters) | 565 (1,050) | 428 (667) | 410 (600) | **313 (424)** | 143 (179) |
| Guardian: players (characters) | 481 (734) | 471 (712) | 430 (620) | **369 (529)** | 194 (248) |
| Damnation: players (characters) | 284 (364) | 205 (250) | 192 (231) | **110 (134)** | 74 (87) |

Mastery II, mastery IV and a p20 cap-down were also run in the prototype.

Findings that shaped the rules:

1. **Per-skill medians compound.** Each core row passes half of the Proven
   pilots, so a set of about 40 rows passes far fewer. Rule D fails 65% of
   Proven pilots, and is stricter than what our own regulars fly. Rule H
   asks only what 90% of Proven pilots already have, row by row.
2. **Utility drones were the biggest false blocker.** With drones counted as
   hard requirements on every fit, only 43% of Proven Apostle pilots and 60%
   of Proven Armageddon pilots were hard-ready. With R2 that rises to 95% and
   80%.
3. **"Proven in the hull" mixes different fits.** Only 59% of Proven Prophecy
   Navy Issue pilots meet the links fit's hard requirements, because most of
   them flew it as DPS. That is why the empirical population requires
   hard-ready pilots (R9), and why seat mapping needs §7.
4. **Masteries undershoot some fits.** They undershoot jump skills on
   capitals (Jump Drive Calibration I at mastery III) and leave out hull
   skills. They over-ask elsewhere: armor comps at IV and above on frigates.
   R9 and R12 cover both directions.
5. **Hard requirements already do most of the work** on T2 battleship fits
   (Gunnery V, Large Energy Turret V, Motion Prediction V). On cheap fits,
   core is where the difference shows: the tackle Punisher goes from 809
   hard-ready players to 638 under B.

The full per-fitting table is in the appendix.

## 11. Decisions (answered 24 Oct 2026)

| # | Question | Answer | What it changes |
|---|---|---|---|
| 1 | Does Doctrine-ready need core? | Yes for strategic doctrines. Non-strategic doctrines need hard only. | Readiness stores `hard_ready` and `core_ready`; each doctrine type picks one (§2). |
| 2 | Do module substitutes count? | Yes | R4 is on. |
| 3 | Anchor? | Not needed: this is about training characters | Anchor and endorsements are removed. Levels stop at Proven. |
| 4 | Player or character? | The player view shows all characters, grouped by account | `CharacterAccount` plus links inferred from co-presence in fleets (§7). |
| 5 | Where does the capability live? | On the fitting. Ambiguous fits still count. | `EveFitting.capability` override; the 9 ambiguous fits keep their auto label until someone overrides it. |
| 6 | A new queue? | Depends on load | It's light (§8), so no new queue: route to `community`. |
| 7 | Character attributes? | Not needed | Flat default training rate (2,250 SP/h), labelled as an estimate. |
| 8 | SDE download in prod? | Use eveuniverse | eveuniverse for types and attributes, plus a checked-in extract for the three things ESI lacks (§3). **Needs your OK.** |

Answered in round 2:

- **SDE updates:** must update without a human looking (§3).
- **Fit check:** required now. Pilots must be able to actually fit it (R17).
- **Overrides:** as low-touch as possible. When a correction is needed, it
  happens on the fitting's admin page in a simple panel (§4).

## 12. What was built

1. **`capabilities` app.**
   - `SdeSnapshot` and the daily `check_sde_build` task, at 12:40 UTC after
     downtime. It is a Sentry cron monitor named "[Capabilities] Load new
     SDE builds".
   - The engine modules in the code map above.
   - The nightly `nightly_capabilities` task, at 03:15 UTC: requirements,
     readiness, capabilities and account links.
   - `refresh_character_readiness`, queued by `update_character` after each
     skill sync.
   - Commands: `python manage.py load_sde_snapshot` and
     `python manage.py recompute_capabilities [--force] [--accounts]`.
   - Tasks route to `community` (`"capabilities."` in `app/queues.py`).
2. **`fittings`.**
   - `EveFittingSkillOverride`, `EveFitting.capability`, and
     `EveFittingHistory.capability` and `.skill_overrides`.
   - The fitting admin page gets a "Fleet job & skill requirements" panel
     and a "Skill corrections" inline. Both save immediately and are
     versioned like tags.
   - Signals queue a recompute 15 s after a fitting, override, substitution,
     doctrine link or doctrine type changes.
3. **Admin.** Read-only lists for requirement sets (with the panel),
   readiness, capabilities, accounts, account links and SDE builds.
4. **Tests** (`capabilities/tests/`).
   - The golden checks and the fit check run on a real SDE subset:
     `fixtures/sde_subset.json.gz`, every skill plus six doctrine fits. To
     regenerate it: `python -m capabilities.tests.make_fixture <zip>`.
   - Services, triggers, account inference, SDE updates and the admin are
     covered too.
5. **Not built yet:** UI, API endpoints and Readiness tribe cards.

## 13. The built engine on prod data

The prototype readiness pass from §10, rerun with the fit check (R17): the
same 51 fittings and about 3,400 characters, in about 8 seconds.

| | Unlocked | Hard-ready | Core-ready |
|---|--:|--:|--:|
| Fitting-player pairs, all 51 fittings | 30,234 | 22,627 | 18,947 |

What the fit check found:

- Every doctrine fit fits with all skills at V. Most are tuned close to the
  limit (the Guardian uses 1,477.4 of 1,478.1 grid).
- **The Rail Links Brutix Navy Issue needs Hybrid Weapon Rigging V.** Its
  Hybrid Metastasis Adjuster rigs raise railgun grid. 14 of 27 Proven pilots
  are 8.7 MW short, so only 82 players can fit it exactly. Before the fit
  check, 348 met its item requirements.
- **The Active Apostle needs Armor Rigging** to offset its rig's grid
  drawback; 5 of 21 Proven pilots can't fit it.
- **The Farm Algos needs Shield Upgrades V**; 3 of its Proven pilots who
  meet the item requirements are short.

These are worth a look from the doctrine team: either the fit asks for a
skill most of its pilots don't have, or they fly it slightly differently.

## 14. The Training tab (player view)

The account page's **Training** tab (`/account/#training`) is the first player view on these tables. Wireframes: https://claude.ai/artifact/8pdrHDxhCkXs5vUkY61f1x.

- **Goals are ships.** A pilot picks doctrine fits per character (`CharacterShipGoal`, ordered by `position`). One ship trains at a time: the first goal that isn't done is "Training now", the rest are "Up next". A goal is done at Ready (`doctrine_ready`), or at Optimal when the pilot chose `target = optimal`.
- **Plans are read, not computed.** A plan is the missing levels from the stored readiness row (`missing_required`, plus `missing_core` for strategic fits), with their prerequisites, ordered cheapest-first but never before a lower level or a prerequisite (`backend/capabilities/engine/plan.py`). Skill ranks and prerequisites come from `CapabilitySkill`, which `store_snapshot` fills from each SDE build, so a request never loads the SDE. Optimal adds every row up to its `optimal_level`. "Copy for EVE" is one `Skill Name IV` line per level.
- **Which fits a pilot sees.** Pilots whose main is in Minmatar Fleet Academy see only a doctrine's `secondary` fits; everyone else never sees them. The role belongs to the doctrine, not the fit (the 10mn Exequror is secondary in Napocs and primary in Beamfields), so a fit is visible when at least one of its doctrine places is. This applies to every view: what you can bring, the ship picker, ready ships and plans.
- **What you can bring** is one row per doctrine (strategic first) and one cell per role (Dreads and Carriers share **Capitals**). A cell is ✓ when every visible fit for that role is ready on some account, "Needs work" otherwise, and "—" when the doctrine has none. A cell opens the doctrine's ships for that role (`/api/training/doctrines/{doctrine_id}/{column}`): how many accounts fly each, or the closest character and a Train button. Characters marked **Not for fleets** (`CharacterTrainingSettings`) don't count.
- **No suggestions in the list.** A character without goals shows only "Pick a ship"; the API still returns its nearest fits as `suggestions`.
- **Account moves** set `CharacterAccountMember.source = pilot` (or no account at all). `infer_accounts` keeps those placements and places the other linked characters around them; empty accounts are dropped.
- API: `/api/training/` (one module per endpoint in `backend/capabilities/endpoints/`), service in `backend/capabilities/training.py`. On dev data the overview takes about 25 ms.

## Appendix: per-fitting readiness (players)

Cells count active and trial players. "Proven" is characters with 3+ fleets
in the hull. Pass rates are shown when 8 or more Proven pilots exist.

| Fitting | Capability | Proven | Unlocked | Hard | Core B | Core H | Proven pass hard / B / H |
|---|---|--:|--:|--:|--:|--:|--:|
| [FL33T] 10mn Augoror | Logistics | 24 | 748 | 588 | 533 | 436 | 100% / 92% / 79% |
| [FL33T] 10mn Exequror | Logistics | 78 | 804 | 604 | 550 | 504 | 86% / 71% / 60% |
| [FL33T] 3X Drake | Links | 2 | 711 | 252 | 251 | 251 | n < 8 |
| [FL33T] 3X Magus | Links | 13 | 374 | 279 | 261 | 140 | 77% / 77% / 54% |
| [FL33T] 3X Pontifex | Links | 5 | 363 | 278 | 264 | 264 | n < 8 |
| [FL33T] 3X Prophecy Navy Issue | Links | 66 | 614 | 249 | 245 | 194 | 59% / 59% / 52% |
| [FL33T] 3X/4X Damnation | Links | 23 | 284 | 205 | 192 | 110 | 91% / 87% / 74% |
| [FL33T] 3X/4X Eos | Links | 9 | 289 | 234 | 214 | 214 | 78% / 56% / 56% |
| [FL33T] 50mn Osprey | Logistics | 4 | 782 | 666 | 609 | 609 | n < 8 |
| [FL33T] 50mn Zarmazd | Logistics | 48 | 314 | 303 | 289 | 224 | 77% / 77% / 60% |
| [FL33T] Active Apostle | Logistics | 21 | 206 | 115 | 110 | 86 | 95% / 81% / 71% |
| [FL33T] Armageddon | Support | 20 | 583 | 511 | 458 | 315 | 80% / 50% / 50% |
| [FL33T] Armor Scorpion | Support | 18 | 639 | 556 | 420 | 363 | 67% / 56% / 50% |
| [FL33T] Battery Augoror | Logistics | 24 | 748 | 697 | 599 | 456 | 100% / 92% / 79% |
| [FL33T] Bhaalgorn | Support | 15 | 555 | 541 | 489 | 308 | 100% / 93% / 80% |
| [FL33T] Buffer Apostle | Logistics | 21 | 206 | 116 | 113 | 87 | 95% / 81% / 71% |
| [FL33T] Buffer Archon | Carriers | 17 | 206 | 58 | 44 | 38 | 82% / 71% / 71% |
| [FL33T] Buffer Nidhoggur | Carriers | 20 | 215 | 62 | 55 | 49 | 65% / 55% / 45% |
| [FL33T] Buffer Thanatos | Carriers | 12 | 196 | 60 | 52 | 50 | 75% / 75% / 75% |
| [FL33T] Cruise Raven | DPS | 97 | 639 | 450 | 408 | 247 | 97% / 93% / 70% |
| [FL33T] Cruise Raven Navy Issue | DPS | 3 | 614 | 448 | 410 | 410 | n < 8 |
| [FL33T] Deacon | Logistics | 7 | 446 | 445 | 386 | 386 | n < 8 |
| [FL33T] Devoter | Tackle | 19 | 369 | 348 | 342 | 315 | 95% / 95% / 79% |
| [FL33T] Enyo | DPS | 27 | 560 | 538 | 482 | 337 | 100% / 89% / 78% |
| [FL33T] Guardian | Logistics | 133 | 481 | 471 | 430 | 369 | 99% / 89% / 80% |
| [FL33T] Inquisitor | Logistics | 7 | 837 | 772 | 618 | 618 | n < 8 |
| [FL33T] Pointrunner Dominix | Support | 18 | 623 | 466 | 435 | 348 | 56% / 50% / 44% |
| [FL33T] Pointrunner Myrmidon | Links | 12 | 675 | 389 | 373 | 373 | 58% / 58% / 58% |
| [FL33T] Pointrunner Vexor | DPS | 18 | 804 | 655 | 541 | 426 | 100% / 56% / 56% |
| [FL33T] Pulse Apocalypse | DPS | 80 | 583 | 428 | 410 | 376 | 98% / 85% / 71% |
| [FL33T] Pulse Apocalypse Navy Issue | DPS | 42 | 565 | 428 | 410 | 313 | 100% / 83% / 74% |
| [FL33T] RR Abaddon | Logistics | 26 | 583 | 524 | 509 | 371 | 81% / 81% / 65% |
| [FL33T] Retribution | DPS | 59 | 572 | 521 | 476 | 293 | 100% / 98% / 81% |
| [FL33T] Revelation | Dreads | 79 | 243 | 181 | 166 | 145 | 100% / 85% / 75% |
| [FL33T] Tackle Maller | Tackle | 15 | 748 | 728 | 626 | 596 | 93% / 67% / 67% |
| [FL33T] Tackle Punisher | Tackle | 45 | 837 | 809 | 638 | 626 | 98% / 64% / 60% |
| [FL33T] Tackle Slasher | Tackle | 71 | 890 | 835 | 694 | 666 | 97% / 77% / 76% |
| [FL33T] Tempest Fleet Issue | DPS | 159 | 655 | 442 | 423 | 281 | 93% / 91% / 69% |
| [FL33T] Torpedo Typhoon | DPS | 168 | 669 | 463 | 418 | 326 | 91% / 80% / 69% |
| [FL33T] Vindicator | Support | 10 | 582 | 540 | 471 | 266 | 100% / 90% / 90% |
| [FL33T] Wolf | DPS | 73 | 618 | 603 | 532 | 399 | 100% / 93% / 73% |
| [NVY] 2Rep Blaster Vexor Navy Issue | DPS | 32 | 790 | 457 | 419 | 253 | 56% / 53% / 44% |
| [NVY] AC Rifter | Tackle | 29 | 890 | 717 | 618 | 572 | 97% / 90% / 86% |
| [NVY] AC Thrasher | Support | 62 | 868 | 751 | 658 | 628 | 95% / 76% / 74% |
| [NVY] AC Thrasher Fleet Issue | Tackle | 136 | 857 | 609 | 580 | 484 | 90% / 88% / 78% |
| [NVY] Beam Harbinger Navy Issue | Links | 7 | 614 | 324 | 319 | 319 | n < 8 |
| [NVY] Beam Omen Navy Issue | DPS | 53 | 727 | 508 | 482 | 353 | 91% / 87% / 70% |
| [NVY] Farm Algos | DPS | 29 | 830 | 622 | 521 | 434 | 69% / 34% / 34% |
| [NVY] Pulse Coercer Navy Issue | Tackle | 6 | 770 | 554 | 506 | 506 | n < 8 |
| [NVY] Rail Exequror Navy Issue | DPS | 152 | 790 | 583 | 522 | 387 | 97% / 91% / 74% |
| [NVY] Rail Links Brutix Navy Issue | Links | 27 | 668 | 348 | 341 | 250 | 78% / 78% / 63% |
