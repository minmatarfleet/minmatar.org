import { useTranslations } from '@i18n/utils';
import type { PostListUI, PostUI, Posts } from '@dtypes/layout_components'
import type { PostRequest } from '@dtypes/api.minmatar.org'
import { get_posts, get_post, get_posts_tags } from '@helpers/api.minmatar.org/posts'
import { get_users_character, get_user_character } from '@helpers/fetching/characters'
import { unique_values } from '@helpers/array'

const t = useTranslations('en');

export async function fetch_posts(post_request:PostRequest) {
    const { total_posts, posts } = await get_posts(post_request)
    
    const posts_tags = await get_posts_tags()

    const user_ids = unique_values(posts.map(post => post.user_id))
    const authors = await get_users_character(user_ids)

    const chunk = posts.map(post => {
        const tags = post.tag_ids.map(tag_id => posts_tags.find(posts_tag => posts_tag.tag_id === tag_id)?.tag)
        const author = authors.find(author => author.user_id === post.user_id)
        const image = post.image

        return {
            post_id: post.post_id,
            title: post.title,
            date_posted: post.date_posted,
            slug: post.slug,
            tags: tags,
            user_id: post.user_id,
            state: post.state,
            author: {
                character_id: author?.character_id ?? 0,
                character_name: author?.character_name ?? t('unknown_character'),
            },
            ...(image && { image }),
        } as PostListUI
    })
    
    return {
        total: total_posts,
        chunk: chunk,
    } as Posts
}

export async function fetch_post(post_id:number) {
    let api_post = await get_post(post_id)

    if (!api_post) return null
    
    const posts_tags = await get_posts_tags()
    
    const tags = api_post.tag_ids.map(tag_id => posts_tags.find(posts_tag => posts_tag.tag_id === tag_id)?.tag)
    const author = await get_user_character(api_post.user_id)

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
            character_id: author?.character_id ?? 0,
            character_name: author?.character_name ?? t('unknown_character'),
        },
    } as PostUI
}

export async function fetch_user_posts(post_request:PostRequest) {
    const { total_posts, posts } = await get_posts(post_request)
    
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
        } as PostListUI
    })
}

export async function fetch_posts_grouped_by_tags() {
    const { total, chunk } = await fetch_posts({ status: 'published' })

    const posts_tags = await get_posts_tags()
    const tags_by_id: Record<string, string> = {}

    for (const post_tag of posts_tags)
        tags_by_id[post_tag.tag_id] = post_tag.tag

    const posts_by_tag: Record<string, PostListUI[]> = {}

    for (const post of chunk) {
        const tag_id = post.tags[0]
        if (!tag_id) continue
        
        (posts_by_tag[tag_id] ??= []).push(post)
    }

    return posts_by_tag
}