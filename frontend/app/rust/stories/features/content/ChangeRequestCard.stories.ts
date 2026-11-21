import { expect, within } from 'storybook/test'
import ChangeRequestCard from '@components/blocks/ChangeRequestCard.astro'
import {
    change_pending_reviewer, change_pending_submitter, change_pending_readonly, change_approved, change_no_diff,
} from '../../../fixtures/features/content'

export default {
    title: 'Features/Content/ChangeRequestCard',
    component: ChangeRequestCard,
    parameters: {
        docs: {
            description: {
                component: [
                    'One doctrine or fitting change request: the target (linking to its page), who submitted it, kind and status tags, the submitter\'s note, the diff, any review note, and the review form. A reviewer gets a note field with Approve and Reject; the submitter can cancel; anyone else just reads. The form posts to the `doctrine_change_queue_component` partial.',
                    'It is the row of the review queue at `/ships/doctrine-changes/`. The scenarios show the reviewer, submitter and read-only views, a decided request and a request with no diff.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        change_request: { control: 'object', description: 'The change request with its diffs and can_review / can_cancel flags.' },
    },
    args: { change_request: change_pending_reviewer },
}

export const ReviewerView = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('link', { name: 'Rifter Fleet Issue (Amamake)' })).toHaveAttribute('href', '/ships/fittings/17/')
        await expect(canvas.getByText(/Submitted by/)).toHaveTextContent("Kel'dar Atram")
        await expect(canvas.getByText('Fitting')).toBeVisible()
        await expect(canvas.getByText('pending')).toBeVisible()
        await expect(canvas.getByText('Swapping the rack for the Amamake neut fit the FCs asked for.')).toBeVisible()
        await expect(canvas.getByRole('textbox', { name: 'Review note' })).toBeVisible()
        await expect(canvas.getByRole('button', { name: 'Approve' })).toHaveAttribute('value', 'approve')
        await expect(canvas.getByRole('button', { name: 'Reject' })).toHaveAttribute('value', 'reject')
        await expect(canvas.queryByRole('button', { name: 'Cancel request' })).toBeNull()
        await expect(canvasElement.querySelectorAll('.change-diff__label').length).toBe(2)
        await expect(canvasElement.querySelector('form')).toHaveAttribute('hx-post', '/partials/doctrine_change_queue_component/?kind=fitting&id=31')
    },
}

export const SubmitterCanCancel = {
    args: { change_request: change_pending_submitter },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('link', { name: 'Amamake Defence Doctrine' })).toHaveAttribute('href', '/ships/doctrines/17/')
        await expect(canvas.getByText('Doctrine')).toBeVisible()
        await expect(canvas.getByRole('button', { name: 'Cancel request' })).toBeVisible()
        await expect(canvas.queryByRole('button', { name: 'Approve' })).toBeNull()
        await expect(canvas.queryByRole('textbox')).toBeNull()
    },
}

export const ReadOnly = {
    args: { change_request: change_pending_readonly },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelector('form')).toBeNull()
        await expect(canvasElement.querySelectorAll('.change-diff__line').length).toBeGreaterThan(0)
    },
}

export const Approved = {
    args: { change_request: change_approved },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('approved')).toBeVisible()
        await expect(canvas.getByText('Approved: matches the FC briefing.')).toBeVisible()
        await expect(canvasElement.querySelector('form')).toBeNull()
    },
}

export const NoDiffAndUnknownSubmitter = {
    args: { change_request: change_no_diff },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        // A deleted submitter shows as a question mark rather than "null".
        await expect(canvas.getByText(/Submitted by/)).toHaveTextContent('Submitted by ?')
        await expect(canvasElement.querySelectorAll('.change-diff__label').length).toBe(0)
    },
}
