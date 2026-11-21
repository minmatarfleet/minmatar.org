import { expect, within } from 'storybook/test'
import NewsReel from '@components/blocks/NewsReel.astro'
import { posts_typical, posts_busy } from '../../../fixtures/features/content'

export default {
    title: 'Features/Content/NewsReel',
    component: NewsReel,
    parameters: {
        docs: {
            description: {
                component: [
                    'The "Recent events" bar fixed to the bottom of the page on large screens. With fewer than five posts the badges sit still; with five or more they scroll in a Marquee. Each badge links to the post and shows the series icon, the series and post number, and the date.',
                    'The scenarios show a short reel, a scrolling reel and an empty reel. The manage-content menu (`show_manage_content`) fetches the creator accounts in its frontmatter, so it is not shown here.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        posts: { control: 'object', description: 'The recent posts, newest first.' },
        show_manage_content: { control: 'boolean', description: 'Shows the manage-content menu (fetches data; not rendered here).' },
    },
    args: { posts: posts_typical.slice(0, 3), show_manage_content: false },
}

export const FewPosts = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Recent events')).toBeInTheDocument()
        await expect(canvasElement.querySelectorAll('.news-reel-badge').length).toBe(3)
        await expect(canvasElement.querySelector('a.news-reel-badge')).toHaveAttribute('href', '/alliance/propaganda/1401')
        await expect(canvas.getByText('Metropolis Daily News #1401')).toBeInTheDocument()
    },
}

export const Scrolling = {
    args: { posts: posts_busy.slice(0, 8) },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        // The marquee repeats its items to loop, so there are at least as many badges as posts.
        await expect(canvasElement.querySelectorAll('.news-reel-badge').length).toBeGreaterThanOrEqual(8)
        await expect(canvasElement.querySelector('.marquee-container')).not.toBeNull()
    },
}

export const Empty = {
    args: { posts: [] },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByText('Recent events')).toBeInTheDocument()
        await expect(canvasElement.querySelectorAll('.news-reel-badge').length).toBe(0)
    },
}
