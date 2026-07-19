import type { GuideFitting } from './types'

/**
 * Example fits for the Faction Warfare Cruiser Guide.
 * fittingId 0 = copy-only (not yet linked in the Fleet library).
 * Names follow navy-destroyer-metagame style: `{Role/Weapon/Prop} {Ship}`.
 */
export const guideFittings: GuideFitting[] = [
    {
        id: 'arby-long-kite',
        fittingId: 0,
        shipId: 628,
        shipGuideId: 'arbitrator',
        name: 'Long Point Arbitrator',
        description:
            'Shield XLASB long-point drone kite with light missiles and a medium neut.',
        eftFormat: `[Arbitrator, Long Point Arbitrator]`,
    },
    {
        id: 'arby-brawl',
        fittingId: 0,
        shipId: 628,
        shipGuideId: 'arbitrator',
        name: 'Brawl Arbitrator',
        description:
            '100MN AB shield brawler with light missiles, small neut, and drones.',
        eftFormat: `[Arbitrator, Brawl Arbitrator]`,
    },
    {
        id: 'arby-td-support',
        fittingId: 0,
        shipId: 628,
        shipGuideId: 'arbitrator',
        name: 'TD Support Arbitrator',
        description:
            'MWD armor buffer with dual tracking disruptors for small-gang / fleet support. Do not expect solo kills.',
        eftFormat: `[Arbitrator, TD Support Arbitrator]`,
    },
    {
        id: 'augni-polarized',
        fittingId: 0,
        shipId: 29337,
        shipGuideId: 'augni',
        name: 'Polarized Augoror Navy Issue',
        description:
            'Dual 1600 polarized heavy pulse zero-range brawler with scram/web.',
        eftFormat: `[Augoror Navy Issue, Polarized Augoror Navy Issue]`,
    },
    {
        id: 'augni-kite-pulse',
        fittingId: 0,
        shipId: 29337,
        shipGuideId: 'augni',
        name: 'Pulse Augoror Navy Issue',
        description:
            'MAAR pulse kite with Scorch, double medium neuts, and long point.',
        eftFormat: `[Augoror Navy Issue, Pulse Augoror Navy Issue]`,
    },
    {
        id: 'maller-pulse',
        fittingId: 0,
        shipId: 624,
        shipGuideId: 'maller',
        name: 'Pulse Maller',
        description:
            'AB 800mm plate pulse brick for plex defense and small gang.',
        eftFormat: `[Maller, Pulse Maller]`,
    },
    {
        id: 'omen-quad-light',
        fittingId: 0,
        shipId: 2006,
        shipGuideId: 'omen',
        name: 'Beam Omen',
        description:
            '1600 plate with five Quad Light Beam Lasers for short-range DPS.',
        eftFormat: `[Omen, Beam Omen]`,
    },
    {
        id: 'omen-kite-pulse',
        fittingId: 0,
        shipId: 2006,
        shipGuideId: 'omen',
        name: 'Pulse Omen',
        description:
            'MWD scram/web heavy pulse kite — AugNI pattern on a T1 hull.',
        eftFormat: `[Omen, Pulse Omen]`,
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
        eftFormat: `[Omen Navy Issue, Kite Omen Navy Issue]`,
    },
    {
        id: 'omenni-mid-sniper',
        fittingId: 0,
        shipId: 17709,
        shipGuideId: 'omenni',
        name: 'Beam Omen Navy Issue',
        description:
            'Heavy beam mid-range sniper with long point for plex flex and kite opens.',
        eftFormat: `[Omen Navy Issue, Beam Omen Navy Issue]`,
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
        eftFormat: `[Caracal Navy Issue, HAM Caracal Navy Issue]`,
    },
    {
        id: 'ospreyni-ham-neut',
        fittingId: 0,
        shipId: 29340,
        shipGuideId: 'ospreyni',
        name: '2X Neut HAM Osprey Navy Issue',
        description:
            'Three HAM launchers and two medium neuts — the one-on-one pressure line versus gunboats and VNI.',
        eftFormat: `[Osprey Navy Issue, 2X Neut HAM Osprey Navy Issue]`,
    },
    {
        id: 'ospreyni-rhml-kite',
        fittingId: 0,
        shipId: 29340,
        shipGuideId: 'ospreyni',
        name: 'RHML Osprey Navy Issue',
        description:
            'RHML long-point kite with XLASB for solo plex work. Utility highs stay free for neut or drone link.',
        eftFormat: `[Osprey Navy Issue, RHML Osprey Navy Issue]`,
    },
    {
        id: 'eni-blaster',
        fittingId: 0,
        shipId: 29344,
        shipGuideId: 'eni',
        name: 'Blaster Exequror Navy Issue',
        description:
            'Neutron plate brawler with double web and a small nos. Prefer Neutrons over ions.',
        eftFormat: `[Exequror Navy Issue, Blaster Exequror Navy Issue]`,
    },
    {
        id: 'eni-250rail',
        fittingId: 0,
        shipId: 29344,
        shipGuideId: 'eni',
        name: '250mm Rail Exequror Navy Issue',
        description:
            '250mm rail plex / gang flex — hold range without giving up the ENI tank skeleton.',
        eftFormat: `[Exequror Navy Issue, 250mm Rail Exequror Navy Issue]`,
    },
    {
        id: 'eni-dual-plate-electron',
        fittingId: 0,
        shipId: 29344,
        shipGuideId: 'eni',
        name: 'Dual Plate Electron Exequror Navy Issue',
        description:
            'Dual 1600 electron blob / mass fight line.',
        eftFormat: `[Exequror Navy Issue, Dual Plate Electron Exequror Navy Issue]`,
    },
    {
        id: 'vexor-neut-plate',
        fittingId: 0,
        shipId: 626,
        shipGuideId: 'vexor',
        name: 'Neut Vexor',
        description:
            '1600 plate plex holder with multi-neut highs and heavy drone DPS.',
        eftFormat: `[Vexor, Neut Vexor]`,
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
            'Dual-rep reactive electron VNI with double medium cap boosters.',
        eftFormat: `[Vexor Navy Issue, Dual Rep Vexor Navy Issue]`,
    },
    {
        id: 'bellicose-ham',
        fittingId: 0,
        shipId: 630,
        shipGuideId: 'bellicose',
        name: 'HAM Bellicose',
        description:
            'Four-HAM shield scram brawler with light drones.',
        eftFormat: `[Bellicose, HAM Bellicose]`,
    },
    {
        id: 'bellicose-xlsb',
        fittingId: 0,
        shipId: 630,
        shipGuideId: 'bellicose',
        name: 'XLASB HAM Bellicose',
        description:
            'XLASB HAM plex protector — trade a LSE for the ancillary and keep the scram.',
        eftFormat: `[Bellicose, XLASB HAM Bellicose]`,
    },
    {
        id: 'scythefi-dual-prop-ac',
        fittingId: 0,
        shipId: 29336,
        shipGuideId: 'scythefi',
        name: 'Dual Prop Scythe Fleet Issue',
        description:
            'Primary dual-prop leave-insurance: MWD + AB XLASB with Dual 180mm ACs.',
        eftFormat: `[Scythe Fleet Issue, Dual Prop Scythe Fleet Issue]`,
    },
    {
        id: 'scythefi-rlml-armor',
        fittingId: 0,
        shipId: 29336,
        shipGuideId: 'scythefi',
        name: 'Armor RLML Scythe Fleet Issue',
        description:
            'Primary RLML line: 800 plate MAAR long-point with medium neut. Refit: RLML XLASB (shield flash kite).',
        eftFormat: `[Scythe Fleet Issue, Armor RLML Scythe Fleet Issue]`,
    },
    {
        id: 'scythefi-rlml-xlsb',
        fittingId: 0,
        shipId: 29336,
        shipGuideId: 'scythefi',
        name: 'RLML XLASB Scythe Fleet Issue',
        description:
            'Refit of Armor RLML: four RLML + XLASB long-point kite with a small neut.',
        eftFormat: `[Scythe Fleet Issue, RLML XLASB Scythe Fleet Issue]`,
    },
    {
        id: 'stabber-xlsb',
        fittingId: 0,
        shipId: 622,
        shipGuideId: 'stabber',
        name: 'AB XLASB Stabber',
        description:
            'AB XLASB plex protector — do not MWD-scram in this hull. Hold the beacon and leave when you must.',
        eftFormat: `[Stabber, AB XLASB Stabber]`,
    },
    {
        id: 'stabber-vulcan-kite',
        fittingId: 0,
        shipId: 622,
        shipGuideId: 'stabber',
        name: 'Vulcan Stabber',
        description:
            'MWD long-point Vulcan kite with twin LSE and twin RLML.',
        eftFormat: `[Stabber, Vulcan Stabber]`,
    },
    {
        id: 'stabberfi-dual-prop',
        fittingId: 0,
        shipId: 17713,
        shipGuideId: 'stabberfi',
        name: 'Dual Prop Stabber Fleet Issue',
        description:
            'MWD + AB 1600 plate Vulcan for range control and punching up.',
        eftFormat: `[Stabber Fleet Issue, Dual Prop Stabber Fleet Issue]`,
    },
]

export function getGuideFittingsForShip(shipGuideId: string): GuideFitting[] {
    return guideFittings.filter((fit) => fit.shipGuideId === shipGuideId)
}

export function getGuideFittingById(id: string): GuideFitting | undefined {
    return guideFittings.find((fit) => fit.id === id)
}
