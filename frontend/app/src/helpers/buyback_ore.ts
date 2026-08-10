/** Shared compressed-ore base names for buyback variant grouping. */

export const BUYBACK_ORE_BASES = [
    'Veldspar',
    'Scordite',
    'Pyroxeres',
    'Plagioclase',
    'Omber',
    'Kernite',
    'Zeolites',
    'Sylvite',
    'Bitumens',
    'Coesite',
    'Hedbergite',
    'Hemorphite',
    'Jaspet',
    'Gneiss',
    'Crokite',
    'Dark Ochre',
    'Mordunium',
    'Ytirium',
    'Eifyrium',
    'Ducinium',
    'Griemeer',
] as const

const BUYBACK_ORE_BASE_SET = new Set<string>(BUYBACK_ORE_BASES)
const GRADE_SUFFIX_RE = /\s+(II|III|IV)-Grade$/
const MOON_PREFIX_RE = /^(Brimful|Glistening)\s+/

export function compressed_buyback_ore_base(name: string): string | null {
    if (!name.startsWith('Compressed ')) return null
    let rest = name.slice('Compressed '.length)
    rest = rest.replace(GRADE_SUFFIX_RE, '')
    rest = rest.replace(MOON_PREFIX_RE, '')
    return BUYBACK_ORE_BASE_SET.has(rest) ? rest : null
}
