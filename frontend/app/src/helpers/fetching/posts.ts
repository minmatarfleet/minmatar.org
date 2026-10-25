import { useTranslations } from '@i18n/utils';
import type { PostListUI, PostUI, Posts } from '@dtypes/layout_components'
import type { Post, PostRequest, PostStates, RestrictedResponse } from '@dtypes/api.minmatar.org'
import { get_posts, get_post, get_post_access, get_posts_tags } from '@helpers/api.minmatar.org/posts'
import { host_group_ref_ui } from '@helpers/post_publishing'

const t = useTranslations('en');

/** The group fields every post card needs: group posts only, alliance posts add nothing. */
export function post_host_fields(post:{ host_group?: Post['host_group'], members_only?: boolean }) {
    const host_group = host_group_ref_ui(post.host_group)

    return host_group
        ? { host_group: host_group, members_only: Boolean(post.members_only) }
        : {}
}

/** With a token, members-only group posts the viewer may see are included. */
export async function fetch_posts(post_request:PostRequest, access_token?:string | false | null) {
    const { total_posts, posts } = await get_posts(post_request, access_token)
    
    const posts_tags = await get_posts_tags()

    const chunk = posts.map(post => {
        const tags = post.tag_ids.map(tag_id => posts_tags.find(posts_tag => posts_tag.tag_id === tag_id)?.tag)

        return {
            post_id: post.post_id,
            title: post.title,
            date_posted: post.date_posted,
            slug: post.slug,
            tags: tags,
            user_id: post.user_id,
            state: post.state,
            author: {
                character_id: post.author_character_id ?? 0,
                character_name: post.author_character_name ?? t('index.page_title'),
            },
            // The API sends the first image in the post body as its cover.
            ...(post.image && { image: post.image }),
            ...post_host_fields(post),
        } as PostListUI
    })
    
    return {
        total: total_posts,
        chunk: chunk,
    } as Posts
}

export async function fetch_post(post_id:number, access_token?:string | false | null) {
    let api_post = await get_post(post_id, access_token)

    if (!api_post) return null
    
    return await post_ui(api_post)
}

/**
 * A post, or the group that hosts it when it is a members-only group post the
 * viewer can't see (403 RestrictedResponse). Other errors throw.
 */
export async function fetch_post_access(post_id:number, access_token?:string | false | null):Promise<
    { post: PostUI, restricted: null } | { post: null, restricted: RestrictedResponse }
> {
    const { post: api_post, restricted } = await get_post_access(post_id, access_token)

    if (!api_post) return { post: null, restricted: restricted as RestrictedResponse }

    return { post: await post_ui(api_post), restricted: null }
}

async function post_ui(api_post:Post) {
    const posts_tags = await get_posts_tags()
    
    const tags = api_post.tag_ids.map(tag_id => posts_tags.find(posts_tag => posts_tag.tag_id === tag_id)?.tag)

    return {
        post_id: api_post.post_id,
        title: api_post.title,
        date_posted: api_post.date_posted,
        slug: api_post.slug,
        tags: tags,
        user_id: api_post.user_id,
        excerpt: api_post.seo_description,
        content: api_post.content,
        state: api_post.state,
        author: {
            character_id: api_post.author_character_id ?? 0,
            character_name: api_post.author_character_name ?? t('index.page_title'),
        },
        ...post_host_fields(api_post),
    } as PostUI
}

/** A pilot's own posts. Pass their token to include their members-only group posts. */
export async function fetch_user_posts(post_request:PostRequest, access_token?:string | false | null) {
    const { total_posts, posts } = await get_posts(post_request, access_token)
    
    const posts_tags = await get_posts_tags()

    return posts.map(post => {
        const tags = post.tag_ids.map(tag_id => posts_tags.find(posts_tag => posts_tag.tag_id === tag_id)?.tag)

        return {
            post_id: post.post_id,
            title: post.title,
            date_posted: post.date_posted,
            slug: post.slug,
            state: post.state,
            tags: tags,
            user_id: post.user_id,
            ...post_host_fields(post),
        } as PostListUI
    })
}

export async function fetch_user_post(post_id:number, access_token?:string | false | null) {
    let api_post = await get_post(post_id, access_token)
    
    const posts_tags = await get_posts_tags()

    const tags = api_post.tag_ids.map(tag_id => posts_tags.find(posts_tag => posts_tag.tag_id === tag_id)?.tag)

    return {
        post_id: api_post.post_id,
        title: api_post.title,
        date_posted: api_post.date_posted,
        slug: api_post.slug,
        state: api_post.state,
        tags: tags,
        user_id: api_post.user_id,
        ...post_host_fields(api_post),
    } as PostListUI
}

const VALID_TAGS = [
    'Metropolis',
    'Frontlines',
    'Propaganda',
    'Metro Daily News',
    'The Cope',
    'Videos',
    'Rust and Blood',
    'Waifu Wars',
    'Dispatches',
]

export async function fetch_posts_grouped_by_tags(post_request:PostRequest, filter_trash:boolean = false, access_token?:string | false | null) {
    let { total, chunk } = await fetch_posts(post_request, access_token)

    const posts_tags = await get_posts_tags()
    const tags_by_id: Record<string, string> = {}

    for (const post_tag of posts_tags)
        tags_by_id[post_tag.tag_id] = post_tag.tag

    const posts_by_tag: Record<string, PostListUI[]> = {}
    let total_post_count = 0

    if (filter_trash)
        chunk = chunk.filter(post => post.state !== 'trash')

    for (const post of chunk) {
        const tag_id = post.tags[0]
        if (!tag_id || !VALID_TAGS.includes(tag_id)) continue
        
        (posts_by_tag[tag_id] ??= []).push(post)
        total_post_count++
    }

    return {
        posts_by_tag: posts_by_tag,
        post_count: total_post_count,
    }
}

export async function fetch_posts_by_tags(tag_id:number, filter_trash:boolean = false) {
    let { total, chunk } = await fetch_posts({
        tag_id: tag_id
    })

    if (filter_trash)
        chunk = chunk.filter(post => post.state !== 'trash')

    return chunk
}
