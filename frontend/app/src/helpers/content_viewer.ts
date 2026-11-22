/**
 * ContentViewer: what a post is, so the viewer can show it the right way.
 *
 * Posts share one model; their body says what they are. Video posts hold a
 * <lite-youtube> (or a YouTube link) or Reddit's embedded player, propaganda
 * is one image (or a gallery of several) and little else, everything longer
 * is an article.
 */

export type ViewerPost =
    | { kind: 'video', embed_url: string, text: string }
    | { kind: 'image', image: string, text: string }
    | { kind: 'gallery', images: string[], text: string }
    | { kind: 'article' }

const YOUTUBE_ID = [
    /<lite-youtube[^>]*\svideoid="([\w-]{11})"/i,
    /youtube(?:-nocookie)?\.com\/(?:watch\?v=|embed\/|shorts\/)([\w-]{11})/i,
    /youtu\.be\/([\w-]{11})/i,
]

const IMAGE = /!\[[^\]]*\]\(([^)\s]+)[^)]*\)/g

// Reddit's embedded player, as the importer writes it for Reddit-hosted video.
const REDDIT_EMBED = /<iframe[^>]*\ssrc="(https:\/\/embed\.reddit\.com\/[^"]+)"/i

// Text that doesn't count as the post's own words: the hidden thumbnail block
// video posts carry, the "Posted on Reddit" source link, HTML tags.
function own_words(content: string): string {
    return content
        .replace(/<div class="hidden">[\s\S]*?<\/div>/gi, '')
        .replace(/<lite-youtube[\s\S]*?<\/lite-youtube>/gi, '')
        .replace(/<iframe[\s\S]*?<\/iframe>/gi, '')
        .replace(IMAGE, '')
        .replace(/\[Posted on Reddit\]\([^)]*\)/gi, '')
        .replace(/<[^>]+>/g, '')
        .trim()
}

/** Up to this many characters of the post's own words, an image post is still a poster. */
export const POSTER_TEXT_LIMIT = 280

export function classify_post(content: string): ViewerPost {
    const text = own_words(content ?? '')

    const reddit = content?.match(REDDIT_EMBED)
    if (reddit) return { kind: 'video', embed_url: reddit[1].replaceAll('&amp;', '&'), text }

    for (const pattern of YOUTUBE_ID) {
        const match = content?.match(pattern)
        if (match) return { kind: 'video', embed_url: youtube_embed_url(match[1]), text }
    }

    // The hidden still of a video post is a card image, not part of the post.
    const shown = (content ?? '').replace(/<div class="hidden">[\s\S]*?<\/div>/gi, '')
    const images = [...shown.matchAll(IMAGE)].map((m) => m[1])
    if (text.length <= POSTER_TEXT_LIMIT) {
        if (images.length === 1) return { kind: 'image', image: images[0], text }
        if (images.length > 1) return { kind: 'gallery', images, text }
    }

    return { kind: 'article' }
}

/** The privacy-friendly embed, playing as it opens (the viewer opened on a click). */
export function youtube_embed_url(video_id: string): string {
    return `https://www.youtube-nocookie.com/embed/${video_id}?autoplay=1&rel=0&modestbranding=1`
}

/** The "Posted on Reddit" source a post links to, if any. */
export function post_source_url(content: string): string | null {
    return content?.match(/\[Posted on Reddit\]\(([^)\s]+)\)/i)?.[1] ?? null
}

/** The public page of a post (what the viewer's "Open full page" links to). */
export function post_page_path(post: { post_id: number, slug?: string | null }): string {
    return post.slug ? `/alliance/propaganda/${post.slug}-${post.post_id}` : `/alliance/propaganda/${post.post_id}`
}
