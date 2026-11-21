import { expect, within } from 'storybook/test'
import PropagandaGrid from '@components/blocks/PropagandaGrid.astro'
import { posts_busy, posts_by_state, EDITOR_ID } from '../../../fixtures/features/content'

export default {
    title: 'Features/Content/PropagandaGrid',
    component: PropagandaGrid,
    parameters: {
        docs: {
            description: {
                component: [
                    'A section of poster cards in a fill grid, with an intro paragraph. Each section on the propaganda page (Metropolis, Frontlines, posters) is one grid; the editor view of `/account/posts` reuses it with actions on the pilot\'s own posts.',
                    'The scenarios show the public grid, the editor grid with posts in every state, and an empty section.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        title: { control: 'text', description: 'Section title (also feeds the anchor).' },
        description: { control: 'text', description: 'Intro paragraph; hidden in the editor view.' },
        posts: { control: 'object', description: 'The posts in the section.' },
        cover: { control: 'text', description: 'When set, the grid is limited to the column width.' },
        is_video: { control: 'boolean', description: 'Video posts (wider tiles).' },
        editor_id: { control: 'number', description: 'The signed-in user id.' },
        is_editing: { control: 'boolean', description: 'Editor view.' },
        hash: { control: 'text', description: 'Anchor id of the section.' },
        as_subsection: { control: 'boolean', description: 'Render the heading as h3.' },
    },
    args: {
        title: 'Metropolis Daily News',
        description: 'Daily news from the Minmatar front lines, written by pilots.',
        posts: posts_busy.slice(0, 8),
        is_editing: false,
        hash: 'metropolis',
    },
}

export const Public = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Daily news from the Minmatar front lines, written by pilots.')).toBeVisible()
        await expect(canvasElement.querySelectorAll('h3').length).toBe(8)
        await expect(canvas.getByRole('link', { name: posts_busy[0].title })).toHaveAttribute('href', '/alliance/propaganda/1500')
    },
}

export const Busy = {
    args: { posts: posts_busy },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelectorAll('h3').length).toBe(12)
    },
}

export const EditingOwnPosts = {
    args: { posts: posts_by_state, is_editing: true, editor_id: EDITOR_ID },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvasElement.querySelectorAll('h3').length).toBe(4)
        // The description is for readers, not editors.
        await expect(canvas.queryByText('Daily news from the Minmatar front lines, written by pilots.')).toBeNull()
        await expect(canvas.getAllByRole('button', { name: 'Publish' }).length).toBe(2)
    },
}

export const Empty = {
    args: { posts: [] },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelectorAll('h3').length).toBe(0)
        await expect(within(canvasElement).getByText('Daily news from the Minmatar front lines, written by pilots.')).toBeVisible()
    },
}
