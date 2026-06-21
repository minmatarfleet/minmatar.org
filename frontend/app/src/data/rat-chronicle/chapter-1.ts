import type { ChronicleChapter } from './types'

export const chapter1: ChronicleChapter = {
    id: 'chapter-1',
    number: 1,
    title: 'Rat Genesis',
    dateRange: 'January – March',
    yc: 'YC125',
    realYear: '2023',
    epigraph: {
        citation: 'Rat Genesis 1:1',
        text: 'In the beginning, Rat created the holes and the cheese.',
    },
    sections: [
        {
            roman: 'I',
            title: 'The Founding of the Tribe',
            illustration: {
                src: '/images/rat-chronicle/rat-genesis.png',
                alt: 'Illuminated manuscript depicting the founding of Rattini Tribe at the Karishal Muritor Memorial',
                caption: 'Convenio ad **Karishal Muritor** — Chaos and Curiosity across the Stars',
            },
            blocks: [
                {
                    type: 'paragraph',
                    text: 'As the war engines of the **Uprising** stirred across the southern frontier, a small band gathered outside the Brutor Tribe Bureau at **Auga X-III**, just outside of the Karishal Muritor Memorial.',
                },
                {
                    type: 'paragraph',
                    text: 'Their leader was known to all who would later write of him as **BearThatCares** — a commander of eccentric habit and volcanic will, who had watched the factional wars drag and smolder for years and had finally decided he had watched long enough. Around him stood **Mortarian Decala**, soft spoken and methodical, the sort of mind that read a battlefield like a ship fitting window and found satisfaction in making the numbers agree; and **Fariius**, who said almost nothing and yet seemed to be everywhere at once, always a step ahead of the noise, keeping the machinery of the thing running smooth.',
                },
                {
                    type: 'paragraph',
                    text: 'Others stood with them too, names not yet familiar — but soon enough they would be.',
                },
                {
                    type: 'paragraph',
                    text: 'The Rattini approached **Ushra\'Khan**, the great Minmatar brotherhood, and were refused. They spent some time with **Wild Geese**, who welcomed them with open arms. Yet, after almost a month, the Rattini realized that it was just more of the same. Frigates and destroyers — but their creed demanded **chaotic grids, capital ships, and destruction**.',
                },
                {
                    type: 'paragraph',
                    text: 'They returned to Auga X-III. An alliance was stood up. It was named **Minmatar Fleet**, and its purpose was simple: **to fight, to learn from every fight, to improve, and to fight again**.',
                },
            ],
        },
        {
            roman: 'II',
            title: 'The Blood Raiders Problem',
            blocks: [
                {
                    type: 'paragraph',
                    text: 'The first test was not against Amarr. It was against **Blood Raiders**, who had established a Forward Operating Base in **Amo**, the system that housed Minmatar Fleet\'s industrial backbone at the time. These blood raiders were shooting Upwell structures daily.',
                },
                {
                    type: 'paragraph',
                    text: 'The rats brought Cyclone Fleet Issues and Osprey logistics on their first attempt to clear the hive. Halfway through the fight, one of the logistics pilots accidentally triggered their combat drones against a fleetmate. **CONCORD** showed up right away and destroyed the entire logistics wing. The remaining Cyclone Fleet Issues did what anyone would do and got out.',
                },
                {
                    type: 'paragraph',
                    text: 'They regrouped and tried again — this time the Crimson Brotherhood\'s defenders came in such numbers that the fleet\'s weapons could not keep pace.',
                },
                { type: 'beat', text: 'Another retreat.' },
                { type: 'beat', text: 'Not the last one, just the second.' },
                { type: 'beat', text: 'Laughter filled the communication channels.' },
                { type: 'beat', text: 'Why was this so hard?' },
                {
                    type: 'paragraph',
                    text: 'On the third attempt, **BearThatCares** flew to Jita and imported a fleet of Muninns and Guardians. Two pilots injected training directly into the new hulls. The fleet returned to Amo with absurd EM resistance — the correct profile for the Crimson Brotherhood\'s preferred damage type — and took the base apart cleanly.',
                },
                {
                    type: 'paragraph',
                    text: 'Seventy million ISK in recovered spoils. Thirty million per pilot. Five billion spent across two days of failures. Final blow to **Fariius**.',
                },
                {
                    type: 'paragraph',
                    text: 'BearThatCares wrote it up as the alliance\'s first formal battle record, with every detail preserved: the CONCORD intervention, the cap failure, the fix. He posted it where everyone in the alliance could read it. He would go on posting these records — after every fight, win or loss — for the next three years.',
                },
                { type: 'beat', text: 'That habit was baked in from day one.' },
                { type: 'beat', text: '**Try it, screw it up, figure out why, fix it, go again.**' },
                {
                    type: 'paragraph',
                    text: 'That loop would end up defining almost everything that followed.',
                },
            ],
        },
        {
            roman: 'III',
            title: 'The First Test — F*ck Around and Find Out',
            blocks: [
                {
                    type: 'paragraph',
                    text: 'The industrial arm of the alliance — Minmatar Fleet Associates (BUILD) — was wardecced in February by an entity called **The-Expanse**, whose members were toxic across every channel and believed the mere threat of structure destruction would produce ransom.',
                },
                { type: 'beat', text: 'They had, very clearly, misunderstood the situation.' },
                {
                    type: 'paragraph',
                    text: 'The rats sent The-Expanse the terms for their own surrender: two and a half billion ISK within twelve hours, or their Fortizar dies. The-Expanse declined.',
                },
                {
                    type: 'paragraph',
                    text: '**FL33T** formed Drekavacs and set out for Solitude, where the Expanse Tower stood. Half of The-Expanse\'s own allied corporations left the war before FL33T even arrived. The internal rot accelerated the timeline.',
                },
                {
                    type: 'paragraph',
                    text: 'FL33T struck the first armor timer, then the final hull. The Fortizar died, final blow to Fariius, worth fifteen and a half billion ISK. The lesson stuck right away: **touch the industrialists, and the rats appear.**',
                },
            ],
        },
        {
            roman: 'IV',
            title: 'Learning to Fight',
            blocks: [
                {
                    type: 'paragraph',
                    text: 'Through February and into March, **FL33T** ran operations nearly every day in Auga and the surrounding systems — Vard, Ardar, Ezzara, Kamela. They fought whoever would form against them.',
                },
                {
                    type: 'paragraph',
                    text: 'The records from these fights are honest in a way most groups never manage. A new commander named **Xadr Twitch** ran his first fleet in Ardar; his Cyclone died to pirates who rolled in before the fleet had fully put together; he called for a regroup, reshipped the fleet into Thrashers, and took the objective anyway. Their logi pilots ran out of capacitor. Their Blackbird electronic warfare ships ran fits that failed against the Amarr composition they were fighting. They analyzed the failure, wrote new fits, and banned the old ones from doctrine.',
                },
                {
                    type: 'paragraph',
                    text: 'The engagement they called **Blood for the Blood God** — four consecutive rounds in one evening against the Amarr — saw FL33T cycle through four different fleet compositions in a single night, losing twice, winning twice, and ending the session with a simple note in the record:',
                },
                {
                    type: 'quote',
                    text: 'We are outnumbered to hell. 22 Cyclone Fleet Issues versus 32 Prophecy Navy Issues. Just need to keep growing.',
                    character_id: 634915984,
                    character_name: 'BearThatCares',
                },
                {
                    type: 'paragraph',
                    text: 'February was not about stacking wins. It was about learning faster than most groups do in a year, and paying for those lessons in hulls. Each engagement produced a critique. Each critique produced a change. The changes accumulated.',
                },
                {
                    type: 'paragraph',
                    text: 'By the end of March, somehow and also very much on purpose, FL33T had flown its first operation with **over two hundred pilots** on the field, ran a **titan bridge**, and run structure campaigns planned days in advance with deliberate timer choices. In ninety days from dying to NPCs in Amo, they had built from nothing a fighting force the warzone had begun to plan around.',
                },
            ],
        },
    ],
    charactersOfTheAge: {
        groups: [
            {
                label: 'Founders',
                characters: [
                    {
                        character_id: 634915984,
                        character_name: 'BearThatCares',
                        description: 'Volcanic will — eccentric commander and founder who watched the faction wars smolder for years, refused to wait any longer, and closed **KG** to start a new chapter.',
                    },
                    {
                        character_id: 91434341,
                        character_name: 'Mortarian Decala',
                        description: 'Methodical patience — soft-spoken executor of Wormhole Society who read a battlefield like a fitting window, found satisfaction in making the numbers agree, and closed **WHSOC** to join the fight.',
                    },
                    {
                        character_id: 299286127,
                        character_name: 'Fariius',
                        description: 'Operational silence — the one who says almost nothing, yet is everywhere at once, at all times; the key figure in the background who kept **KG** afloat and the machinery running smooth.',
                    },
                ],
            },
            {
                label: 'Founding members',
                characters: [
                    {
                        character_id: 346498653,
                        character_name: 'CSmoke',
                        description: 'Old guard — long versed in wormhole space, fond of a drink and a laugh, and eventually retired from New Eden when the founding era passed.',
                    },
                    {
                        character_id: 1108975025,
                        character_name: 'Nou Mene',
                        description: 'Small-gang specialist — a quiet **KG** veteran from wormhole country, exacting on the wire and happiest when the grid was small enough to know every name.',
                    },
                    {
                        character_id: 1857216100,
                        character_name: 'Aliventi',
                        description: 'Sharp tongue — imported from **Mouth Trumpet Calvary** with a wormhole pedigree, quick-witted, irreverent, and never the last to say what everyone else was thinking.',
                    },
                    {
                        character_id: 96245093,
                        character_name: 'Hoss Fever',
                        description: 'Avid wormhole pilot — a Wormhole Society hand who followed the founding fights long enough to matter, then departed to reboot **Violence is the Answer** elsewhere.',
                    },
                    {
                        character_id: 92541450,
                        character_name: 'Drake Eldritch',
                        description: 'Tenured wanderer — wormhole pilot through Wormhole Society and No Vacancies who helped carry the early tribe, then departed for sovereignty with **The Initiative**.',
                    },
                ],
            },
        ],
    },
}
