import { useTranslations } from '@i18n/utils';
import type { PostListUI, PostUI, PostRequestUI, Posts } from '@dtypes/layout_components'
import type { PostRequest } from '@dtypes/api.minmatar.org'
import { get_posts, get_post, get_posts_tags } from '@helpers/api.minmatar.org/posts'
import { get_users_character, get_user_character } from '@helpers/fetching/characters'
import { paginate, unique_values } from '@helpers/array'

const t = useTranslations('en');

export async function fetch_posts(post_request:PostRequestUI) {
    const { user_id, tag_id } = post_request

    const api_post_request = {
        ...(user_id && { user_id }),
        ...(tag_id && { tag_id }),
    } as PostRequest

    let api_posts = await get_posts(api_post_request)
    api_posts = api_posts.filter(api_post => api_post.state === 'published')

    const total_posts = api_posts.length

    api_posts = paginate(api_posts, post_request.page ?? 1, post_request.page_length ?? 9)
    
    const posts_tags = await get_posts_tags()

    const user_ids = unique_values(api_posts.map(post => post.user_id))
    const authors = await get_users_character(user_ids)

    const chunk = api_posts.map(api_post => {
        const tags = api_post.tag_ids.map(tag_id => posts_tags.find(posts_tag => posts_tag.tag_id === tag_id)?.tag)
        const author = authors.find(author => author.user_id === api_post.user_id)

        return {
            post_id: api_post.post_id,
            title: api_post.title,
            date_posted: api_post.date_posted,
            slug: api_post.slug,
            tags: tags,
            user_id: api_post.user_id,
            state: api_post.state,
            author: {
                character_id: author?.character_id ?? 0,
                character_name: author?.character_name ?? t('unknown_character'),
            },
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

export async function fetch_user_posts(post_request:PostRequestUI) {
    const { user_id, tag_id } = post_request

    const api_post_request = {
        ...(user_id && { user_id }),
        ...(tag_id && { tag_id }),
    } as PostRequest

    let api_posts = await get_posts(api_post_request)
    
    const posts_tags = await get_posts_tags()

    return api_posts.map(api_post => {
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
    })
}