import { describe, expect, it } from 'vitest'

import { module_slot, parse_eft, swappable_cargo } from '@helpers/eft'
import { guideFittings as cruiser_fits } from '@/data/faction-warfare-cruiser-guide'
import { guideFittings as destroyer_fits } from '@/data/navy-destroyer-metagame'
import { guideFittings as frigate_fits } from '@/data/navy-frigate-guide'

// Verbatim copy of parse_eft before "/offline" was handled (for parity).
type Legacy = { ship: string, name: string, modules: { index: number, group: string, name: string }[], cargo: { name: string, quantity: number }[] }
const SLOT_ORDER = ['low', 'mid', 'high', 'rig']
const QTY_RE = /^(.+?)\s+x(\d+)$/
function legacy_parse_eft(eft: string | null | undefined): Legacy {
    const lines = (eft ?? '').replace(/\r/g, '').split('\n')
    const header = (lines.shift() ?? '').trim()
    const header_match = header.match(/^\[(.+?),\s*(.+?)\]$/)
    const result: Legacy = {
        ship: header_match?.[1]?.trim() ?? header.replace(/[\[\]]/g, '').split(',')[0]?.trim() ?? '',
        name: header_match?.[2]?.trim() ?? '',
        modules: [],
        cargo: [],
    }
    const sections: string[][] = []
    let current: string[] = []
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
            const name = line.split(',', 1)[0].trim()
            result.modules.push({ index: index++, group, name })
        }
    }
    return result
}

const HURRICANE = `[Hurricane, Cane [FL33T]]
Gyrostabilizer II
[Empty Low slot]
Damage Control II

50MN Microwarpdrive II
Stasis Webifier II /offline

425mm AutoCannon II, Republic Fleet EMP M
Heavy Missile Launcher II, Scourge Heavy Missile

Medium Projectile Burst Aerator II


Hammerhead II x5

Republic Fleet EMP M x2000
Stasis Webifier II x1
`

describe('parse_eft', () => {
    it('reads the header, slots, charges and cargo', () => {
        const parsed = parse_eft(HURRICANE)
        expect(parsed.ship).toBe('Hurricane')
        expect(parsed.name).toBe('Cane [FL33T]')
        expect(parsed.modules.map(module => [module.index, module.group, module.name])).toEqual([
            [0, 'low', 'Gyrostabilizer II'],
            [2, 'low', 'Damage Control II'],
            [3, 'mid', '50MN Microwarpdrive II'],
            [4, 'mid', 'Stasis Webifier II'],
            [5, 'high', '425mm AutoCannon II'],
            [6, 'high', 'Heavy Missile Launcher II'],
            [7, 'rig', 'Medium Projectile Burst Aerator II'],
        ])
        expect(parsed.cargo).toEqual([
            { name: 'Hammerhead II', quantity: 5 },
            { name: 'Republic Fleet EMP M', quantity: 2000 },
            { name: 'Stasis Webifier II', quantity: 1 },
        ])
        expect(swappable_cargo(parsed).map(item => item.name)).toEqual(['Stasis Webifier II'])
        expect(module_slot(parsed.modules[3], { 'Stasis Webifier II': 'mid' })).toBe('mid')
    })

    it('drops "/offline" like the backend parser (the old parser kept it in the name)', () => {
        expect(legacy_parse_eft(HURRICANE).modules[3].name).toBe('Stasis Webifier II /offline')
        expect(parse_eft(HURRICANE).modules[3].name).toBe('Stasis Webifier II')
        expect(parse_eft('[Rifter, x]\nStasis Webifier II /OFFLINE').modules[0].name).toBe('Stasis Webifier II')
    })

    it('matches the old parser on every guide fit without "/offline"', () => {
        const fits = [...cruiser_fits, ...destroyer_fits, ...frigate_fits].map(fit => fit.eftFormat)
        expect(fits.length).toBeGreaterThan(10)
        for (const eft of fits) {
            if (/\/offline/i.test(eft)) continue
            expect(parse_eft(eft)).toEqual(legacy_parse_eft(eft))
        }
    })

    it('tolerates empty input', () => {
        expect(parse_eft(null)).toEqual({ ship: '', name: '', modules: [], cargo: [] })
    })
})
