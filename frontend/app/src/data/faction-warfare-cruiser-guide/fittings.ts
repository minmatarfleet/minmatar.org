import type { GuideFitting } from './types'

/**
 * Example fits for the Faction Warfare Cruiser Guide.
 * fittingId 0 = copy-only (not yet linked in the Fleet library).
 * Names follow navy-destroyer-metagame style: `{Role/Weapon/Prop} {Ship}`.
 * EFTs from Dato Koppla (YC 128) where available; others stay header-only until filled.
 */
export const guideFittings: GuideFitting[] = [
    {
        id: 'arby-long-kite',
        fittingId: 0,
        shipId: 628,
        shipGuideId: 'arbitrator',
        name: 'Long Point Arbitrator',
        description:
            'MAAR long-point drone kite with RLMLs, medium neut, and a tracking disruptor.',
        eftFormat: `[Arbitrator, Long Point Arbitrator]

Damage Control II
Drone Damage Amplifier II
Drone Damage Amplifier II
Multispectrum Energized Membrane II
Medium Ancillary Armor Repairer

50MN Quad LiF Restrained Microwarpdrive
Warp Disruptor II
Medium F-RX Compact Capacitor Booster
Tracking Disruptor II

Medium Energy Neutralizer II
Rapid Light Missile Launcher II
Rapid Light Missile Launcher II
Rapid Light Missile Launcher II

Medium Auxiliary Nano Pump I
Medium Drone Speed Augmentor I
Medium Polycarbon Engine Housing I


Warrior II x5
Hammerhead II x5
Valkyrie II x5
Hornet EC-300 x5

Inferno Fury Light Missile x500
Mjolnir Fury Light Missile x500
Nova Fury Light Missile x500
Navy Cap Booster 800 x12
Caldari Navy Inferno Light Missile x500
Caldari Navy Mjolnir Light Missile x500
Caldari Navy Nova Light Missile x500
Nanite Repair Paste x120
Optimal Range Disruption Script x1
Tracking Speed Disruption Script x1`,
    },
    {
        id: 'arby-brawl',
        fittingId: 0,
        shipId: 628,
        shipGuideId: 'arbitrator',
        name: 'Brawl Arbitrator',
        description:
            'AB 1600 plate brawler with dual medium neuts, dual nos, and a tracking disruptor.',
        eftFormat: `[Arbitrator, Brawl Arbitrator]

Drone Damage Amplifier II
Multispectrum Energized Membrane II
Multispectrum Energized Membrane II
1600mm Rolled Tungsten Compact Plates
Damage Control II

10MN Afterburner II
Warp Scrambler II
Stasis Webifier II
Balmer Series Compact Tracking Disruptor I

Medium Gremlin Compact Energy Neutralizer
Medium Gremlin Compact Energy Neutralizer
Small Ghoul Compact Energy Nosferatu
Small Ghoul Compact Energy Nosferatu

Medium Trimark Armor Pump I
Medium Trimark Armor Pump I
Medium Trimark Armor Pump I


Hobgoblin II x5
Warrior II x5
Hammerhead II x5

Republic Fleet Phased Plasma S x320
Tracking Speed Disruption Script x1`,
    },
    {
        id: 'arby-td-support',
        fittingId: 0,
        shipId: 628,
        shipGuideId: 'arbitrator',
        name: 'TD Support Arbitrator',
        description:
            'MWD armor buffer with dual tracking disruptors for small-gang / fleet support. Do not expect solo kills.',
        eftFormat: `[Arbitrator, TD Support Arbitrator]

1600mm Rolled Tungsten Compact Plates
Multispectrum Energized Membrane II
Multispectrum Energized Membrane II
Damage Control II
Reactive Armor Hardener

50MN Y-T8 Compact Microwarpdrive
Tracking Disruptor II
Tracking Disruptor II
Small Capacitor Booster II

Medium Energy Neutralizer II
Small Energy Neutralizer II
Small Energy Neutralizer II
Small Energy Neutralizer II

Medium Trimark Armor Pump I
Medium Trimark Armor Pump I
Medium Trimark Armor Pump I


Acolyte II x5
Warrior II x5
Hammerhead II x5
Valkyrie II x5


Navy Cap Booster 400 x1
Nanite Repair Paste x32
Republic Fleet Phased Plasma S x240
Caldari Navy Nova Rocket x50`,
    },
    {
        id: 'augni-polarized',
        fittingId: 0,
        shipId: 29337,
        shipGuideId: 'augni',
        name: 'Polarized Augoror Navy Issue',
        description:
            'Dual 1600 polarized heavy pulse zero-range brawler with scram/web.',
        eftFormat: `[Augoror Navy Issue, Polarized Augoror Navy Issue]

1600mm Rolled Tungsten Compact Plates
1600mm Rolled Tungsten Compact Plates
Layered Energized Membrane II
Reactor Control Unit II
Heat Sink II
Heat Sink II
Heat Sink II

50MN Y-T8 Compact Microwarpdrive
Stasis Webifier II
Warp Scrambler II

Small Ghoul Compact Energy Nosferatu
Small Knave Scoped Energy Nosferatu
Polarized Heavy Pulse Laser
Polarized Heavy Pulse Laser
Polarized Heavy Pulse Laser

Medium Energy Collision Accelerator II
Medium Trimark Armor Pump I
Medium Trimark Armor Pump I


Hobgoblin II x3


Conflagration M x6
Scorch M x3
Imperial Navy Multifrequency M x3
Nanite Repair Paste x50`,
    },
    {
        id: 'augni-kite-pulse',
        fittingId: 0,
        shipId: 29337,
        shipGuideId: 'augni',
        name: 'Pulse Augoror Navy Issue',
        description:
            'MAAR pulse kite with Scorch, double medium neuts, and long point.',
        eftFormat: `[Augoror Navy Issue, Pulse Augoror Navy Issue]

Medium Ancillary Armor Repairer
Multispectrum Energized Membrane II
IFFA Compact Damage Control
Heat Sink II
Heat Sink II
Extruded Compact Heat Sink
Nanofiber Internal Structure II

50MN Cold-Gas Enduring Microwarpdrive
Warp Disruptor II
Medium F-RX Compact Capacitor Booster

Heavy Pulse Laser II
Heavy Pulse Laser II
Heavy Pulse Laser II
Medium Energy Neutralizer II
Medium Energy Neutralizer II

Medium Energy Locus Coordinator II
Medium Energy Locus Coordinator II
Medium Polycarbon Engine Housing I


Hornet II x3

Conflagration M x3
Scorch M x6
Navy Cap Booster 800 x19
Imperial Navy Multifrequency M x3
Nanite Repair Paste x120`,
    },
    {
        id: 'maller-pulse',
        fittingId: 0,
        shipId: 624,
        shipGuideId: 'maller',
        name: 'Pulse Maller',
        description:
            'MWD 800mm plate pulse brick for plex defense and small gang.',
        eftFormat: `[Maller, Pulse Maller]

800mm Steel Plates II
IFFA Compact Damage Control
Multispectrum Coating II
Extruded Compact Heat Sink
Heat Sink II
Heat Sink II

50MN Quad LiF Restrained Microwarpdrive
Warp Scrambler II
Fleeting Compact Stasis Webifier

Heavy Pulse Laser II
Heavy Pulse Laser II
Heavy Pulse Laser II
Heavy Pulse Laser II
Heavy Pulse Laser II

Medium Energy Collision Accelerator II
Medium Trimark Armor Pump I
Medium Trimark Armor Pump I


Hobgoblin II x3

Conflagration M x5
Scorch M x5
Imperial Navy Multifrequency M x5`,
    },
    {
        id: 'omen-quad-light',
        fittingId: 0,
        shipId: 2006,
        shipGuideId: 'omen',
        name: 'Beam Omen',
        description:
            'MWD 1600 plate with five Quad Light Beam Lasers for short-range DPS.',
        eftFormat: `[Omen, Beam Omen]

Damage Control II
1600mm Steel Plates II
Multispectrum Energized Membrane II
Heat Sink II
Heat Sink II
Heat Sink II

50MN Quad LiF Restrained Microwarpdrive
Stasis Webifier II
Warp Scrambler II

Quad Light Beam Laser II
Quad Light Beam Laser II
Quad Light Beam Laser II
Quad Light Beam Laser II
Quad Light Beam Laser II

Medium Trimark Armor Pump I
Medium Trimark Armor Pump I
Medium Energy Collision Accelerator II


Hobgoblin II x2
Hammerhead II x3

Aurora M x5
Gleam M x5
Imperial Navy Multifrequency M x5`,
    },
    {
        id: 'omen-kite-pulse',
        fittingId: 0,
        shipId: 2006,
        shipGuideId: 'omen',
        name: 'Pulse Omen',
        description:
            'MWD scram/web heavy pulse kite — AugNI pattern on a T1 hull.',
        eftFormat: `[Omen, Pulse Omen]

Medium Ancillary Armor Repairer
Multispectrum Energized Membrane II
Damage Control II
800mm Rolled Tungsten Compact Plates
Heat Sink II
Heat Sink II

50MN Cold-Gas Enduring Microwarpdrive
Warp Disruptor II
Medium F-RX Compact Capacitor Booster

Focused Medium Pulse Laser II
Focused Medium Pulse Laser II
Focused Medium Pulse Laser II
Focused Medium Pulse Laser II
Focused Medium Pulse Laser II

Medium Energy Locus Coordinator II
Medium Energy Locus Coordinator II
Medium Polycarbon Engine Housing I


Warrior II x5


Conflagration M x5
Scorch M x5
Navy Cap Booster 800 x16
Imperial Navy Multifrequency M x5
Nanite Repair Paste x90`,
    },
    {
        id: 'omen-sniper',
        fittingId: 0,
        shipId: 2006,
        shipGuideId: 'omen',
        name: 'Sniper Omen',
        description:
            'Heavy beam long-point plex protector with MAAR.',
        eftFormat: `[Omen, Sniper Omen]`,
    },
    {
        id: 'omenni-mid-kite',
        fittingId: 0,
        shipId: 17709,
        shipGuideId: 'omenni',
        name: 'Kite Omen Navy Issue',
        description:
            'MAAR Scorch pulse kite with long point and a small neut.',
        eftFormat: `[Omen Navy Issue, Kite Omen Navy Issue]

Heat Sink II
Heat Sink II
Heat Sink II
Nanofiber Internal Structure II
Damage Control II
Medium Ancillary Armor Repairer
Multispectrum Energized Membrane II

50MN Microwarpdrive II
Warp Disruptor II
Medium Capacitor Booster II

Heavy Pulse Laser II
Heavy Pulse Laser II
Heavy Pulse Laser II
Heavy Pulse Laser II
Small Energy Neutralizer II

Medium Energy Locus Coordinator II
Medium Energy Locus Coordinator II
Medium Ancillary Current Router I


Warrior II x5
Hornet EC-300 x5

Conflagration M x4
Scorch M x4
Navy Cap Booster 800 x16
Imperial Navy Multifrequency M x4
Nanite Repair Paste x150`,
    },
    {
        id: 'omenni-mid-sniper',
        fittingId: 0,
        shipId: 17709,
        shipGuideId: 'omenni',
        name: 'Beam Omen Navy Issue',
        description:
            'Heavy beam mid-range kite with long point for plex flex.',
        eftFormat: `[Omen Navy Issue, Beam Omen Navy Issue]

Heat Sink II
Heat Sink II
Extruded Compact Heat Sink
Medium Ancillary Armor Repairer
Damage Control II
F-89 Compact Signal Amplifier
Multispectrum Energized Membrane II

50MN Quad LiF Restrained Microwarpdrive
Warp Disruptor II
Medium Capacitor Booster II

Heavy Beam Laser II
Heavy Beam Laser II
Heavy Beam Laser II
Heavy Beam Laser II
[Empty High slot]

Medium Energy Locus Coordinator II
Medium Ionic Field Projector II
Medium Ancillary Current Router II


Warrior II x5
Hornet EC-300 x5

Navy Cap Booster 800 x15
Nanite Repair Paste x214`,
    },
    {
        id: 'omenni-pulse',
        fittingId: 0,
        shipId: 17709,
        shipGuideId: 'omenni',
        name: 'Pulse Omen Navy Issue',
        description:
            'Closer-range pulse variant of the mid-range kite line.',
        eftFormat: `[Omen Navy Issue, Pulse Omen Navy Issue]`,
    },
    {
        id: 'caracalni-ham',
        fittingId: 0,
        shipId: 17634,
        shipGuideId: 'caracalni',
        name: 'HAM Caracal Navy Issue',
        description:
            'Idiot-proof six-HAM shield brawler with scram/web.',
        eftFormat: `[Caracal Navy Issue, HAM Caracal Navy Issue]

Damage Control II
Ballistic Control System II
Ballistic Control System II

50MN Quad LiF Restrained Microwarpdrive
Large Shield Extender II
Large Shield Extender II
Warp Scrambler II
Fleeting Compact Stasis Webifier
Multispectrum Shield Hardener II

Heavy Assault Missile Launcher II
Heavy Assault Missile Launcher II
Heavy Assault Missile Launcher II
Heavy Assault Missile Launcher II
Heavy Assault Missile Launcher II
Heavy Assault Missile Launcher II

Medium EM Shield Reinforcer II
Medium Core Defense Field Extender I
Medium Core Defense Field Extender I


Hobgoblin II x5

Inferno Javelin Heavy Assault Missile x1000
Inferno Rage Heavy Assault Missile x1000
Mjolnir Rage Heavy Assault Missile x1000
Nova Rage Heavy Assault Missile x1396
Caldari Navy Inferno Heavy Assault Missile x700
Caldari Navy Mjolnir Heavy Assault Missile x700
Caldari Navy Nova Heavy Assault Missile x700`,
    },
    {
        id: 'ospreyni-ham-neut',
        fittingId: 0,
        shipId: 29340,
        shipGuideId: 'ospreyni',
        name: '2X Neut HAM Osprey Navy Issue',
        description:
            'Three HAM launchers and two medium neuts — the one-on-one pressure line versus gunboats and VNI.',
        eftFormat: `[Osprey Navy Issue, 2X Neut HAM Osprey Navy Issue]

Damage Control II
Ballistic Control System II
Ballistic Control System II
Ballistic Control System II

50MN Y-T8 Compact Microwarpdrive
Large Shield Extender II
Large F-S9 Regolith Compact Shield Extender
Multispectrum Shield Hardener II
Warp Scrambler II
Small Capacitor Booster II

Heavy Assault Missile Launcher II
Heavy Assault Missile Launcher II
Heavy Assault Missile Launcher II
Medium Gremlin Compact Energy Neutralizer
Medium Gremlin Compact Energy Neutralizer

Medium EM Shield Reinforcer II
Medium Core Defense Field Extender I
Medium Ancillary Current Router I


Hobgoblin II x5

Inferno Rage Heavy Assault Missile x1000
Mjolnir Rage Heavy Assault Missile x1000
Nova Rage Heavy Assault Missile x1000
Scourge Rage Heavy Assault Missile x1000
Navy Cap Booster 400 x26
Caldari Navy Inferno Heavy Assault Missile x1000
Caldari Navy Mjolnir Heavy Assault Missile x1000
Caldari Navy Nova Heavy Assault Missile x1000
Caldari Navy Scourge Heavy Assault Missile x1000
Nanite Repair Paste x100`,
    },
    {
        id: 'ospreyni-rhml-kite',
        fittingId: 0,
        shipId: 29340,
        shipGuideId: 'ospreyni',
        name: 'RLML Osprey Navy Issue',
        description:
            'RLML long-point kite with XLASB, scram, and dual small neuts for solo plex work.',
        eftFormat: `[Osprey Navy Issue, RLML Osprey Navy Issue]

Ballistic Control System II
Ballistic Control System II
Nanofiber Internal Structure II
Nanofiber Internal Structure II

50MN Quad LiF Restrained Microwarpdrive
Warp Disruptor II
Warp Scrambler II
X-Large Ancillary Shield Booster
Compact Multispectrum Shield Hardener
Small F-RX Compact Capacitor Booster

Rapid Light Missile Launcher II
Rapid Light Missile Launcher II
Rapid Light Missile Launcher II
Small Gremlin Compact Energy Neutralizer
Small Gremlin Compact Energy Neutralizer

Medium EM Shield Reinforcer II
Medium Hydraulic Bay Thrusters II
Medium Rocket Fuel Cache Partition II


Warrior II x5

Navy Cap Booster 400 x30
Caldari Navy Scourge Light Missile x180`,
    },
    {
        id: 'eni-blaster',
        fittingId: 0,
        shipId: 29344,
        shipGuideId: 'eni',
        name: 'Blaster Exequror Navy Issue',
        description:
            'Neutron plate brawler with double web and a small nos. Prefer Neutrons over ions.',
        eftFormat: `[Exequror Navy Issue, Blaster Exequror Navy Issue]

1600mm Steel Plates II
Multispectrum Energized Membrane II
Multispectrum Coating II
Damage Control II
Magnetic Field Stabilizer II
Magnetic Field Stabilizer II

50MN Quad LiF Restrained Microwarpdrive
Warp Scrambler II
Stasis Webifier II
Stasis Webifier II

Heavy Neutron Blaster II
Heavy Neutron Blaster II
Heavy Neutron Blaster II
Heavy Neutron Blaster II
Small Energy Nosferatu II

Medium Ancillary Current Router I
Medium Trimark Armor Pump I
Medium Explosive Armor Reinforcer I


Acolyte II x5

Null M x1000
Void M x2320
Missile Precision Disruption Script x1
Missile Range Disruption Script x1
Federation Navy Antimatter Charge M x650
Nanite Repair Paste x30
Optimal Range Disruption Script x1
Tracking Speed Disruption Script x1
Balmer Series Compact Tracking Disruptor I x1
C-IR Compact Guidance Disruptor x1`,
    },
    {
        id: 'eni-250rail',
        fittingId: 0,
        shipId: 29344,
        shipGuideId: 'eni',
        name: '250mm Rail Exequror Navy Issue',
        description:
            '250mm rail plex / gang flex — hold range without giving up the ENI tank skeleton.',
        eftFormat: `[Exequror Navy Issue, 250mm Rail Exequror Navy Issue]

Damage Control II
Magnetic Field Stabilizer II
Magnetic Field Stabilizer II
Shadow Serpentis Multispectrum Coating
Medium Ancillary Armor Repairer
1600mm Rolled Tungsten Compact Plates

50MN Y-T8 Compact Microwarpdrive
Warp Disruptor II
Stasis Webifier II
Medium F-RX Compact Capacitor Booster

250mm Railgun II
250mm Railgun II
250mm Railgun II
250mm Railgun II
[Empty High slot]

Medium Ancillary Current Router I
Medium Ancillary Current Router II
Medium Ionic Field Projector II


Acolyte II x5

Javelin M x2000
Spike M x6308
Caldari Navy Antimatter Charge M x2000
Caldari Navy Iron Charge M x1744
Caldari Navy Thorium Charge M x2000
Nanite Repair Paste x132
ECCM Script x1
Scan Resolution Script x1
Targeting Range Script x2
Optimal Range Script x3
Tracking Speed Script x3
Tracking Computer II x1`,
    },
    {
        id: 'eni-dual-plate-electron',
        fittingId: 0,
        shipId: 29344,
        shipGuideId: 'eni',
        name: 'Dual Plate Electron Exequror Navy Issue',
        description:
            'Dual 1600 electron blob / mass fight line.',
        eftFormat: `[Exequror Navy Issue, Dual Plate Electron Exequror Navy Issue]

1600mm Crystalline Carbonide Restrained Plates
1600mm Rolled Tungsten Compact Plates
Multispectrum Energized Membrane II
Multispectrum Energized Membrane II
Corelum C-Type Explosive Energized Membrane
Damage Control II

50MN Quad LiF Restrained Microwarpdrive
Warp Scrambler II
Stasis Webifier II
Stasis Webifier II

Heavy Electron Blaster II
Heavy Electron Blaster II
Heavy Electron Blaster II
Heavy Electron Blaster II
Small Energy Nosferatu II

Medium Ancillary Current Router II
Medium Trimark Armor Pump I
Medium Trimark Armor Pump I


Hobgoblin II x5

Null M x1000
Void M x2800
Caldari Navy Antimatter Charge M x1000
Nanite Repair Paste x50`,
    },
    {
        id: 'vexor-neut-plate',
        fittingId: 0,
        shipId: 626,
        shipGuideId: 'vexor',
        name: 'Neut Vexor',
        description:
            '1600 plate plex holder with multi-neut highs and heavy drone DPS.',
        eftFormat: `[Vexor, Neut Vexor]

1600mm Rolled Tungsten Compact Plates
Multispectrum Energized Membrane II
Multispectrum Energized Membrane II
Damage Control II
Drone Damage Amplifier II

50MN Quad LiF Restrained Microwarpdrive
Warp Scrambler II
Stasis Webifier II
Small Capacitor Booster II

Medium Energy Neutralizer II
Small Energy Neutralizer II
Small Energy Neutralizer II
Small Energy Neutralizer II

Medium Trimark Armor Pump I
Medium Trimark Armor Pump I
Medium Explosive Armor Reinforcer I


Hobgoblin II x5
Warrior II x5
Hammerhead II x5
Hornet EC-300 x5

Navy Cap Booster 400 x1`,
    },
    {
        id: 'vexor-blaster-neut',
        fittingId: 0,
        shipId: 626,
        shipGuideId: 'vexor',
        name: 'Blaster Vexor',
        description:
            'Neutron + dual magnetic stab scram brawler with bulkhead rigs.',
        eftFormat: `[Vexor, Blaster Vexor]`,
    },
    {
        id: 'vni-dual-rep',
        fittingId: 0,
        shipId: 17843,
        shipGuideId: 'vni',
        name: 'Dual Rep Vexor Navy Issue',
        description:
            'Dual-rep reactive ion VNI with scram/web and a medium cap booster.',
        eftFormat: `[Vexor Navy Issue, Dual Rep Vexor Navy Issue]

Medium Armor Repairer II
Medium Armor Repairer II
Multispectrum Energized Membrane II
Multispectrum Energized Membrane II
Damage Control II
Reactive Armor Hardener

50MN Quad LiF Restrained Microwarpdrive
Warp Scrambler II
Stasis Webifier II
Medium F-RX Compact Capacitor Booster

Heavy Ion Blaster II
Heavy Ion Blaster II
Heavy Ion Blaster II
Small Energy Neutralizer II

Medium Auxiliary Nano Pump I
Medium Auxiliary Nano Pump I
Medium Nanobot Accelerator I


Acolyte II x5
Hobgoblin II x1
Hammerhead II x2
Ogre II x2

Void M x360
Navy Cap Booster 800 x1`,
    },
    {
        id: 'bellicose-ham',
        fittingId: 0,
        shipId: 630,
        shipGuideId: 'bellicose',
        name: 'HAM Bellicose',
        description:
            'Cheap four-HAM shield scram brawler with Hammerheads.',
        eftFormat: `[Bellicose, HAM Bellicose]

Ballistic Control System II
Ballistic Control System II
Ballistic Control System II
IFFA Compact Damage Control

50MN Y-T8 Compact Microwarpdrive
Faint Epsilon Scoped Warp Scrambler
Multispectrum Shield Hardener II
Large Shield Extender II
Large Shield Extender II

Heavy Assault Missile Launcher II
Heavy Assault Missile Launcher II
Heavy Assault Missile Launcher II
Heavy Assault Missile Launcher II

Medium EM Shield Reinforcer I
Medium Core Defense Field Extender I
Medium Core Defense Field Extender I


Hammerhead II x5


Inferno Rage Heavy Assault Missile x1200
Mjolnir Rage Heavy Assault Missile x1200
Nova Rage Heavy Assault Missile x1200
Caldari Navy Inferno Heavy Assault Missile x700
Caldari Navy Mjolnir Heavy Assault Missile x700
Caldari Navy Nova Heavy Assault Missile x700
Fleeting Compact Stasis Webifier x1
Parallel Enduring Target Painter x1`,
    },
    {
        id: 'bellicose-xlsb',
        fittingId: 0,
        shipId: 630,
        shipGuideId: 'bellicose',
        name: 'XLASB HAM Bellicose',
        description:
            'AB XLASB HAM plex protector — cheap Caracal Navy Issue stand-in with scram/web.',
        eftFormat: `[Bellicose, XLASB HAM Bellicose]

Damage Control II
Co-Processor II
Ballistic Control System II
Ballistic Control System II

10MN Afterburner II
X-Large Ancillary Shield Booster
Warp Scrambler II
Fleeting Compact Stasis Webifier
Multispectrum Shield Hardener II

Heavy Assault Missile Launcher II
Heavy Assault Missile Launcher II
Heavy Assault Missile Launcher II
Heavy Assault Missile Launcher II

Medium Processor Overclocking Unit I
Medium EM Shield Reinforcer II
Medium Thermal Shield Reinforcer II


Hammerhead II x5

Inferno Javelin Heavy Assault Missile x530
Inferno Rage Heavy Assault Missile x530
Mjolnir Rage Heavy Assault Missile x530
Nova Rage Heavy Assault Missile x530
Scourge Rage Heavy Assault Missile x264
Navy Cap Booster 400 x39
Caldari Navy Inferno Heavy Assault Missile x530
Caldari Navy Mjolnir Heavy Assault Missile x530
Caldari Navy Nova Heavy Assault Missile x530
Zainou 'Gypsy' CPU Management EE-602 x1`,
    },
    {
        id: 'scythefi-dual-prop-ac',
        fittingId: 0,
        shipId: 29336,
        shipGuideId: 'scythefi',
        name: 'Dual Prop Scythe Fleet Issue',
        description:
            'Primary dual-prop leave-insurance: MWD + AB XLASB with Dual 180mm ACs.',
        eftFormat: `[Scythe Fleet Issue, Dual Prop Scythe Fleet Issue]

Reactor Control Unit II
Damage Control II
Nanofiber Internal Structure II
Gyrostabilizer II
Gyrostabilizer II

50MN Microwarpdrive II
10MN Afterburner II
Warp Scrambler II
X-Large Ancillary Shield Booster
Multispectrum Shield Hardener II

Dual 180mm AutoCannon II
Dual 180mm AutoCannon II
Dual 180mm AutoCannon II
Dual 180mm AutoCannon II
Small Energy Nosferatu II

Medium Processor Overclocking Unit I
Medium EM Shield Reinforcer II
Medium Polycarbon Engine Housing II


Hobgoblin II x5

Navy Cap Booster 400 x9
Republic Fleet Phased Plasma M x1600`,
    },
    {
        id: 'scythefi-rlml-armor',
        fittingId: 0,
        shipId: 29336,
        shipGuideId: 'scythefi',
        name: 'Armor RLML Scythe Fleet Issue',
        description:
            'Primary RLML line: 800 plate MAAR long-point with medium neut. Refit: RLML XLASB (shield flash kite).',
        eftFormat: `[Scythe Fleet Issue, Armor RLML Scythe Fleet Issue]

Ballistic Control System II
Ballistic Control System II
Damage Control II
Medium Ancillary Armor Repairer
800mm Crystalline Carbonide Restrained Plates

50MN Cold-Gas Enduring Microwarpdrive
Warp Disruptor II
Missile Guidance Computer II
Missile Guidance Computer II
Medium Cap Battery II

Rapid Light Missile Launcher II
Rapid Light Missile Launcher II
Rapid Light Missile Launcher II
Rapid Light Missile Launcher II
Medium Infectious Scoped Energy Neutralizer

Medium Polycarbon Engine Housing II
Medium Polycarbon Engine Housing I
Medium Ancillary Current Router I


Hornet II x5

Inferno Fury Light Missile x1000
Mjolnir Fury Light Missile x1000
Nova Fury Light Missile x1000
Scourge Fury Light Missile x1000
Caldari Navy Inferno Light Missile x1000
Caldari Navy Mjolnir Light Missile x1000
Caldari Navy Nova Light Missile x1000
Caldari Navy Scourge Light Missile x1000
Missile Precision Script x2
Missile Range Script x2
Nanite Repair Paste x150`,
    },
    {
        id: 'scythefi-rlml-xlsb',
        fittingId: 0,
        shipId: 29336,
        shipGuideId: 'scythefi',
        name: 'RLML XLASB Scythe Fleet Issue',
        description:
            'Refit of Armor RLML: four RLML + XLASB long-point kite with a small neut.',
        eftFormat: `[Scythe Fleet Issue, RLML XLASB Scythe Fleet Issue]

Ballistic Control System II
Ballistic Control System II
Co-Processor II
Nanofiber Internal Structure II
Nanofiber Internal Structure II

50MN Y-T8 Compact Microwarpdrive
Warp Disruptor II
Compact Multispectrum Shield Hardener
X-Large Ancillary Shield Booster
Small F-RX Compact Capacitor Booster

Rapid Light Missile Launcher II
Rapid Light Missile Launcher II
Rapid Light Missile Launcher II
Rapid Light Missile Launcher II
Small Gremlin Compact Energy Neutralizer

Medium Rocket Fuel Cache Partition II
Medium EM Shield Reinforcer II
Medium Hydraulic Bay Thrusters II


Hornet II x5

Inferno Fury Light Missile x1000
Mjolnir Fury Light Missile x1000
Nova Fury Light Missile x1000
Navy Cap Booster 400 x37
Caldari Navy Inferno Light Missile x1000
Caldari Navy Mjolnir Light Missile x1100
Caldari Navy Nova Light Missile x1080`,
    },
    {
        id: 'stabber-xlsb',
        fittingId: 0,
        shipId: 622,
        shipGuideId: 'stabber',
        name: 'AB XLASB Stabber',
        description:
            'AB XLASB plex protector — do not MWD-scram in this hull. Hold the beacon and leave when you must.',
        eftFormat: `[Stabber, AB XLASB Stabber]

Gyrostabilizer II
IFFA Compact Damage Control
Gyrostabilizer II
Counterbalanced Compact Gyrostabilizer

10MN Afterburner II
Warp Scrambler II
Multispectrum Shield Hardener II
X-Large Ancillary Shield Booster

Dual 180mm AutoCannon II
Dual 180mm AutoCannon II
Dual 180mm AutoCannon II
Dual 180mm AutoCannon II
Small Gremlin Compact Energy Neutralizer
Small Ghoul Compact Energy Nosferatu

Medium EM Shield Reinforcer II
Medium Processor Overclocking Unit I
Medium Processor Overclocking Unit I


Hobgoblin II x5

Navy Cap Booster 400 x18
Republic Fleet Fusion M x800
Republic Fleet Phased Plasma M x800`,
    },
    {
        id: 'stabber-vulcan-kite',
        fittingId: 0,
        shipId: 622,
        shipGuideId: 'stabber',
        name: 'Vulcan Stabber',
        description:
            'MWD long-point Vulcan kite with twin LSE and twin RLML.',
        eftFormat: `[Stabber, Vulcan Stabber]

Damage Control II
Gyrostabilizer II
Gyrostabilizer II
Power Diagnostic System II

50MN Cold-Gas Enduring Microwarpdrive
Large Shield Extender II
Large Shield Extender II
Warp Disruptor II

220mm Vulcan AutoCannon II
220mm Vulcan AutoCannon II
220mm Vulcan AutoCannon II
220mm Vulcan AutoCannon II
Rapid Light Missile Launcher II
Rapid Light Missile Launcher II

Medium Core Defense Field Extender I
Medium Core Defense Field Extender I
Medium Core Defense Field Extender I


Hornet II x5


Barrage M x1000
Hail M x1640
Inferno Fury Light Missile x400
Mjolnir Fury Light Missile x400
Nova Fury Light Missile x440
Caldari Navy Inferno Light Missile x400
Caldari Navy Mjolnir Light Missile x400
Caldari Navy Nova Light Missile x400
Nanite Repair Paste x50
Republic Fleet EMP M x800
Republic Fleet Fusion M x800
Republic Fleet Phased Plasma M x800`,
    },
    {
        id: 'stabberfi-dual-prop',
        fittingId: 0,
        shipId: 17713,
        shipGuideId: 'stabberfi',
        name: 'Dual Prop Stabber Fleet Issue',
        description:
            'MWD + AB 1600 plate Vulcan for range control and punching up.',
        eftFormat: `[Stabber Fleet Issue, Dual Prop Stabber Fleet Issue]

1600mm Rolled Tungsten Compact Plates
Multispectrum Energized Membrane II
Multispectrum Energized Membrane II
Damage Control II
Gyrostabilizer II
Gyrostabilizer II

50MN Quad LiF Restrained Microwarpdrive
Warp Scrambler II
Stasis Webifier II
10MN Afterburner II

220mm Vulcan AutoCannon II
220mm Vulcan AutoCannon II
220mm Vulcan AutoCannon II
220mm Vulcan AutoCannon II
220mm Vulcan AutoCannon II

Medium Trimark Armor Pump I
Medium Trimark Armor Pump I
Medium Explosive Armor Reinforcer I


Hobgoblin II x2
Hammerhead II x3

Barrage M x1000
Hail M x1800
Nanite Repair Paste x100
Republic Fleet EMP M x1000
Republic Fleet Fusion M x1000
Republic Fleet Phased Plasma M x1000`,
    },
]

export function getGuideFittingsForShip(shipGuideId: string): GuideFitting[] {
    return guideFittings.filter((fit) => fit.shipGuideId === shipGuideId)
}

export function getGuideFittingById(id: string): GuideFitting | undefined {
    return guideFittings.find((fit) => fit.id === id)
}
