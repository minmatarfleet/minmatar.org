import type { ChronicleChapter } from './types'

export const chapter3: ChronicleChapter = {
    id: 'chapter-3',
    number: 3,
    title: 'The Hek Affair',
    dateRange: 'October – December',
    yc: 'YC125',
    realYear: '2023',
    epigraph: {
        citation: 'Rat Luke 8:17',
        text: 'For there is nothing hidden that will not be disclosed, and no cheese concealed that will not be known or brought out into the open.',
    },
    sections: [
        {
            roman: 'I',
            title: 'The Problem with Hek',
            blocks: [
                {
                    type: 'paragraph',
                    text: 'While the guns fell quieter in **Auga**, a different war was being assembled in a highsec trade hub eight jumps to the north.',
                },
                {
                    type: 'paragraph',
                    text: 'In **Hek**, the **Hek Mining Association** ran renting schemes that extracted ISK from smaller highsec corporations under threat of wardec.',
                },
                {
                    type: 'paragraph',
                    text: '**FL33T** placed spies inside. What they brought back was a business with two faces. **Nebula Industries** offered mining incentives and infrastructure, while the Hek Mining Association ganked any pilot who was not affiliated.',
                },
                { type: 'beat', text: 'They were run by the same players, under different names.' },
                {
                    type: 'paragraph',
                    text: 'The racket sat on top of Minmatar Fleet\'s own industrial base, and the alliance had written the rule for that in February: **touch the industrialists, and the rats appear.**',
                },
            ],
        },
        {
            roman: 'II',
            title: 'The Front Page',
            blocks: [
                {
                    type: 'paragraph',
                    text: '**Metropolis Daily News**, the alliance\'s propaganda arm, ran the story on the tenth of November, across two pages:',
                },
                {
                    type: 'quote',
                    text: 'Hek Mining Asociation: A dark story about crime and renting in Minmatar hisec.',
                    attribution: 'Metropolis Daily News',
                },
                {
                    type: 'paragraph',
                    text: 'The same day, FL33T declared war on the Hek Mining Association.',
                },
                { type: 'beat', text: 'It went live twenty-four hours later.' },
                {
                    type: 'paragraph',
                    text: 'On the fourteenth, **BearThatCares** published "The end to corruption in Minmatar high security space." He had appointed **Jerran Osbourne** as FL33T\'s diplomat to Nebula Industries.',
                },
                {
                    type: 'paragraph',
                    text: 'FL33T was negotiating with one face of the racket while at war with the other.',
                },
            ],
        },
        {
            roman: 'III',
            title: 'Four Killmails',
            blocks: [
                {
                    type: 'paragraph',
                    text: 'For six days, nothing died. On the seventeenth, FL33T brought Tempest Fleet Issues, Typhoon Fleet Issues and Guardians to Hek. The first thing to die was an Apocalypse belonging to **Amity Lane**, the association\'s vice president, final blow to **HeavyForces**.',
                },
                { type: 'beat', text: 'Every name on that killmail, hers included, was enlisted in the Minmatar militia.' },
                { type: 'beat', text: 'Then the Athanor.' },
                { type: 'beat', text: 'Then Amity Lane\'s pod, parked beside the wreck of her Apocalypse.' },
                { type: 'beat', text: 'That evening, the Raitaru.' },
                {
                    type: 'paragraph',
                    text: 'FL33T retracted the war one minute after the Raitaru died. It had killed two structures, a battleship and a capsule, worth over four billion ISK on the killboard. The Hek Mining Association had killed none.',
                },
            ],
        },
        {
            roman: 'IV',
            title: 'Capital Ships Down',
            blocks: [
                {
                    type: 'paragraph',
                    text: 'In **Floseswin**, five jumps from Hek, pirates had dug into the insurgency sites. They were **Deepwater Hooligans**, out of **Turnur**, two jumps down the road.',
                },
                {
                    type: 'paragraph',
                    text: 'On the eighteenth, BearThatCares decided to push very hard, in Cyclone Fleet Issues with dreadnoughts behind them. The battle record went up afterward under a plain title: "Capital Ships Down in Floseswin."',
                },
                {
                    type: 'paragraph',
                    text: 'Deepwater\'s Phoenix Navy Issue died with a hundred and fifty-nine names on its killmail, more of them enlisted with the Angel Cartel than with the Minmatar militia. **Raptor Lake**\'s Revelation did the heavy lifting on it, and again on their Minokawa.',
                },
                { type: 'beat', text: 'Then a Deepwater Zirnitra killed one of FL33T\'s Naglfars.' },
                { type: 'beat', text: 'Its pilot was called **Best Nestor Pilot**.' },
                {
                    type: 'paragraph',
                    text: 'Raptor Lake took the final blow on the Zirnitra\'s mobile depot. The Zirnitra went on to kill the Revelation, almost by itself, and then a second Naglfar.',
                },
                {
                    type: 'paragraph',
                    text: 'The only thing Best Nestor Pilot lost that night was the mobile depot, worth about two million ISK.',
                },
            ],
        },
        {
            roman: 'V',
            title: 'Kek',
            blocks: [
                {
                    type: 'paragraph',
                    text: 'On the twenty-ninth of November, Metropolis Daily News ran an Extra:',
                },
                {
                    type: 'quote',
                    text: 'Hek renamed to Kek following petition by Metropolis resident! Extra!',
                    attribution: 'Metropolis Daily News',
                },
                {
                    type: 'paragraph',
                    text: 'On the ninth of December it followed up: "FL33T issues stern warning to metropolis extortionists! Extra!" FL33T never had to declare war on them again.',
                },
                {
                    type: 'paragraph',
                    text: 'The association\'s corporation description still carries its motto: "If you want to mine, you can go to Hek." It has two members.',
                },
            ],
        },
    ],
}
