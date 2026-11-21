import { expect, within } from 'storybook/test'
import PostTile from '@components/blocks/PostTile.astro'
import { tile_plain, tile_cover, tile_members, tile_tagged, tile_long } from '../../../fixtures/features/content'

export default {
    title: 'Features/Content/PostTile',
    component: PostTile,
    parameters: {
        docs: {
            description: {
                component: [
                    'A blog tile: cover (or the group crest when the post has none), visibility, title, a two-line excerpt, author and date.',
                    'It fills the Posts tab of a tribe group page. The scenarios show a post with the crest fallback, one with a cover image, a members-only post, a post a pilot wrote that the group tagged, and long text.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        post: { control: 'object', description: 'The tile data (PostTileUI).' },
        crest_url: { control: 'text', description: 'Stands in for the cover when the post has none.' },
    },
    args: { post: tile_plain, crest_url: '/images/fleet-logo-square.svg' },
}

export const CrestFallback = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { name: 'Amamake holds' })).toBeVisible()
        await expect(canvasElement.querySelector('.post-tile__cover--crest img')).toHaveAttribute('src', '/images/fleet-logo-square.svg')
        await expect(canvas.getByText(/Kel'dar Atram/)).toBeVisible()
        await expect(canvasElement.querySelector('time')).toHaveAttribute('datetime', '2026-11-14T19:20:00Z')
        await expect(canvas.getByRole('link', { name: 'Amamake holds' })).toHaveAttribute('href', '/alliance/propaganda/1401')
    },
}

export const WithCover = {
    args: { post: tile_cover },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelector('img.post-tile__cover')).toHaveAttribute('src', '/images/fleets-cover.jpg')
        await expect(canvasElement.querySelector('.post-tile__cover--crest')).toBeNull()
    },
}

export const MembersOnly = {
    args: { post: tile_members },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelector('.post-tile__tags .visibility-tag')).not.toBeNull()
        await expect(within(canvasElement).getByText(/Hek Roamer/)).toBeVisible()
    },
}

export const TaggedByGroup = {
    args: { post: tile_tagged },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelector('.post-tile__tags .tag')).not.toBeNull()
        await expect(canvasElement.querySelector('.visibility-tag')).toBeNull()
    },
}

export const LongText = {
    args: { post: tile_long },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByRole('heading', { name: tile_long.title })).toBeVisible()
        await expect(canvasElement.querySelector('.post-tile__excerpt')?.textContent?.length).toBeGreaterThan(300)
    },
}
