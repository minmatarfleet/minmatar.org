import type { ChronicleEra } from './types'

/**
 * An era is where the alliance lived. Its chapters are what happened while
 * living there. The intro is shown before the era's first chapter.
 */
export const rat_chronicle_eras: ChronicleEra[] = [
    {
        id: 'auga',
        name: 'The Auga Era',
        home: 'Auga X, Brutor Tribe Bureau',
        date_range: 'January YC125 – January YC126',
        yc: 'YC125',
        intro: [{ type: 'paragraph', text: `Minmatar Fleet was founded on the first day of YC125 in a station in Auga, the system where three regions and the front line of the Amarr war met. It lived there for a year, and for most of that year the war came to its door every night.` }],
    },
    {
        id: 'sosala',
        name: 'The Sosala Era',
        home: 'Sosala, the Watermelon',
        date_range: 'January YC126 – May YC127',
        yc: 'YC126–127',
        intro: [{ type: 'paragraph', text: `Sosala had been the heart of Amarr space. When the Amarr militia fell apart and the system was there to be taken, the rats anchored a Fortizar in it, called it the Watermelon, and stayed sixteen months. From its doorstep they fought Providence, and then everyone Providence could call.` }],
    },
    {
        id: 'vard',
        name: 'The Vard Era',
        home: 'Vard',
        date_range: 'May – November YC127',
        yc: 'YC127',
        intro: [{ type: 'paragraph', text: `By the spring of YC127 the war on Providence was going nowhere, and the great nullsec alliances had started turning up to it. The rats chose a home nearer the middle of the warzone. They lived in Vard for six months, most of them at war with the neighbours.` }],
    },
    {
        id: 'amamake',
        name: 'The Amamake Era',
        home: 'Amamake, the Keepstar',
        date_range: 'November YC127 – today',
        yc: 'YC127–128',
        intro: [{ type: 'paragraph', text: `In November of YC127 the alliance went north to nullsec and chose not to defend the Fortizars it left behind. Home became the Keepstar in Amamake, and still is. This era is not over. The chronicle follows it as far as the end of the Dronelands campaign.` }],
    },
]
