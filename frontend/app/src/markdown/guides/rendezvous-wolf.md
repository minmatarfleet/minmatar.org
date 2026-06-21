---
title: 'Rendezvous sites in an AC Wolf'
excerpt: 'Run Amarr Rendezvous sites with a PvE-fit autocannon Wolf assault frigate.'
category: 'Faction Warfare'
tags: ['pve']
author: 'Buppas'
---
## Before you start

Rendezvous sites are easy to complete with the right ship, fitting, and tactics—but they can get you killed very quickly if you are unprepared.

## The Concept

To capture systems in faction warfare, the attacking faction must capture plexes, raising the system's *contested* level to 100%, at which point the i-hub becomes vulnerable and the system can be flipped. The defending faction can also capture plexes to reduce the contested level. Different plexes shift contested by different amounts, but there is also an *advantage* mechanism: the faction with advantage gets greater changes to contested from each plex.

If both factions are actively plexing a system, advantage will likely determine the outcome.

There are several ways to increase advantage; one of them is running Rendezvous sites. These are PvE cosmic signature (probeable) sites that spawn one at a time per system, per faction, in which the player(s) must destroy multiple random waves of NPCs.

One approach is to use a drone boat and kite the NPCs while passively letting the drones kill them on auto-aggro.

This guide describes a more active approach using a Wolf assault frigate with autocannons, MWD, and armor repairer.

## Requirements and Initial Investment

The ship costs around 100 million ISK, including faction mods. No implants or boosters are needed.

Beyond being able to fly the Wolf, Minmatar Assault Frigates should be trained to at least IV, and you need solid Armor, Autocannon, and Capacitor skills. The fit is not massively tight on CPU or PG.

## Fitting

The fit emphasises very high EM and thermal resistance (all incoming DPS is from lasers) and cap stability with MWD and repairer running—there is no neuting in these sites. A probe launcher is required to find the sites; after that, the priority is maximising short-range DPS (it should exceed 200). In addition to high resists (93% EM / 84% Therm), the fit has a small signature radius (118m) even with the MWD active.

```
[Wolf, RV AC Wolf]
Small Armor Repairer II
Centii A-Type Thermal Coating
Multispectrum Energized Membrane II
Tracking Enhancer II
Gyrostabilizer II

Republic Fleet Small Cap Battery
Republic Fleet 5MN Microwarpdrive

200mm AutoCannon II
200mm AutoCannon II
Core Probe Launcher I
200mm AutoCannon II
200mm AutoCannon II

Small Capacitor Control Circuit I
Small Projectile Collision Accelerator II

Sisters Core Scanner Probe x16
Republic Fleet Phased Plasma S x5000
```

## Finding the sites

Rendezvous sites must be probed down, but they can be scanned to 100% with an unbonused 8 AU scan, and they always spawn within 8 AU of a celestial. Launch probes, set to 8 AU, and scan each planet in turn until you find the Amarr Rendezvous site. You can also spot Rendezvous sigs on the map: they have smaller red spheres than most other signatures.

Because each system only respawns sites every 30 minutes or so, and each run takes around 10 minutes, it is best to fly circuits of three or more systems.

Select "ignore" on other signatures once Rendezvous sites are identified, so they do not clutter the scan when you return to a previously-scanned system.

Bookmark the site after you find it, pull probes, and warp to the site at zero.

## Running the sites

Activate the repper and MWD on landing, lock the first target, activate guns, and click "keep at range" (1000m). Shoot destroyers first, then battlecruisers, then cruisers, then battleships, then frigates. When each target is reaching hull, click "keep at range" on the next one. After all ships in the wave are dead, approach the bookmark to avoid drifting off to one side of the site and being out of position for the next wave. When the officer battleship lands, immediately hit "orbit" (500m) on it to start approaching, leaving the other rats behind. Turn off the MWD when close to the officer and chew through the target.

When the officer dies, warp to the gate for the next system and repeat.

Note that none of the NPCs scram or point.

## Timings

These are timings from a fairly typical Rendezvous run. Spawns are random, so each run is unique.

```
00:00:00        Warp in
00:01:08        Spawn 1 dead
00:01:40        Spawn 2 lands
00:02:59        Spawn 2 dead
00:04:04        Spawn 3 lands
00:04:39        Spawn 3 dead
00:05:36        Spawn 4 lands
00:06:28        Officer lands
00:06:58        Shooting officer
00:07:40        Officer dead
```

That is about 4.5 minutes of shooting, 2.5 minutes waiting for spawns, and 30 seconds burning over to the officer.

Jumping into the next system and probing down the next site generally takes a couple of minutes, so the whole loop is under 10 minutes end-to-end.

## Avoiding hostile players

The site NPCs are not a danger to this Wolf fit, but nothing prevents other players from scanning down the site and coming in to kill you.

Keep an eye on d-scan. If anything appears on a 0.1 AU 360° scan, align out. With your MWD you will be out of range in a few seconds; if a hostile warps in, you can wave cheerfully. There is no need to leave the site if they do not chase you down.

## Income

Each site pays 10,000 LP (if run solo) and can be completed end-to-end in around 10 minutes. At 750 ISK/LP that works out to 45 million ISK per hour, and this can be sustained reliably and indefinitely.

This is entirely aside from the benefit that having advantage provides to system capture.

## Supply Caches and Depots

This fit can also handle enemy supply caches and depots: it has the DPS to kill them in a few minutes and enough tank to ignore the defending NPCs. Again, the biggest danger is hostile players—especially as there is no need to probe these sites down.
