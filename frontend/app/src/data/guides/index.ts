import type { GuideMeta, Author } from '@/data/guides/types'

import * as faction_warfare_basics from '@markdown/guides/faction-warfare-basics.md'
import * as faction_warfare_advantage from '@markdown/guides/faction-warfare-advantage.md'
import * as faction_warfare_plexing from '@markdown/guides/faction-warfare-plexing.md'
import * as new_player_fleet_guide from '@markdown/guides/new-player-fleet-guide.md'
import * as abyssals from '@markdown/guides/abyssals.md'
import * as abyss_duo_jackdaws_t6_dark from '@markdown/guides/abyss-duo-jackdaws-t6-dark.md'
import * as level5_missions from '@markdown/guides/level5-missions.md'
import * as abyss_nergal_trio_t6_firestorm from '@markdown/guides/abyss-nergal-trio-t6-firestorm.md'
import * as pochven_standings from '@markdown/guides/pochven-standings.md'
import * as abyss_stormbringer_t6_electrical from '@markdown/guides/abyss-stormbringer-t6-electrical.md'
import * as abyss_trio_hawk_t5_dark from '@markdown/guides/abyss-trio-hawk-t5-dark.md'
import * as zohar_hunting from '@markdown/guides/zohar-hunting.md'
import * as bookmarks from '@markdown/guides/bookmarks.md'

type GuideModule = {
    frontmatter: {
        title: string
        excerpt: string
        category: string
        author: string
    }
    rawContent: () => string
}

const guideModules: Record<string, GuideModule> = {
    'faction-warfare-basics': faction_warfare_basics,
    'faction-warfare-advantage': faction_warfare_advantage,
    'faction-warfare-plexing': faction_warfare_plexing,
    'new-player-fleet-guide': new_player_fleet_guide,
    'abyssals': abyssals,
    'abyss-duo-jackdaws-t6-dark': abyss_duo_jackdaws_t6_dark,
    'level5-missions': level5_missions,
    'abyss-nergal-trio-t6-firestorm': abyss_nergal_trio_t6_firestorm,
    'pochven-standings': pochven_standings,
    'abyss-stormbringer-t6-electrical': abyss_stormbringer_t6_electrical,
    'abyss-trio-hawk-t5-dark': abyss_trio_hawk_t5_dark,
    'zohar-hunting': zohar_hunting,
    'bookmarks': bookmarks,
}

export const guideCategories = ["Faction Warfare","PVP","PVE","Utility"] as const

export const guides: GuideMeta[] = [
    {
        slug: "faction-warfare-basics",
        title: "Faction Warfare Basics",
        excerpt: "An overview of the basic mechanics of faction warfare in EVE Online.",
        category: "Faction Warfare",
        author: "BearThatCares",
        authors: [{
            name: "BearThatCares",
            id: 634915984,
            entity: 'character',
        }],
    },
    {
        slug: "faction-warfare-plexing",
        title: "Faction Warfare Complexes",
        excerpt: "An in-depth breakdown for capturing complexes in faction warfare space",
        category: "Faction Warfare",
        author: "BearThatCares",
        authors: [{
            name: "BearThatCares",
            id: 634915984,
            entity: 'character',
        }],
    },
    {
        slug: "faction-warfare-advantage",
        title: "Faction Warfare Advantage",
        excerpt: "An in-depth breakdown for advantage in faction warfare.",
        category: "Faction Warfare",
        author: "A'Songala",
        authors: [{
            name: "A'Songala",
            id: 2120647389,
            entity: 'character',
        }],
    },
    {
        slug: "navy-destroyer-metagame",
        title: "Destroyer Guide",
        excerpt: "Destroyer guide for faction warfare: navy hulls plus Algos, Thrasher, Coercer, and Dragoon—fits, archetypes, and 1v1 matchups.",
        category: "Faction Warfare",
        author: "Furl0w",
        authors: [{
            name: "Furl0w",
            id: 2120153200,
            entity: 'character',
        }],
        path: "/guides/navy-destroyer-metagame/",
    },
    {
        slug: "navy-frigate-guide",
        title: "Frigate Guide",
        excerpt: "Comprehensive frigate guide for faction warfare.",
        category: "Faction Warfare",
        author: "BearThatCares",
        authors: [{
            name: "BearThatCares",
            id: 634915984,
            entity: 'character',
        }],
        path: "/guides/navy-frigate-guide/",
    },
    {
        slug: "new-player-fleet-guide",
        title: "New Player Fleet Guide",
        excerpt: "Everything you need for your first militia fleet: doctrines, support ships, fleet UI, and FAQ.",
        category: "PVP",
        author: "Minmatar Fleet",
        authors: [{
            name: "Minmatar Fleet",
            id: 99011978,
            entity: 'alliance',
        }],
    },
    {
        slug: "abyssals",
        title: "Farming the Abyss",
        excerpt: "EVE Online abyssal deadspace overview: filament tiers, weather types, and links to solo, duo, and trio fit guides.",
        category: "PVE",
        author: "Buppas",
        authors: [{
            name: "Buppas",
            id: 140971074,
            entity: 'character',
        }],
    },
    {
        slug: "abyss-duo-jackdaws-t6-dark",
        title: "Duo Jackdaws - T6 Dark",
        excerpt: "Duo Jackdaw fit and room guide for T6 Dark abyssals.",
        category: "PVE",
        author: "Buppas",
        authors: [{
            name: "Buppas",
            id: 140971074,
            entity: 'character',
        }],
        hiddenFromIndex: true,
    },
    {
        slug: "level5-missions",
        title: "L5 Mission Farming",
        excerpt: "Blitz Minmatar level 5 missions in EVE Online: tactics, mission walkthroughs, and ship fits.",
        category: "PVE",
        author: "Buppas",
        authors: [{
            name: "Buppas",
            id: 140971074,
            entity: 'character',
        }],
    },
    {
        slug: "abyss-nergal-trio-t6-firestorm",
        title: "Nergal / Retribution / Deacon - T6 Firestorm",
        excerpt: "Trio Nergal, Retribution, and Deacon guide for T6 Firestorm abyssals.",
        category: "PVE",
        author: "Buppas",
        authors: [{
            name: "Buppas",
            id: 140971074,
            entity: 'character',
        }],
        hiddenFromIndex: true,
    },
    {
        slug: "pochven-standings",
        title: "Pochven Standings",
        excerpt: "How to fix Triglavian standings for OBS fleets: ship choice, sites to run, and extraction options.",
        category: "Utility",
        author: "Minmatar Fleet",
        authors: [{
            name: "Minmatar Fleet",
            id: 99011978,
            entity: 'alliance',
        }],
    },
    {
        slug: "abyss-stormbringer-t6-electrical",
        title: "Stormbringer - T6 Electrical",
        excerpt: "Solo Stormbringer fit and room guide for T6 Electrical abyssals.",
        category: "PVE",
        author: "Kae2",
        authors: [{
            name: "Kae2",
            id: 95628204,
            entity: 'character',
        }],
        hiddenFromIndex: true,
    },
    {
        slug: "abyss-trio-hawk-t5-dark",
        title: "x3 Hawk - T5 Dark",
        excerpt: "Triple Hawk fit and room guide for T5 Dark abyssals.",
        category: "PVE",
        author: "Kae2",
        authors: [{
            name: "Kae2",
            id: 95628204,
            entity: 'character',
        }],
        hiddenFromIndex: true,
    },
    {
        slug: "zohar-hunting",
        title: "Zohar's Chosen Angel Hunting",
        excerpt: "Hunt Zohar's Chosen Angel NPCs in insurgency systems: fitting, scanning, tactics, and cashing in.",
        category: "PVE",
        author: "Bobb Bobbington",
        authors: [{
            name: "Bobb Bobbington",
            id: 93613873,
            entity: 'character',
        }, {
            name: "Silvatek",
            id: 2119722788,
            entity: 'character',
        }],
    },
    {
        slug: "bookmarks",
        title: "Bookmarks",
        excerpt: "Bookmark types, creation techniques, and sharing for safespots, gate pings, grid pings, and more.",
        category: "Utility",
        author: "Minmatar Fleet",
        authors: [{
            name: "Minmatar Fleet",
            id: 99011978,
            entity: 'alliance',
        }],
    }
]

export function getGuideBySlug(slug: string): (GuideMeta & { module: GuideModule }) | undefined {
    const meta = guides.find((guide) => guide.slug === slug)
    const module = guideModules[slug]
    if (!meta || !module) return undefined
    return { ...meta, module }
}

export function getIndexedGuides(): GuideMeta[] {
    return guides.filter((guide) => !guide.hiddenFromIndex)
}

export function getGuidesByCategory(): Record<string, GuideMeta[]> {
    const grouped: Record<string, GuideMeta[]> = {}
    for (const category of guideCategories) {
        grouped[category] = getIndexedGuides().filter((guide) => guide.category === category)
    }
    return grouped
}
