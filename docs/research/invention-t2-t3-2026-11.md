# Invention, T2 and T3 production

- **Date:** 2026-11-06
- **Scope:** How invention, Tech II and Tech III production work today, and what they earn at the alliance's Amamake Sotiyo.
- **Data:** CCP SDE build 3670638 (released 2026-11-04), ESI adjusted prices and system cost indices (2026-11-06), Fuzzwork Jita 4-4 aggregates (2026-11-06), ESI The Forge market history (last 30 and 90 days), and the ESI TLF loyalty store.
- **Acted on by:** none yet.
- **Reproduce:** the scripts in [`invention-t2-t3-2026-11/`](invention-t2-t3-2026-11/). The run order is in the docstring of `fetch_inputs.py`. Prices move daily, so treat every ISK figure as a 6 November snapshot.

## Key findings

1. **Invention itself is cheap. Tax, components and the build job are where the money goes.** For T2 ships, invention averages 1.4% of the unit cost. On a Muninn, the manufacturing job fee is about 11.8M per hull at Amamake, roughly 7 times the 1.6M spent on invention.
2. **Buying components on the market and selling the product in Jita loses money on most T2 ships.** At Jita sell prices for inputs, the median T2 ship line runs at **−9.5%** and only 31% of lines make a profit. Modules (+6.2%) and ammo (+12.2%) still work at retail prices.
3. **The profit comes from going up the chain or buying patiently.** Building components in-house moves the median T2 ship to +1.9%, with 58% of lines profitable. Filling inputs with buy orders moves it to +5.8%. Composite reactions add a median +9% at Jita sell and +18% from buy orders. Component manufacturing adds a median +12.7%.
4. **For T2 ships, a decryptor always pays.** No T2 ship line is cheapest without one. Optimized Augmentation wins 46 hulls and Parity 36. For modules and ammo, no decryptor or a cheap Process or Symmetry decryptor usually wins.
5. **Minmatar's best lines right now are Hyena, Wolf, Hound and Broadsword.** Muninn, Rapier and Vagabond are underwater even with in-house components (table below).
6. **T3 relic grades are priced to an even cost per unit.** Wrecked relics sell for 0.2–4M and intact relics for 18–97M, but the cost per unit comes out within 1–3% across grades. Pick the grade by how many jobs you want to run, not to save ISK.
7. **Datacore prices are set by FW loyalty points.** TLF sells 5 datacores for 250 LP plus 250k ISK, so 50 LP + 50k per core. At about 1,000 ISK/LP that puts the floor near 100k, and most datacores trade between 97k and 120k. The alliance's LP buyback and T2 invention costs share that market.
8. **Amamake's FW discount is worth the same as moving to a quiet system.** Amamake's cost index is high (10.75% manufacturing, 10.68% invention). The −50% FW infrastructure discount brings the total fee to about Basgerin's level. Auner, with no discount and a 1% tax, costs about 50% more per job.
9. **The invention mechanics haven't changed since the 2014–15 merge.** The changes since then are to fees and taxes: SCC surcharge 4% (Feb 2024), sales tax base 7.5% (Mar 2025), SCC on ME/TE research halved (Jul 2025), and +5% installation fees in starter space (May 2026).

## 1. The two pipelines

**Tech II:** T1 BPO → copy (T1 BPC) → **invention** (+ datacores, optional decryptor) → T2 BPC → manufacture (+ T2 components, the T1 hull or module, morphite, R.A.M., P2 commodities) → T2 item.

T2 components come from moon materials: moon ore → reprocess → raw moon materials → **intermediate reaction** → **composite reaction** → component manufacturing. On a Muninn that means 75 Plasma Thrusters, 5,625 Fernite Carbide Composite Armor Plates, 1,350 Nanomechanical Microprocessors and more. Each component pulls from Fernite Carbide, Phenolic Composites, Ferrogel, Nanotransistors and other composites.

**Tech III:** Ancient relic (from hacking Sleeper relic sites in wormholes) → **invention** (+ subsystem or engineering datacores, optional decryptor) → T3 BPC → manufacture. Inputs are hybrid tech components, built from **hybrid polymers** (fullerite gas from wormhole gas sites, reacted in a hybrid reactor) plus **Sleeper salvage** (Melted Nanoribbons, Neurovisual Input Matrix, Electromechanical Hull Sheeting and others).

Reactions need a refinery in space of 0.4 security or lower. Amamake (0.44) is lowsec and qualifies.

## 2. Invention mechanics (from the SDE)

### Success chance

```
chance = base × (1 + (science₁ + science₂) / 30 + encryption / 40) × decryptor multiplier
```

With both science skills at V and encryption at IV, the skill factor is **1.433**. With everything at V it is 1.458. Encryption IV → V adds only 1.7% relative chance. Science IV/IV → V/V adds 4.9%. Train science first.

Neither the input copy's ME/TE/runs nor your attributes affect the chance. The input BPC loses a run on every attempt, and datacores and decryptors are consumed whether the job succeeds or fails.

### Base chance, runs, datacores and time by product type

| Product | Base chance | Runs per BPC | Datacores (each of 2 types) | Base invention time |
|---|---|---|---|---|
| Modules, rigs, ammo, drones, fighters | 34% | 10 (some 5; rigs 1; Rapid Heavy launcher 20) | 1–2 (flex hardeners 8) | 3.8–20 h |
| T2 frigates and destroyers | 30% | 1 | 2 (dictors 4) | 17.8–26.7 h |
| T2 cruisers, battlecruisers, barges, haulers | 26% | 1 | 8 (command ships 16) | 35.6–44.5 h |
| Marauders, Black Ops | 22% | 1 | 32 | 53.3 h |
| Jump freighters, T2 capitals | 18% | 1 | 64–85 | 412–550 h |
| T3 from **intact** relic | 26% | 20 | 3 | 1 h |
| T3 from **malfunctioning** relic | 21% | 10 | 3 | 1 h |
| T3 from **wrecked** relic | 14% | 3 | 3 | 1 h |

Every invented BPC starts at ME 2% and TE 4%. Decryptors modify ME, TE and runs, and T2 BPCs cannot be researched or copied. Relic outputs are listed per outcome, so you choose the exact subsystem or hull. The random subsystem roll is gone. A single Intact Armor Nanobot can become any of the three Loki defensive subsystems.

### Decryptors (SDE values; Jita sell on 2026-11-06)

| Decryptor | Chance × | Runs | ME | TE | Jita |
|---|---|---|---|---|---|
| Accelerant | 1.2 | +1 | +2 | +10 | 307k |
| Attainment | 1.8 | +4 | −1 | +4 | 2.13M |
| Augmentation | 0.6 | +9 | −2 | +2 | 656k |
| Optimized Attainment | 1.9 | +2 | +1 | −2 | 2.93M |
| Optimized Augmentation | 0.9 | +7 | +2 | 0 | 4.24M |
| Parity | 1.5 | +3 | +1 | −2 | 761k |
| Process | 1.1 | 0 | +3 | +6 | 217k |
| Symmetry | 1.0 | +2 | +1 | +8 | 202k |

**Which decryptor wins** (cheapest cost per unit at Amamake):

- **T2 ships:** Optimized Augmentation 46, Parity 36, Process 10, Accelerant 8, Symmetry 5. None wins 0 times.
- **T2 modules:** none 173, Process 148, Symmetry 93, Parity 78, Augmentation 69.
- **Ammo:** none 73, Process 62, Parity 26.

On ships, runs and ME are worth much more than chance, because each extra run spreads an expensive attempt over another hull and each ME point saves 1% of a 100M+ bill of materials. On modules, attempts are cheap, so the decryptor's price usually outweighs what it adds.

### Skills

- Each line needs its race's encryption skill: Amarr (315 lines), Caldari (280), Gallente (251), Minmatar (173), Sleeper for all T3 (169), Upwell (18: Vorton weapons, condenser packs, Deluge/Torrent) and Triglavian (13). It also needs two science skills, the most common being Electronic Engineering (330), Quantum Physics (228) and Mechanical Engineering (222).
- T3 lines use Sleeper Encryption plus a science skill and the matching Subsystem Technology skill, or Mechanical Engineering for hulls.
- Laboratory Operation and Advanced Laboratory Operation add science job slots. Scientific Networking adds remote range.

## 3. Facilities and job cost

### Bonuses at the Amamake Sotiyo (Police Weapons Facility)

These are the SDE values, using the rig fit in [`facility_profiles.py`](../../backend/industry/helpers/facility_profiles.py). Lowsec rig multiplier is ×1.9.

| Source | Material | Time | Job cost |
|---|---|---|---|
| Sotiyo hull (all industry) | −1% | −30% | −5% |
| XL Ship Manufacturing Efficiency I (*all* ships incl. T2/T3 and subsystems) | −3.8% | −38% | |
| XL Thukker Structure & Component Efficiency (components) | −3.8% | −38% | |
| XL Laboratory Optimization I (copy, invention, research) | | −38% | −19% |
| Tatara + L Reactor Efficiency II (reactions; lowsec ×1.0, null ×1.1) | −2.4% | −25% hull, −24% rig | |

Two things stand out:

- **The Thukker rig is a lowsec specialist.** It gets ×1.9 in lowsec but only ×0.1 in highsec and null, so it is the right rig for Amamake and the wrong one anywhere else.
- **No module or ammo ME rig is fitted.** T2 modules and ammo get only the Sotiyo's 1%. An XL Equipment and Consumable Efficiency rig would add 3.8% ME on the categories with the most profitable lines.

### Job fee formula

The formula matches [`industry_formulas.py`](../../backend/industry/helpers/industry_formulas.py):

```
fee = EIV × index × (1 − structure/rig cost bonus) × (1 + FW bonus) + EIV × (facility tax + SCC 4%)
```

- **EIV** is the ME0 materials priced at ESI adjusted prices.
- **Invention and copying** use **2% of EIV** of the product: the T2 item for invention, the T1 item for copying.

Because SCC (4%) and facility tax apply to the whole EIV, T2 manufacturing pays about **4.75% of item value in fixed tax wherever you build.** That is before the cost index.

Manufacturing fee per **Muninn** (EIV 120.1M per hull):

| Where | Index | Fee per hull |
|---|---|---|
| Amamake Sotiyo, FW −50%, 0.75% tax | 10.75% | **11.8M** |
| Basgerin Sotiyo, 0.75% tax | 5.82% | 12.3M |
| Auner Sotiyo, 1% tax | 11.14% | 18.7M |
| Hypothetical quiet system (1.4% index), Sotiyo, 0.75% tax | 1.4% | 7.3M |

The fee runs from about 5% to 13% of the hull's sale price. Spreading jobs over low-index systems saves more than any decryptor or skill choice.

## 4. Economics at Amamake

### Model assumptions

- Science V/V and encryption IV.
- Inputs at Jita sell (5th percentile). Output sold on a Jita sell order, less 3.375% sales tax and 1.5% broker fee.
- The cheapest decryptor per line, and the Amamake fees above.
- The T1 BPC is copied from your own BPO; copy job cost is included. Relics are bought at Jita.
- "Buy orders" prices every input at the Jita buy 5th percentile. "In-house components" builds T2 or hybrid components from Jita-priced composites or polymers at the Sotiyo.
- 1,074 products had prices.

| Category | Lines | Median margin (Jita sell inputs) | Median with in-house components | Median with buy-order inputs | Invention share of unit cost |
|---|---|---|---|---|---|
| T2 ships | 112 | **−9.5%** | +1.9% | +5.8% | 1.4% |
| T2 modules | 588 | +6.2% | +9.1% | +17.1% | 5.4% |
| T2 ammo | 161 | +12.2% | +13.2% | +29.4% | 9.3% |
| T3 subsystems | 48 | −7.3% | −5.6% | +10.4% | n/a |

Skills and decryptors matter most for ammo and drones, where invention is about 10% of the unit cost. For ships, getting components cheaply matters far more.

### Minmatar hulls

Volumes are Jita sales per day, 30-day average.

| Hull | Class | Jita sell | Sold/day | Best decryptor | Margin (retail) | In-house components | Buy-order inputs |
|---|---|---|---|---|---|---|---|
| Hyena | Electronic Attack | 22.7M | 32 | Parity | +16.4% | +26.7% | +29.1% |
| Wolf | Assault Frigate | 23.5M | 60 | Accelerant | +5.8% | +14.5% | +16.5% |
| Hound | Stealth Bomber | 19.8M | 56 | Symmetry | +2.1% | +12.4% | +15.2% |
| Broadsword | HIC | 272.6M | 15 | Process | +7.4% | +12.6% | +15.8% |
| Svipul | Tactical Destroyer | 69.3M | 34 | Opt. Attainment | +2.4% | +3.6% | +16.3% |
| Vargur | Marauder | 1,052M | 66 | Opt. Augmentation | −6.5% | +1.6% | +5.7% |
| Huginn | Combat Recon | 157.9M | 38 | Opt. Augmentation | −8.8% | +0.8% | +3.6% |
| Scimitar | Logistics | 152.2M | 40 | Opt. Augmentation | −5.4% | +1.1% | +4.0% |
| Sabre | Interdictor | 39.6M | 137 | Parity | −9.5% | +1.1% | +3.2% |
| Jaguar | Assault Frigate | 19.0M | 56 | Accelerant | −13.4% | −2.7% | −0.2% |
| Loki | Strategic Cruiser | 232.2M | 161 | Opt. Augmentation | −5.4% | −4.0% | +13.3% |
| Sleipnir | Command Ship | 277.2M | 69 | Opt. Augmentation | −13.1% | −4.3% | −0.9% |
| Claymore | Command Ship | 284.4M | 18 | Opt. Augmentation | −13.2% | −4.6% | −1.7% |
| Panther | Black Ops | 814.1M | 12 | Opt. Augmentation | −13.9% | −7.5% | −1.4% |
| Vagabond | HAC | 145.2M | 37 | Opt. Augmentation | −18.9% | −7.8% | −4.8% |
| Rapier | Force Recon | 140.0M | 30 | Opt. Augmentation | −22.6% | −11.8% | −8.6% |
| Muninn | HAC | 141.6M | 32 | Accelerant | −21.7% | −12.8% | −8.5% |

### Where the Muninn's cost goes

Values are per hull, Jita sell, ME0:

- Nanomechanical Microprocessors: 55.8M
- Fernite Carbide Composite Armor Plates: 34.9M
- Electrolytic Capacitor Units: 25.7M
- Deflection Shield Emitters: 16.3M
- Rupture hull: 11.5M
- Everything else: about 19M

That is 163M of inputs against a 141.6M sale price. Building the Minmatar components yourself barely helps. A Nanomechanical Microprocessor costs 42.2k to build from Jita composites and sells for 41.3k. HAC prices only work for someone who also owns the composite and moon-material stages.

### Where the margin sits along the chain

All figures are medians at Jita prices, after Amamake and Tatara bonuses:

| Stage | Median margin (sell inputs) | Median margin (buy-order inputs) |
|---|---|---|
| Composite reactions (41 formulas) | +9.0% | +17.8% |
| Polymer reactions, T3 (9) | −2.3% | +20.0% |
| T2 construction components (44) | +12.7% | n/a |
| Hybrid tech components, T3 (15) | −15.8%, thin market and noisy | n/a |
| T2 ships from bought components | −9.5% | +5.8% |

The market pays for the **reaction and component stages and for owning the moon or gas.** The final T2 ship step mostly breaks even. That matches how T2 industry is organised: groups that mine their own moons and run their own Tatara take the margin, and pure inventors compete on thin spreads.

### T3: relic grades come out even

| Product | Relic | Relic price | Cost per unit (best decryptor) | Jita sell |
|---|---|---|---|---|
| Loki hull | Intact / Malfunctioning / Wrecked | 97.1M / 28.7M / 4.1M | 233.3M / 233.7M / 232.8M | 232.2M |
| Svipul | Intact / Malfunctioning / Wrecked | 22.2M / 5.8M / 0.9M | 64.4M / 65.3M / 66.2M | 69.3M |
| Loki Offensive: Projectile Scoping Array | Intact / Malf. / Wrecked | 17.7M / 5.0M / 0.15M | 38.4M / 38.1M / 37.8M | 36.2M |

With intact relics, Optimized Attainment wins: a 0.71 chance and 22 runs. With wrecked relics, the run-adding decryptors win. Subsystem datacores cost only 11–13k, so T3 invention costs are almost all relic and decryptor.

### Higher-margin liquid lines right now (snapshot)

These are ranked by profit at 10% of Jita daily volume. Lines whose Jita sell price was more than 25% off their 30-day average were dropped.

| Line | Jita sell | Profit/unit | Margin | Sold/day |
|---|---|---|---|---|
| Vorton Tuning System II | 29.4M | 4.38M | 15.7% | 234 |
| Medium Trimark Armor Pump II | 13.5M | 1.28M | 10.0% | 777 |
| Oneiros | 170.2M | 22.1M | 13.7% | 40 |
| Nergal | 301.5M | 25.3M | 8.8% | 32 |
| Confessor | 75.6M | 7.57M | 10.5% | 101 |
| Capital Transverse Bulkhead II | 238.3M | 43.7M | 19.3% | 15 |
| Medium Hyperspatial Velocity Optimizer II | 14.0M | 1.11M | 8.3% | 486 |
| Buzzard | 19.4M | 1.97M | 10.7% | 241 |
| Helios | 20.5M | 3.69M | 18.9% | 83 |
| Large Thermal Shield Reinforcer II | 8.2M | 1.55M | 19.8% | 149 |

Medium T2 rigs keep showing up. They take 1 run per BPC, but their inputs are salvage, not moon components. Rigs, as a group, are the cleanest T2 market for a lowsec builder without moons.

## 5. Datacores and FW loyalty points

- **The TLF store sells six datacore types**, 5 cores for 250 LP + 250k ISK: Hydromagnetic Physics, Molecular Engineering, Nuclear Physics, Minmatar Starship Engineering, Upwell Starship Engineering and Mechanical Engineering. Most datacores trade at 97k–120k in Jita, which is the LP floor at about 1,000 ISK/LP.
- **Two datacore types are outliers.** Mechanical Engineering (27.5k, below the LP floor, so it is oversupplied from somewhere) and the four subsystem engineering cores (11–13k, from wormhole sites) are much cheaper.
- **For the alliance:** a TLF datacore offer returns 430–800 ISK/LP sold to buy orders (Mechanical Engineering loses money), against more than 1,000 ISK/LP for the best Republic Fleet modules. Datacores are not the best LP sink. An in-house inventor who would otherwise pay Jita prices still saves about 50k per core by redeeming LP.

## 6. Risk and variance

- **Failure streaks are normal.** At 45% (Muninn with Accelerant), five failures in a row happen 5% of the time and expected attempts are 2.2. At 18% (wrecked relic with Optimized Augmentation), ten straight failures happen 14% of the time. Budget for streaks; don't read them as bad luck.
- **Invention lead times are long.** Base invention time is 35.6 h for a cruiser hull and 53 h for battleship-class hulls. The Sotiyo and lab rig cut that by about 57%. Manufacturing a Muninn takes 66.7 h base, or about 19 h with Sotiyo, rig, TE 4% and Industry/Advanced Industry V. Thin markets like Panther (12/day) or Claymore (18/day) can move a lot between starting a job and selling.
- **Cost indices are self-inflicted.** The index rises with the share of cluster industry in that system. Concentrating alliance jobs in Amamake raises its index, which is why the FW discount matters.

## 7. What changed recently

- **Feb 2024:** SCC surcharge on industry jobs went from 1.5% to 4%.
- **Mar 2025:** sales tax base went to 7.5%, or 3.375% at Accounting V.
- **Jul 2025 (Legion):** SCC on ME/TE research was halved to 2%, described as temporary.
- **Mar 2026:** reaction times on several mineral and Prismaticite formulas were cut tenfold (3,600 s → 360 s).
- **May 2026:** installation fees rose 5% for manufacturing, ME/TE research and invention, as part of starter-space balancing.
- **Jun 2026:** a UI fix made Archon blueprints show their invention info.
- **Not found:** no change to invention chances, datacore or decryptor values, or relic mechanics since the 2014–15 merge of invention and reverse engineering. The SDE numbers above are current as of build 3670638.

## 8. Implications for alliance industry

1. **Price T2 against owned or buy-order inputs, never Jita retail.** At retail, most of our doctrine hulls lose money.
2. **Small T2 hulls are worth inventing in Amamake now:** Hyena, Wolf, Hound, Broadsword, and medium T2 rigs. Treat HACs and recons as service builds for doctrine supply, not as profit lines, unless we own the composite stage.
3. **Consider an XL Equipment and Consumable Efficiency rig.** No module or ammo ME rig is fitted, and those are the categories where T2 invention profits even at retail.
4. **Split jobs by index.** Basgerin's unbonused index (5.8%) is about as cheap as Amamake's bonused one (10.75% × 0.5). If the FW discount ever drops, Amamake becomes the most expensive of our three freeports.
5. **The site's build planner** ([`build_planner.py`](../../backend/industry/helpers/build_planner.py)) costs manufacture and reaction trees but has no invention step. Adding datacores, decryptor choice and success chance to the per-unit cost would put T2 orders on the same footing as the navy BPC lines it already handles. `model.py` here is a working reference for that calculation.

## Sources

- CCP static data export, build 3670638: `developers.eveonline.com/static-data` (`blueprints`, `typeDogma`, `industryModifierSources`, `industryTargetFilters`).
- ESI: `/markets/prices/`, `/industry/systems/`, `/markets/10000002/history/`, `/loyalty/stores/1000182/offers/`.
- Fuzzwork market aggregates, Jita 4-4: <https://market.fuzzwork.co.uk/>
- [EVE University: Invention](https://wiki.eveuniversity.org/Invention), [Reactions](https://wiki.eveuniversity.org/Reactions), [Tax](https://wiki.eveuniversity.org/Tax)
- [CCP: Lighting the invention bulb (2014)](https://www.eveonline.com/news/view/lighting-the-invention-bulb). This was the original proposal; the SDE values above supersede its numbers.
- [CCP: Exploration & Industry Balance Rework (2025-07-18)](https://www.eveonline.com/news/view/exploration-and-industry-balance-rework)
- [CCP: Patch notes 23.02](https://www.eveonline.com/news/view/patch-notes-version-23-02), [24.01](https://www.eveonline.com/news/view/patch-notes-version-24-01)
- [EVE support: Invention](https://support.eveonline.com/hc/en-us/articles/203210642-Invention)
- [EVE Forums: job cost of invention and copy](https://forums.eveonline.com/t/job-cost-of-invention-and-copy/260821)
