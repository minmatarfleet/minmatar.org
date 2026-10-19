import type { NewsletterIssue } from './types'

export const SLUG = 'yc128-10'
export const PERMALINK_PATH = `/newsletter/${SLUG}/`
export const COVER_IMAGE = '/images/home-vard-cover-eve.jpg'

const IMG = `/images/newsletter/${SLUG}`
const HELP_URL = 'https://discord.com/channels/1041384161505722368/1183401618943791186'
const HELP_LINK = `<a href="${HELP_URL}">#help</a>`
const AAR_URL = '/fleets/history/2405/#fights'
const TEST_DATA = 'Shown with test data.'

export const YC128_10: NewsletterIssue = {
    slug: SLUG,
    permalink_path: PERMALINK_PATH,
    published_at: new Date('2026-10-20T00:00:00Z'),
    cover_image: COVER_IMAGE,
    eyebrow: "What's new on my.minmatar.org",
    period_label: 'October YC 128',
    dek: 'Campaigns, a desktop overlay, after-action reports for every fleet, and a lot for tribes. Several of the biggest pieces are things you asked for in the Q3 survey.',
    lead_video: {
        kicker: 'Watch first',
        title: 'Town Hall #37 highlights',
        text: 'Missed the October town hall? The highlights cut covers it in a fraction of the time.',
        url: 'https://www.youtube.com/watch?v=VKdhxNxEua8',
        thumbnail: `${IMG}/townhall37.webp`,
        thumbnail_alt: 'Town Hall #37, October 2026, Highlights',
        play_position: 'top-right',
        cta: { links: [{ label: 'Watch on YouTube', href: 'https://www.youtube.com/watch?v=VKdhxNxEua8' }] },
    },
    sections: [
        {
            kind: 'feature',
            id: 'campaigns',
            toc_label: 'Campaigns',
            kicker: 'Faction Warfare',
            title: 'Enlist in a campaign',
            lede: "Enlist, and your kills, losses and complexes count toward a named goal. Every system shows how far we've moved it this week.",
            panel: {
                title: 'Now running: Aldodan YC128',
                paragraphs: [
                    "Fraternity have been building a farming nest in the Aldodan constellation. Until 30 November we're breaking it up by capturing and defending complexes across eight systems, from Arnher to Todifrauan.",
                    "Some of you didn't wait for the newsletter. Forty-five pilots have enlisted so far, and two are already running away with it:",
                ],
                pilots: [
                    { character_id: 91387091, character_name: 'darktal1 Kasenumi', note: '30 complexes run' },
                    { character_id: 2124160775, character_name: 'Sadthumper', note: '36 kills, top of the board' },
                ],
            },
            callout: {
                tag: 'You asked · Q3 survey',
                text: 'One theme kept coming up in your write-ins: <q>a warzone with a named objective</q>. This is it.',
            },
            figures: [
                {
                    src: `${IMG}/campaign.webp`,
                    width: 1440,
                    height: 900,
                    alt: "A campaign page: this week's progress per system, each with its goal and its move this week, and the enlist bar at the bottom.",
                    caption: "Aldodan's weekly progress, with this week's top killers in the enlist bar.",
                },
            ],
            cta: {
                links: [{ label: 'Join Aldodan', href: '/campaigns/aldodan-yc128/' }],
                note: 'Press <b>Add to campaign</b> on the You tab.',
            },
        },
        {
            kind: 'feature',
            id: 'desktop',
            toc_label: 'Desktop app',
            kicker: 'New app · Early testing',
            title: 'The fleet overlay for desktop',
            lede: 'See-through windows on top of your EVE client: the fleet schedule, your fleet, campaign progress and shared intel, without tabbing out.',
            callout: {
                tag: 'You asked · Q3 survey',
                text: "About 68 of 104 of you said you'd use a desktop overlay.",
            },
            figures: [
                {
                    src: `${IMG}/desktop.webp`,
                    width: 1600,
                    height: 633,
                    alt: 'Three overlay windows over an EVE scene: the Fleet window on its Upcoming tab, a campaign, and Intel with two shared d-scans.',
                    caption: `Fleet, Campaigns and Intel windows. ${TEST_DATA}`,
                    wide: true,
                },
            ],
            list: [
                { title: 'Fleet.', text: 'Your fleet at a glance, the schedule with a reminder before form-up, and File SRP or Reship when you lose a ship.' },
                { title: 'Campaigns.', text: "Every system, which way it's moving, and who's been out in the last hour." },
                { title: 'Intel.', text: 'Paste a d-scan or Local and share it with a link for fleet chat. It also flags Amarr fleets and capitals we spot on killmails, even when nobody has filed a report.' },
            ],
            aside: {
                tag: 'Early testing',
                text: `The app is brand new, so expect rough edges and changes from week to week. If something breaks, tell us in ${HELP_LINK}.`,
            },
            cta: {
                links: [{ label: 'Try the early version', href: 'https://github.com/minmatarfleet/minmatar.org/releases/latest' }],
                note: 'Windows only. It updates itself.',
            },
        },
        {
            kind: 'feature',
            id: 'corps',
            toc_label: 'Corp pages',
            kicker: 'Corporations',
            title: 'Every corp gets its own page',
            lede: 'See how a corp actually flies before you apply: when its pilots are on, what they bring, and its all-time records.',
            figures: [
                {
                    src: `${IMG}/corp.webp`,
                    width: 1260,
                    height: 1470,
                    alt: 'The Rattini Tribe About tab: pilots, fleets, kills and average tenure, then a heatmap of fleet turnout by EVE hour and weekday.',
                    caption: 'When we fly: fleet turnout by EVE hour.',
                },
            ],
            aside: {
                tag: 'Recruiting on Reddit',
                text: "We're working with the r/evejobs mods so that the sub isn't completely dominated by FL33T corporations, despite us staying within the rules. Our corporations' ads are spread out a bit more.",
            },
            cta: {
                links: [{ label: 'Browse corporations', href: '/alliance/corporations/' }],
                note: 'One open application at a time.',
            },
        },
        {
            kind: 'rollup',
            id: 'october',
            toc_label: 'October fleets',
            kicker: 'On grid',
            title: 'October so far',
            stats: [
                { value: '28', label: 'alliance fleets flown' },
                { value: '9', label: 'FCs, 2 of them new' },
                { value: '443', label: 'characters on grid' },
                { value: '373B', label: 'ISK destroyed, 74% efficiency' },
            ],
            nights_title: 'Biggest nights',
            nights: [
                { date_label: 'Sat 10 Oct', title: 'Battlefield before the town hall', fc_name: 'BearThatCares', pilots: 160, isk_destroyed: '13.6B', isk_lost: '8.9B' },
                { date_label: 'Sat 10 Oct', title: 'Amamake Birthday Brawl', fc_name: 'treges', pilots: 126, isk_destroyed: '255.1B', isk_lost: '57.1B' },
                { date_label: 'Mon 12 Oct', title: 'Contesting a moon', fc_name: 'treges', pilots: 120, isk_destroyed: '29.4B', isk_lost: '20.9B' },
                { date_label: 'Sun 18 Oct', title: 'Battlefield and more', fc_name: 'BearThatCares', pilots: 111, isk_destroyed: '20.1B', isk_lost: '23.5B' },
                { date_label: 'Thu 15 Oct', title: "Taking Todifrauan's complexes", fc_name: 'BearThatCares', pilots: 80, isk_destroyed: '5.1B', isk_lost: '1.2B' },
            ],
            nights_note: 'ISK destroyed / lost per fleet.',
            fcs_title: 'The FCs who took us out',
            fcs: [
                { character_id: 634915984, character_name: 'BearThatCares', fleets: 8, first_fleets: false },
                { character_id: 2117059479, character_name: 'MiniSpartan', fleets: 4, first_fleets: false },
                { character_id: 217145210, character_name: 'Darquies Shade', fleets: 4, first_fleets: true },
                { character_id: 2122950343, character_name: 'Mula Soldats', fleets: 3, first_fleets: false },
                { character_id: 365375372, character_name: 'treges', fleets: 3, first_fleets: false },
                { character_id: 154198067, character_name: 'Barret Smythe', fleets: 2, first_fleets: false },
                { character_id: 2123699290, character_name: 'Lilith Himmelsgaenger', fleets: 2, first_fleets: false },
                { character_id: 95063349, character_name: 'Xavi Estemaire', fleets: 1, first_fleets: true },
                { character_id: 94949900, character_name: 'Vic Tranow', fleets: 1, first_fleets: false },
            ],
            welcome: {
                tag: 'Welcome',
                text: 'Darquies Shade and Xavi Estemaire ran their first fleets with us this month. o7',
            },
            footnote: "Alliance fleets flown 1–19 October. Not counting standing fleets or fleets that didn't go out.",
            cta: {
                links: [
                    { label: "Read Sunday's after-action report", href: AAR_URL },
                    { label: 'See upcoming fleets', href: '/fleets/upcoming/', secondary: true },
                ],
            },
        },
        {
            kind: 'video',
            id: 'footage',
            toc_label: 'Call for footage',
            kicker: 'Call for footage',
            title: 'Help make the YC128 review',
            video: {
                kicker: 'Call for footage',
                title: 'Help make the YC128 review',
                text: "Faye Vaelent is cutting this year's annual review, like last year's YC127 In Review. Recorded a big fight, a good roam or a moment on comms worth remembering? Send it in.",
                url: 'https://www.youtube.com/watch?v=-BIQ5UIF3N0',
                thumbnail: `${IMG}/annual-review.webp`,
                thumbnail_alt: 'FL33T YC127 In Review',
                copy_username: { label: 'Send your clips to Faye on Discord by direct message:', username: 'schmendrik_' },
                cta: {
                    links: [{ label: "Watch last year's review", href: 'https://www.youtube.com/watch?v=-BIQ5UIF3N0', secondary: true }],
                },
            },
        },
        {
            kind: 'hits',
            id: 'fleets',
            toc_label: 'Fleet pages',
            kicker: 'Fleet pages',
            title: 'Every fleet gets an after-action report',
            callout: {
                tag: 'You asked · Q3 survey',
                text: 'Some of you asked for more <q>debriefs</q>. Now every fleet builds a timeline as it progresses to help fleet commanders tell their story.',
            },
            figures: [
                {
                    src: `${IMG}/fleet-outcome.webp`,
                    width: 1160,
                    height: 865,
                    alt: "A finished fleet's overview: ISK destroyed and lost, efficiency, and our pilots against theirs.",
                    caption: 'The outcome, including how outnumbered we were.',
                },
                {
                    src: `${IMG}/battle-report.webp`,
                    width: 1150,
                    height: 770,
                    alt: 'A battle report for a seven-minute engagement in Lantorn: Team A and Team B with ISK lost, efficiency, ships lost and damage, the groups on each side and the first pilots.',
                    caption: 'Every engagement gets its own battle report.',
                },
            ],
            items: [
                { title: 'Next fleet first', text: 'The Fleets page opens on the next fleet with a countdown in EVE and your local time.' },
                { title: 'After-action reports', text: 'ISK destroyed and lost, our numbers against theirs, and the night split into engagements.' },
                { title: 'Battle reports', text: 'Laid out like br.evetools. Move a group between sides and the link keeps your sides.' },
                { title: 'Share the kills', text: 'Every finished fleet has a public kills page you can link anywhere.' },
                { title: 'Your usual ship, pre-picked', text: 'Sign-ups start on the hull you usually fly, and your ship fills your role: links, cyno or logi.' },
                {
                    title: 'Lost the MOTD?',
                    text: 'Fleet chat, three dots, Reload Channel\'s MOTD. It now links the <a href="/learning/guides/new-player-fleet-guide/">new player guide</a>.',
                    credit: { character_id: 2116242012, character_name: 'Sycamoria', verb: 'Asked for by' },
                },
            ],
            cta: {
                links: [{ label: 'Open the after-action report', href: AAR_URL }],
                note: "Sunday's Battlefield and more, 111 pilots.",
            },
        },
        {
            kind: 'hits',
            id: 'tribes',
            toc_label: 'Tribes',
            kicker: 'Tribes',
            title: 'Tribes tell their story, and run their own fleets',
            figures: [
                {
                    src: `${IMG}/group-about.webp`,
                    width: 1180,
                    height: 1186,
                    alt: "The Market group's About tab with Fleets, Events and Posts tabs, its year in numbers, top pilots and hulls sold most.",
                    caption: "The Market group's year at a glance, plus its new Fleets, Events and Posts tabs.",
                },
            ],
            items: [
                { title: 'About pages', text: 'Every tribe and group shows its year: headline records, best month and top pilots.' },
                { title: 'Activity tabs', text: 'Eight groups, from Market to Fishermen, get trophies and top contributors.' },
                { title: 'Group fleets', text: 'Groups schedule their own fleets, members-only or open to everyone. Filter the Fleets page by Tribe fleets or My groups.' },
                { title: 'Group posts', text: "Post as the group, for members only or the whole alliance, and announce it in the group's Discord channel." },
                { title: 'Discord events', text: 'Create Discord events from the group page. Chiefs decide who can post, schedule fleets or create events.' },
                { title: 'Private rosters', text: 'Groups like Fishermen can hide their member list from outsiders.' },
            ],
            cta: { links: [{ label: 'Find your tribe', href: '/alliance/tribes/' }] },
        },
        {
            kind: 'hits',
            id: 'industry',
            toc_label: 'Industry',
            kicker: 'Industry & market',
            title: 'For builders and traders',
            orders: {
                title: "This month's orders",
                orders: [
                    { type_ids: [644, 24692, 17732, 17726], title: 'Typhoon ×150 · Abaddon ×100 · Tempest Fleet Issue ×50 · Apocalypse Navy Issue ×50', status: 'delivered', status_label: 'Delivered 13 Oct', progress: 100, note: '350 hulls from 13 builders' },
                    { type_ids: [639], title: 'Tempest ×40', status: 'delivered', status_label: 'Delivered 13 Oct', progress: 100, note: '3 builders' },
                    { type_ids: [73794], title: 'Thrasher Fleet Issue ×40', status: 'delivered', status_label: 'Delivered 13 Oct', progress: 100, note: '2 builders' },
                    { type_ids: [37604, 23757, 24483], title: 'Apostle ×8 · Archon ×3 · Nidhoggur ×3', status: 'in_progress', status_label: '12 of 14 · due 30 Oct', progress: 86, note: '5 builders' },
                    { type_ids: [644, 24692], title: 'Typhoon ×50 · Abaddon ×50', status: 'in_progress', status_label: '80 of 100 claimed · due 25 Oct', progress: 0, note: '20 hulls still need a builder' },
                ],
                builders: [
                    'AlphaOne Stenier-Tian', 'Azure Opiate', 'Barret Smythe', 'Digital Blink', 'Entitiez', 'Gin Taylor',
                    'Hasine en Tilavine', 'Inner Okel', 'Jenna Addams', 'Jyll Ataru', 'Kayra Nathuul', "Kel'dar Atram",
                    'Lance Adoudel', 'PanykButton', 'SoulStorm', 'Teirg Askold', 'Wolf Pappotte', 'Zack Prof', 'Zigg Omelo',
                ],
                cta: {
                    links: [
                        { label: 'Claim a build', href: '/industry/orders/' },
                        { label: 'Sell LP', href: '/industry/loyalty/', secondary: true },
                    ],
                },
            },
            figures_after_orders: [
                {
                    src: `${IMG}/product.webp`,
                    width: 1210,
                    height: 1250,
                    alt: 'A product page with a one-line verdict and a weekly chart of builds against losses and sales.',
                    caption: 'Product pages open on a verdict, here the Typhoon.',
                },
                {
                    src: `${IMG}/lp.webp`,
                    width: 1190,
                    height: 1300,
                    alt: 'The LP sell page: pick an amount, choose Standard or Express, and see your payout.',
                    caption: 'Sell LP and see your payout before you post.',
                },
            ],
            items: [
                { title: 'Product pages', text: 'Each item shows a verdict, who builds it, who needs it, and a Build tab of orders still looking for a builder.' },
                { title: 'LP buyback, rebuilt', text: 'TLF only. Standard pays more, Express pays within 24 hours, and your order page tells you exactly what to do next.' },
                {
                    title: 'BUILD packs on order claims',
                    text: "See if BUILD already has blueprint copies or material packs for the hull you're claiming.",
                    credit: { character_id: 684108979, character_name: 'Zigg Omelo', verb: 'Asked for by' },
                },
                {
                    title: 'Smarter ore buying',
                    text: 'Mineral orders use Veldspar first, and Water buyback is paused while we have too much.',
                    credit: { character_id: 2112954532, character_name: "Kel'dar Atram", verb: 'Reported by' },
                },
            ],
        },
        {
            kind: 'hits',
            id: 'account',
            toc_label: 'Also new',
            kicker: 'Also new',
            title: "Smaller things you'll notice",
            items: [
                { title: 'Choose what you share', text: 'Adding a character lets you pick which EVE permissions to grant, with what each is for.' },
                { title: 'Faster pings', text: 'Discord pings and notifications no longer wait behind big background jobs.' },
                {
                    title: 'SRP fixes',
                    text: "Attached combat logs stay linked, and a killmail that can't be used now says why.",
                    credit: { character_id: 2117059479, character_name: 'MiniSpartan', verb: 'Reported the blank warning:' },
                },
                { title: 'Easier to use', text: 'Every page shows where you are, phones get buttons and tables that fit, and we fixed bugs found in a sweep of about 400 pages.' },
            ],
            cta: { links: [{ label: 'Check your characters', href: '/account/' }] },
        },
        {
            kind: 'feature',
            id: 'help',
            toc_label: 'Report a bug',
            kicker: 'Tell us',
            title: 'Found a bug? Want something built?',
            lede: 'Open a ticket in #help on the alliance Discord. A lot of this month started as your reports and requests, from the MOTD guide to BUILD packs on order claims.',
            cta: {
                links: [{ label: 'Open #help', href: HELP_URL }],
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
                { title: 'The Rat Chronicle, ch. 5–11', text: "The alliance's history, from the Providence War to the DRL Reckoning.", href: '/alliance/story/chapter-5/' },
                { title: 'September Frontline Report', text: 'Eight systems changed hands, and the 625B brawl in Amamake.', href: '/warzone/yc128-09/' },
                { title: 'September Market Report', text: "What sold in Amamake in September, and what's dying faster than it's sold.", href: '/amamake-market/yc128-09/' },
            ],
        },
    ],
    footer: {
        thanks: 'Built this month by BearThatCares, Beautiful Mim and Marcelo Paez Sequeira. Thanks to everyone who reported bugs.',
        data_note: 'The desktop app screenshot uses sample data. October numbers are live data up to 19 October.',
        help: `Found something broken, or want something built? Open a ticket in ${HELP_LINK} on the alliance Discord.`,
    },
}
