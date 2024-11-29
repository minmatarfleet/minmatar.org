import type { Post, PostParams, PostTag, PostRequest } from '@dtypes/api.minmatar.org'
import { get_error_message, query_string, parse_error_message } from '@helpers/string'

const API_ENDPOINT =  `${import.meta.env.API_URL}/api/blog`

export async function get_posts(post_request:PostRequest) {
    const headers = {
        'Content-Type': 'application/json',
    }

    const { user_id, tag_id, page_size, page_num, status } = post_request

    const query_params = {
        ...(user_id && { user_id }),
        ...(tag_id && { tag_id }),
        ...(page_size && { page_size }),
        ...(page_num && { page_num }),
        ...(status && { status }),
    };

    const query = query_string(query_params)

    const ENDPOINT = `${API_ENDPOINT}/posts${query ? `?${query}` : ''}`

    console.log(`Requesting: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `GET ${ENDPOINT}`
            ))
        }

        const total_posts = response.headers.get('x-total-count')

        return {
            total_posts: total_posts ? parseInt(total_posts) : 0,
            posts: await response.json() as Post[]
        }
    } catch (error) {
        throw new Error(`Error fetching posts: ${error.message}`);
    }
}

export async function get_post(post_id:number) {
    const headers = {
        'Content-Type': 'application/json',
    }

    const ENDPOINT = `${API_ENDPOINT}/posts/${post_id}`

    console.log(`Requesting GET: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers,
        })

        // console.log(response)

        if (!response.ok) {
            let error = await response.json()
            const error_msg = parse_error_message(error.detail)
            error = error_msg ? error_msg : error?.detail

            throw new Error(error ? error : get_error_message(response.status, `GET ${ENDPOINT}`))
        }

        return await response.json() as Post;
    } catch (error) {
        throw new Error(`Error fetching post: ${error.message}`);
    }
}

export async function create_post(access_token:string, post:PostParams) {
    const data = JSON.stringify(post);

    console.log(data)

    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/posts`

    console.log(`Requesting POST: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers,
            body: data,
            method: 'POST'
        })

        // console.log(response)

        if (!response.ok) {
            let error = await response.json()
            const error_msg = parse_error_message(error.detail)
            error = error_msg ? error_msg : error?.detail

            throw new Error(error ? error : get_error_message(response.status, `POST ${ENDPOINT}`))
        }

        return await response.json() as Post;
    } catch (error) {
        throw new Error(`Error creating post: ${error.message}`);
    }
}

export async function update_post(access_token:string, post_id:number, post:PostParams) {
    const data = JSON.stringify(post);

    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/posts/${post_id}`

    console.log(`Requesting PATCH: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers,
            body: data,
            method: 'PATCH'
        })

        // console.log(response)

        if (!response.ok) {
            let error = await response.json()
            const error_msg = parse_error_message(error.detail)
            error = error_msg ? error_msg : error?.detail

            throw new Error(error ? error : get_error_message(response.status, `PATCH ${ENDPOINT}`))
        }

        return await response.json() as Post;
    } catch (error) {
        throw new Error(`Error updating post: ${error.message}`);
    }
}

export async function delete_post(access_token:string, post_id:number) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/posts/${post_id}`

    console.log(`Requesting DELETE: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers,
            method: 'DELETE'
        })

        // console.log(response)

        if (!response.ok) {
            let error = await response.json()
            const error_msg = parse_error_message(error.detail)
            error = error_msg ? error_msg : error?.detail

            throw new Error(error ? error : get_error_message(response.status, `DELETE ${ENDPOINT}`))
        }

        return await response.json() as Post;
    } catch (error) {
        throw new Error(`Error deleting post: ${error.message}`);
    }
}

export async function get_posts_tags() {
    const headers = {
        'Content-Type': 'application/json',
    }

    const ENDPOINT = `${API_ENDPOINT}/tags`

    console.log(`Requesting: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `GET ${ENDPOINT}`
            ))
        }

        return await response.json() as PostTag[];
    } catch (error) {
        throw new Error(`Error fetching post tags: ${error.message}`);
    }
}