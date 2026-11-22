import type { ChronicleEra } from './types'

/**
 * An era is where the alliance lived. Its chapters are what happened while
 * living there. The intro is shown before the era's first chapter.
 */
export const ratChronicleEras: ChronicleEra[] = [
    {
        id: 'auga',
        name: 'The Auga Era',
        home: 'Auga X, Brutor Tribe Bureau',
        dateRange: 'January YC125 – January YC126',
        yc: 'YC125',
        intro: [],
    },
    {
        id: 'sosala',
        name: 'The Sosala Era',
        home: 'Sosala, the Watermelon',
        dateRange: 'January YC126 – May YC127',
        yc: 'YC126–127',
        intro: [],
    },
    {
        id: 'vard',
        name: 'The Vard Era',
        home: 'Vard',
        dateRange: 'May – November YC127',
        yc: 'YC127',
        intro: [],
    },
    {
        id: 'amamake',
        name: 'The Amamake Era',
        home: 'Amamake, the Keepstar',
        dateRange: 'November YC127 – today',
        yc: 'YC127–128',
        intro: [],
    },
]
