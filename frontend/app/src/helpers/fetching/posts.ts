import type { PostListUI, PostUI } from '@dtypes/layout_components'
import { get_posts, get_post, get_posts_tags } from '@helpers/api.minmatar.org/posts'
import { get_user_character } from '@helpers/fetching/characters'

export async function fetch_posts(user_id:number | null = null, tag_id:number | null = null) {
    let api_posts = await get_posts(user_id, tag_id)
    
    const posts_tags = await get_posts_tags()
    api_posts = api_posts.filter(api_post => api_post.state === 'published')
    
    return await Promise.all(api_posts.map(async (api_post) => {
        const tags = api_post.tag_ids.map(tag_id => posts_tags.find(posts_tag => posts_tag.tag_id === tag_id)?.tag)
        const author = await get_user_character(api_post.user_id)

        return {
            post_id: api_post.post_id,
            title: api_post.title,
            date_posted: api_post.date_posted,
            slug: api_post.slug,
            tags: tags,
            user_id: api_post.user_id,
            state: api_post.state,
            author: {
                character_id: author.character_id,
                character_name: author.character_name,
            },
        } as PostListUI
    }))
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
            character_id: author.character_id,
            character_name: author.character_name,
        },
    } as PostUI
}

export async function fetch_user_posts(user_id:number | null = null, tag_id:number | null = null) {
    let api_posts = await get_posts(user_id, tag_id)
    
    const posts_tags = await get_posts_tags()
    
    return await Promise.all(api_posts.map(async (api_post) => {
        const tags = api_post.tag_ids.map(tag_id => posts_tags.find(posts_tag => posts_tag.tag_id === tag_id)?.tag)

        return {
            post_id: api_post.post_id,
            title: api_post.title,
            date_posted: api_post.date_posted,
            slug: api_post.slug,
            state: api_post.state,
            tags: tags,
            user_id: api_post.user_id,
        } as PostListUI
    }))
}