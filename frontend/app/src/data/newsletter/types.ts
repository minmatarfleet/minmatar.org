/**
 * One monthly newsletter issue. Copy lives in the issue file (English only,
 * like the warzone reports); page and meta titles live in i18n.
 *
 * Short strings marked `html` may hold <b>, <q> and <a> markup written by us.
 */

export interface NewsletterLink {
    label: string
    href: string
    /** Second-tier button next to the primary one. */
    secondary?: boolean
}

export interface NewsletterCta {
    links: NewsletterLink[]
    /** Short note beside the buttons. html */
    note?: string
}

export interface NewsletterFigure {
    src: string
    width: number
    height: number
    alt: string
    caption: string
}

/** A member credited for reporting or asking for an item. */
export interface NewsletterCredit {
    character_id: number
    character_name: string
    /** e.g. "Reported by" or "Asked for by". */
    verb: string
}

export interface NewsletterItem {
    title: string
    /** html */
    text: string
    credit?: NewsletterCredit
}

/** A "You asked · Q3 survey" style callout. */
export interface NewsletterCallout {
    tag: string
    /** html */
    text: string
}

export interface NewsletterPilot {
    character_id: number
    character_name: string
    note: string
}

export interface NewsletterPanel {
    title: string
    /** html paragraphs */
    paragraphs: string[]
    pilots?: NewsletterPilot[]
}

export interface NewsletterVideo {
    kicker: string
    title: string
    text: string
    url: string
    thumbnail: string
    thumbnail_alt: string
    /** Where the play badge sits so it clears the thumbnail's own title. */
    play_position?: 'center' | 'top-right'
    cta: NewsletterCta
    /** Discord username to copy, shown under the text. */
    copy_username?: { label: string; username: string }
}

export interface NewsletterStat {
    value: string
    label: string
}

export interface NewsletterNight {
    date_label: string
    title: string
    fc_name: string
    pilots: number
    isk_destroyed: string
    isk_lost: string
}

export interface NewsletterFc {
    character_id: number
    character_name: string
    fleets: number
    first_fleets: boolean
}

export interface NewsletterOrder {
    type_ids: number[]
    title: string
    status: 'delivered' | 'in_progress'
    status_label: string
    /** 0–100 */
    progress: number
    note: string
}

interface NewsletterSectionBase {
    /** Anchor id, also used by the contents strip. */
    id: string
    toc_label: string
    kicker: string
    title: string
}

export interface NewsletterFeatureSection extends NewsletterSectionBase {
    kind: 'feature'
    lede?: string
    panel?: NewsletterPanel
    callout?: NewsletterCallout
    figures?: NewsletterFigure[]
    /** Short single-column list, used under a figure. */
    list?: NewsletterItem[]
    aside?: NewsletterCallout
    cta?: NewsletterCta
}

export interface NewsletterHitsSection extends NewsletterSectionBase {
    kind: 'hits'
    callout?: NewsletterCallout
    /** One figure spans the column; two sit side by side. */
    figures?: NewsletterFigure[]
    orders?: { title: string; orders: NewsletterOrder[]; builders: string[]; cta?: NewsletterCta }
    figures_after_orders?: NewsletterFigure[]
    items: NewsletterItem[]
    cta?: NewsletterCta
}

export interface NewsletterRollupSection extends NewsletterSectionBase {
    kind: 'rollup'
    stats: NewsletterStat[]
    nights_title: string
    nights: NewsletterNight[]
    nights_note: string
    fcs_title: string
    fcs: NewsletterFc[]
    welcome?: NewsletterCallout
    footnote: string
    cta?: NewsletterCta
}

export interface NewsletterVideoSection extends NewsletterSectionBase {
    kind: 'video'
    video: NewsletterVideo
}

export interface NewsletterReadingSection extends NewsletterSectionBase {
    kind: 'reading'
    books: { title: string; text: string; href: string }[]
}

export type NewsletterSection =
    | NewsletterFeatureSection
    | NewsletterHitsSection
    | NewsletterRollupSection
    | NewsletterVideoSection
    | NewsletterReadingSection

export interface NewsletterIssue {
    slug: string
    permalink_path: string
    published_at: Date
    cover_image: string
    /** Masthead line above the title, e.g. "What's new on my.minmatar.org". */
    eyebrow: string
    period_label: string
    dek: string
    /** Video shown above the contents strip. */
    lead_video?: NewsletterVideo
    sections: NewsletterSection[]
    footer: {
        thanks: string
        data_note: string
        /** html */
        help: string
    }
}
