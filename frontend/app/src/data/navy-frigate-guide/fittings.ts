import type { GuideFitting } from './types'

/** Example fits for the navy frigate guide. fittingId 0 = copy-only (not in Fleet library). */
export const guideFittings: GuideFitting[] = [
    {
        id: 'hookbill-control',
        fittingId: 0,
        shipId: 17619,
        shipGuideId: 'hookbill',
        name: 'Scram Kite — Control',
        description:
            'AB, scram, double web, scoped TD, SAAR. Default Hookbill scram line. Load Scourge—swap TD for missile disruptor into missiles; MASB instead of TD is often fine.',
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
        id: 'hookbill-shield',
        fittingId: 0,
        shipId: 17619,
        shipGuideId: 'hookbill',
        name: 'Scram Kite — Shield',
        description:
            'MSE + BCS buffer race. Trades EWAR for raw tank and DPS. Still Scourge primary.',
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
        id: 'comet-blaster',
        fittingId: 0,
        shipId: 17841,
        shipGuideId: 'comet',
        name: 'Blaster Comet',
        description:
            'AB scram/web brawler. Wins DPS races; loses control to double-web ships. Second web or MWD anti-kite variants are common.',
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
            'Scram-kite rails with a neut. Answer to ships sitting outside blaster range.',
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
            'MWD + point beam kiter. Highest damage and range under good piloting; tracking and capacitor are the skill checks.',
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
        id: 'slicer-pulse',
        fittingId: 0,
        shipId: 17703,
        shipGuideId: 'slicer',
        name: 'Pulse Slicer',
        description:
            'Easier kite line with better tracking than beams. Same MWD + point skeleton.',
        eftFormat: `[Imperial Navy Slicer, Pulse Slicer]

Small Ancillary Armor Repairer
Heat Sink II
Heat Sink II
Nanofiber Internal Structure II
Nanofiber Internal Structure II

5MN Y-T8 Compact Microwarpdrive
Faint Scoped Warp Disruptor

Small Focused Pulse Laser II
Small Focused Pulse Laser II
[Empty High slot]

Small Energy Locus Coordinator II
Small Energy Locus Coordinator II
Small Energy Locus Coordinator I


Imperial Navy Multifrequency S x1000
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
            'Scram kite 280 mm artillery with double web. Swap scram for enduring point and load Javelin for web kite.',
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
        id: 'firetail-brawl',
        fittingId: 0,
        shipId: 17812,
        shipGuideId: 'firetail',
        name: 'AC Firetail',
        description:
            'MASB autocannon brawler with neut. Better control than Comet; loses pure DPS races.',
        eftFormat: `[Republic Fleet Firetail, AC Firetail]

IFFA Compact Damage Control
Gyrostabilizer II
Overdrive Injector System II

1MN Y-S8 Compact Afterburner
Medium Ancillary Shield Booster
Faint Epsilon Scoped Warp Scrambler
Fleeting Compact Stasis Webifier

200mm AutoCannon II
200mm AutoCannon II
Small Gremlin Compact Energy Neutralizer

Small EM Shield Reinforcer I
Small Thermal Shield Reinforcer I
Small Projectile Burst Aerator I


Barrage S x1000
Hail S x1000
Navy Cap Booster 50 x63
Nanite Repair Paste x50
Republic Fleet EMP S x1200
Republic Fleet Phased Plasma S x1200`,
    },
    {
        id: 'vigil-web-kite',
        fittingId: 0,
        shipId: 37454,
        shipGuideId: 'vigil',
        name: 'Web Kite Vigil Fleet',
        description:
            'AB point double-web Javelin kite with a utility rail. Default Vigil Fleet line. Common refit puts MASB in place of the second web with shield rigs.',
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
        id: 'vigil-scram-kite',
        fittingId: 0,
        shipId: 37454,
        shipGuideId: 'vigil',
        name: 'Scram Kite Vigil Fleet',
        description:
            'AB MSE scram/web Rage line with a utility autocannon. Mid-range rocket scram-kite. Swap AB for MWD as the anti-kite version.',
        eftFormat: `[Vigil Fleet Issue, Scram Kite Vigil Fleet]

IFFA Compact Damage Control
Crosslink Compact Ballistic Control System
Crosslink Compact Ballistic Control System

1MN Y-S8 Compact Afterburner
Medium F-S9 Regolith Compact Shield Extender
Warp Scrambler II
Fleeting Compact Stasis Webifier

Rocket Launcher II
Rocket Launcher II
150mm Light AutoCannon II

Small Hydraulic Bay Thrusters I
Small Core Defense Field Extender I
Small Core Defense Field Extender I


Nova Rage Rocket x2000
Scourge Rage Rocket x1500
Scourge Javelin Rocket x1000
Republic Fleet EMP S x1000
Republic Fleet Phased Plasma S x1000
Nanite Repair Paste x50`,
    },
    {
        id: 'rifter-ac',
        fittingId: 0,
        shipId: 587,
        shipGuideId: 'rifter',
        name: 'Autocannon Rifter',
        description:
            'AB scram/web T1 brawler. Same role as AC Firetail at lower cost—decline more navy fights.',
        eftFormat: `[Rifter, Autocannon Rifter]

Damage Control II
Gyrostabilizer II
Fourier Compact Tracking Enhancer
Small Ancillary Armor Repairer

1MN Y-S8 Compact Afterburner
Warp Scrambler II
Fleeting Compact Stasis Webifier

200mm AutoCannon II
200mm AutoCannon II
200mm AutoCannon II

Small Projectile Burst Aerator I
Small Transverse Bulkhead I
Small Transverse Bulkhead I


Hail S x1200
Nanite Repair Paste x30
Republic Fleet EMP S x1200
Republic Fleet Phased Plasma S x1200`,
    },
    {
        id: 'tristan-brawl',
        fittingId: 0,
        shipId: 593,
        shipGuideId: 'tristan',
        name: 'Brawl Tristan',
        description:
            'AB scram/web drone brawler. Drones are the weapon; hybrids support.',
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
            'AB scram single-web rocket Breacher with MASB + SAAR. Default tank-forward scram-kite; load Navy Scourge when Rage application fails.',
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
    return guideFittings.filter((fit) => fit.shipGuideId === shipGuideId)
}

export function getGuideFittingById(id: string): GuideFitting | undefined {
    return guideFittings.find((fit) => fit.id === id)
}
