import { describe, expect, it } from 'vitest'

import {
    merge_content_stream,
    sort_content_stream,
    type ContentStreamItem,
} from '@helpers/content_stream'
import type { PostListUI } from '@dtypes/layout_components'

function item(partial: Partial<ContentStreamItem> & Pick<ContentStreamItem, 'id' | 'published_at'>): ContentStreamItem {
    return {
        kind: 'post',
        href: '/',
        title: partial.id,
        excerpt: '',
        cover: '',
        featured: false,
        ...partial,
    }
}

describe('content_stream', () => {
    it('sorts featured items before non-featured, then by published_at descending', () => {
        const sorted = sort_content_stream([
            item({ id: 'old', published_at: new Date('2024-01-01T00:00:00Z') }),
            item({ id: 'featured-old', published_at: new Date('2023-01-01T00:00:00Z'), featured: true }),
            item({ id: 'new', published_at: new Date('2025-01-01T00:00:00Z') }),
            item({ id: 'featured-new', published_at: new Date('2024-06-01T00:00:00Z'), featured: true }),
        ])

        expect(sorted.map((entry) => entry.id)).toEqual([
            'featured-new',
            'featured-old',
            'new',
            'old',
        ])
    })

    it('merges posts with static campaign items by date', () => {
        const static_items: ContentStreamItem[] = [
            item({
                id: 'campaign-1',
                kind: 'campaign',
                published_at: new Date('2026-06-18T00:00:00Z'),
            }),
        ]
        const posts: PostListUI[] = [
            {
                post_id: 1,
                title: 'Recent post',
                state: 'published',
                slug: 'recent-post',
                date_posted: new Date('2026-08-01T00:00:00Z'),
                user_id: 1,
                author: { character_id: 1, character_name: 'Pilot' },
                tags: ['Propaganda'],
                image: '/images/propaganda-cover.jpg',
            },
        ]

        const merged = merge_content_stream(static_items, posts)

        expect(merged[0].id).toBe('post-1')
        expect(merged[1].id).toBe('campaign-1')
    })

    it('sorts warzone items with campaigns by published_at', () => {
        const sorted = sort_content_stream([
            item({
                id: 'campaign-1',
                kind: 'campaign',
                published_at: new Date('2026-06-18T00:00:00Z'),
            }),
            item({
                id: 'warzone-yc128-07',
                kind: 'warzone',
                published_at: new Date('2026-07-31T00:00:00Z'),
            }),
        ])

        expect(sorted.map((entry) => entry.id)).toEqual([
            'warzone-yc128-07',
            'campaign-1',
        ])
    })
})
