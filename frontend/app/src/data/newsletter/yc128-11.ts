import type { NewsletterIssue } from './types'

export const SLUG = 'yc128-11'
export const PERMALINK_PATH = `/newsletter/${SLUG}/`
export const COVER_IMAGE = '/images/home-vard-cover-eve.jpg'

const IMG = `/images/newsletter/${SLUG}`
const HELP_URL = 'https://discord.com/channels/1041384161505722368/1183401618943791186'
const QUESTIONS_URL = 'https://discord.com/channels/1041384161505722368/1561471935462903839'
// TODO(town hall #38): swap in the highlights video URL and its thumbnail once the cut is published.
const TOWN_HALL_URL = 'https://www.youtube.com/@MinmatarFleet'

export const YC128_11: NewsletterIssue = {
    slug: SLUG,
    permalink_path: PERMALINK_PATH,
    published_at: new Date('2026-11-06T00:00:00Z'),
    cover_image: COVER_IMAGE,
    share_image: `/images/newsletter/${SLUG}/share.jpg`,
    eyebrow: "What's new on my.minmatar.org",
    period_label: 'November YC 128',
    dek: 'A Training tab that tells you what you can fly and what to train next, a Trial tab for new pilots, fleet invites in your Discord DMs, and quiet mode fleets nobody sees coming.',
    lead_video: {
        kicker: 'Watch first',
        title: 'Town Hall #38 highlights',
        text: 'The highlights cut of the November town hall goes here once it is published.',
        placeholder: true,
        url: TOWN_HALL_URL,
        thumbnail: `${IMG}/townhall38.webp`,
        thumbnail_alt: 'Town Hall #38, November YC 128, Highlights, coming soon',
        play_position: 'top-right',
        cta: { links: [{ label: 'Watch on YouTube', href: TOWN_HALL_URL }] },
    },
    sections: [
        {
            kind: 'feature',
            id: 'training',
            layout: 'wide',
            toc_label: 'Training',
            kicker: 'Your account',
            title: 'What can I fly? What should I train?',
            lede: 'The new Training tab checks every character against every doctrine fit, and tells you how long until the next one is ready.',
            figures: [
                {
                    src: `${IMG}/training-plan.webp`,
                    width: 1160,
                    height: 1220,
                    alt: "The Training tab: a doctrine table showing how many characters can bring each role at once, then a character's training plan for an Armor Buffer Nidhoggur with the skills in order and the time to Ready.",
                    caption: 'Pick the ship a character is training for and get the skills in the order EVE accepts them.',
                },
            ],
            list: [
                { title: 'What you can bring.', text: 'Every doctrine and role in one table. Multibox? It counts how many of your accounts can fly it at the same time.' },
                { title: 'One ship per character.', text: 'Each character trains for one doctrine ship at a time. The rest wait their turn, and you can swap any time.' },
                { title: 'A plan for EVE.', text: 'Train to Ready to fly it in fleets, or carry on to Optimal. Copy the skills into your EVE queue, and see which of your characters gets there first.' },
            ],
            cta: {
                links: [{ label: 'Open your Training tab', href: '/account/#training' }],
            },
        },
        {
            kind: 'feature',
            id: 'trial',
            layout: 'split-reverse',
            toc_label: 'Trial',
            kicker: 'New pilots',
            title: 'Your trial, at a glance',
            lede: 'New to the alliance? The Trial tab shows where you are in your trial, how your corp’s trials usually go, and what gets you to full member.',
            figures: [
                {
                    src: `${IMG}/trial.webp`,
                    width: 1170,
                    height: 720,
                    alt: "The Trial tab: day 41 of the trial on a bar from day 1 to day 90, with the review at day 60 and the corp's average at day 72, then fleets, kills and voice each on a five-step scale.",
                    caption: 'How you compare to the rest of the alliance, without a leaderboard.',
                },
            ],
            list: [
                { title: 'Day of your trial.', text: 'When review opens, and when most trials in your corp finish.' },
                { title: 'How you compare.', text: 'Fleets, kills and time on comms over the last month, from well below to well above average.' },
                { title: 'What you bring.', text: 'Every fleet you flew, and whether your ship was on the doctrine.' },
                { title: 'For CEOs.', text: 'Promote a trial pilot straight from your corp’s Members tab. Applications also close by themselves once the pilot joins your corp in game.' },
            ],
            cta: { links: [{ label: 'See your Trial tab', href: '/account/#trial' }] },
        },
        {
            kind: 'feature',
            id: 'invites',
            layout: 'split',
            toc_label: 'Invites',
            kicker: 'Fleets',
            title: 'An FC might invite you to a fleet',
            lede: 'FCs can now invite pilots to an upcoming fleet by Discord DM. Answer with one button, and pick your ships on the site.',
            figures: [
                {
                    src: `${IMG}/invites.webp`,
                    width: 640,
                    height: 714,
                    alt: "The Invite pilots dialog: the timezones set by the fleet time, a choice of new pilots, names or a pasted list, a note, and a preview of the Discord invite with I'm in, Sitting out and Stop fleet invites buttons.",
                    caption: 'What the FC sees, and the DM you get.',
                },
            ],
            list: [
                { title: 'One a week, at most.', text: 'However many fleets are going, you get one invite a week.' },
                { title: 'Only when you’re on.', text: 'Invites follow the fleet time, so you only hear about fleets in your timezone.' },
                { title: 'Not interested?', text: 'Stop fleet invites is on every DM. Turn them back on under Account › Notifications.' },
                { title: 'New pilots.', text: 'FCs can invite pilots who are in their first week, so your first fleet can come to you.' },
            ],
            cta: { links: [{ label: 'See upcoming fleets', href: '/fleets/upcoming/' }] },
        },
        {
            kind: 'feature',
            id: 'quiet',
            layout: 'story',
            toc_label: 'Quiet mode',
            kicker: 'Quiet mode',
            title: 'The fleet nobody saw coming',
            lede: 'Strategic FCs can now run invite-only fleets. They never go on the schedule or in pings: the FC invites pilots by Discord DM, and everyone who says yes gets a private thread.',
            panel: {
                title: 'Quiet mode fleet · Saturday 24 October',
                paragraphs: [
                    'Word was that something big might kick off near Amamake, so BearThatCares kept the fleet off the schedule. Seven waves of DMs went out, 38 pilots said they were in, and the fleet asked for <b>40 dreads, 30 TFIs and 20 logi</b>.',
                    'We waited at the login screen, then took the fight in Dudreda against Cryonic Origin and Ahbazon-Prime, outnumbered 1.5 to 1. The ISK went their way, 13.6B to 16.4B, but nobody saw us coming. Once it was over the fleet was declassified, so its reports are public now.',
                ],
            },
            figures: [
                {
                    src: `${IMG}/quiet-fleet.webp`,
                    width: 1170,
                    height: 411,
                    alt: 'The declassified quiet mode fleet: Saturday 24 October, 1 hour 10 minutes, staged in Amamake on TFIs, FC BearThatCares. Outcome: 13.6B destroyed, 16.4B lost, 45% efficiency, 120 against 180.',
                    caption: 'Declassified after the fight, like any other fleet.',
                    wide: true,
                },
            ],
            list: [
                { title: 'Invites in waves.', text: 'Pick pilots, groups or corps, or paste a list. Each wave is paced so Discord doesn’t throttle it.' },
                { title: 'Ship targets.', text: 'The FC asks for 40 dreads or 20 logi, and pilots see what is still needed when they pick a ship.' },
                { title: 'A private thread.', text: 'Everyone who is in gets a thread for updates, and the start ping goes there.' },
                { title: 'Declassify after.', text: 'When it’s over, one button puts the fleet in history with its reports. Who was invited stays private.' },
            ],
            cta: {
                links: [
                    { label: 'Read the after-action report', href: '/fleets/history/2421/#fights' },
                ],
            },
        },
        {
            kind: 'hits',
            id: 'reports',
            toc_label: 'Reports',
            kicker: 'After the fight',
            title: 'Battle reports for the whole fleet',
            figures: [
                {
                    src: `${IMG}/battle-report-apiculture.webp`,
                    width: 1176,
                    height: 531,
                    alt: "Apiculture's battle report: 1,267 killmails, 4,245 pilots and 2.11T destroyed over two hours. Dragging across 18:49 to 19:19 narrows it to 421 killmails and 624.3B.",
                    caption: 'A 4,245-pilot fight in Amamake, narrowed to its busiest half hour.',
                    wide: true,
                },
            ],
            items: [
                { title: 'The whole night', text: 'A fleet’s battle report now opens on every kill and loss from form-up to dock.' },
                { title: 'Drag to zoom in', text: 'Drag or click on the strip for a fight, a minute or a roam leg, and share the link.' },
                { title: 'Saved by the FC', text: 'FCs can name the fights that mattered, so they’re one click away for everyone.' },
                { title: 'The report in your mail', text: 'FCs get an EVE mail after each fleet with the numbers and links to the kill and battle reports.' },
            ],
            cta: { links: [{ label: 'Find a fleet', href: '/fleets/history/' }] },
        },
        {
            kind: 'hits',
            id: 'fcs',
            toc_label: 'For FCs',
            kicker: 'For FCs',
            title: 'More tools for fleet commanders',
            figures: [
                {
                    src: `${IMG}/participants.webp`,
                    width: 1170,
                    height: 660,
                    alt: 'The Participants tab: peak in fleet, pilots, pilots on a killmail and engagements, a chart of fleet size over time, and each pilot with their ship, kills and losses on a timeline.',
                    caption: 'Who came, when, and in what.',
                },
                {
                    src: `${IMG}/copy-fleet.webp`,
                    width: 512,
                    height: 398,
                    alt: 'The Copy this fleet dialog with only a new date and EVE time to fill in.',
                    caption: 'Copy a fleet to next week.',
                },
            ],
            items: [
                { title: 'Participants', text: 'Every pilot in the order they joined, with their ships, and who was on grid for each fight.' },
                { title: 'Copy this fleet', text: 'Same doctrine, briefing and staging on a new date. Pick the day and you’re done.' },
                { title: 'Fleet on an alt', text: 'Boss on another character? Tracking finds it, and the site still shows you as the FC.' },
                { title: 'Bring what you have', text: 'Pilots can sign up in a hull that isn’t on the doctrine, so the FC knows what’s coming.' },
                { title: 'Hidden rosters', text: 'New fleets hide pilot names from other pilots. The FC still sees everyone who signed up.' },
                { title: 'Academy fits', text: 'Secondary fits are now called Academy, and only Academy pilots can bring them.' },
            ],
            cta: { links: [{ label: 'Schedule a fleet', href: '/fleets/upcoming/' }] },
        },
        {
            kind: 'hits',
            id: 'tribes',
            toc_label: 'Corps',
            kicker: 'Corporations & tribes',
            title: 'Easier to join',
            items: [
                { title: 'Tribe invitations', text: 'Chiefs can invite you to their group. You get a DM, and you join in one step, no application.' },
                { title: 'Corp Discord', text: 'CEOs and directors can put their Discord server on the corp page, so you can say hi before you apply.' },
                { title: 'Apply from the top', text: 'Submit Application sits in the corp page header now, on every tab.' },
                { title: 'No forgotten applications', text: 'Joined the corp in game? Your application closes itself within half an hour.' },
            ],
            cta: {
                links: [
                    { label: 'Browse corporations', href: '/alliance/corporations/' },
                    { label: 'Find your tribe', href: '/alliance/tribes/', secondary: true },
                ],
            },
        },
        {
            kind: 'hits',
            id: 'also',
            toc_label: 'More',
            kicker: 'Also new',
            title: "Smaller things you'll notice",
            items: [
                { title: 'Timezone roles', text: 'Discord now gives you USTZ, EUTZ or AUTZ roles from when you actually play, so pings reach people who are on.' },
                { title: 'Industry pricing', text: 'Order lines are priced from Jita buy, split or sell, or a margin over build cost, and never below what it costs to build.' },
                { title: 'Build planner', text: 'Set the runs per job for your blueprint copies, and the bill matches what you will actually install.' },
                { title: 'Desktop app 0.12', text: 'The Recent tab lists your last fleets by day, with kills, losses and your SRP state. It updates itself.' },
                { title: 'Every tab in reach', text: 'Tabs wrap onto a second row instead of hiding off the side of the page.' },
                { title: 'Buyback sales close', text: 'Finished sales no longer sit open with their Discord thread.' },
            ],
            cta: { links: [{ label: 'Open your account', href: '/account/' }] },
        },
        {
            kind: 'feature',
            id: 'help',
            toc_label: 'Help',
            kicker: 'Tell us',
            title: 'Found a bug? Want something built?',
            lede: 'Open a ticket in #help on the alliance Discord. Several fixes this month started as your tickets. New to the game? Ask anything in #questions.',
            cta: {
                links: [
                    { label: 'Open #help', href: HELP_URL },
                    { label: 'Ask in #questions', href: QUESTIONS_URL, secondary: true },
                ],
                note: "Pick a category, say what happened or what you'd like, and add a screenshot if you can.",
            },
        },
        {
            kind: 'reading',
            id: 'reading',
            toc_label: 'Reading',
            kicker: 'On the site',
            title: 'Something to read',
            books: [
                { title: 'October Frontline Report', text: 'The month in the Amarr–Minmatar warzone, and the 461B Amamake birthday brawl.', href: '/warzone/yc128-10/' },
                { title: 'October Economic Report', text: '1.25T ISK sold in Amamake, and what died faster than it sold.', href: '/amamake-market/yc128-10/' },
                { title: 'Gallente–Caldari Frontline', tag: 'New', text: 'Our first report on the other warzone.', href: '/warzone/gallente-caldari-yc128-10/' },
            ],
        },
    ],
    footer: {
        thanks: 'Built this month by BearThatCares and Beautiful Mim. Thanks to everyone who opened a ticket, tested something half-finished, or told us what was confusing.',
    },
}
