/**
 * Minimal EFT parser for the fleet refit modal.
 *
 * EFT exports list modules by slot group separated by blank lines
 * (low, mid, high, rig, then drones / cargo as "Name xN" lines).
 */

export type EftSlotGroup = 'low' | 'mid' | 'high' | 'rig' | 'other'

export interface EftModule {
    /** Position across the whole fit, used to address a slot in forms. */
    index: number
    group: EftSlotGroup
    name: string
}

export interface EftItem {
    name: string
    quantity: number
}

export interface ParsedEft {
    ship: string
    name: string
    modules: EftModule[]
    /** Drones and cargo: anything listed as "Name xN". */
    cargo: EftItem[]
}

const SLOT_ORDER:EftSlotGroup[] = [ 'low', 'mid', 'high', 'rig' ]
const QTY_RE = /^(.+?)\s+x(\d+)$/

export function parse_eft(eft:string | null | undefined):ParsedEft {
    const lines = (eft ?? '').replace(/\r/g, '').split('\n')
    const header = (lines.shift() ?? '').trim()
    const header_match = header.match(/^\[(.+?),\s*(.+?)\]$/)

    const result:ParsedEft = {
        ship: header_match?.[1]?.trim() ?? header.replace(/[\[\]]/g, '').split(',')[0]?.trim() ?? '',
        name: header_match?.[2]?.trim() ?? '',
        modules: [],
        cargo: [],
    }

    // Split into blank-line separated sections.
    const sections:string[][] = []
    let current:string[] = []
    for (const raw of lines) {
        const line = raw.trim()
        if (!line) {
            if (current.length) sections.push(current)
            current = []
            continue
        }
        current.push(line)
    }
    if (current.length) sections.push(current)

    let slot_section = 0
    let index = 0
    for (const section of sections) {
        const is_item_section = section.every(line => QTY_RE.test(line) || line.startsWith('[Empty '))
        if (is_item_section && section.some(line => QTY_RE.test(line))) {
            for (const line of section) {
                const match = line.match(QTY_RE)
                if (match) result.cargo.push({ name: match[1].trim(), quantity: parseInt(match[2]) })
            }
            continue
        }

        const group = SLOT_ORDER[slot_section] ?? 'other'
        slot_section++
        for (const line of section) {
            if (line.startsWith('[Empty ')) { index++; continue }
            const qty = line.match(QTY_RE)
            if (qty) { result.cargo.push({ name: qty[1].trim(), quantity: parseInt(qty[2]) }); continue }
            // "Module, Charge": the loaded charge is not a swappable module.
            const name = line.split(',', 1)[0].trim()
            result.modules.push({ index: index++, group, name })
        }
    }

    return result
}

// Ammo, scripts, drones, drugs and deployables never count as a spare module.
const NOT_A_MODULE = new RegExp([
    '( Script| Charge| Paste| Crystal| Probe| Dose I{0,3}V?)$',
    '(Cap Booster|Mindflood|Synth |Exile|Blue Pill|Crash|Frentix|Sooth Sayer|X-Instinct|Drop|Pyrolancea|Agency |Quafe)',
    '(Mobile Depot|Mobile Tractor|Mobile Cynosural)',
    '(Warrior|Valkyrie|Hobgoblin|Hammerhead|Acolyte|Infiltrator|Praetor|Ogre|Berserker|Vespa|Wasp|Garde|Bouncer|Curator|Warden|Gecko|Hornet|Vexor)',
    '(Maintenance Bot|Bot I{1,2}$| Drone )',
].join('|'), 'i')

/**
 * Cargo entries that are plausibly spare modules to swap in: one or two of
 * them, and not ammo, scripts, drones or consumables.
 */
export function swappable_cargo(parsed:ParsedEft, slots?:Record<string, string>):EftItem[] {
    const has_slot_data = slots && Object.keys(slots).length > 0
    return parsed.cargo.filter(item =>
        item.quantity <= 2
        && !NOT_A_MODULE.test(item.name)
        && (!has_slot_data || [ 'high', 'mid', 'low' ].includes(slots[item.name] ?? ''))
    )
}

/** Slot group for a fitted module: dogma data when available, else the EFT section it was listed in. */
export function module_slot(module:EftModule, slots?:Record<string, string>):EftSlotGroup {
    const known = slots?.[module.name]
    return known === 'high' || known === 'mid' || known === 'low' || known === 'rig' ? known : module.group
}
