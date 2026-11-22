import type { ChronicleChapterSource } from './types'

export const theSiegeOfAldodan: ChronicleChapterSource = {
    id: 'the-siege-of-aldodan',
    era: 'sosala',
    title: 'The Siege of Aldodan',
    dateRange: 'April – May',
    yc: 'YC127',
    realYear: '2025',
    epigraph: {
        citation: 'Rat Psalms 121:1-2',
        text: 'I lift up my eyes to the holes— where does my help come from? My help comes from the Rat, the Maker of heaven and earth.',
    },
    sections: [
        {
            roman: 'I',
            title: 'What the Fuck Is This Doctrine',
            blocks: [
                {
                    type: 'paragraph',
                    text: `In April of YC127 the rats still lived in the **Watermelon**, in **Sosala**. Providence had stopped paying, and most of the warzone around them had been lost while they were looking the other way. The neighbours they fought most were **Sedition**, and that war was conducted for pleasure: the two alliances, **BearThatCares** explained, "just enjoy fighting eachother", mostly over worthless structures, and "try and one-up each other doing *weird things*."`,
                },
                {
                    type: 'paragraph',
                    text: `Bear came back that month from two weeks away and formed a fleet of Abaddons, a battleship nobody flies, because it runs out of power every two minutes. He brought a freighter full of batteries to keep them firing. His own account records the fleet's opinion.`,
                },
                {
                    type: 'quote',
                    text: `Bear, you're gone for two weeks, come back, and pull this shit?`,
                    attribution: 'the fleet, as its commander recorded it, 10 April',
                    source: {
                        title: 'AAR: 150B DOWN IN HUOLA',
                        href: 'https://www.reddit.com/r/Eve/comments/1jwrqgr/aar_150b_down_in_huola/',
                        kind: 'Battle report',
                    },
                },
                {
                    type: 'paragraph',
                    text: `They shot a Sedition moon drill for half an hour. Then Sedition undocked to defend it, and Bear thought he was looking at the wrong character. "I had to to do a double take, because they undocked in fucking *abaddons*. Who the hell has abaddons in their hangar?" The rats won. Bear's verdict on his invention was that it was terrible and should be thrown away.`,
                },
            ],
        },
        {
            roman: 'II',
            title: 'The Map Was Gone',
            blocks: [
                {
                    type: 'paragraph',
                    text: `The cause was the **Fraternity**, one of the largest alliances in nullsec. Its pilots had enlisted in the militia war to farm it. They enlisted half a fleet on each side at once, so that nobody could shoot them cleanly. "They farmed with an iron fist," Bear wrote, "often AWOX'ing members of their own militia."`,
                },
                {
                    type: 'paragraph',
                    text: `The rats had been busy elsewhere, with what Bear called "a *lot* of cookie jars", and had not been watching.`,
                },
                {
                    type: 'quote',
                    text: `In what felt like the blink of an eye, the map was *gone*. Amarr controlled nearly 50 systems, and pretty much everything except for Auga and Sosala (our Fortizar systems) was falling.`,
                    character_id: 634915984,
                    character_name: 'BearThatCares',
                    attribution: 'The Siege of Aldodan',
                    source: {
                        title: 'The Siege of Aldodan',
                        href: 'https://www.reddit.com/r/Eve/comments/1k74892/the_siege_of_aldodan/',
                        kind: 'Announcement',
                    },
                },
                {
                    type: 'paragraph',
                    text: `With the map went the small fights that a lowsec alliance lives on. Then one day the rats chased a Sedition fleet into a backwater constellation called **Aldodan** and found it full of Fraternity structures. The farmers had moved up there, away from everyone, to work in peace. Bear gave the moment two words: "*It clicked.*"`,
                },
            ],
        },
        {
            roman: 'III',
            title: 'It Builds Character',
            blocks: [
                {
                    type: 'paragraph',
                    text: `The plan was to take the systems around Aldodan, lock the farmers in, and choke them. It began as an errand for Bear's own corporation, which he moved into a station next door that had no medical bay and no repair shop, and which belonged to somebody who could throw them out. "*It builds character*," he wrote.`,
                },
                {
                    type: 'paragraph',
                    text: `Then it caught. The alliance put money behind it. The militia joined. Rats sat in a standing fleet around the clock, twenty of them at hours when the alliance was usually asleep, and took the systems one at a time. Whenever the Fraternity came out it was met by small fast gangs it could not catch, and fed them cheap ships in waves until its pilots logged off. One afternoon the bait was a lone dreadnought, and what came to kill it was no farmer. "It was Faymm," Bear wrote, of a dreadnought brawler who turns up in this history again. The rats beat him as well.`,
                },
                {
                    type: 'paragraph',
                    text: `Then the alliance's propaganda machine started up. Bear credited it with turning "what should've been a two week siege into a two day siege." On the twenty-fourth of April he declared Aldodan liberated. He admitted he did not know exactly why the farmers had gone: there had been "some internal drama" among them. He thanked them for the content, counted twelve hundred hours his members had spent in the standing fleet, and judged it "time well spent."`,
                },
            ],
        },
        {
            roman: 'IV',
            title: 'Bigger Than Our Britches',
            blocks: [
                {
                    type: 'paragraph',
                    text: `The same announcement carried a paragraph in italics, as an aside. The war on Providence, which the rats had been fighting for sixteen months, was over. The moon drills were sold or taken down. "We had gotten a little bit bigger than our britches, and we needed to streamline and refocus."`,
                },
                {
                    type: 'paragraph',
                    text: `That night they anchored a new Fortizar in **Vard**, a system nearer the middle of the warzone. Two and a half hours later Sedition anchored one of its own in Sisiede. A truce over the pair was offered. The rats declined on principle. "No deals, no batphones, no fucks," wrote Bear, "let's see what Minmatar Fleet can form and throw down."`,
                },
                {
                    type: 'paragraph',
                    text: `Nobody came to Vard. Everybody came to Sedition's. The rats brought fifty battleships fitted with the wrong guns, were shot by Sedition and by a passing Goonswarm fleet at once, and retired to a station to think. When they came back the field was full of fleets circling each other, so Bear dropped his dreadnoughts in the middle of it "to start the party". Everyone present escalated on top of everyone else. Four hundred billion ISK was destroyed, and Bear, who had commanded with the flu, lost his voice ten minutes after it ended. He listed three lessons. The third was "A lot of people like shooting FL33T".`,
                },
                {
                    type: 'paragraph',
                    text: `In the second week of May the alliance moved house. The Amarr took Sosala behind them. The Watermelon stayed where it was, in a system that now belonged to the enemy.`,
                },
            ],
        },
        {
            roman: 'V',
            title: 'Tau Has Plans',
            blocks: [
                {
                    type: 'paragraph',
                    text: `There was meant to be a victory parade: freighters escorted from the front to Vard, carrying, the announcement promised, "the spoils of war and thousands of freed slaves." On the day, Bear looked at who was forming to meet it and cancelled, because "it would not get us the content we wanted". The fleet went and found a different fight instead.`,
                },
                {
                    type: 'paragraph',
                    text: `The next day **Twan Molenaar** took the rats to contest a station in Lamaa. "Twan doesn't need any intel," Bear wrote of his European commander. A fifty-ship fleet nobody had scouted landed on him, and he called for capitals. Then **Snuffed Out** arrived, ninety strong, and killed every dreadnought on the field, including those of the side that had invited them. Bear wrote the night up as a set of intercepted conversations and labelled the result propaganda. The last is between Twan and one of his pilots.`,
                },
                {
                    type: 'quote',
                    text: `Tau has plans. Nuke has plans. Hy wanto has plans. You know, they're schemers. We don't have a plan.`,
                    character_id: 2114993571,
                    character_name: 'Twan Molenaar',
                    attribution: 'asked whether there had been a plan, as Bear told it',
                },
                {
                    type: 'paragraph',
                    text: `The pilot pointed out that they had lost their dreadnoughts. "Next time we'll have more."`,
                },
                {
                    type: 'paragraph',
                    text: `There was a next time every week. By the start of June the rats in their new home were being jumped by five alliances whenever they committed anything large, and Bear told them that brawling was over unless it was on their terms. The reason he gave was "we're the hot commodity".`,
                },
            ],
        },
    ],
    charactersOfTheAge: {
        groups: [
            {
                label: 'The last spring in Sosala',
                characters: [
                    {
                        character_id: 2114993571,
                        character_name: 'Twan Molenaar',
                        description: `No plan — the European commander who called for capitals first and intelligence afterwards, and promised more dreadnoughts next time.`,
                    },
                    {
                        character_id: 684108979,
                        character_name: 'Zigg Omelo',
                        description: `The armorer — built the Abaddon fleet nobody asked for, and most of the doctrines people did.`,
                    },
                    {
                        character_id: 2120834555,
                        character_name: 'Faye Vaelent',
                        description: `The propaganda machine — drew the campaign that Bear said turned a two-week siege into two days.`,
                    },
                ],
            },
        ],
    },
}
