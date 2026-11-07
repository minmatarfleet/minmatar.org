# Invention in the industry planner (T2 / T3)

The build planner prices and plans Tech II and Tech III products end to end:
- inventing the blueprint copy, or building from a copy you already have
- the root build job from that copy
- the component and reaction tree under it, from researched BPOs

Every caller of `plan_item_cost` gets this without its own invention code: the planner page, order pricing floors, the order profit summary, and the guide export.

The mechanics, SDE numbers and market study behind it are in [`docs/research/invention-t2-t3-2026-11.md`](../research/invention-t2-t3-2026-11.md).

## Data

eveuniverse stores invention materials and products but not the success chance, so the planner keeps its own copy of the invention activity. It comes from CCP's official JSONL SDE, the same download the capability engine uses.

| Model | Rows | What |
|---|---|---|
| `InventionOutcome` | ~1,225 | One per (source, outcome): T1 blueprint or ancient relic → T2/T3 blueprint and product, `probability`, `runs` per copy, invention time, datacores, encryption and science skills, copy time and T1 product (for the copy fee) |
| `InventionDecryptor` | 8 | Generic decryptors: chance multiplier, runs, ME, TE (dogma 1112/1124/1113/1114) |
| `IndustrySystemCostIndex.invention` / `.copying` | per system | ESI science cost indices, next to manufacturing and reaction |

How the data is loaded and refreshed:
- **Loader:** `backend/industry/helpers/invention_sde.py` replaces all rows at once.
- **Daily task:** `industry.tasks.refresh_invention_data_task` runs at 12:55. It downloads only when CCP's latest build is newer than the stored rows.
- **By hand:** `manage.py load_invention_data [--path <sde zip or dir>]`. Run it once after deploying, or the planner treats T2/T3 products as T1 (BPO at ME 10).

## Mechanics

| Rule | Value |
|---|---|
| Chance | `base × (1 + (science₁ + science₂)/30 + encryption/40) × decryptor`, capped at 1. Default skills are Science V/V and Encryption IV. |
| Base chance | From the SDE: 34% modules/ammo, 30% frigates and destroyers, 26% cruisers, 22% battleships, 18% capitals. Relics: 26/21/14% for intact/malfunctioning/wrecked. |
| Output | One copy per success with the SDE's runs: 10 for most modules, 1 for ships and rigs, 20/10/3 for relics. ME 2 / TE 4 plus the decryptor. T3 is assumed to work like T2. |
| Consumed per attempt | Datacores, the decryptor, and one T1 copy run or one relic, whether the attempt succeeds or not |
| Invention fee | `0.02 × EIV(product run)` charged like any job: index × (1 − hull and lab-rig bonus) × (1 + FW bonus), plus facility tax and SCC on the same base |
| Copy fee (T2) | `0.02 × EIV(T1 product run)` at the copying index |
| Science times | Sotiyo −30%, XL Laboratory Optimization I −20% × 1.9 in lowsec. Advanced Industry −3%/level on invention; Science −5%/level on copying. |

Facility profiles gained two job classes in `backend/industry/helpers/facility_profiles.py`:
- `SCIENCE`: the hull plus the XL lab rig at the Sotiyo freeports, the Azbel role bonus at Hydra.
- `EQUIPMENT_MANUFACTURING`: modules, charges, drones, fighters, implants and deployables. These are the SDE Equipment / Charges / Drones rig filters, and no freeport fits those rigs, so they get the hull bonus only.

Before this change, any root product used the ship rig. A T1 or T2 module root lost 3.8% ME and 38% TE that the Sotiyo never gave it. Other roots (fuel blocks, structures) keep the ship profile they had.

## How a plan is built

Pure maths lives in `backend/industry/helpers/invention.py`. Database access and pricing live in `backend/industry/helpers/invention_planner.py`.

1. **`quote_invention(product, quantity, facility, request)`** prices every source × decryptor (none plus the 8). It skips a decryptor without a Jita price unless you ask for it by name. The cheapest full cost per unit wins. That cost is invention plus the root build job: the root's materials at Jita sell at that copy's ME, plus its install fee batched per copy. That's why Optimized Augmentation or Parity usually wins on ships, while modules usually take no decryptor.
2. **`plan_invented_build`** runs `plan_build` with a `RootBlueprint(me, te, runs_per_copy)`:
   - The root job uses the copy's ME/TE and is split into one job per copy. Copies can't be merged, so ME rounding is per copy.
   - Every other job keeps the tree's BPO `blueprint_me/te`.
   - The quote is attached as `plan.invention`.
3. **`cost_build_plan`** adds the expected invention cost to the grand total and `cost_per_isk`, the way it adds the navy BPC. It stays outside `manufacturing_isk`. The line items are `invention_materials` and `invention_jobs`.
4. **`plan_item_cost`** does this for any root with invention outcomes and sets `kind` to `"T2"` or `"T3"`. With `include_invention=False` (LP conversion, or a supplied copy) it builds from a copy at `bpc_me`/`bpc_te`, default 2/4, with no invention cost.

Costs are expected values and amortise copy runs. One unit from a 10-run copy is charged a tenth of the expected attempts, because the leftover runs build the next lot. The buy list rounds up to whole attempts. The quote also gives the attempts that cover 9 runs in 10 (`attempts_p90`).

## API

| Endpoint | What |
|---|---|
| `POST /api/industry/planner/plans` | New request fields: `blueprint_source` (`invent` default, or `supplied_bpc`), `decryptor` (`auto`, `none` or a type id), `invention_source_type_id`, `bpc_me`/`bpc_te`, `invention_skills`. New response fields: `blueprint_source`, `default_blueprint_me/te`, `root_blueprint_me/te`, `root_runs_per_copy`, `invention`, and the cost breakdown's `invention_*` fields. |
| `GET /api/industry/planner/invention/{type_id}` | Sources and decryptors, for the planner controls. 404 when the product isn't invented. |
| `GET /api/industry/planner/invention/{type_id}/quote` | The same quote the plan uses, for the htmx card |
| `GET /api/industry/products/{id}/build` | `invention` (sources, datacores, the cheapest way at Amamake) and `invention_cost`. The Build tab margin subtracts it. |
| `GET /api/industry/planner/facilities/{key}` | `job_classes` include `equipment_manufacturing` and `science`; `cost_indices` include `invention` and `copying` |

## UI

- **Planner page** (`/industry/orders/planner`): for invented products it adds the controls *T2/T3 copy* (Invent / I have the copy), *Decryptor*, *Invent from* (when there's more than one source), and Copy ME/TE for a supplied copy. The cost summary gains an *Invention* cell. The invention card is the htmx partial `planner_invention_component`, reloaded after each plan from hidden inputs that Alpine binds. It shows one headline line, with the buy list, the P90 attempts and the decryptor comparison behind a disclosure.
- **Product Build tab**: `ProductBuildInvention` shows the sources, datacores and invention cost per unit. The margin hint says invention was taken off.

## Not covered yet

- **Unconfirmed mechanics:** check these against an in-game Industry window: SCC on the 2% invention base, Advanced Industry on invention time, and T3 copies starting at ME 2 / TE 4.
- **Root only:** nested invented inputs (a T2 item used inside another build) stay leaves priced at Jita.
- **Copy sourcing:** buying T1 copies or T2 BPOs on the market is not modelled. The planner assumes you copy from your own T1 BPO, or that the copy is supplied.
- **Skills:** pricing uses fixed skills (Science V/V, Encryption IV). It doesn't read a character's skills.
