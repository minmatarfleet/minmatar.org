import { expect, within } from 'storybook/test'
import PostsList from '@components/blocks/PostsList.astro'
import { posts_typical, posts_busy } from '../../../fixtures/features/content'

export default {
    title: 'Features/Content/PostsList',
    component: PostsList,
    parameters: {
        docs: {
            description: {
                component: [
                    'A paginated grid of PostItem rows with a pager above it. The pager shows the neighbouring pages, plus first and last links once there are more than four pages.',
                    'It is the body of `/alliance/propaganda/` and the group news pages. The scenarios show a short list on page one, a busy page in the middle of a long run, the last page and an empty page.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        posts: { control: 'object', description: 'The posts on this page.' },
        total_pages: { control: { type: 'number', min: 1 }, description: 'How many pages there are in all.' },
        current_page: { control: { type: 'number', min: 1 }, description: 'The page shown; its pager button is the active one.' },
    },
    args: { posts: posts_typical, total_pages: 3, current_page: 1 },
}

export const Typical = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvasElement.querySelectorAll('h3').length).toBe(5)
        await expect(canvas.getByRole('link', { name: posts_typical[0].title })).toHaveAttribute('href', '/alliance/propaganda/1401')
        // Three pages, so no first/last buttons.
        await expect(canvas.queryByText('First')).toBeNull()
    },
}

export const Busy = {
    args: { posts: posts_busy, total_pages: 9, current_page: 5 },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelectorAll('h3').length).toBe(12)
        await expect(canvasElement.querySelector('#posts-list')).not.toBeNull()
        // More than four pages adds first and last.
        await expect(canvasElement.textContent).toMatch(/First/i)
        await expect(canvasElement.textContent).toMatch(/Last/i)
    },
}

export const LastPage = {
    args: { posts: posts_typical.slice(0, 2), total_pages: 9, current_page: 9 },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelectorAll('h3').length).toBe(2)
        await expect(canvasElement.textContent).toContain('9')
    },
}

export const Empty = {
    args: { posts: [], total_pages: 1, current_page: 1 },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelectorAll('h3').length).toBe(0)
        await expect(canvasElement.querySelector('#posts-list')).not.toBeNull()
    },
}
