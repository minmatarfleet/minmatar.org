import type { GuideFitting } from './types'

export const guideFittings: GuideFitting[] = [
    {
        id: 'cat-plate-web-scram',
        fittingId: 362,
        shipId: 73796,
        shipGuideId: 'catalyst',
        name: 'plate-web-scram',
        description: 'Versatile blaster brawler with armor plate, web, and scram. High buffer EHP wins most close-range destroyer scram fights; very weak to anything that can kite.',
        eftFormat: `[Catalyst Navy Issue, [NVY] Catalyst Navy Issue — plate-web-scram]

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
        id: 'cat-saar-web-scram',
        fittingId: 363,
        shipId: 73796,
        shipGuideId: 'catalyst',
        name: 'saar-web-scram',
        description: 'Active armor blaster brawler using a SAAR and nosferatu for sustain. More flexible than the plate variant but with a thinner buffer; still beats most destroyers you can land scram and web on.',
        eftFormat: `[Catalyst Navy Issue, [NVY] Catalyst Navy Issue — saar-web-scram]

Small Ancillary Armor Repairer
Damage Control II
Vortex Compact Magnetic Field Stabilizer

5MN Y-T8 Compact Microwarpdrive
Warp Scrambler II
Fleeting Compact Stasis Webifier

Light Neutron Blaster II
Light Neutron Blaster II
Light Neutron Blaster II
Small Ghoul Compact Energy Nosferatu
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
        id: 'cat-10mn-150mm',
        fittingId: 364,
        shipId: 73796,
        shipGuideId: 'catalyst',
        name: '10mn-150mm',
        description: '10MN afterburner rail kiter with 150mm gauss guns. Slippery scram-kite fit that controls range against other destroyers; over-propped, so turn on prey early and avoid slingshots.',
        eftFormat: `[Catalyst Navy Issue, [NVY] Catalyst Navy Issue — 10mn-150mm]

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
        id: 'cat-10mn-125mm',
        fittingId: 365,
        shipId: 73796,
        shipGuideId: 'catalyst',
        name: '10mn-125mm',
        description: 'Faster 10MN rail kiter with T2 125mm rails and a disruptor. Even harder to catch than the 150mm variant but with lower raw DPS; excellent for picking destroyer fights on your terms.',
        eftFormat: `[Catalyst Navy Issue, [NVY] Catalyst Navy Issue — 10mn-125mm]

Damage Control II
Magnetic Field Stabilizer II
Small Ancillary Armor Repairer

10MN Monopropellant Enduring Afterburner
X5 Enduring Stasis Webifier
Warp Disruptor II

125mm Railgun II
125mm Railgun II
125mm Railgun II
[Empty High slot]
125mm Railgun II
125mm Railgun II
125mm Railgun II

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
        name: 'dual-neuts-mwd',
        description: 'Classic dual neut brawler with MWD. Uses the hull neut bonus to drain cap-reliant targets, then grind them down at scram range. Beware kiters and capless guns.',
        eftFormat: `[Coercer Navy Issue, [NVY] Coercer Navy Issue — dual-neuts-mwd]

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
        id: 'coercer-dual-neuts-no-prop',
        fittingId: 367,
        shipId: 73789,
        shipGuideId: 'coercer',
        name: 'dual-neuts-no-prop',
        description: 'Slow brawler with dual neuts, web, and no prop mod. Trades mobility for more tank and control at scram range; ideal when you expect a straight brawl rather than a chase.',
        eftFormat: `[Coercer Navy Issue, [NVY] Coercer Navy Issue — dual-neuts-no-prop]

400mm Rolled Tungsten Compact Plates
Damage Control II
Heat Sink II
Multispectrum Coating II

Faint Epsilon Scoped Warp Scrambler
Fleeting Compact Stasis Webifier

Small Focused Pulse Laser II
Small Focused Pulse Laser II
Small Focused Pulse Laser II
Small Energy Neutralizer II
Small Infectious Scoped Energy Neutralizer
Small Focused Pulse Laser II
Small Focused Pulse Laser II

Small Ancillary Current Router II
Small Trimark Armor Pump I
Small Energy Locus Coordinator II


Conflagration S x5
Scorch S x5
Imperial Navy Multifrequency S x5
Nanite Repair Paste x50`,
    },
    {
        id: 'coercer-ab-scram-brawl',
        fittingId: 368,
        shipId: 73789,
        shipGuideId: 'coercer',
        name: 'ab-scram-brawl',
        description: 'Afterburner pulse brawler for tighter range control without MWD signature penalty. Full dual-pulse rack with a neut for cap warfare in straight scram brawls.',
        eftFormat: `[Coercer Navy Issue, [NVY] Coercer Navy Issue — ab-scram-brawl]

Damage Control II
Multispectrum Energized Membrane II
400mm Rolled Tungsten Compact Plates
Heat Sink II

1MN Afterburner II
Warp Scrambler II

Dual Light Pulse Laser II
Dual Light Pulse Laser II
Dual Light Pulse Laser II
Small Infectious Scoped Energy Neutralizer
Dual Light Pulse Laser II
Dual Light Pulse Laser II
Dual Light Pulse Laser II

Small Trimark Armor Pump I
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
        name: 'mwd-scram-brawl',
        description: 'Focused pulse MWD brawler with a full gun rack and no neut. Pure scram-range DPS for pilots who want to close quickly and brawl.',
        eftFormat: `[Coercer Navy Issue, [NVY] Coercer Navy Issue — mwd-scram-brawl]

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
        id: 'coercer-locus-pulse',
        fittingId: 370,
        shipId: 73789,
        shipGuideId: 'coercer',
        name: 'locus-pulse',
        description: 'Locus coordinator pulse kiter with SAAR for mid-range pressure. Uses tracking and the hull\'s neut-adjacent slot layout to fight at pulse falloff while staying mobile.',
        eftFormat: `[Coercer Navy Issue, [NVY] Coercer Navy Issue — locus-pulse]

Heat Sink II
Extruded Compact Heat Sink
Damage Control II
Small Ancillary Armor Repairer

5MN Y-T8 Compact Microwarpdrive
Initiated Compact Warp Disruptor

Small Focused Pulse Laser II
Small Focused Pulse Laser II
Small Focused Pulse Laser II
[Empty High slot]
Small Focused Pulse Laser II
Small Focused Pulse Laser II
Small Focused Pulse Laser II

Small Transverse Bulkhead II
Small Energy Locus Coordinator II
Small Energy Locus Coordinator II


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
        name: 'kite-beams',
        description: 'Beam kiter with tracking enhancer for fighting near falloff. Keeps range with MWD and disruptor while applying steady beam DPS to slower brawlers and other kiters.',
        eftFormat: `[Coercer Navy Issue, [NVY] Coercer Navy Issue — kite-beams]

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
        id: 'coercer-web-beams',
        fittingId: 372,
        shipId: 73789,
        shipGuideId: 'coercer',
        name: 'web-beams',
        description: 'Double-web beam fit for catching other kiters and holding them in beam range. A niche meme build that punishes pilots who assume every Coercer is a neut brawler.',
        eftFormat: `[Coercer Navy Issue, [NVY] Coercer Navy Issue — web-beams]

Heat Sink II
Heat Sink II
Damage Control II
Fourier Compact Tracking Enhancer

Stasis Webifier II
Fleeting Compact Stasis Webifier

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
        id: 'tfi-280mm-acr',
        fittingId: 373,
        shipId: 73794,
        shipGuideId: 'thrasher',
        name: '280mm-acr',
        description: 'Standard 280mm artillery kiter with collision accelerator for alpha and range control. Excellent for fighting on your terms; if you get tackled, you die.',
        eftFormat: `[Thrasher Fleet Issue, [NVY] Thrasher Fleet Issue — 280mm-acr]

Gyrostabilizer II
Counterbalanced Compact Gyrostabilizer
IFFA Compact Damage Control

5MN Y-T8 Compact Microwarpdrive
Fleeting Compact Stasis Webifier
Initiated Compact Warp Disruptor

280mm Howitzer Artillery II
280mm Howitzer Artillery II
280mm Howitzer Artillery II
[Empty High slot]
280mm Howitzer Artillery II
280mm Howitzer Artillery II
280mm Howitzer Artillery II

Small Transverse Bulkhead II
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
        id: 'tfi-280-overdrive',
        fittingId: 374,
        shipId: 73794,
        shipGuideId: 'thrasher',
        name: '280-overdrive',
        description: 'Simpler overdrive artillery kiter with more speed and less alpha than the ACR variant. Good entry 280mm fit for pilots learning Thrasher Fleet Issue kiting.',
        eftFormat: `[Thrasher Fleet Issue, [NVY] Thrasher Fleet Issue — 280-overdrive]

Gyrostabilizer II
Overdrive Injector System II
Damage Control II

5MN Y-T8 Compact Microwarpdrive
Fleeting Compact Stasis Webifier
Warp Disruptor II

280mm Howitzer Artillery II
280mm Howitzer Artillery II
280mm Howitzer Artillery II
[Empty High slot]
280mm Howitzer Artillery II
280mm Howitzer Artillery II
280mm Howitzer Artillery II

Small Transverse Bulkhead II
Small Transverse Bulkhead II
Small Transverse Bulkhead II


Quake S x1500
Tremor S x1500
Nanite Repair Paste x50
Republic Fleet Depleted Uranium S x1000
Republic Fleet EMP S x1000
Republic Fleet Fusion S x1000
Republic Fleet Phased Plasma S x1000`,
    },
    {
        id: 'tfi-armour-acs',
        fittingId: 375,
        shipId: 73794,
        shipGuideId: 'thrasher',
        name: 'armour-acs',
        description: 'Armor autocannon brawler with a rocket launcher for close-range brawling. Scram, web, and MWD into range then tear down other destroyers with AC alpha.',
        eftFormat: `[Thrasher Fleet Issue, [NVY] Thrasher Fleet Issue — armour-acs]

Damage Control II
Gyrostabilizer II
400mm Crystalline Carbonide Restrained Plates

Warp Scrambler II
Fleeting Compact Stasis Webifier
5MN Quad LiF Restrained Microwarpdrive

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
        id: 'tfi-shield-acs',
        fittingId: 376,
        shipId: 73794,
        shipGuideId: 'thrasher',
        name: 'shield-acs',
        description: 'Shield autocannon brawler with a neut for cap-dependent targets at scram range. More speed and buffer than the armor AC variant; trades some EHP for mobility.',
        eftFormat: `[Thrasher Fleet Issue, [NVY] Thrasher Fleet Issue — shield-acs]

Gyrostabilizer II
Gyrostabilizer II
IFFA Compact Damage Control

5MN Quad LiF Restrained Microwarpdrive
Republic Fleet Medium Shield Extender
Warp Scrambler II

200mm AutoCannon II
200mm AutoCannon II
200mm AutoCannon II
Small Energy Neutralizer II
200mm AutoCannon II
200mm AutoCannon II
200mm AutoCannon II

Small Core Defense Field Extender I
Small EM Shield Reinforcer II
Small Thermal Shield Reinforcer II


Barrage S x2500
Hail S x5000
Nanite Repair Paste x50
Republic Fleet Depleted Uranium S x1000
Republic Fleet EMP S x1000
Republic Fleet Phased Plasma S x1000`,
    },
    {
        id: 'tfi-280-double-web',
        fittingId: 377,
        shipId: 73794,
        shipGuideId: 'thrasher',
        name: '280-double-web',
        description: 'Dual-web afterburner arty fit for catching kiters and controlling range at artillery optimal. A meme build that turns the tables on other 280mm kiters who rely on keeping you at range.',
        eftFormat: `[Thrasher Fleet Issue, [NVY] Thrasher Fleet Issue — 280-double-web]

Damage Control II
Gyrostabilizer II
Gyrostabilizer II

1MN Afterburner II
Fleeting Compact Stasis Webifier
Fleeting Compact Stasis Webifier

280mm Howitzer Artillery II
280mm Howitzer Artillery II
280mm Howitzer Artillery II
[Empty High slot]
280mm Howitzer Artillery II
280mm Howitzer Artillery II
280mm Howitzer Artillery II

Small Transverse Bulkhead II
Small Transverse Bulkhead II
Small Transverse Bulkhead II


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
        name: 'dual-masb-neutrons',
        description: 'Dual MASB neutron brawler with burst shield tank for winning scram brawls. Pulses XLASB charges and overheats to outlast other destroyers at close range.',
        eftFormat: `[Cormorant Navy Issue, [NVY] Cormorant Navy Issue — dual-masb-neutrons]

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
        id: 'corm-dual-masb-ions',
        fittingId: 379,
        shipId: 73795,
        shipGuideId: 'cormorant',
        name: 'dual-masb-ions',
        description: 'Dual MASB ion blaster brawler with slightly longer reach than the neutron variant. Same burst-shield brawl concept for pilots who prefer ion range and tracking tradeoffs.',
        eftFormat: `[Cormorant Navy Issue, [NVY] Cormorant Navy Issue — dual-masb-ions]

Damage Control II
Magnetic Field Stabilizer II

1MN Afterburner II
Warp Scrambler II
Medium Ancillary Shield Booster
Medium Ancillary Shield Booster

Light Ion Blaster II
Light Ion Blaster II
Light Ion Blaster II
[Empty High slot]
Light Ion Blaster II
Light Ion Blaster II
Light Ion Blaster II

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
        name: 'buffer',
        description: 'Surprise MWD buffer fit with a Republic Fleet medium shield extender. Looks like a kiter until you scram and brawl with strong shield buffer and blaster DPS.',
        eftFormat: `[Cormorant Navy Issue, [NVY] Cormorant Navy Issue — buffer]

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
        name: '10mn',
        description: '10MN rail scram-kite with cap booster and shield booster for sustained mid-range pressure. Uses 75mm rails to control range while staying under scram and applying steady DPS.',
        eftFormat: `[Cormorant Navy Issue, [NVY] Cormorant Navy Issue — 10mn]

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
]

export function getGuideFittingsForShip(shipGuideId: string): GuideFitting[] {
    return guideFittings.filter((fit) => fit.shipGuideId === shipGuideId)
}

export function getGuideFittingById(id: string): GuideFitting | undefined {
    return guideFittings.find((fit) => fit.id === id)
}
