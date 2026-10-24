import type { GuideMeta, Author } from '@/data/guides/types'

import * as faction_warfare_basics from '@markdown/guides/faction-warfare-basics.md'
import * as faction_warfare_advantage from '@markdown/guides/faction-warfare-advantage.md'
import * as faction_warfare_plexing from '@markdown/guides/faction-warfare-plexing.md'
import * as faction_warfare_battlefields from '@markdown/guides/faction-warfare-battlefields.md'
import * as new_player_fleet_guide from '@markdown/guides/new-player-fleet-guide.md'
import * as abyssals from '@markdown/guides/abyssals.md'
import * as abyss_duo_jackdaws_t6_dark from '@markdown/guides/abyss-duo-jackdaws-t6-dark.md'
import * as level5_missions from '@markdown/guides/level5-missions.md'
import * as abyss_nergal_trio_t6_firestorm from '@markdown/guides/abyss-nergal-trio-t6-firestorm.md'
import * as abyss_stormbringer_t6_electrical from '@markdown/guides/abyss-stormbringer-t6-electrical.md'
import * as abyss_trio_hawk_t5_dark from '@markdown/guides/abyss-trio-hawk-t5-dark.md'
import * as zohar_hunting from '@markdown/guides/zohar-hunting.md'
import * as bookmarks from '@markdown/guides/bookmarks.md'
import * as selling_loyalty_points from '@markdown/guides/selling-loyalty-points.md'
import * as capital_ship_basics from '@markdown/guides/capital-ship-basics.md'
import * as onboarding_home_base from '@markdown/guides/onboarding-home-base.md'
import * as onboarding_first_fleet from '@markdown/guides/onboarding-first-fleet.md'
import * as onboarding_fleet_types_and_hangar from '@markdown/guides/onboarding-fleet-types-and-hangar.md'
import * as onboarding_faction_warfare_essentials from '@markdown/guides/onboarding-faction-warfare-essentials.md'
import * as onboarding_first_billion from '@markdown/guides/onboarding-first-billion.md'
import * as onboarding_make_content from '@markdown/guides/onboarding-make-content.md'
import * as onboarding_trial_srp_help from '@markdown/guides/onboarding-trial-srp-help.md'
import * as onboarding_culture_map from '@markdown/guides/onboarding-culture-map.md'


type GuideModule = {
    frontmatter: {
        title: string
        excerpt: string
        category: string
        author: string
    }
    rawContent: () => string
}

/** What Astro types a `*.md` import as: frontmatter is an untyped record. */
type MarkdownModule = {
    frontmatter: Record<string, any>
    rawContent: () => string
}

// Every guide's frontmatter carries the GuideModule fields; narrow the type
// once here instead of per import.
const guideModules = ({
    'faction-warfare-basics': faction_warfare_basics,
    'faction-warfare-advantage': faction_warfare_advantage,
    'faction-warfare-plexing': faction_warfare_plexing,
    'faction-warfare-battlefields': faction_warfare_battlefields,
    'new-player-fleet-guide': new_player_fleet_guide,
    'abyssals': abyssals,
    'abyss-duo-jackdaws-t6-dark': abyss_duo_jackdaws_t6_dark,
    'level5-missions': level5_missions,
    'abyss-nergal-trio-t6-firestorm': abyss_nergal_trio_t6_firestorm,
    'abyss-stormbringer-t6-electrical': abyss_stormbringer_t6_electrical,
    'abyss-trio-hawk-t5-dark': abyss_trio_hawk_t5_dark,
    'zohar-hunting': zohar_hunting,
    'bookmarks': bookmarks,
    'selling-loyalty-points': selling_loyalty_points,
    'capital-ship-basics': capital_ship_basics,
    'onboarding-home-base': onboarding_home_base,
    'onboarding-first-fleet': onboarding_first_fleet,
    'onboarding-fleet-types-and-hangar': onboarding_fleet_types_and_hangar,
    'onboarding-faction-warfare-essentials': onboarding_faction_warfare_essentials,
    'onboarding-first-billion': onboarding_first_billion,
    'onboarding-make-content': onboarding_make_content,
    'onboarding-trial-srp-help': onboarding_trial_srp_help,
    'onboarding-culture-map': onboarding_culture_map,
} satisfies Record<string, MarkdownModule>) as Record<string, GuideModule>

export const guideCategories = ["Onboarding","Faction Warfare Mechanics","Faction Warfare Ships","PVP","Subcapital Ships","Capital Ships","ISK Generation","Utility"] as const

/** Preferred subsection order within a category (index page). */
export const guideSectionsByCategory: Partial<Record<(typeof guideCategories)[number], readonly string[]>> = {
    'Onboarding': ['Day One', 'Week One', 'Month One', 'Trial'],
}

export const guides: GuideMeta[] = [
    {
        slug: "onboarding-home-base",
        title: "Home Base: Three Discords and Amamake",
        excerpt: "Day one: which Discord is which, how roles work, and why Amamake is home.",
        category: "Onboarding",
        section: "Day One",
        author: "Minmatar Fleet",
        authors: [{
            name: "Minmatar Fleet",
            id: 99011978,
            entity: 'alliance',
        }],
    },
    {
        slug: "onboarding-first-fleet",
        title: "Your First Fleet",
        excerpt: "Day one: find tonight's fleet, bring what you have, and undock without panic.",
        category: "Onboarding",
        section: "Day One",
        author: "Minmatar Fleet",
        authors: [{
            name: "Minmatar Fleet",
            id: 99011978,
            entity: 'alliance',
        }],
    },
    {
        slug: "onboarding-fleet-types-and-hangar",
        title: "Fleet Types and Your Hangar",
        excerpt: "Week one: strategic versus everything else, what to keep in your hangar, and where fits live.",
        category: "Onboarding",
        section: "Week One",
        author: "Minmatar Fleet",
        authors: [{
            name: "Minmatar Fleet",
            id: 99011978,
            entity: 'alliance',
        }],
    },
    {
        slug: "onboarding-faction-warfare-essentials",
        title: "Faction Warfare Essentials",
        excerpt: "Week one: the faction warfare you need to not be lost, written for returning players.",
        category: "Onboarding",
        section: "Week One",
        author: "Minmatar Fleet",
        authors: [{
            name: "Minmatar Fleet",
            id: 99011978,
            entity: 'alliance',
        }],
    },
    {
        slug: "onboarding-first-billion",
        title: "Your First Billion ISK",
        excerpt: "Month one: plex frontlines, sell LP on the loyalty desk, and pay for your own ships.",
        category: "Onboarding",
        section: "Month One",
        author: "Minmatar Fleet",
        authors: [{
            name: "Minmatar Fleet",
            id: 99011978,
            entity: 'alliance',
        }],
    },
    {
        slug: "onboarding-make-content",
        title: "You're Allowed to Make Content",
        excerpt: "Month one: form standing fleet, run a battlefield, and schedule fleets without being a famous FC.",
        category: "Onboarding",
        section: "Month One",
        author: "Minmatar Fleet",
        authors: [{
            name: "Minmatar Fleet",
            id: 99011978,
            entity: 'alliance',
        }],
    },
    {
        slug: "onboarding-trial-srp-help",
        title: "Trial, SRP, and Getting Help",
        excerpt: "Trial: what trial means, how ship replacement works, and where to take problems.",
        category: "Onboarding",
        section: "Trial",
        author: "Minmatar Fleet",
        authors: [{
            name: "Minmatar Fleet",
            id: 99011978,
            entity: 'alliance',
        }],
    },
    {
        slug: "onboarding-culture-map",
        title: "The Culture Map",
        excerpt: "Trial: town hall, values, tribes, and where the rest of the alliance lives once you are fleeting.",
        category: "Onboarding",
        section: "Trial",
        author: "Minmatar Fleet",
        authors: [{
            name: "Minmatar Fleet",
            id: 99011978,
            entity: 'alliance',
        }],
    },
    {
        slug: "faction-warfare-basics",
        title: "Faction Warfare Basics",
        excerpt: "An overview of the basic mechanics of faction warfare in EVE Online.",
        category: "Faction Warfare Mechanics",
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
        category: "Faction Warfare Mechanics",
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
        category: "Faction Warfare Mechanics",
        author: "A'Songala",
        authors: [{
            name: "A'Songala",
            id: 2120647389,
            entity: 'character',
        }],
    },
    {
        slug: "faction-warfare-battlefields",
        title: "Faction Warfare Battlefields",
        excerpt: "Learn how to run the most lucrative faction warfare site in the warzone, without getting AWOX'd.",
        category: "Faction Warfare Mechanics",
        author: "Furl0w",
        authors: [
            {
                name: "Furl0w",
                id: 2120153200,
                entity: 'character',
            },
            {
                name: "Silvatek",
                id: 2119722788,
                entity: 'character',
            },
            {
                name: "Emberdark",
                id: 2123859576,
                entity: 'character',
            },
        ],
    },
    {
        slug: "selling-loyalty-points",
        title: "Faction Warfare Loyalty Points",
        excerpt: "Convert Tribal Liberation Force LP into ISK: LP store offers, pitfalls, and alliance brokers.",
        category: "Faction Warfare Mechanics",
        author: "BearThatCares",
        authors: [{
            name: "BearThatCares",
            id: 634915984,
            entity: 'character',
        }],
        tribe_group_codes: ["supply.loyalty-points"],
    },
    {
        slug: "faction-warfare-cruiser-guide",
        title: "Faction Warfare Cruiser Guide",
        excerpt: "Fittings, roles, and 1v1 matchups for cruisers in faction warfare.",
        category: "Faction Warfare Ships",
        author: "Dato Koppla",
        authors: [{
            name: "Dato Koppla",
            id: 1761145024,
            entity: 'character',
        }],
    },
    {
        slug: "navy-destroyer-metagame",
        title: "Faction Warfare Destroyer Guide",
        excerpt: "Fittings, roles, and 1v1 matchups for destroyers in faction warfare.",
        category: "Faction Warfare Ships",
        author: "Furl0w",
        authors: [{
            name: "Furl0w",
            id: 2120153200,
            entity: 'character',
        }],
    },
    {
        slug: "navy-frigate-guide",
        title: "Faction Warfare Frigate Guide",
        excerpt: "Fittings, roles, and 1v1 matchups for frigates in faction warfare.",
        category: "Faction Warfare Ships",
        author: "BearThatCares",
        authors: [{
            name: "BearThatCares",
            id: 634915984,
            entity: 'character',
        }],
    },
    {
        slug: "subcapital-basics",
        title: "Subcapital Basics",
        excerpt: "Fundamentals of flying subcapital ships in Minmatar Fleet doctrines.",
        category: "Subcapital Ships",
        author: "Minmatar Fleet",
        authors: [{
            name: "Minmatar Fleet",
            id: 99011978,
            entity: 'alliance',
        }],
        comingSoon: true,
    },
    {
        slug: "subcapital-dps-guide",
        title: "DPS Guide",
        excerpt: "DPS roles, fittings, and expectations for fleet subcaps.",
        category: "Subcapital Ships",
        author: "Minmatar Fleet",
        authors: [{
            name: "Minmatar Fleet",
            id: 99011978,
            entity: 'alliance',
        }],
        comingSoon: true,
    },
    {
        slug: "subcapital-logi-guide",
        title: "Logi Guide",
        excerpt: "Logistics roles, reps, and how to keep the fleet alive.",
        category: "Subcapital Ships",
        author: "Minmatar Fleet",
        authors: [{
            name: "Minmatar Fleet",
            id: 99011978,
            entity: 'alliance',
        }],
        comingSoon: true,
    },
    {
        slug: "subcapital-support-guide",
        title: "Support Guide",
        excerpt: "Ewar, tackle, and other support roles in subcapital fleets.",
        category: "Subcapital Ships",
        author: "Minmatar Fleet",
        authors: [{
            name: "Minmatar Fleet",
            id: 99011978,
            entity: 'alliance',
        }],
        comingSoon: true,
    },
    {
        slug: "new-player-fleet-guide",
        title: "New Player Fleet Guide",
        excerpt: "Voice, ships, fleet UI, and FAQ for your first militia fleet.",
        category: "Utility",
        author: "BearThatCares",
        authors: [{
            name: "BearThatCares",
            id: 634915984,
            entity: 'character',
        }],
    },
    {
        slug: "capital-ship-basics",
        title: "Capital Ship Basics",
        excerpt: "How Minmatar Fleet members use, lose, and fund their capital ships. Covers the high level fundamentals for all capital types.",
        category: "Capital Ships",
        author: "BearThatCares",
        authors: [{
            name: "BearThatCares",
            id: 634915984,
            entity: 'character',
        }],
        tribe_group_codes: [
            "capitals.dreads",
            "capitals.carriers",
            "capitals.faxes",
        ],
    },
    {
        slug: "force-auxiliary-carrier-guide",
        title: "FAX Guide",
        excerpt: "Learn the basics of the Force Auxiliary Carrier. Which hulls are good, when to use what, and how to reach end-game remote repair content.",
        category: "Capital Ships",
        author: "BearThatCares",
        authors: [{
            name: "BearThatCares",
            id: 634915984,
            entity: 'character',
        }],
        tribe_group_codes: ["capitals.faxes"],
    },
    {
        slug: "dreadnought-guide",
        title: "Dread Guide",
        excerpt: "Learn everything you need to know about the dreadnought. The meta, why armor is good, and which dreads to use in which situations.",
        category: "Capital Ships",
        author: "BearThatCares",
        authors: [{
            name: "BearThatCares",
            id: 634915984,
            entity: 'character',
        }],
        tribe_group_codes: ["capitals.dreads"],
    },
    {
        slug: "carrier-guide",
        title: "Carrier Guide",
        excerpt: "Learn about the carrier, one of the most beloved and useful capital classes in New Eden.",
        category: "Capital Ships",
        author: "BearThatCares",
        authors: [{
            name: "BearThatCares",
            id: 634915984,
            entity: 'character',
        }],
        tribe_group_codes: ["capitals.carriers"],
    },
    {
        slug: "abyssals",
        title: "Farming the Abyss",
        excerpt: "EVE Online abyssal deadspace overview: filament tiers, weather types, and links to solo, duo, and trio fit guides.",
        category: "ISK Generation",
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
        category: "ISK Generation",
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
        category: "ISK Generation",
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
        category: "ISK Generation",
        author: "Buppas",
        authors: [{
            name: "Buppas",
            id: 140971074,
            entity: 'character',
        }],
        hiddenFromIndex: true,
    },
    {
        slug: "abyss-stormbringer-t6-electrical",
        title: "Stormbringer - T6 Electrical",
        excerpt: "Solo Stormbringer fit and room guide for T6 Electrical abyssals.",
        category: "ISK Generation",
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
        category: "ISK Generation",
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
        category: "ISK Generation",
        author: "Bobb Bobbington",
        authors: [{
            name: "Bobb Bobbington",
            id: 93613873,
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
    },
]

export function getGuideBySlug(slug: string): (GuideMeta & { module: GuideModule }) | undefined {
    const meta = guides.find((guide) => guide.slug === slug)
    const module = guideModules[slug]
    if (!meta || !module) return undefined
    return { ...meta, module }
}

export function getIndexedGuides(): GuideMeta[] {
    return guides.filter((guide) => !guide.hiddenFromIndex && !guide.comingSoon)
}

export function getPublishedGuides(): GuideMeta[] {
    return getIndexedGuides().filter((guide) => !guide.comingSoon)
}

/** Guides tagged to a tribe group via stable TribeGroup.code. */
export function getGuidesByTribeGroupCode(code: string | undefined | null): GuideMeta[] {
    if (!code) return []
    return getPublishedGuides().filter(
        (guide) => guide.tribe_group_codes?.includes(code),
    )
}


export function getGuidesByCategory(): Record<string, GuideMeta[]> {
    const grouped: Record<string, GuideMeta[]> = {}
    for (const category of guideCategories) {
        grouped[category] = getIndexedGuides().filter((guide) => guide.category === category)
    }
    return grouped
}

export type GuideCategorySection = {
    label: string | null
    guides: GuideMeta[]
}

/** Split a category's guides into ordered subsections when configured. */
export function getGuideSectionsForCategory(
    category: (typeof guideCategories)[number],
    categoryGuides: GuideMeta[],
): GuideCategorySection[] {
    const preferred = guideSectionsByCategory[category]
    if (!preferred?.length) {
        return [{ label: null, guides: categoryGuides }]
    }

    const used = new Set<string>()
    const sections: GuideCategorySection[] = []

    for (const label of preferred) {
        const guides = categoryGuides.filter((guide) => guide.section === label)
        if (!guides.length) continue
        for (const guide of guides) used.add(guide.slug)
        sections.push({ label, guides })
    }

    const remainder = categoryGuides.filter((guide) => !used.has(guide.slug))
    if (remainder.length) {
        sections.push({ label: null, guides: remainder })
    }

    return sections.length ? sections : [{ label: null, guides: categoryGuides }]
}
