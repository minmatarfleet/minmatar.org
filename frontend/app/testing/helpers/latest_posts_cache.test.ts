// @vitest-environment node
import { afterEach, beforeEach, expect, test, vi } from 'vitest'

const api = vi.hoisted(() => ({
    get_posts: vi.fn(),
    get_posts_tags: vi.fn(),
}))

vi.mock('@helpers/api.minmatar.org/posts', async (original) => ({
    ...(await original<typeof import('@helpers/api.minmatar.org/posts')>()),
    get_posts: api.get_posts,
    get_posts_tags: api.get_posts_tags,
}))

import { fetch_latest_published_posts, reset_latest_posts_cache } from '@helpers/fetching/posts'

const POST = {
    post_id: 1,
    title: 'Hello',
    date_posted: '2026-11-01T00:00:00Z',
    slug: 'hello',
    tag_ids: [7],
    user_id: 1,
    state: 'published',
    author_character_id: 5,
    author_character_name: 'Pilot',
}

beforeEach(() => {
    reset_latest_posts_cache(60_000)
    api.get_posts.mockReset().mockResolvedValue({ total_posts: 1, posts: [POST] })
    api.get_posts_tags.mockReset().mockResolvedValue([{ tag_id: 7, tag: 'News' }])
})

afterEach(() => {
    reset_latest_posts_cache(null)
})

test('repeat visits within the TTL share one fetch, without a token', async () => {
    const first = await fetch_latest_published_posts(3)
    const second = await fetch_latest_published_posts(3)

    expect(first.chunk[0]).toMatchObject({ title: 'Hello', tags: ['News'] })
    expect(second).toEqual(first)
    expect(api.get_posts).toHaveBeenCalledTimes(1)
    expect(api.get_posts).toHaveBeenCalledWith({ page_num: 1, page_size: 3, status: 'published' }, undefined)
})

test('each caller gets its own copy', async () => {
    const first = await fetch_latest_published_posts(3)
    first.chunk[0].title = 'changed by a renderer'

    expect((await fetch_latest_published_posts(3)).chunk[0].title).toBe('Hello')
})

test('a failure is not cached', async () => {
    api.get_posts.mockRejectedValueOnce(new Error('blog down'))

    await expect(fetch_latest_published_posts(3)).rejects.toThrow('blog down')
    expect((await fetch_latest_published_posts(3)).chunk).toHaveLength(1)
    expect(api.get_posts).toHaveBeenCalledTimes(2)
})

test('a TTL of 0 fetches every time', async () => {
    reset_latest_posts_cache(0)

    await fetch_latest_published_posts(3)
    await fetch_latest_published_posts(3)
    expect(api.get_posts).toHaveBeenCalledTimes(2)
})
