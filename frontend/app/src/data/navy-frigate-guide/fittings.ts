import type { GuideFitting } from './types'
import { withGuideKnownKey } from '@helpers/guide_fittings'

/** Example fits for the navy frigate guide. fittingId 0 = copy-only (not in Fleet library). */
export const GUIDE_FITTING_KEY_PREFIX = 'guide.navy-frigate'

export const guideFittings: GuideFitting[] = [
    {
        id: 'hookbill-shield',
        fittingId: 0,
        shipId: 17619,
        shipGuideId: 'hookbill',
        name: 'Scram Kite — Shield',
        description:
            'MSE + BCS buffer race. Trades EWAR for raw tank and DPS. Still Scourge primary. Fly this first.',
        eftFormat: `[Caldari Navy Hookbill, Scram Kite — Shield]

IFFA Compact Damage Control
Crosslink Compact Ballistic Control System

1MN Y-S8 Compact Afterburner
Warp Scrambler II
Fleeting Compact Stasis Webifier
Fleeting Compact Stasis Webifier
Medium F-S9 Regolith Compact Shield Extender

Rocket Launcher II
Rocket Launcher II
Rocket Launcher II

Small Bay Loading Accelerator I
Small Core Defense Field Extender I
Small Core Defense Field Extender I


Scourge Rage Rocket x3000
Nanite Repair Paste x50
Caldari Navy Scourge Rocket x2000`,
    },
    {
        id: 'hookbill-control',
        fittingId: 0,
        shipId: 17619,
        shipGuideId: 'hookbill',
        name: 'Scram Kite — Control',
        description:
            'AB, scram, double web, scoped TD, SAAR. Load Scourge—swap TD for missile disruptor into missiles; MASB instead of TD is often fine.',
        eftFormat: `[Caldari Navy Hookbill, Scram Kite — Control]

Damage Control II
Small Ancillary Armor Repairer

1MN Y-S8 Compact Afterburner
Warp Scrambler II
Fleeting Compact Stasis Webifier
Fleeting Compact Stasis Webifier
DDO Scoped Tracking Disruptor I

Rocket Launcher II
Rocket Launcher II
Rocket Launcher II

Small Bay Loading Accelerator I
Small Transverse Bulkhead II
Small Transverse Bulkhead II


Hornet EC-300 x5

Scourge Rage Rocket x3000
Caldari Navy Scourge Rocket x2000
Scourge Javelin Rocket x1000
Tracking Speed Disruption Script x2
Optimal Range Disruption Script x2
Nanite Repair Paste x50`,
    },
    {
        id: 'comet-blaster',
        fittingId: 0,
        shipId: 17841,
        shipGuideId: 'comet',
        name: 'Blaster Comet',
        description:
            'Get on top of them and start blastin\'. Carry a damage drone flight and an ECM flight for emergencies. There are a few variants with extra webs or MWD anti-kite for opportunistic fits.',
        eftFormat: `[Federation Navy Comet, Blaster Comet]

IFFA Compact Damage Control
Magnetic Field Stabilizer II
Magnetic Field Stabilizer II
Small Ancillary Armor Repairer

1MN Y-S8 Compact Afterburner
Warp Scrambler II
Fleeting Compact Stasis Webifier

Light Neutron Blaster II
Light Neutron Blaster II
Small Ghoul Compact Energy Nosferatu

Small Transverse Bulkhead I
Small Transverse Bulkhead I
Small Transverse Bulkhead I


Hobgoblin II x5
Hornet EC-300 x5

Null S x2000
Void S x3000
Caldari Navy Antimatter Charge S x1000
Nanite Repair Paste x50`,
    },
    {
        id: 'comet-rail',
        fittingId: 0,
        shipId: 17841,
        shipGuideId: 'comet',
        name: 'Rail Comet',
        description:
            'Same thing, different tactic. Keep them at scram/kite range and load Null/Antimatter like you would different ranges of missiles.',
        eftFormat: `[Federation Navy Comet, Rail Comet]

IFFA Compact Damage Control
Magnetic Field Stabilizer II
Magnetic Field Stabilizer II
Small Ancillary Armor Repairer

1MN Y-S8 Compact Afterburner
Faint Epsilon Scoped Warp Scrambler
Fleeting Compact Stasis Webifier

150mm Railgun II
150mm Railgun II
Small Gremlin Compact Energy Neutralizer

Small Transverse Bulkhead I
Small Transverse Bulkhead I
Small Transverse Bulkhead I


Hobgoblin II x5

Caldari Navy Antimatter Charge S x2000
Caldari Navy Iridium Charge S x1500
Caldari Navy Iron Charge S x1500
Nanite Repair Paste x50`,
    },
    {
        id: 'slicer-beam',
        fittingId: 0,
        shipId: 17703,
        shipGuideId: 'slicer',
        name: 'Beam Slicer',
        description:
            'Get ready to play DDR and manage your buttons like crazy. Stay past scram and most webs.',
        eftFormat: `[Imperial Navy Slicer, Beam Slicer]

Small Ancillary Armor Repairer
Heat Sink II
Heat Sink II
Nanofiber Internal Structure II
Nanofiber Internal Structure II

5MN Y-T8 Compact Microwarpdrive
Faint Scoped Warp Disruptor

Small Focused Beam Laser II
Small Focused Beam Laser II
[Empty High slot]

Small Energy Locus Coordinator II
Small Energy Locus Coordinator II
Small Energy Locus Coordinator I


Imperial Navy Multifrequency S x1000
Imperial Navy Ultraviolet S x1000
Imperial Navy Xray S x1000
Nanite Repair Paste x50`,
    },
    {
        id: 'firetail-arty',
        fittingId: 0,
        shipId: 17812,
        shipGuideId: 'firetail',
        name: 'Arty Firetail',
        description:
            'Primary fit you\'ll see. Tracking is a bit of a skill check — don\'t sit still. Load ammo based on if you\'re scram-kiting or web-kiting.',
        eftFormat: `[Republic Fleet Firetail, Arty Firetail]

IFFA Compact Damage Control
Gyrostabilizer II
Small Ancillary Armor Repairer

1MN Y-S8 Compact Afterburner
Warp Scrambler II
Fleeting Compact Stasis Webifier
Fleeting Compact Stasis Webifier

280mm Howitzer Artillery II
280mm Howitzer Artillery II
Rocket Launcher II

Small Projectile Collision Accelerator I
Small Transverse Bulkhead II
Small Transverse Bulkhead II


Quake S x1500
Republic Fleet Titanium Sabot S x1500
Republic Fleet EMP S x1000
Republic Fleet Fusion S x1000
Scourge Rage Rocket x1000
Scourge Javelin Rocket x1000
Nova Rage Rocket x500
Inferno Rage Rocket x500
Mjolnir Rage Rocket x500
Nanite Repair Paste x50`,
    },
    {
        id: 'vigil-web-kite',
        fittingId: 0,
        shipId: 37454,
        shipGuideId: 'vigil',
        name: 'Web Kite Vigil Fleet',
        description:
            'Hold outside their webs and apply Javelin. Common refits are MASB, and there are scram-kite variants.',
        eftFormat: `[Vigil Fleet Issue, Web Kite Vigil Fleet]

IFFA Compact Damage Control
Crosslink Compact Ballistic Control System
Small Ancillary Armor Repairer

1MN Y-S8 Compact Afterburner
Faint Scoped Warp Disruptor
Fleeting Compact Stasis Webifier
Fleeting Compact Stasis Webifier

Rocket Launcher II
Rocket Launcher II
150mm Railgun II

Small Hydraulic Bay Thrusters I
Small Transverse Bulkhead II
Small Transverse Bulkhead II


Scourge Javelin Rocket x2000
Nova Rage Rocket x1500
Scourge Rage Rocket x1000
Caldari Navy Antimatter Charge S x1000
Caldari Navy Iridium Charge S x1000
Nanite Repair Paste x50`,
    },
    {
        id: 'tristan-brawl',
        fittingId: 0,
        shipId: 593,
        shipGuideId: 'tristan',
        name: 'Brawl Tristan',
        description:
            'Drones out as soon as you can, lock them down and start praying. A few ECM drones might save you in a bad matchup.',
        eftFormat: `[Tristan, Brawl Tristan]

IFFA Compact Damage Control
Drone Damage Amplifier II
Small Ancillary Armor Repairer

1MN Y-S8 Compact Afterburner
Warp Scrambler II
Fleeting Compact Stasis Webifier

Light Neutron Blaster II
Light Neutron Blaster II
Small Gremlin Compact Energy Neutralizer

Small Transverse Bulkhead I
Small Transverse Bulkhead I
Small Hybrid Collision Accelerator I


Hobgoblin II x8


Null S x1000
Void S x1500
Nanite Repair Paste x40`,
    },
    {
        id: 'breacher-masb',
        fittingId: 0,
        shipId: 598,
        shipGuideId: 'breacher',
        name: 'MASB Breacher',
        description:
            'Heat the booster and SAAR for the damage spike. Keep them at range as best you can.',
        eftFormat: `[Breacher, MASB Breacher]

IFFA Compact Damage Control
Crosslink Compact Ballistic Control System
Small Ancillary Armor Repairer

1MN Y-S8 Compact Afterburner
Warp Scrambler II
Fleeting Compact Stasis Webifier
Medium Ancillary Shield Booster

Rocket Launcher II
Rocket Launcher II
Rocket Launcher II

Small Bay Loading Accelerator I
Small EM Shield Reinforcer I
Small Thermal Shield Reinforcer I


Scourge Rage Rocket x2000
Caldari Navy Scourge Rocket x2000
Scourge Javelin Rocket x1000
Navy Cap Booster 50 x27
Nanite Repair Paste x50`,
    },
]

export function getGuideFittingsForShip(shipGuideId: string): GuideFitting[] {
    return guideFittings
        .filter((fit) => fit.shipGuideId === shipGuideId)
        .map((fit) => withGuideKnownKey(fit, GUIDE_FITTING_KEY_PREFIX))
}

export function getGuideFittingById(id: string): GuideFitting | undefined {
    const fit = guideFittings.find((row) => row.id === id)
    return fit ? withGuideKnownKey(fit, GUIDE_FITTING_KEY_PREFIX) : undefined
}
