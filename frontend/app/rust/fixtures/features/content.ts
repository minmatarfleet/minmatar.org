// Fixtures for the Features/Content stories: propaganda and news posts, guides,
// learning certificates, skillsets, doctrine change requests and the #help panel.
import type { PostListUI, PostTileUI, Skillset, CharacterBasic, TribeGroupRefUI } from '@dtypes/layout_components'
import type { DoctrineChangeRequestRow, DoctrineChangeDiff, HelpSettings, LearningCertificate } from '@dtypes/api.minmatar.org'
import type { GuideMeta } from '@/data/guides/types'

/** Characters used as authors and submitters. */
export const AUTHORS: CharacterBasic[] = [
    { character_id: 2112954532, character_name: "Kel'dar Atram" },
    { character_id: 2112954533, character_name: 'Rattini Pilot' },
    { character_id: 2112954534, character_name: 'Hek Roamer' },
    { character_id: 2112954535, character_name: 'Amamake Defender' },
]

/** The alliance itself posts as character 0 (the fleet logo stands in for a portrait). */
export const ALLIANCE_AUTHOR: CharacterBasic = { character_id: 0, character_name: 'Minmatar Fleet Alliance' }

export const RATTINI_GROUP: TribeGroupRefUI = {
    id: 12, code: 'capitals.dreads', name: 'Dreadnoughts', tribe_id: 3, tribe_name: 'Capitals',
}

const post = (post_id: number, title: string, tag: string, date_posted: string, author: CharacterBasic, extra: Partial<PostListUI> = {}): PostListUI => ({
    post_id,
    title,
    state: 'published',
    slug: title.toLowerCase().replace(/[^a-z0-9]+/g, '-'),
    date_posted,
    user_id: author.character_id,
    author,
    tags: [tag],
    ...extra,
})

export const post_metropolis = post(1401, 'Amamake holds: 41 Rifters buy the system a night', 'Metropolis', '2026-11-14T19:20:00Z', AUTHORS[0])
export const post_frontlines = post(1398, 'Frontlines: plexing the Tama chain', 'Frontlines', '2026-11-12T08:05:00Z', AUTHORS[1])
export const post_alliance = post(1395, 'Welcome the November intake to Rens', 'Dispatches', '2026-11-10T12:00:00Z', ALLIANCE_AUTHOR)
export const post_group = post(1390, 'Dreadnought doctrine: why we bring the Revelation', 'Dispatches', '2026-11-08T17:45:00Z', AUTHORS[2], { host_group: RATTINI_GROUP })
export const post_long_title = post(
    1388,
    'A very long headline that keeps going because the editor forgot that headlines are meant to be short: the Rattini Tribe, Snuffed Out and every roamer between Auga and Amamake agree on one thing',
    'The Cope', '2026-11-06T09:30:00Z', AUTHORS[3],
)
export const post_no_tags: PostListUI = { ...post(1385, 'Untagged dispatch from Hek', 'x', '2026-11-04T10:00:00Z', AUTHORS[2]), tags: [] }

const TITLES: [string, string][] = [
    ['Metropolis', 'Rifter fits that survive a Stabber blob'],
    ['Frontlines', 'Auga plexes flip on Tuesday downtime'],
    ['Metro Daily News', 'SRP paid out: 2.14 billion ISK this week'],
    ['The Cope', 'Amarr cope of the week'],
    ['Rust and Blood', 'Rust and Blood: chapter six'],
    ['Waifu Wars', 'Waifu Wars: the Hek tournament'],
    ['Propaganda', 'Join the Minmatar Fleet'],
    ['Videos', 'Town hall highlights'],
]

/** Twelve published posts, newest first, across the media series the site tags posts with. */
export const posts_busy: PostListUI[] = Array.from({ length: 12 }, (_, i) => {
    const [tag, title] = TITLES[i % TITLES.length]
    const day = String(28 - i).padStart(2, '0')
    return post(1500 - i, i >= TITLES.length ? `${title} (${i - TITLES.length + 2})` : title, tag, `2026-10-${day}T18:00:00Z`, AUTHORS[i % AUTHORS.length])
})

export const posts_typical: PostListUI[] = [post_metropolis, post_frontlines, post_alliance, post_group, post_long_title]

/** An editor's own posts in each state, for the propaganda management view. */
export const posts_by_state: PostListUI[] = [
    post(1601, 'Draft: November fleet recap', 'Metropolis', '2026-11-18T10:00:00Z', AUTHORS[0], { state: 'draft' }),
    post(1600, 'Published: Rens shipyard open day', 'Dispatches', '2026-11-16T10:00:00Z', AUTHORS[0], { state: 'published' }),
    post(1599, 'Trashed: old recruitment poster', 'Propaganda', '2026-11-01T10:00:00Z', AUTHORS[0], { state: 'trash' }),
    post(1598, 'Published for members: capitals roster', 'Dispatches', '2026-10-28T10:00:00Z', AUTHORS[0], { state: 'published', host_group: RATTINI_GROUP, members_only: true }),
]

export const EDITOR_ID = AUTHORS[0].character_id

const tile = (id: number, title: string, excerpt: string, extra: Partial<PostTileUI> = {}): PostTileUI => ({
    id,
    title,
    excerpt,
    image_url: null,
    href: `/alliance/propaganda/${id}`,
    author_character_id: AUTHORS[0].character_id,
    author_character_name: AUTHORS[0].character_name,
    date: '2026-11-14T19:20:00Z',
    members_only: false,
    tagged: false,
    ...extra,
})

export const tile_plain = tile(1401, 'Amamake holds', 'Forty-one Rifters undocked from Rens and held the system through two reinforcement timers without a single hull lost to the gate camp.')
export const tile_cover = tile(1402, 'Plexing the Tama chain', 'A walkthrough of the November plex rotation with the Auga and Amamake runs marked.', { image_url: '/images/fleets-cover.jpg' })
export const tile_members = tile(1403, 'Dreadnought doctrine for members', 'The Revelation fit, the tackle wing and the call order. Members only.', { members_only: true, author_character_id: AUTHORS[2].character_id, author_character_name: AUTHORS[2].character_name })
export const tile_tagged = tile(1404, 'A pilot post the group tagged', 'Written by a pilot and tagged to the Dreadnought group, not published by it.', { tagged: true, author_character_id: AUTHORS[1].character_id, author_character_name: AUTHORS[1].character_name })
export const tile_long = tile(
    1405,
    'An exceptionally long post title that would wrap to several lines on a narrow tile and must not break the grid',
    'An excerpt that runs on and on about the Rattini Tribe, the Snuffed Out war, the Auga plexes, Hek logistics and everything else a long-winded author could cram into two lines of preview. '.repeat(3),
    { author_character_name: "Kel'dar Atram of the Rattini Tribe and the Minmatar Fleet Alliance" },
)

const guide = (slug: string, title: string, excerpt: string, category: string, extra: Partial<GuideMeta> = {}): GuideMeta => ({
    slug, title, excerpt, category,
    author: "Kel'dar Atram",
    authors: [{ name: "Kel'dar Atram", id: 2112954532, entity: 'character' }],
    ...extra,
})

export const guide_onboarding = guide('onboarding-first-fleet', 'Your first fleet', 'What to bring, where to dock and how to read the FC ping before your first Rifter fleet out of Rens.', 'Onboarding')
export const guide_cruiser = guide('faction-warfare-cruiser-guide', 'Faction warfare cruiser guide', 'Stabber, Rupture and Scythe Fleet Issue fits, with the roles they play in a plex fight.', 'Faction Warfare Ships')
export const guide_capitals = guide('capital-guide', 'Dreadnoughts in the warzone', 'When a Revelation is worth the hangar space, and when it is not.', 'Capital Ships')
export const guide_long = guide(
    'long-guide', 'The complete and exhaustive guide to everything about faction warfare plexing, advantage and battlefields',
    'An excerpt that goes on far longer than the card is meant to show, covering plexing, advantage, battlefields, the Auga chain and Amamake. '.repeat(3),
    'Faction Warfare Mechanics',
)
export const guide_custom_path = guide('town-hall', 'Town hall archive', 'Every recording, with highlights.', 'Utility', { path: '/alliance/town-halls/' })

export const skillsets_typical: Skillset[] = [
    { name: 'Academy Starter Plan', progress: 100, missing_skills: [] },
    { name: 'Magic 14', progress: 86, missing_skills: [{ skill_name: 'Medium Projectile Turret', skill_level: 5 }, { skill_name: 'Navigation', skill_level: 4 }] },
    { name: 'Shield Logistics Cruisers', progress: 42, missing_skills: [{ skill_name: 'Logistics Cruisers', skill_level: 3 }, { skill_name: 'Shield Emission Systems', skill_level: 5 }] },
    { name: 'Armor Logistics Cruisers', progress: 12, missing_skills: [{ skill_name: 'Remote Armor Repair Systems', skill_level: 5 }] },
    { name: 'Revelation/RNI', progress: 3, missing_skills: [{ skill_name: 'Dreadnoughts', skill_level: 1 }, { skill_name: 'Capital Ships', skill_level: 5 }] },
    { name: 'Apostle', progress: 0, missing_skills: [{ skill_name: 'Capital Ships', skill_level: 5 }] },
]

export const pilot: CharacterBasic = AUTHORS[0]

const certificate = (slug: string, title: string, summary: string, learning_slugs: string[]): LearningCertificate => ({
    slug, title, summary,
    sort_order: 1,
    personas: ['new-pilot'],
    learning_count: learning_slugs.length,
    learnings: learning_slugs.map((s, order) => ({
        slug: s, title: s.replaceAll('-', ' '), summary: '', content_kind: 'guide', order, url: `/guides/${s}/`, estimated_minutes: 8, thumbnail_url: '',
    })),
})

export const certificate_onboarding = certificate('alliance-onboarding', 'Alliance onboarding', 'Home base, your first fleet and your first billion ISK, in four short guides.', ['onboarding-home-base', 'onboarding-first-fleet', 'onboarding-fleet-types-and-hangar', 'onboarding-first-billion'])
export const certificate_empty = certificate('coming-soon', 'Coming soon', 'A certificate with no guides yet.', [])

const lines = (...entries: [string, string][]): DoctrineChangeDiff['lines'] => entries.map(([kind, text]) => ({ kind, text }))

export const diff_name: DoctrineChangeDiff = { field: 'name', label: 'name', lines: lines(['del', 'Rifter Fleet Issue (Amamake)'], ['add', 'Rifter Fleet Issue (Amamake v2)']) }
export const diff_description: DoctrineChangeDiff = { field: 'description', label: 'description', lines: lines(['same', 'Standing tackle doctrine.'], ['del', 'Bring two scram, one web.'], ['add', 'Bring one scram, one web, one neut.'], ['same', 'Contact the FC before you undock.']) }
export const diff_fit: DoctrineChangeDiff = { field: 'eft', label: 'fit', lines: lines(['same', '[Rifter, Amamake tackle]'], ['del', '200mm AutoCannon II, Republic Fleet Phased Plasma S'], ['add', '200mm AutoCannon II, Republic Fleet EMP S'], ['add', 'Small Nosferatu II'], ['same', 'Warp Scrambler II']) }

const request = (id: number, kind: 'doctrine' | 'fitting', target_name: string, extra: Partial<DoctrineChangeRequestRow>): DoctrineChangeRequestRow => ({
    id,
    kind,
    change_kind: 'edit',
    status: 'pending',
    tier: 'standard',
    target_id: 17,
    target_name,
    submit_note: '',
    review_note: '',
    submitted_by: "Kel'dar Atram",
    submitted_at: '2026-11-18T14:00:00Z',
    reviewed_by: null,
    reviewed_at: null,
    can_review: false,
    can_cancel: false,
    diffs: [diff_name],
    ...extra,
})

export const change_pending_reviewer = request(31, 'fitting', 'Rifter Fleet Issue (Amamake)', { submit_note: 'Swapping the rack for the Amamake neut fit the FCs asked for.', diffs: [diff_name, diff_fit], can_review: true })
export const change_pending_submitter = request(32, 'doctrine', 'Amamake Defence Doctrine', { diffs: [diff_description], can_cancel: true })
export const change_pending_readonly = request(33, 'fitting', 'Stabber Fleet Issue', { diffs: [diff_fit] })
export const change_approved = request(34, 'doctrine', 'Auga Plex Doctrine', { status: 'approved', review_note: 'Approved: matches the FC briefing.', reviewed_by: 'Hek Roamer', reviewed_at: '2026-11-19T09:00:00Z', diffs: [diff_description] })
export const change_no_diff = request(35, 'fitting', 'Scythe Fleet Issue', { diffs: [], submitted_by: null })

const help_category = (id: number, code: string, title: string, is_active: boolean, extra: Partial<HelpSettings['categories'][number]> = {}): HelpSettings['categories'][number] => ({
    id, code, title, is_active, description: `${title} tickets`, section: 'general', sort_order: id, assignee_names: ["Kel'dar Atram"], tribe_group_id: null, tribe_group_name: null, ...extra,
})

export const help_full: HelpSettings = {
    panel: { channel_id: '1180000000000000001', channel_name: 'help', message_id: '1180000000000000002' },
    tribe_groups: [{ id: 12, name: 'Dreadnoughts', taken: false, tribe_name: 'Capitals' }],
    categories: [
        help_category(1, 'recruitment', 'Recruitment', true),
        help_category(2, 'srp', 'SRP', true),
        help_category(3, 'industry', 'Industry orders', true),
        help_category(4, 'bug', 'Report a bug', true),
        help_category(5, 'capitals', 'Capitals', true, { tribe_group_id: 12, tribe_group_name: 'Dreadnoughts' }),
        help_category(6, 'old', 'Retired option', false),
    ],
}
export const help_empty: HelpSettings = { ...help_full, categories: help_full.categories.map(c => ({ ...c, is_active: false })) }
export const help_no_channel: HelpSettings = { ...help_full, panel: { channel_id: '0', channel_name: null, message_id: null } }
export const help_unknown_channel: HelpSettings = { ...help_full, panel: { channel_id: '1180000000000000001', channel_name: null, message_id: null } }

type RotationMonth = import('@dtypes/api.minmatar.org').RedditRotationMonth
type RotationPost = RotationMonth['posts'][number]

const CORPS = [
    { corporation_id: 98726134, corporation_name: 'Rattini Tribe', corporation_ticker: 'A-RAT' },
    { corporation_id: 98494147, corporation_name: 'Tribal Liberation Force', corporation_ticker: 'TLF' },
    { corporation_id: 98079862, corporation_name: 'Minmatar Fleet Academy', corporation_ticker: 'L3ARN' },
]

const rotation_post = (post_id: number, slot: number, corp: number, title: string, status: string, extra: Partial<RotationPost> = {}): RotationPost => ({
    ...CORPS[corp],
    post_id,
    template_id: 200 + post_id,
    title,
    status,
    delivery_method: 'bot',
    reddit_url: '',
    has_discord_channel: true,
    can_link_to_discord: false,
    slot_date: `2026-11-${String(slot).padStart(2, '0')}`,
    scheduled_for: `2026-11-${String(slot).padStart(2, '0')}T14:00:00Z`,
    ...extra,
})

export const rotation_published: RotationMonth = {
    month: '2026-11-01', status: 'published', schedule_id: 11, published_at: '2026-10-24T10:00:00Z',
    posts: [
        rotation_post(1, 2, 0, 'Rattini Tribe is recruiting: capitals, FW and mining', 'posted', { reddit_url: 'https://www.reddit.com/r/Eve/comments/1abc123/' }),
        rotation_post(2, 4, 1, 'TLF opens applications for faction warfare pilots', 'confirmed', { reddit_url: 'https://www.reddit.com/r/Eve/comments/1abc124/' }),
        rotation_post(3, 6, 2, 'New to EVE? The Fleet Academy teaches you to fly', 'pending'),
        rotation_post(4, 8, 0, 'Dreadnoughts in the warzone: join the doctrine', 'failed', { can_link_to_discord: true, has_discord_channel: false }),
        rotation_post(5, 10, 1, 'Plex with us in Auga', 'reminded'),
        rotation_post(6, 12, 2, 'Skipped slot', 'skipped'),
    ],
}
export const rotation_draft: RotationMonth = {
    month: '2026-12-01', status: 'draft', schedule_id: 12, published_at: null,
    posts: [
        rotation_post(11, 2, 0, 'Rattini Tribe winter recruitment', 'draft', { slot_date: '2026-12-02', scheduled_for: '2026-12-02T14:00:00Z' }),
        rotation_post(12, 4, 1, 'TLF: December plex weeks', 'draft', { slot_date: '2026-12-04', scheduled_for: '2026-12-04T14:00:00Z' }),
    ],
}
export const rotation_draft_empty: RotationMonth = { month: '2027-01-01', status: 'draft', schedule_id: 13, published_at: null, posts: [] }
