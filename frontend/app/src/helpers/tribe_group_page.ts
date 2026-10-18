/**
 * Pure rules for the tribe group page (docs/tribes/tribe-publishing.md,
 * Website): which tabs show, what the New menu offers, and the view models
 * the Fleets, Posts and Events tabs render. No Astro or fetch here, so the
 * rules are unit tested.
 */
import type {
    ApiResponse,
    DiscordChannel,
    Fleet,
    TribeEvent,
    TribeGroup,
} from '@dtypes/api.minmatar.org'
import type {
    DiscordChannelUI,
    PostTileUI,
    TribeEventRowUI,
    TribeVisibility,
} from '@dtypes/layout_components'
import { eve_day } from '@helpers/date'
import { escape_html } from '@helpers/string'

export const TRIBE_GROUP_TABS = [
    'about',
    'requirements',
    'guides',
    'activity',
    'members',
    'fleets',
    'events',
    'posts',
    'settings',
] as const

export type TribeGroupTab = typeof TRIBE_GROUP_TABS[number]

/** The Events tab block; the cancel partial swaps it back. */
export const TRIBE_GROUP_EVENTS_ID = 'tribe-group-events'

/** The old tab name: `#propaganda` links keep opening Posts. */
export const TRIBE_GROUP_HASH_ALIASES: Record<string, string> = { propaganda: 'posts' }

export interface TribeGroupTabInput {
    has_about:          boolean;
    has_guides:         boolean;
    has_activity:       boolean;
    fleet_count:        number;
    event_count:        number;
    post_count:         number;
    can_schedule_fleets: boolean;
    can_create_events:  boolean;
    can_post:           boolean;
    can_manage:         boolean;
}

/**
 * Tabs in the contract's order. A tab shows when it has something or the
 * viewer can add to it; Requirements and Members always show, Settings only
 * for managers.
 */
export function tribe_group_tab_ids(input: TribeGroupTabInput): TribeGroupTab[] {
    const shown: Record<TribeGroupTab, boolean> = {
        about: input.has_about,
        requirements: true,
        guides: input.has_guides,
        activity: input.has_activity,
        members: true,
        fleets: input.fleet_count > 0 || input.can_schedule_fleets,
        events: input.event_count > 0 || input.can_create_events,
        posts: input.post_count > 0 || input.can_post,
        settings: input.can_manage,
    }
    return TRIBE_GROUP_TABS.filter((tab) => shown[tab])
}

export type TribeNewMenuKind = 'post' | 'fleet' | 'event'

export interface TribeNewMenuItem {
    kind:   TribeNewMenuKind;
    href:   string;
}

type PublishFlags = Pick<TribeGroup, 'can_post' | 'can_schedule_fleets' | 'can_create_events'>

/** What "New" offers, from the API's viewer flags. Empty means no menu. */
export function tribe_new_menu_items(group: PublishFlags, tribe_id: number, group_id: number): TribeNewMenuItem[] {
    const items: TribeNewMenuItem[] = []
    if (group.can_post)
        items.push({ kind: 'post', href: `/alliance/propaganda/new/editor?host=${group_id}` })
    if (group.can_schedule_fleets)
        items.push({ kind: 'fleet', href: `/fleets/add/?host=${group_id}` })
    if (group.can_create_events)
        items.push({ kind: 'event', href: `/alliance/tribes/${tribe_id}/${group_id}/events/new` })
    return items
}

/** A group fleet is members only unless it was opened to the alliance. */
export function fleet_visibility(fleet: Pick<Fleet, 'open_to_alliance'>): TribeVisibility {
    return fleet.open_to_alliance ? 'open' : 'members_only'
}

/** Fleets bucketed by EVE day, in start order; the day key is YYYY-MM-DD. */
export function group_by_eve_day<T extends { start_time: Date | string }>(fleets: T[]): { key: string, fleets: T[] }[] {
    const sorted = [...fleets].sort((a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime())
    const days: { key: string, fleets: T[] }[] = []
    for (const fleet of sorted) {
        const key = eve_day(fleet.start_time)
        const day = days.at(-1)
        if (day?.key === key) day.fleets.push(fleet)
        else days.push({ key, fleets: [fleet] })
    }
    return days
}

/** The posts list item (the list sends `image`, the first image in the post). */
type PostListItem = ApiResponse<'EvePostListResponse'>
export type GroupPostSource = Pick<PostListItem,
    'post_id' | 'title' | 'seo_description' | 'author_character_id' | 'author_character_name' | 'date_posted' | 'members_only' | 'host_group'
> & { image?: string | null }

/**
 * A post on the group's Posts tab. It is "tagged" when another pilot (or
 * group) published it and tagged this group.
 */
export function post_tile(post: GroupPostSource, group_id: number, href: string): PostTileUI {
    return {
        id: post.post_id,
        title: post.title,
        excerpt: post.seo_description ?? '',
        image_url: post.image ? post.image : null,
        href,
        author_character_id: post.author_character_id,
        author_character_name: post.author_character_name,
        date: post.date_posted,
        members_only: Boolean(post.members_only),
        tagged: post.host_group?.id !== group_id,
    }
}

/** Newest first. */
export function sort_newest_first<T extends { date_posted: string }>(posts: T[]): T[] {
    return [...posts].sort((a, b) => new Date(b.date_posted).getTime() - new Date(a.date_posted).getTime())
}

/** Channel ids from the API are strings; the type says which picker group they belong to. */
export function discord_channel_ui(channel: DiscordChannel): DiscordChannelUI {
    const type = channel.type === 'stage' ? 'stage' : channel.type === 'voice' ? 'voice' : 'text'
    return { id: channel.id, name: channel.name, type }
}

/**
 * The event's row. Stage vs voice comes from the channel list when the
 * viewer can read it (publishers); otherwise a voice event shows as voice.
 */
export function event_row(
    event: TribeEvent,
    options: { cover_url: string | null, edit_href: string | null, voice_channels?: DiscordChannelUI[] },
): TribeEventRowUI {
    const channel = event.voice_channel_id
        ? options.voice_channels?.find((item) => item.id === event.voice_channel_id)
        : undefined
    const where_kind = event.where_kind === 'place' ? 'place' : channel?.type === 'stage' ? 'stage' : 'voice'
    return {
        id: event.id,
        title: event.title,
        cover_url: options.cover_url,
        starts_at: event.starts_at,
        ends_at: event.ends_at ?? null,
        where_kind,
        where_label: event.where_label,
        recurrence_label: event.recurrence === 'none' ? null : event.recurrence_label,
        status: event.status,
        interested_count: event.interested_count ?? 0,
        discord_event_url: event.discord_event_url ?? null,
        edit_href: event.status === 'scheduled' ? options.edit_href : null,
    }
}

/**
 * The hero is the first scheduled event; everything else (later events and
 * ones cancelled in the last day) lists under it in start order.
 */
export function split_events(events: TribeEvent[]): { next: TribeEvent | null, rest: TribeEvent[] } {
    const sorted = [...events].sort((a, b) => new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime())
    const next = sorted.find((event) => event.status === 'scheduled') ?? null
    return { next, rest: sorted.filter((event) => event !== next) }
}

/**
 * The Alpine call that asks before cancelling an event, then posts to the
 * events partial and swaps the Events tab back. The dialog renders `content`
 * as HTML, so the event title is escaped.
 */
export function cancel_event_dialog_call(args: { title: string, event_title: string, body: string, url: string }): string {
    return `show_confirm_dialog(${JSON.stringify({
        title: args.title,
        content: `<p><b>${escape_html(args.event_title)}</b></p><p>${escape_html(args.body)}</p>`,
        hx: {
            method: 'post',
            url: args.url,
            target: `#${TRIBE_GROUP_EVENTS_ID}`,
            swap: 'outerHTML',
        },
    })})`
}
