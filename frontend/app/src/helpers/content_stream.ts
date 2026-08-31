import type { PostListUI } from '@dtypes/layout_components'
import type { CampaignMeta } from '@/data/campaigns'
import { campaigns } from '@/data/campaigns'

export type ContentStreamKind = 'campaign' | 'siege' | 'warzone' | 'post'

export type ContentStreamItem = {
    id: string
    kind: ContentStreamKind
    href: string
    title: string
    excerpt: string
    cover: string
    published_at: Date
    featured?: boolean
    tags?: string[]
    isk_destroyed?: number
    period_key?: string
    campaign?: CampaignMeta
    post?: PostListUI
}

export function campaign_to_stream_item(
    campaign: CampaignMeta,
    resolve: (key: string) => string,
): ContentStreamItem {
    return {
        id: `campaign-${campaign.slug}`,
        kind: campaign.kind,
        href: campaign.path,
        title: resolve(campaign.nameKey),
        excerpt: resolve(campaign.excerptKey),
        cover: campaign.coverImage,
        published_at: campaign.published_at,
        isk_destroyed: campaign.iskDestroyed,
        period_key: campaign.periodKey,
        campaign,
    }
}

export function post_to_stream_item(post: PostListUI): ContentStreamItem {
    return {
        id: `post-${post.post_id}`,
        kind: 'post',
        href: `/alliance/propaganda/${post.post_id}`,
        title: post.title,
        excerpt: '',
        cover: post.image || '',
        published_at: new Date(post.date_posted),
        tags: post.tags?.filter((tag): tag is string => Boolean(tag)) ?? [],
        post,
    }
}

export function sort_content_stream(items: ContentStreamItem[]): ContentStreamItem[] {
    return [...items].sort((a, b) => {
        const featured_a = a.featured ? 1 : 0
        const featured_b = b.featured ? 1 : 0
        if (featured_a !== featured_b) {
            return featured_b - featured_a
        }
        return b.published_at.getTime() - a.published_at.getTime()
    })
}

export function build_static_stream_items(resolve: (key: string) => string): ContentStreamItem[] {
    const campaign_items = campaigns.map((campaign) => campaign_to_stream_item(campaign, resolve))
    return sort_content_stream(campaign_items)
}

export function merge_content_stream(
    static_items: ContentStreamItem[],
    posts: PostListUI[],
): ContentStreamItem[] {
    const post_items = posts.map(post_to_stream_item)
    return sort_content_stream([...static_items, ...post_items])
}

export const CONTENT_STREAM_PAGE_SIZE = 21
