---
title: 'Faction Warfare Complexes'
excerpt: 'FW plexing in depth: gate and landing mechanics, LP payouts, and victory points by site—including Cradle of War complexes.'
category: 'Faction Warfare'
author: 'BearThatCares'
---
Faction warfare complexes (**plexes**) are where most fights and most LP happen. Capture them to earn loyalty points and push systems toward flipping for the Minmatar Republic.

For map colors, system types (frontline / command ops / rearguard), contested vs advantage, and how site names are read, start with [Faction Warfare Basics](/guides/faction-warfare-basics/). This guide covers plexing itself: the deadspace pocket, and the LP / victory point tables.

## Basics

### Outside the plex

Warping to a plex lands you at an acceleration gate (Open plexes have no gate—you land inside at your warp range).

- Align to the pocket before activating the gate so you don’t sit still on the gate.
- Gate activation range is ~90km. A warp-to-100 may land you just outside range.
- A warp disruptor or scram blocks the gate.
- The gate is collidable—warping to 0 often means bouncing off it when you activate.
- Longer warps are safer: you always land between the gate and your origin, so distant warpins leave more room.
- You can warp to objects on the **outside** grid.

### Inside the plex

- You cannot warp to anything on the grid (objects or fleetmates), even after the site finishes.
- You can always warp out (unless pointed/scrambled); warping back returns you to the acceleration gate.
- Capture radius is 30km; the pocket itself is much larger.
- The central structure has no collision.

### Landing beacon

You land within ~3.5km of the landing beacon at a random spot.

- Enable brackets so you can see the beacon.
- The beacon is a large collidable with a small hitbox—rarely sticky.
- Sitting on the beacon minimizes distance to anyone entering.
- Hold the range you want for the next fight relative to the beacon.
- The NPC spawns from the central structure ~8–12km from the beacon.

### Landing invulnerability

Anyone already inside sees you before you finish landing and can move on you early.

- Landing ships decelerate to 0 m/s.
- ~10 seconds of invulnerability after landing ends immediately if you do anything other than preheat modules.
- Use that window to decide: burn in, burn out, or hold.
- Reinforcements always land on the beacon—they cannot land on a friendly already inside.

## Site Restrictions

Each site name encodes size, ship classification, and how many pilots get a full payout. Anything under the size cap can usually enter.

| Size | Capture time | Maximum ship class |
| --- | --- | --- |
| Scout | 10 min (BSC-1: 5 min) | Frigates and below |
| Interceptor | 10 min | Interceptors only |
| Small | 10 min | Destroyers and below |
| Medium | 15 min | Cruisers and below |
| Moderate | 15 min | Battlecruisers and below |
| Large | 15 min | Battleships and below |
| Open | 15 min | Any ship |

| Classification | Allowed ships |
| --- | --- |
| BSC | Tech I only |
| NVY | Navy and Tech I |
| ADV | Tech II, Pirate, Navy, and Tech I |
| ELT | Tech III destroyers and below (all ships of that size, including T3s) |

| Payout suffix | Meaning |
| --- | --- |
| `-1` | One pilot receives full payout before rewards split |
| `-2` | Up to two pilots receive full payout before rewards split |
| `-3` | Up to three pilots receive full payout before rewards split |
| `-4` | Up to four pilots receive full payout before rewards split |
| `-X` | Up to X pilots receive full payout before rewards split |

Example: **Minmatar Scout BSC-1** — frigates only, Tech I only, one full payout before splitting.

Other rules:

- The payout number is not a hard entry cap—extra pilots can enter, but LP splits past the cap.
- Smaller ships can enter larger plexes (e.g. destroyers in a Large).
- T3 destroyers count as one size larger (Medium ADV+). T3 cruisers only fit Large ADV and Open.

**Where to plex:** Frontlines pay the most LP and VP. Command Ops and rearguards pay less, but are quieter and sometimes useful for surprise contest / advantage work. See [Faction Warfare Basics → Systems](/guides/faction-warfare-basics/#systems).

## Site rewards

Loyalty points depend on site type and system type.

| System type | LP multiplier |
| --- | --- |
| Frontline | 1.5× base |
| Command Operations | 1.0× base |
| Rearguard | ~0.01× base (almost nothing) |

| Site | Full-payout pilots | Base LP | Frontline LP |
| --- | --- | --- | --- |
| Scout BSC-1 | 1 | 7,500 | 11,250 |
| Scout NVY-1 | 1 | 10,000 | 15,000 |
| Scout NVY-2 | 2 | 12,500 | 18,750 |
| Small Interceptor-1 | 1 | 25,000 | 25,000 |
| Small NVY-1 | 1 | 15,000 | 22,500 |
| Small NVY-2 | 2 | 18,750 | 28,150 |
| Small ADV-1 | 1 | 17,500 | 26,250 |
| Small ADV-2 | 2 | 20,000 | 30,000 |
| Contested Field Research Facility | up to 5 | 30,000 | 45,000 |
| Medium NVY-1 | 1 | 20,000 | 30,000 |
| Medium NVY-3 | 3 | 25,000 | 37,500 |
| Medium ADV-1 | 1 | 25,000 | 37,500 |
| Medium ADV-3 | 3 | 30,000 | 45,000 |
| Moderate NVY-3 | 3 | 35,000 | 52,500 |
| Large NVY-1 | 1 | 25,000 | 37,500 |
| Large NVY-4 | 4 | 30,000 | 45,000 |
| Large ADV-1 | 1 | 25,000 | 37,500 |
| Large ADV-4 | 4 | 30,000 | 45,000 |
| Open | up to 5 | 30,000 | 45,000 |
| Battlefield | up to ~30 | 50,000 | 50,000 |

Notes:

- Multi-pilot sites pay the listed LP to each pilot up to the cap; past that, the pool splits.
- Solo (`-1`) versions of a size usually pay a bit less than the multi-pilot variant of the same size/class.
- Grouping into a `-2` / `-3` / `-4` site is often better ISK than splitting a `-1`.
- Small Interceptor-1 is listed at the same LP in both columns because it pays frontline-like rates while spawning in Command Ops.

CCP is always tweaking these values—numbers above may have changed recently.

## Site impact

Capturing a plex adds victory points toward contested %. A system needs **75,000 VP** to hit 100% and become vulnerable. Advantage increases VP per capture—see [Faction Warfare Advantage](/guides/faction-warfare-advantage/).

| Site | Victory points | ≈ Contested % (no advantage) | Capture time |
| --- | --- | --- | --- |
| Scout NVY | 25 | 0.03% | 10 min |
| Scout BSC-1 | 50 | 0.07% | 5 min |
| Small NVY | 50 | 0.07% | 10 min |
| Small ADV | 75 | 0.10% | 10 min |
| Small Interceptor-1 | 150 | 0.20% | 10 min |
| Medium NVY | 150 | 0.20% | 15 min |
| Medium ADV | 175 | 0.23% | 15 min |
| Contested Field Research Facility | 300 | 0.40% | 10 min |
| Large NVY | 250 | 0.33% | 15 min |
| Large ADV | 300 | 0.40% | 15 min |
| Moderate NVY-3 | 600 | 0.80% | 15 min |
| Open | 350 | 0.47% | 15 min |
| Battlefield | 2,000 | 2.67% | ~30–45 min |

Larger sites move contested much faster. When both sides are pushing the same system, expect the real fight over Mediums, Larges, Moderates, Opens, and Battlefields.

## System Capture

At 100% contested the infrastructure hub becomes vulnerable. Push a bit past 100% before committing to the siege—defenders will try to grind contested back down.

Destroying the i-hub flips the system and resets victory points to 0.

## Additional Resources

- [Faction Warfare Basics](/guides/faction-warfare-basics/)
- [Faction Warfare Advantage](/guides/faction-warfare-advantage/)
- [New Player Fleet Guide](/guides/new-player-fleet-guide/)
- [Guides index](/guides/)
- [Amarr vs Minmatar Dotlan](https://evemaps.dotlan.net/map/Amarr_VS_Minmatar#sov)
- [Patch Notes — Version 21.05](https://www.eveonline.com/news/view/patch-notes-version-21-05) (victory point rebalance)
- [Patch Notes — Version 22.02](https://www.eveonline.com/news/view/patch-notes-version-22-02) (multi-pilot payout caps)
- [Cradle of War: Expansion Notes](https://www.eveonline.com/news/view/cradle-of-war-expansion-notes) (new sites and battlefield LP)
