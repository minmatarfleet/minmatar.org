import { expect, within } from 'storybook/test'
import CorporationsList from '@components/blocks/CorporationsList.astro'
import { corporations_busy, corporations_typical } from '../../../fixtures/features/corporations-and-tribes'

export default {
    title: 'Features/Corporations and tribes/CorporationsList',
    component: CorporationsList,
    parameters: {
        docs: {
            description: {
                component: [
                    'The grid of corporation cards on `/alliance/corporations/`; each card is a `CorporationItem` in a bordered block.',
                    'Scenarios show the usual alliance roster, a long list that wraps into more rows, the pilot\'s own corporation marked Joined, and the empty message.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        corporations: { control: 'object' },
        user_corporation_id: { control: 'number', description: 'Corporation of the viewer; its card shows Joined.' },
        disable_applications: { control: 'boolean' },
        link_to_page: { control: 'boolean' },
    },
    args: { corporations: corporations_typical, user_corporation_id: 0, disable_applications: false, link_to_page: true },
}

export const Typical = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvasElement.querySelectorAll('.corporation-item').length).toBe(7)
        await expect(canvas.getByRole('link', { name: 'Rattini Tribe' })).toBeVisible()
        await expect(canvas.getByText('Trial')).toBeVisible()
        await expect(canvas.getAllByText('Minmatar Fleet Alliance').length).toBe(7)
    },
}

export const Busy = {
    args: { corporations: corporations_busy },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelectorAll('.corporation-item').length).toBe(19)
        await expect(within(canvasElement).getByText('Ember Wing Lima')).toBeVisible()
    },
}

export const MemberOfOne = {
    args: { user_corporation_id: 98726134 },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getAllByText('Joined').length).toBe(1)
    },
}

export const Empty = {
    args: { corporations: [] },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelectorAll('.corporation-item').length).toBe(0)
        await expect(canvasElement.textContent?.trim().length).toBeGreaterThan(0)
    },
}
