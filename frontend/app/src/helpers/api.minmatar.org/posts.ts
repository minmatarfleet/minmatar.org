import type { Post, PostParams, PostTag, PostRequest } from '@dtypes/api.minmatar.org'
import { query_string } from '@helpers/string'
import { api_request, api_response, api_status_is } from '@helpers/api.minmatar.org/client'

const API_ENDPOINT =  `${import.meta.env.API_URL}/api/blog`

export async function get_posts(post_request:PostRequest) {
    const { user_id, tag_id, tribe_group_id, page_size, page_num, status } = post_request

    const query_params = {
        ...(user_id && { user_id }),
        ...(tag_id && { tag_id }),
        ...(tribe_group_id && { tribe_group_id }),
        ...(page_size && { page_size }),
        ...(page_num && { page_num }),
        ...(status && { status }),
    };

    const query = query_string(query_params)

    const ENDPOINT = `${API_ENDPOINT}/posts${query ? `?${query}` : ''}`

    try {
        const response = await api_response(ENDPOINT)

        const total_posts = response.headers.get('x-total-count')

        return {
            total_posts: total_posts ? parseInt(total_posts) : 0,
            posts: await response.json() as Post[]
        }
    } catch (error) {
        throw new Error(`Error fetching posts: ${error.message}`, { cause: error.cause });
    }
}

export async function get_post(post_id:number) {
    return await api_request<Post>(`${API_ENDPOINT}/posts/${post_id}`, {
        error: 'Error fetching post',
    })
}

export async function create_post(access_token:string, post:PostParams) {
    return await api_request<Post>(`${API_ENDPOINT}/posts`, {
        method: 'POST',
        token: access_token,
        body: post,
        error: 'Error creating post',
    })
}

export async function update_post(access_token:string, post_id:number, post:PostParams) {
    return await api_request<Post>(`${API_ENDPOINT}/posts/${post_id}`, {
        method: 'PATCH',
        token: access_token,
        body: post,
        error: 'Error updating post',
    })
}

export async function delete_post(access_token:string, post_id:number) {
    return await api_status_is(`${API_ENDPOINT}/posts/${post_id}`, {
        method: 'DELETE',
        token: access_token,
        error: 'Error deleting post',
    })
}

export async function get_posts_tags() {
    return await api_request<PostTag[]>(`${API_ENDPOINT}/tags`, {
        error: 'Error fetching post tags',
    })
}
