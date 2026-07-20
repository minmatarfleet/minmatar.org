import type { GuideFitting } from './types'

/** Example fits for the navy destroyer metagame guide. */
export const guideFittings: GuideFitting[] = [
    {
        id: 'cat-blaster',
        fittingId: 37,
        shipId: 73796,
        shipGuideId: 'catalyst',
        name: 'Blaster Catalyst Navy Issue',
        description:
            'Plate + web + scram blaster brawler. High buffer EHP wins most close-range destroyer scram fights. Refit: SAAR Web Scram (active tank + nos).',
        eftFormat: `[Catalyst Navy Issue, [NVY] Blaster Catalyst Navy Issue]

Damage Control II
400mm Rolled Tungsten Compact Plates
Vortex Compact Magnetic Field Stabilizer

5MN Y-T8 Compact Microwarpdrive
Warp Scrambler II
Fleeting Compact Stasis Webifier

Light Neutron Blaster II
Light Neutron Blaster II
Light Neutron Blaster II
[Empty High slot]
Light Neutron Blaster II
Light Neutron Blaster II
Light Neutron Blaster II

Small Transverse Bulkhead II
Small Transverse Bulkhead II
Small Transverse Bulkhead II


Null S x2500
Void S x5000
Caldari Navy Antimatter Charge S x1000
Nanite Repair Paste x50`,
    },
    {
        id: 'cat-10mn',
        fittingId: 32,
        shipId: 73796,
        shipGuideId: 'catalyst',
        name: '10mn Catalyst Navy Issue',
        description:
            'Overpropped 10MN rail kiter (150mm gauss). Slippery scram-kite that controls range. Refit: 10mn 125mm (T2 rails, harder to catch, less raw DPS).',
        eftFormat: `[Catalyst Navy Issue, [NVY] 10mn Catalyst Navy Issue]

Damage Control II
Vortex Compact Magnetic Field Stabilizer
Small Ancillary Armor Repairer

10MN Y-S8 Compact Afterburner
Fleeting Compact Stasis Webifier
Faint Scoped Warp Disruptor

150mm Prototype Gauss Gun
150mm Prototype Gauss Gun
150mm Prototype Gauss Gun
[Empty High slot]
150mm Prototype Gauss Gun
150mm Prototype Gauss Gun
150mm Prototype Gauss Gun

Small Transverse Bulkhead II
Small Transverse Bulkhead II
Small Transverse Bulkhead II


Caldari Navy Antimatter Charge S x2000
Caldari Navy Iridium Charge S x2000
Caldari Navy Iron Charge S x2000
Caldari Navy Thorium Charge S x2000
Nanite Repair Paste x120`,
    },
    {
        id: 'coercer-dual-neuts-mwd',
        fittingId: 366,
        shipId: 73789,
        shipGuideId: 'coercer',
        name: '2X Neut Coercer Navy Issue',
        description:
            'Classic 2X neut brawler with MWD. Drain cap-reliant targets, then grind at scram range. Refit: 2X Neut No-Prop (web + locus, slower, more control).',
        eftFormat: `[Coercer Navy Issue, [NVY] 2X Neut Coercer Navy Issue]

400mm Rolled Tungsten Compact Plates
Damage Control II
Heat Sink II
Multispectrum Energized Membrane II

5MN Y-T8 Compact Microwarpdrive
Faint Epsilon Scoped Warp Scrambler

Dual Light Pulse Laser II
Dual Light Pulse Laser II
Dual Light Pulse Laser II
Small Infectious Scoped Energy Neutralizer
Small Infectious Scoped Energy Neutralizer
Dual Light Pulse Laser II
Dual Light Pulse Laser II

Small Ancillary Current Router I
Small Trimark Armor Pump I
Small Trimark Armor Pump I


Conflagration S x5
Scorch S x5
Imperial Navy Multifrequency S x5
Nanite Repair Paste x50`,
    },
    {
        id: 'coercer-mwd-scram-brawl',
        fittingId: 369,
        shipId: 73789,
        shipGuideId: 'coercer',
        name: 'Pulse Coercer Navy Issue',
        description:
            'Pulse MWD brawler with a full gun rack. Pure scram-range DPS. Refit: AB Pulse (tighter range control, no MWD sig bloom).',
        eftFormat: `[Coercer Navy Issue, [NVY] Pulse Coercer Navy Issue]

200mm Steel Plates II
Heat Sink II
Multispectrum Coating II
Multispectrum Energized Membrane II

5MN Quad LiF Restrained Microwarpdrive
Warp Scrambler II

Small Focused Pulse Laser II
Small Focused Pulse Laser II
Small Focused Pulse Laser II
[Empty High slot]
Small Focused Pulse Laser II
Small Focused Pulse Laser II
Small Focused Pulse Laser II

Small Trimark Armor Pump I
Small Trimark Armor Pump I
Small Trimark Armor Pump I


Conflagration S x5
Scorch S x5
Imperial Navy Multifrequency S x5
Nanite Repair Paste x50`,
    },
    {
        id: 'coercer-kite-beams',
        fittingId: 371,
        shipId: 73789,
        shipGuideId: 'coercer',
        name: 'Beam Coercer Navy Issue',
        description:
            'Beam kiter with tracking enhancer for falloff fights. Refits: Locus Pulse Coercer (sit on beacon); Web Beam Coercer (dual web meme, no point).',
        eftFormat: `[Coercer Navy Issue, [NVY] Beam Coercer Navy Issue]

Heat Sink II
Extruded Compact Heat Sink
Damage Control II
Fourier Compact Tracking Enhancer

5MN Y-T8 Compact Microwarpdrive
Initiated Compact Warp Disruptor

Small Focused Beam Laser II
Small Focused Beam Laser II
Small Focused Beam Laser II
[Empty High slot]
Small Focused Beam Laser II
Small Focused Beam Laser II
Small Focused Beam Laser II

Small Processor Overclocking Unit II
Small Transverse Bulkhead I
Small Transverse Bulkhead I


Conflagration S x5
Imperial Navy Multifrequency S x5
Scorch S x5
Nanite Repair Paste x50`,
    },
    {
        id: 'tfi-ac',
        fittingId: 28,
        shipId: 73794,
        shipGuideId: 'thrasher',
        name: 'AC Thrasher Fleet Issue',
        description:
            'Armor autocannon brawler with rocket launcher. Scram, web, MWD into range. Refit: Shield ACs (MSE + neut, more speed, less buffer).',
        eftFormat: `[Thrasher Fleet Issue, [NVY] AC Thrasher Fleet Issue]

Damage Control II
Gyrostabilizer II
400mm Crystalline Carbonide Restrained Plates

5MN Quad LiF Restrained Microwarpdrive
Fleeting Compact Stasis Webifier
Warp Scrambler II

200mm AutoCannon II
200mm AutoCannon II
200mm AutoCannon II
Rocket Launcher II
200mm AutoCannon II
200mm AutoCannon II
200mm AutoCannon II

Small Trimark Armor Pump I
Small Trimark Armor Pump I
Small Projectile Burst Aerator II


Barrage S x2500
Hail S x5000
Inferno Rage Rocket x1000
Nanite Repair Paste x50
Republic Fleet Depleted Uranium S x1000
Republic Fleet EMP S x1000
Republic Fleet Phased Plasma S x1000`,
    },
    {
        id: 'tfi-arty',
        fittingId: 41,
        shipId: 73794,
        shipGuideId: 'thrasher',
        name: 'Arty Thrasher Fleet Issue',
        description:
            'Default TFI: 280mm artillery kiter. Fight on your terms; if you get tackled, you die. Refits: 280mm ACR (meta MWD/rig); 280 Overdrive (entry/speed); 280 Double Web (AB meme).',
        eftFormat: `[Thrasher Fleet Issue, [NVY] Arty Thrasher Fleet Issue]

Counterbalanced Compact Gyrostabilizer
Counterbalanced Compact Gyrostabilizer
IFFA Compact Damage Control

5MN Quad LiF Restrained Microwarpdrive
Fleeting Compact Stasis Webifier
Initiated Compact Warp Disruptor

280mm Howitzer Artillery II
280mm Howitzer Artillery II
280mm Howitzer Artillery II
[Empty High slot]
280mm Howitzer Artillery II
280mm Howitzer Artillery II
280mm Howitzer Artillery II

Small Transverse Bulkhead I
Small Projectile Collision Accelerator I
Small Ancillary Current Router I


Quake S x1500
Tremor S x1500
Nanite Repair Paste x50
Republic Fleet Depleted Uranium S x1000
Republic Fleet EMP S x1000
Republic Fleet Fusion S x1000
Republic Fleet Phased Plasma S x1000`,
    },
    {
        id: 'corm-dual-masb-neutrons',
        fittingId: 378,
        shipId: 73795,
        shipGuideId: 'cormorant',
        name: 'Dual MASB Cormorant Navy Issue',
        description:
            'Dual MASB neutron brawler for scram brawls. Refit: Dual MASB Ions Cormorant (slightly more reach, same concept).',
        eftFormat: `[Cormorant Navy Issue, [NVY] Dual MASB Cormorant Navy Issue]

IFFA Compact Damage Control
Vortex Compact Magnetic Field Stabilizer

1MN Y-S8 Compact Afterburner
Initiated Compact Warp Scrambler
Medium Ancillary Shield Booster
Medium Ancillary Shield Booster

Light Neutron Blaster II
Light Neutron Blaster II
Light Neutron Blaster II
[Empty High slot]
Light Neutron Blaster II
Light Neutron Blaster II
Light Neutron Blaster II

Small EM Shield Reinforcer I
Small Hybrid Burst Aerator II
Small Thermal Shield Reinforcer I


Null S x2500
Void S x5000
Caldari Navy Antimatter Charge S x1000
Nanite Repair Paste x100
Navy Cap Booster 400 x25`,
    },
    {
        id: 'corm-buffer',
        fittingId: 380,
        shipId: 73795,
        shipGuideId: 'cormorant',
        name: 'Buffer Cormorant Navy Issue',
        description:
            'Surprise MWD buffer with RF MSE. Looks like a kiter until you scram and brawl.',
        eftFormat: `[Cormorant Navy Issue, [NVY] Buffer Cormorant Navy Issue]

Magnetic Field Stabilizer II
Damage Control II

5MN Y-T8 Compact Microwarpdrive
Republic Fleet Medium Shield Extender
Stasis Webifier II
Warp Scrambler II

Light Neutron Blaster II
Light Neutron Blaster II
Light Neutron Blaster II
[Empty High slot]
Light Neutron Blaster II
Light Neutron Blaster II
Light Neutron Blaster II

Small Core Defense Field Extender I
Small EM Shield Reinforcer II
Small Hybrid Burst Aerator I


Null S x2500
Void S x5000
Caldari Navy Antimatter Charge S x1000
Nanite Repair Paste x50`,
    },
    {
        id: 'corm-10mn',
        fittingId: 381,
        shipId: 73795,
        shipGuideId: 'cormorant',
        name: '10mn Cormorant Navy Issue',
        description:
            '10MN rail scram-kite with cap booster and Pithum MSB. 75mm rails for mid-range pressure under scram.',
        eftFormat: `[Cormorant Navy Issue, [NVY] 10mn Cormorant Navy Issue]

Damage Control II
Magnetic Field Stabilizer II

10MN Afterburner II
Warp Scrambler II
Small Capacitor Booster II
Pithum C-Type Medium Shield Booster

75mm Gatling Rail II
75mm Gatling Rail II
75mm Gatling Rail II
[Empty High slot]
75mm Gatling Rail II
75mm Gatling Rail II
75mm Gatling Rail II

Small EM Shield Reinforcer II
Small Hybrid Collision Accelerator I
Small Thermal Shield Reinforcer II


Caldari Navy Antimatter Charge S x2000
Caldari Navy Iridium Charge S x2000
Caldari Navy Iron Charge S x2000
Caldari Navy Thorium Charge S x2000
Nanite Repair Paste x120
Navy Cap Booster 400 x25`,
    },
    {
        id: 'talfi-10mn-rocket',
        fittingId: 382,
        shipId: 91858,
        shipGuideId: 'talwar',
        name: '10mn Talwar Fleet Issue',
        description:
            '10MN afterburner rocket brawler with MASB burst tank. Early solo meta: beats many MWD + scram + web destroyers when you manage the slide.',
        eftFormat: `[Talwar Fleet Issue, [NVY] 10mn Talwar Fleet Issue]

Navy Micro Auxiliary Power Core
Ballistic Control System II
IFFA Compact Damage Control

10MN Y-S8 Compact Afterburner
Warp Scrambler II
Medium Ancillary Shield Booster
Compact Multispectrum Shield Hardener

Rocket Launcher II
Rocket Launcher II
Rocket Launcher II
[Empty High slot]
Rocket Launcher II
Rocket Launcher II

Small Bay Loading Accelerator II
Small EM Shield Reinforcer I
Small Thermal Shield Reinforcer I


Scourge Rage Rocket x250
Navy Cap Booster 50 x9`,
    },
    {
        id: 'algos-10mn',
        fittingId: 0,
        shipId: 32872,
        shipGuideId: 'algos',
        name: '10mn Algos',
        description:
            'Overpropped rail/drone web-kite. Hold range, apply rails, let drones work. Refit: AC brawl for close MASB fights.',
        eftFormat: `[Algos, 10mn Algos]

Damage Control II
Drone Damage Amplifier II
Small Ancillary Armor Repairer

10MN Y-S8 Compact Afterburner
Fleeting Compact Stasis Webifier
Faint Scoped Warp Disruptor

75mm Gatling Rail II
75mm Gatling Rail II
75mm Gatling Rail II
75mm Gatling Rail II
75mm Gatling Rail II
[Empty High slot]

Small Transverse Bulkhead I
Small Transverse Bulkhead I
Small Transverse Bulkhead I


Hobgoblin II x3
Hammerhead II x2

Caldari Navy Antimatter Charge S x2000
Caldari Navy Iridium Charge S x1500
Caldari Navy Iron Charge S x1500
Nanite Repair Paste x50`,
    },
    {
        id: 'algos-brawl',
        fittingId: 0,
        shipId: 32872,
        shipGuideId: 'algos',
        name: 'Brawl Algos',
        description:
            'MWD MASB autocannon brawler with plate and SAAR. Close-range T1 duel line.',
        eftFormat: `[Algos, Brawl Algos]

Damage Control II
400mm Rolled Tungsten Compact Plates
Small Ancillary Armor Repairer

5MN Y-T8 Compact Microwarpdrive
Medium Ancillary Shield Booster
Warp Scrambler II

200mm AutoCannon II
200mm AutoCannon II
200mm AutoCannon II
200mm AutoCannon II
200mm AutoCannon II
[Empty High slot]

Small Ancillary Current Router II
Small Transverse Bulkhead I
Small Transverse Bulkhead I


Hammerhead II x2
Hobgoblin II x3

Navy Cap Booster 50 x16
Nanite Repair Paste x50
Republic Fleet EMP S x1500
Republic Fleet Phased Plasma S x2500`,
    },
    {
        id: 'algos-farm',
        fittingId: 0,
        shipId: 32872,
        shipGuideId: 'algos',
        name: 'Farm Algos',
        description:
            'Triple-MSE drone farmer for plex grinding and multi-boxing. Not a duel fit.',
        eftFormat: `[Algos, Farm Algos]

AE-K Compact Drone Damage Amplifier
AE-K Compact Drone Damage Amplifier
Damage Control II

Medium Azeotropic Restrained Shield Extender
Medium Azeotropic Restrained Shield Extender
Medium Azeotropic Restrained Shield Extender

125mm Light Carbine Repeating Cannon I
[Empty High slot]
[Empty High slot]
[Empty High slot]
[Empty High slot]
[Empty High slot]

Small Core Defense Field Extender I
Small Core Defense Field Extender I
Small Core Defense Field Extender I


Hammerhead II x2
Acolyte II x5
Hobgoblin II x3

EMP S x3000`,
    },
    {
        id: 'thrasher-arty',
        fittingId: 0,
        shipId: 16242,
        shipGuideId: 'thrasher-t1',
        name: 'Arty Thrasher',
        description:
            '280 double-web artillery gank. No scram—volley frigates or leave. Refit: AC scram MSE for destroyer duels.',
        eftFormat: `[Thrasher, Arty Thrasher]

Damage Control II
Gyrostabilizer II

5MN Y-T8 Compact Microwarpdrive
Fleeting Compact Stasis Webifier
Fleeting Compact Stasis Webifier

280mm Howitzer Artillery II
280mm Howitzer Artillery II
280mm Howitzer Artillery II
280mm Howitzer Artillery II
280mm Howitzer Artillery II
280mm Howitzer Artillery II
280mm Howitzer Artillery II
[Empty High slot]

Small Transverse Bulkhead I
Small Transverse Bulkhead I
Small Transverse Bulkhead I


Quake S x1500
Republic Fleet Titanium Sabot S x1500
Republic Fleet EMP S x1000
Republic Fleet Fusion S x1000
Nanite Repair Paste x40`,
    },
    {
        id: 'thrasher-ac',
        fittingId: 0,
        shipId: 16242,
        shipGuideId: 'thrasher-t1',
        name: 'AC Thrasher',
        description:
            'MWD MSE scram autocannon brawler with a neut. Better destroyer duel than 280 gank.',
        eftFormat: `[Thrasher, AC Thrasher]

Gyrostabilizer II
Gyrostabilizer II

5MN Y-T8 Compact Microwarpdrive
Medium F-S9 Regolith Compact Shield Extender
Warp Scrambler II

200mm AutoCannon II
200mm AutoCannon II
200mm AutoCannon II
200mm AutoCannon II
200mm AutoCannon II
200mm AutoCannon II
200mm AutoCannon II
Small Gremlin Compact Energy Neutralizer

Small EM Shield Reinforcer I
Small Core Defense Field Extender I
Small Core Defense Field Extender I


Republic Fleet Phased Plasma S x2500
Republic Fleet EMP S x1500
Hail S x1000
Nanite Repair Paste x40`,
    },
    {
        id: 'coercer-brawl',
        fittingId: 0,
        shipId: 16236,
        shipGuideId: 'coercer-t1',
        name: 'Brawl Coercer',
        description:
            'MWD scram Dual Light Pulse plate brawler. Close-range T1 duel line.',
        eftFormat: `[Coercer, Brawl Coercer]

Damage Control II
400mm Rolled Tungsten Compact Plates
Multispectrum Coating II

5MN Y-T8 Compact Microwarpdrive
Warp Scrambler II

Dual Light Pulse Laser II
Dual Light Pulse Laser II
Dual Light Pulse Laser II
Dual Light Pulse Laser II
Dual Light Pulse Laser II
Dual Light Pulse Laser II
Dual Light Pulse Laser II
Dual Light Pulse Laser II

Small Trimark Armor Pump I
Small Trimark Armor Pump I
Small Trimark Armor Pump I


Conflagration S x8
Scorch S x8
Imperial Navy Multifrequency S x8
Imperial Navy Radio S x8
Nanite Repair Paste x40`,
    },
    {
        id: 'dragoon-neut',
        fittingId: 0,
        shipId: 32874,
        shipGuideId: 'dragoon',
        name: 'Neut Dragoon',
        description:
            'Three small neuts, MWD, compact cap booster, scram. Drain active tanks, then grind. Plate + drone amp for longer trades.',
        eftFormat: `[Dragoon, Neut Dragoon]

Damage Control II
400mm Rolled Tungsten Compact Plates
Multispectrum Coating II
Drone Damage Amplifier II

5MN Y-T8 Compact Microwarpdrive
Small F-RX Compact Capacitor Booster
Warp Scrambler II

Small Infectious Scoped Energy Neutralizer
Small Infectious Scoped Energy Neutralizer
Small Infectious Scoped Energy Neutralizer
125mm Gatling AutoCannon II
125mm Gatling AutoCannon II

Small Ancillary Current Router I
Small Trimark Armor Pump I
Small Trimark Armor Pump I


Hobgoblin II x5
Hornet EC-300 x5

Navy Cap Booster 200 x16
Nanite Repair Paste x40
Republic Fleet Phased Plasma S x1000`,
    },
]

export function getGuideFittingsForShip(shipGuideId: string): GuideFitting[] {
    return guideFittings.filter((fit) => fit.shipGuideId === shipGuideId)
}

export function getGuideFittingById(id: string): GuideFitting | undefined {
    return guideFittings.find((fit) => fit.id === id)
}
