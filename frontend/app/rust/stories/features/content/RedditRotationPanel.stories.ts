import { expect, within } from 'storybook/test'
import RedditRotationPanel from '@components/blocks/RedditRotationPanel.astro'
import { rotation_published, rotation_draft, rotation_draft_empty } from '../../../fixtures/features/content'

export default {
    title: 'Features/Content/RedditRotationPanel',
    component: RedditRotationPanel,
    parameters: {
        docs: {
            description: {
                component: [
                    'The Reddit rotation for corp recruitment posts: one table per month listing when each corp posts, the title and the delivery status, with Regenerate and Publish on a draft month and Submit now / Link to Discord on a post. Each action posts to the `reddit_review_component` partial and gets the panel back.',
                    'It is the Rotation tab of `/admin/reddit-review/`. The scenarios show a published month with every post status, a draft month, an empty draft, no months at all, and the error and notice banners.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        months: { control: 'object', description: 'The rotation months, newest first.' },
        error: { control: 'text', description: 'Error banner after a failed action.' },
        notice: { control: 'text', description: 'Success notice after an action.' },
    },
    args: { months: [rotation_draft, rotation_published], error: null, notice: null },
}

export const DraftAndPublished = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { name: 'December 2026' })).toBeVisible()
        await expect(canvas.getByRole('heading', { name: 'November 2026' })).toBeVisible()
        // Only the draft month can be regenerated or published.
        await expect(canvas.getAllByRole('button', { name: 'Regenerate' }).length).toBe(1)
        await expect(canvas.getAllByRole('button', { name: 'Publish' }).length).toBe(1)
        await expect(canvas.getByText('2 posts')).toBeVisible()
        await expect(canvas.getByText('6 posts')).toBeVisible()
    },
}

export const PublishedMonthStatuses = {
    args: { months: [rotation_published] },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Posted')).toBeVisible()
        await expect(canvas.getByText('Confirmed')).toBeVisible()
        await expect(canvas.getByText('Failed')).toBeVisible()
        await expect(canvas.getByText('CEO reminded')).toBeVisible()
        await expect(canvas.getAllByRole('link', { name: 'Open on Reddit' })[0]).toHaveAttribute('href', 'https://www.reddit.com/r/Eve/comments/1abc123/')
        // The failed post has no Discord channel, so it offers to link one.
        await expect(canvas.getAllByRole('button', { name: 'Link to Discord' }).length).toBe(1)
        await expect(canvas.getAllByRole('button', { name: 'Submit now' }).length).toBe(6)
    },
}

export const EmptyDraftMonth = {
    args: { months: [rotation_draft_empty] },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('No posts in this month.')).toBeVisible()
        await expect(canvas.getByRole('button', { name: 'Regenerate' })).toBeVisible()
    },
}

export const NoMonths = {
    args: { months: [] },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByText('No rotation months yet.')).toBeVisible()
    },
}

export const ErrorAndNotice = {
    args: { months: [rotation_draft], error: 'Reddit refused the post: rate limited.', notice: 'Month published.' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('alert')).toHaveTextContent('Reddit refused the post: rate limited.')
        await expect(canvas.getByRole('status')).toHaveTextContent('Month published.')
    },
}
