import type { NewsletterIssue } from './types'

export const SLUG = 'yc128-11'
export const PERMALINK_PATH = `/newsletter/${SLUG}/`
export const COVER_IMAGE = '/images/home-vard-cover-eve.jpg'

const IMG = `/images/newsletter/${SLUG}`
const HELP_URL = 'https://discord.com/channels/1041384161505722368/1183401618943791186'
const QUESTIONS_URL = 'https://discord.com/channels/1041384161505722368/1561471935462903839'
const TOWN_HALL_URL = 'https://www.youtube.com/watch?v=qZwMM5xm7c0'

export const YC128_11: NewsletterIssue = {
    slug: SLUG,
    permalink_path: PERMALINK_PATH,
    published_at: new Date('2026-11-06T00:00:00Z'),
    cover_image: COVER_IMAGE,
    share_image: `/images/newsletter/${SLUG}/share.jpg`,
    eyebrow: "What's new on my.minmatar.org",
    period_label: 'November YC 128',
    dek: 'This month: a Training tab that tells you what you can fly and what to train next, fleet invites straight to your Discord DMs, a Trial tab for new pilots, and the story of our first quiet fleet.',
    lead_video: {
        kicker: 'Watch first',
        title: 'Town Hall #38 highlights',
        text: 'Missed the November town hall? The highlights cut covers it in a fraction of the time.',
        url: TOWN_HALL_URL,
        thumbnail: `${IMG}/townhall38.webp`,
        thumbnail_alt: 'Town Hall #38, November 2026, Highlights',
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
            lede: 'The new Training tab on your account checks every one of your characters against every doctrine fit. It shows what you can fly today, and how long until the next ship is ready.',
            figures: [
                {
                    src: `${IMG}/training-plan.webp`,
                    width: 1160,
                    height: 1220,
                    alt: "The Training tab: a doctrine table showing how many characters can bring each role at once, then a character's training plan for an Armor Buffer Nidhoggur with the skills in order and the time to Ready.",
                    caption: 'Click the ship a character is training for to see every skill it needs, in an order EVE will accept.',
                },
            ],
            list: [
                { title: 'What you can bring.', text: 'Every doctrine and role in one table. If you multibox, it counts how many of your accounts can fly each role at once.' },
                { title: 'One goal per character.', text: 'Each character works toward one doctrine ship. The others wait in line, and you can change the order whenever you like.' },
                { title: 'A plan you can paste into EVE.', text: 'Train to Ready, which is good enough for fleets, or all the way to Optimal. Then copy the skill list straight into your EVE queue.' },
            ],
            cta: {
                links: [{ label: 'Open your Training tab', href: '/account/#training' }],
            },
        },
        {
            kind: 'feature',
            id: 'invites',
            layout: 'split',
            toc_label: 'Invites',
            kicker: 'Fleets',
            title: 'An FC might invite you to a fleet',
            lede: 'FCs can now invite you to an upcoming fleet with a Discord DM. Press I’m in or Sitting out, then pick your ship on the site.',
            figures: [
                {
                    src: `${IMG}/invites.webp`,
                    width: 640,
                    height: 714,
                    alt: "The Invite pilots dialog: the timezones set by the fleet time, a choice of new pilots, names or a pasted list, a note, and a preview of the Discord invite with I'm in, Sitting out and Stop fleet invites buttons.",
                    caption: 'The FC’s invite screen, with a preview of the DM you get.',
                },
            ],
            list: [
                { title: 'One a week, at most.', text: 'However many fleets are going up, you get at most one invite a week.' },
                { title: 'Only when you play.', text: 'Invites follow the fleet time, so you only hear about fleets in your timezone.' },
                { title: 'Easy to switch off.', text: 'Every DM has a Stop fleet invites button. You can turn them back on under Account › Notifications.' },
                { title: 'New here?', text: 'FCs can invite pilots in their first week, so your first fleet can come looking for you.' },
            ],
            cta: { links: [{ label: 'See upcoming fleets', href: '/fleets/upcoming/' }] },
        },
        {
            kind: 'feature',
            id: 'trial',
            layout: 'split-reverse',
            toc_label: 'Trial',
            kicker: 'New pilots',
            title: 'Your trial, at a glance',
            lede: 'Just joined? The Trial tab shows how far through your trial you are, how long trials in your corp usually take, and what will get you to full member.',
            figures: [
                {
                    src: `${IMG}/trial.webp`,
                    width: 1170,
                    height: 720,
                    alt: "The Trial tab: day 41 of the trial on a bar from day 1 to day 90, with the review at day 60 and the corp's average at day 72, then fleets, kills and voice each on a five-step scale.",
                    caption: 'Where you stand, without a leaderboard.',
                },
            ],
            list: [
                { title: 'Where you are.', text: 'Your day of the trial, when review opens at day 60, and when most trials in your corp finish.' },
                { title: 'How you compare.', text: 'Your fleets, kills and time on comms over the last month, from well below to well above average. You see where you sit, not a ranking.' },
                { title: 'What you brought.', text: 'Every fleet you flew and whether your ship was on the doctrine, so you know what to bring next time.' },
                { title: 'For CEOs.', text: 'Promote a trial pilot from your corp’s Members tab. Applications now close on their own once the pilot joins your corp in game.' },
            ],
            cta: { links: [{ label: 'See your Trial tab', href: '/account/#trial' }] },
        },
        {
            kind: 'feature',
            id: 'quiet',
            layout: 'story',
            toc_label: 'Quiet mode',
            kicker: 'Quiet mode',
            title: 'The fleet nobody saw coming',
            lede: 'Strategic FCs can now run invite-only fleets. They never appear on the schedule or in pings. The FC invites pilots by Discord DM, and everyone who says yes joins a private thread.',
            panel: {
                title: 'Quiet mode fleet · Saturday 24 October',
                paragraphs: [
                    'Word was that something big might kick off near Amamake, so BearThatCares kept the fleet off the schedule. Seven waves of invites went out, 38 pilots said they were in, and the FC asked for <b>40 dreads, 30 TFIs and 20 logi</b>.',
                    'We waited at the login screen, then took the fight in Dudreda against Cryonic Origin and Ahbazon-Prime, outnumbered 1.5 to 1. The ISK went their way, 13.6B to 16.4B, but nobody saw us coming. Once it was over, the FC declassified the fleet, so its reports are public now.',
                ],
            },
            figures: [
                {
                    src: `${IMG}/quiet-fleet.webp`,
                    width: 1170,
                    height: 411,
                    alt: 'The declassified quiet mode fleet: Saturday 24 October, 1 hour 10 minutes, staged in Amamake on TFIs, FC BearThatCares. Outcome: 13.6B destroyed, 16.4B lost, 45% efficiency, 120 against 180.',
                    caption: 'After the fight, the fleet shows up in history like any other.',
                    wide: true,
                },
            ],
            list: [
                { title: 'Invites in waves.', text: 'Pick pilots, tribe groups or corps, or paste a list of names, and send more waves as the night takes shape.' },
                { title: 'Ship targets.', text: 'The FC sets targets like 40 dreads and 20 logi, and pilots see what’s still needed when they pick a ship.' },
                { title: 'A private thread.', text: 'Everyone who says yes gets a Discord thread for updates, and the start ping goes there.' },
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
                { title: 'The whole night', text: 'A fleet’s battle report now covers every kill and loss from form-up to dock, not just one fight.' },
                { title: 'Drag to zoom in', text: 'Drag across the timeline to focus on one fight or one leg of a roam, then share the link.' },
                { title: 'Fights worth keeping', text: 'FCs can save and name the fights that mattered, so everyone can find them in one click.' },
                { title: 'Reports by EVE mail', text: 'After each fleet, the FC gets an EVE mail with the numbers and links to both reports, ready to share.' },
            ],
            cta: { links: [{ label: 'Browse past fleets', href: '/fleets/history/' }] },
        },
        {
            kind: 'hits',
            id: 'fcs',
            toc_label: 'For FCs',
            kicker: 'Fleet pages',
            title: 'More tools for fleet commanders',
            figures: [
                {
                    src: `${IMG}/participants.webp`,
                    width: 1170,
                    height: 660,
                    alt: 'The Participants tab: peak in fleet, pilots, pilots on a killmail and engagements, a chart of fleet size over time, and each pilot with their ship, kills and losses on a timeline.',
                    caption: 'Participants: who came, when, and in what.',
                },
                {
                    src: `${IMG}/copy-fleet.webp`,
                    width: 512,
                    height: 398,
                    alt: 'The Copy this fleet dialog with only a new date and EVE time to fill in.',
                    caption: 'Run a good fleet again next week.',
                },
            ],
            items: [
                { title: 'Participants', text: 'Every pilot in the order they joined, with their ships, and who was on grid for each fight.' },
                { title: 'Copy this fleet', text: 'Same doctrine, briefing and staging on a new date. Pick the day and time, and you’re done.' },
                { title: 'Run it on an alt', text: 'Fleet boss on another character? Tracking finds it, and the site still shows you as the FC.' },
                { title: 'Bring what you have', text: 'Pilots can sign up in a ship that isn’t on the doctrine, so the FC knows what’s coming.' },
                { title: 'Private sign-ups', text: 'New fleets hide who signed up from other pilots. The FC still sees everyone.' },
                { title: 'Academy fits', text: 'Secondary fits are now called Academy fits, and only Academy pilots can bring them.' },
            ],
            cta: { links: [{ label: 'Schedule a fleet', href: '/fleets/upcoming/' }] },
        },
        {
            kind: 'hits',
            id: 'tribes',
            toc_label: 'Corps',
            kicker: 'Corporations & tribes',
            title: 'Easier to find your people',
            items: [
                { title: 'Tribe invitations', text: 'Tribe chiefs can invite you to their group. You get a DM and join in one step, no application needed.' },
                { title: 'Corp Discord links', text: 'Corps can put their Discord server on their page, so you can say hi before you apply.' },
                { title: 'Apply from any tab', text: 'Submit Application now sits at the top of every corp page.' },
                { title: 'No forgotten applications', text: 'Already joined the corp in game? Your application closes itself within half an hour.' },
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
                { title: 'Timezone roles', text: 'Discord now gives you a USTZ, EUTZ or AUTZ role based on when you actually play, so pings reach people who are online.' },
                { title: 'Fairer build orders', text: 'Industry orders are priced against Jita or as a margin over build cost, and never below what a ship costs to build.' },
                { title: 'Build planner', text: 'Set how many runs your blueprint copies have, and the material bill matches the jobs you will actually install.' },
                { title: 'Desktop app 0.12', text: 'The Recent tab lists your last fleets by day, with kills, losses and SRP status. Already installed? It updates itself.' },
                { title: 'No hidden tabs', text: 'Pages with lots of tabs now wrap them onto a second row instead of hiding them off the edge.' },
                { title: 'Tidier buyback', text: 'Finished buyback sales now close properly, along with their Discord thread.' },
            ],
            cta: { links: [{ label: 'Open your account', href: '/account/' }] },
        },
        {
            kind: 'feature',
            id: 'help',
            toc_label: 'Help',
            kicker: 'Tell us',
            title: 'Found a bug? Want something built?',
            lede: 'Open a ticket in #help on the alliance Discord. Several fixes in this issue started as your tickets. New to the game? There are no stupid questions in #questions.',
            cta: {
                links: [
                    { label: 'Open #help', href: HELP_URL },
                    { label: 'Ask in #questions', href: QUESTIONS_URL, secondary: true },
                ],
                note: "Say what happened or what you'd like, and add a screenshot if you can.",
            },
        },
        {
            kind: 'reading',
            id: 'reading',
            toc_label: 'Reading',
            kicker: 'On the site',
            title: 'Something to read',
            books: [
                { title: 'October Frontline Report', text: 'A month in the Amarr–Minmatar warzone, including the 461B Amamake birthday brawl.', href: '/warzone/yc128-10/' },
                { title: 'October Economic Report', text: '1.25T ISK traded in Amamake, and which ships died faster than they sold.', href: '/amamake-market/yc128-10/' },
                { title: 'Gallente–Caldari Frontline', tag: 'New', text: 'Our first look at the other warzone.', href: '/warzone/gallente-caldari-yc128-10/' },
            ],
        },
    ],
    footer: {
        thanks: 'Built this month by BearThatCares and Beautiful Mim. Thanks to everyone who opened a ticket, tested something half-finished, or told us what was confusing.',
    },
}
