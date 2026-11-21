import { expect, within } from 'storybook/test'
import PostItem from '@components/blocks/PostItem.astro'
import {
    post_metropolis, post_alliance, post_group, post_long_title, post_no_tags,
} from '../../../fixtures/features/content'

export default {
    title: 'Features/Content/PostItem',
    component: PostItem,
    parameters: {
        docs: {
            description: {
                component: [
                    'One row of a news list: the author portrait (or the fleet logo for alliance posts), the title linking to the post, the group byline, tags and date.',
                    'It appears in the news carousel on the home page and in PostsList on `/alliance/propaganda/`. The scenarios cover a character post, an alliance post, a group post with its byline, a very long title and a post with no tags.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        post: { control: 'object', description: 'The post as the list API returns it (PostListUI).' },
    },
    args: { post: post_metropolis },
}

export const CharacterPost = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        const link = canvas.getByRole('link', { name: post_metropolis.title })
        await expect(link).toHaveAttribute('href', '/alliance/propaganda/1401')
        await expect(canvas.getByText('Metropolis')).toBeVisible()
        await expect(canvasElement.querySelector('img[src*="2112954532"]')).not.toBeNull()
    },
}

export const AlliancePost = {
    args: { post: post_alliance },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        // Author id 0 has no portrait: the fleet logo stands in, named after the author.
        await expect(canvas.getByRole('img', { name: 'Minmatar Fleet Alliance' })).toHaveAttribute('src', '/images/fleet-logo-square.svg')
        await expect(canvas.getByRole('link', { name: post_alliance.title })).toHaveAttribute('href', '/alliance/propaganda/1395')
    },
}

export const GroupPost = {
    args: { post: post_group },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Dispatches')).toBeVisible()
        await expect(canvas.getByText(/Rattini Pilot|Hek Roamer/)).toBeVisible()
        await expect(canvasElement.textContent).toContain('Dreadnoughts')
    },
}

export const LongTitle = {
    args: { post: post_long_title },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const link = within(canvasElement).getByRole('link', { name: post_long_title.title })
        await expect(link).toHaveAttribute('href', '/alliance/propaganda/1388')
    },
}

export const NoTags = {
    args: { post: post_no_tags },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('link', { name: post_no_tags.title })).toBeVisible()
        await expect(canvasElement.querySelectorAll('.tag').length).toBe(0)
    },
}
