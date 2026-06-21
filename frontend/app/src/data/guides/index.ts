import type { GuideMeta } from '@/data/guides/types'

import faction_warfare_advantage from '@markdown/guides/faction-warfare-advantage.md'
import battlefields from '@markdown/guides/battlefields.md'
import faction_warfare_plexing from '@markdown/guides/faction-warfare-plexing.md'
import rendezvous_wolf from '@markdown/guides/rendezvous-wolf.md'
import mumble_setup from '@markdown/guides/mumble-setup.md'
import new_player_fleet_guide from '@markdown/guides/new-player-fleet-guide.md'
import abyssals from '@markdown/guides/abyssals.md'
import level5_missions from '@markdown/guides/level5-missions.md'
import pochven_standings from '@markdown/guides/pochven-standings.md'
import zohar_hunting from '@markdown/guides/zohar-hunting.md'
import bookmarks from '@markdown/guides/bookmarks.md'
import overview_guide from '@markdown/guides/overview-guide.md'

type GuideModule = {
    frontmatter: {
        title: string
        excerpt: string
        category: string
        wiki_url: string
        tags: string[]
    }
    rawContent: () => string
}

const guideModules: Record<string, GuideModule> = {
    'faction-warfare-advantage': faction_warfare_advantage,
    'battlefields': battlefields,
    'faction-warfare-plexing': faction_warfare_plexing,
    'rendezvous-wolf': rendezvous_wolf,
    'mumble-setup': mumble_setup,
    'new-player-fleet-guide': new_player_fleet_guide,
    'abyssals': abyssals,
    'level5-missions': level5_missions,
    'pochven-standings': pochven_standings,
    'zohar-hunting': zohar_hunting,
    'bookmarks': bookmarks,
    'overview-guide': overview_guide,
}

export const guideCategories = ["Faction Warfare","PVP","PVE","Utility"] as const

export const guides: GuideMeta[] = [
    {
        "slug": "faction-warfare-advantage",
        "title": "Advantage Guide",
        "excerpt": "Faction Warfare Advantage Advantage is a faction warfare mechanism that increases your victory points per complex capture . Without it, hundreds of extra complexes are needed to capture a system, s...",
        "category": "Faction Warfare",
        "wiki_url": "https://wiki.minmatar.org/en/alliance/Academy/faction-warfare-advantage",
        "tags": []
    },
    {
        "slug": "battlefields",
        "title": "Battlefield Guide",
        "excerpt": "The Extensive Battlefield Guide Guide Written By Furl0w, updated by Silvatek for new mechanics ¶ What is a “BF”? Battlefields (BF) are a particular type of Faction Warfare (FW) complex. Circa every...",
        "category": "Faction Warfare",
        "wiki_url": "https://wiki.minmatar.org/en/guides/battlefields",
        "tags": []
    },
    {
        "slug": "faction-warfare-plexing",
        "title": "Faction Warfare Plexing",
        "excerpt": "Faction Warfare Complexes Faction warfare Complexes, or \"plexes\" for short, are key elements of Minmatar territory control. By capturing complexes, pilots gain loyalty points and contribute to the...",
        "category": "Faction Warfare",
        "wiki_url": "https://wiki.minmatar.org/en/alliance/Academy/Faction_Warfare_Plexing",
        "tags": []
    },
    {
        "slug": "rendezvous-wolf",
        "title": "Rendezvous sites in an AC Wolf",
        "excerpt": "How to easily run Amarr Rendezvous sites with a PVE-fit autocannon Wolf assault frigate.",
        "category": "Faction Warfare",
        "wiki_url": "https://wiki.minmatar.org/en/guides/rendezvous-wolf",
        "tags": [
            "pve"
        ]
    },
    {
        "slug": "mumble-setup",
        "title": "Mumble Setup",
        "excerpt": "Mumble Setup In mumble open settings, then choose Shortcuts. ¶ Download & Setup Download and install the latest version of Mumble directly from the Mumble website . ¶ Saving the Connection Open you...",
        "category": "PVP",
        "wiki_url": "https://wiki.minmatar.org/en/guides/Mumble-Setup",
        "tags": [
            "onboarding",
            "mumble"
        ]
    },
    {
        "slug": "new-player-fleet-guide",
        "title": "New Player Fleet Guide",
        "excerpt": "New Player Fleet Guide New players are a critical part of the Minmatar ecosystem, so we want to make sure you have everything you need to attend your very first militia fleet with our alliance. Fle...",
        "category": "PVP",
        "wiki_url": "https://wiki.minmatar.org/en/alliance/Academy/new-player-fleet-guide",
        "tags": [
            "onboarding",
            "academy"
        ]
    },
    {
        "slug": "abyssals",
        "title": "Abyssals",
        "excerpt": "Venture into the Abyss ¶ Before you start.. Abyssal is a form of High-skill ceiling PvE content in eve that is on a time limit, each abyssal site takes <20minutes to run, or you die and lose your s...",
        "category": "PVE",
        "wiki_url": "https://wiki.minmatar.org/en/guides/Abyss",
        "tags": [
            "abyss",
            "abyssals",
            "crabbing"
        ]
    },
    {
        "slug": "level5-missions",
        "title": "Level 5 Mission Farming",
        "excerpt": "Level 5 mission guide Guide written and tested by [FL33T] Buppas This guide is considered incomplete Updated: 2024-02-02 ¶ The Concept This guide is written from the perspective of Minmatar space/a...",
        "category": "PVE",
        "wiki_url": "https://wiki.minmatar.org/en/guides/level5s",
        "tags": []
    },
    {
        "slug": "pochven-standings",
        "title": "Pochven Standings",
        "excerpt": "Pochven Standings This is a guide about fixing/setting initial standings - something all of you should be familiar with to some degree I imagine. Thankfully, it’s really simple. ¶ Why do I need to...",
        "category": "PVE",
        "wiki_url": "https://wiki.minmatar.org/en/guides/pochven-standings",
        "tags": []
    },
    {
        "slug": "zohar-hunting",
        "title": "Zohar's Chosen Angel Hunting",
        "excerpt": "Hunting Zohar's Chosen Angel NPCs",
        "category": "PVE",
        "wiki_url": "https://wiki.minmatar.org/en/guides/zohar-hunting",
        "tags": [
            "pve"
        ]
    },
    {
        "slug": "bookmarks",
        "title": "Bookmarks",
        "excerpt": "USING BOOKMARKS ¶ BOOKMARK FUNDAMENTALS A Bookmark is a saved representation of a specific spot in space. They are used for a variety of purposes. You can create your own bookmarks, organise them i...",
        "category": "Utility",
        "wiki_url": "https://wiki.minmatar.org/en/alliance/Academy/Bookmarks",
        "tags": []
    },
    {
        "slug": "overview-guide",
        "title": "Overview Guide",
        "excerpt": "Minmatar FL33T Alliance Overview Setup Guide Guide originally written by Alesis Wicked Eve online’s UI provides a copious amount of information and while playing this can often lead to information...",
        "category": "Utility",
        "wiki_url": "https://wiki.minmatar.org/en/guides/Alesis-Overview-Guide",
        "tags": []
    }
]

export function getGuideBySlug(slug: string): (GuideMeta & { module: GuideModule }) | undefined {
    const meta = guides.find((guide) => guide.slug === slug)
    const module = guideModules[slug]
    if (!meta || !module) return undefined
    return { ...meta, module }
}

export function getGuidesByCategory(): Record<string, GuideMeta[]> {
    const grouped: Record<string, GuideMeta[]> = {}
    for (const category of guideCategories) {
        grouped[category] = guides.filter((guide) => guide.category === category)
    }
    return grouped
}
