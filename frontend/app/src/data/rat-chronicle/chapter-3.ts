import type { ChronicleChapter } from './types'

export const chapter3: ChronicleChapter = {
    id: 'chapter-3',
    number: 3,
    title: 'The Hek Affair',
    dateRange: 'August – November',
    yc: 'YC125',
    realYear: '2023',
    epigraph: {
        citation: 'Non omnes qui errant perditi sunt — nisi in Hek.',
        text: 'Not all who wander are lost — except in Hek.',
    },
    sections: [
        {
            roman: 'I',
            title: 'The Problem with Hek',
            blocks: [
                {
                    type: 'paragraph',
                    text: 'While the guns fell quieter in **Auga**, a different war was being assembled in a highsec trade hub eleven jumps to the north.',
                },
                {
                    type: 'paragraph',
                    text: '**Hek** sits in the **Metropolis** region like a waystation with ambitions — never quite the market that **Jita** is, never quite the frontier that the warzone is, but indispensable to both. The Minmatar stations there bulk-process ore from a hundred mining corporations, and the market feeds ships and materials back through the faction warfare supply chain. If you were moving minerals in Metropolis, you knew Hek. If you were running a corporation in Minmatar space, you eventually had business there.',
                },
                {
                    type: 'paragraph',
                    text: 'The **Hek Mining Association** had, apparently, understood this better than most. Their method was methodical: renting schemes that extracted ISK from smaller highsec corporations under threat of wardec, the kind of protection racket that persists because most small corporations in highsec don\'t have the organizational capacity or the willingness to escalate the fight. The Hek Mining Association understood this, and exploited it. They had been running the scheme for long enough that it had become institutional.',
                },
                {
                    type: 'paragraph',
                    text: 'What they had not understood was that **FL33T** had been watching.',
                },
                {
                    type: 'paragraph',
                    text: 'FL33T was not a passive observer of Minmatar space. Their presence had made them a visible public voice for what Minmatar space was supposed to be: a fighting zone, a community, a place where people came to fight. The highsec corruption in Hek was not just a financial threat to the alliance\'s industrial base. It was a violation of the thing they had been publicly arguing for.',
                },
                {
                    type: 'paragraph',
                    text: 'The Hek Affair began in the quiet way that FL33T\'s operations always began: placing spies, and gathering intelligence. What they found appalled them. A group named **Nebula Industries** had been offering mining incentives and infrastructure, while the Hek Mining Association "ganked" any pilots that were not affiliated. The problem? They were run by the same players, under different names.',
                },
            ],
        },
        {
            roman: 'II',
            title: 'The Campaign Begins',
            blocks: [
                {
                    type: 'paragraph',
                    text: '**BearThatCares** published "The end to corruption in Minmatar high security space" on the fourteenth of November. The post reached tens of thousands of readers. The most-read piece that he had published.',
                },
                {
                    type: 'paragraph',
                    text: 'He appointed **Jerran Osbourne** as FL33T\'s formal diplomat to Nebula Industries, a front for The Hek Mining Association. The Hek Mining Association\'s extortion network — the names, the operations, the amounts, the structures — was documented in full. Then it was published for the warzone to read.',
                },
            ],
        },
        {
            roman: 'III',
            title: 'Two Fronts, One Alliance',
            blocks: [
                {
                    type: 'paragraph',
                    text: 'The eighteenth of November saw FL33T fighting in two theaters on the same day.',
                },
                {
                    type: 'paragraph',
                    text: 'In **Floseswin**, pirates had dug into insurgency sites with the confidence of an organization that expected no organized response. BearThatCares decided to push very hard. The operation that became the Reddit post "Capital Ships Down in Floseswin" — eleven and a half billion ISK destroyed, one hundred and ninety-four pilots. What the insurgency mechanics had created in Floseswin was a gravity well. Every group that came to farm the corruption sites attracted more groups, and every group that came to fight those groups attracted more again. FL33T had become the organizing force at the center of that gravity.',
                },
                {
                    type: 'paragraph',
                    text: 'While the Floseswin operations ran, BearThatCares posted the Hek corruption expose, and led fleets to destroy Nebula Industries infrastructure. Two different wars, the same alliance, the same day. The propaganda arm of **Metropolis Daily News** ran the story with appropriate headline energy. The Hek Mining Association\'s extortion scheme continued to be blasted everywhere.',
                },
                {
                    type: 'paragraph',
                    text: 'The day after, the servers themselves offered a comment on FL33T\'s operational tempo. Intelligence came through about an Eagle fleet forming on the undock in Auga. BearThatCares pinged for Caldari Faction Interceptors. The ping went out right as **EVE Online** hit forty thousand players concurrent — the servers began to choke. When they came back up, FL33T reformed, undocked, and killed some of the Eagles as they returned.',
                },
            ],
        },
        {
            roman: 'IV',
            title: 'The Meaning of Hek',
            blocks: [
                {
                    type: 'paragraph',
                    text: 'The Hek Affair mattered less for the ISK involved than for what it demonstrated about the alliance\'s reach.',
                },
                {
                    type: 'paragraph',
                    text: 'Highsec politics rarely move numbers that register against the scales FL33T was operating at by November of YC125. What the Hek Affair showed was that FL33T was not simply a faction warfare organization. It fought for Minmatar space broadly — the warzone, the trade hubs, the industrial heartland, the political narrative of what Minmatar space was supposed to be.',
                },
                {
                    type: 'paragraph',
                    text: 'The propaganda that followed was appropriately absurd. Metropolis Daily News ran a satirical Extra bulletin declaring that Hek had been renamed to **Kek** in honor of the cleansing — the kind of joke that works because it is also, in the register of faction warfare culture, a genuine trophy. The Hek Mining Association\'s schemes were documented, their structures were gone, and their story had been published on the capsuleer networks for every alliance in the warzone to read.',
                },
                {
                    type: 'paragraph',
                    text: 'From August through November of YC125, while the Siege of Auga ground the Amarr coalition toward its breaking point in the south, the Hek Affair was fought and won in the north. The alliance that could hold both fronts simultaneously was not the same organization that had been flying Ospreys and Cyclone Fleet Issues in Auga seven months earlier.',
                },
                { type: 'beat', text: 'The warzone was about to find out exactly how much it had changed.' },
            ],
        },
    ],
    charactersOfTheAge: {
        groups: [
            {
                label: 'Northern campaign',
                characters: [
                    {
                        character_id: 634915984,
                        character_name: 'BearThatCares',
                        description: 'Public prosecutor — published the corruption expose that reached tens of thousands of readers, then led fleets against Nebula Industries infrastructure on the same day FL33T tore through Floseswin.',
                    },
                ],
            },
        ],
    },
}
