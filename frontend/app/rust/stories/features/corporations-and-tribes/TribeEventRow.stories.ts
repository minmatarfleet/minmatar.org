import { expect, within } from 'storybook/test'
import TribeEventRow from '@components/blocks/TribeEventRow.astro'
import {
    event_cancelled,
    event_completed,
    event_editable,
    event_no_date,
    event_scheduled,
} from '../../../fixtures/features/corporations-and-tribes'

export default {
    title: 'Features/Corporations and tribes/TribeEventRow',
    component: TribeEventRow,
    parameters: {
        docs: {
            description: {
                component: [
                    "One Discord-backed event on a tribe group's Events tab (`/alliance/tribes/<tribe>/<group>/`): date block, cover, title, where and when in EVE time plus local time, interested count and an Interested link to the Discord event.",
                    'Scenarios cover a live scheduled event, one the viewer can edit, cancelled and completed events, an event with no date yet or not on Discord, and a full week of rows.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        event: { control: 'object', description: 'TribeEventRowUI built by the Events tab from the API.' },
    },
    args: { event: event_scheduled },
}

export const Scheduled = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Capital Doctrine Night: Nidhoggur logistics')).toBeVisible()
        await expect(canvas.getByText('Weekly')).toBeVisible()
        await expect(canvas.getByText('23 interested')).toBeVisible()
        await expect(canvas.getByText('Capitals Stage')).toBeVisible()
        await expect(canvasElement.textContent).toContain('19:00–21:00 EVE')
        const interested = canvas.getByRole('link', { name: /Interested/ })
        await expect(interested).toHaveAttribute('href', 'https://discord.com/events/1000/501')
        await expect(interested).toHaveAttribute('rel', 'noopener noreferrer')
        await expect(canvas.queryByRole('link', { name: 'Edit' })).toBeNull()
    },
}

export const EditableByLeader = {
    args: { event: event_editable },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const edit = within(canvasElement).getByRole('link', { name: 'Edit' })
        await expect(edit).toHaveAttribute('href', '/alliance/tribes/1/3/events/502/edit/')
        await expect(within(canvasElement).getByText('8 interested')).toBeVisible()
    },
}

export const Cancelled = {
    args: { event: event_cancelled },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const row = canvasElement.querySelector('article') as HTMLElement
        await expect(row).toHaveAttribute('data-status', 'cancelled')
        await expect(within(row).getByText('Cancelled')).toBeVisible()
        await expect(within(row).getByText('41 were interested')).toBeVisible()
    },
}

export const Completed = {
    args: { event: event_completed },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const row = canvasElement.querySelector('article') as HTMLElement
        await expect(row).toHaveAttribute('data-status', 'completed')
        await expect(within(row).getByText('Hauler escort run to Rens')).toBeVisible()
        await expect(within(row).queryByRole('link', { name: /Interested/ })).toBeNull()
    },
}

export const NoDateNotOnDiscord = {
    args: { event: event_no_date },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('TBD')).toBeVisible()
        await expect(canvas.getByText('Not on Discord yet')).toBeVisible()
        await expect(canvas.queryByRole('link')).toBeNull()
    },
}
