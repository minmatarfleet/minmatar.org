import { expect, within } from 'storybook/test'
import FleetListItem from '@components/blocks/FleetListItem.astro'
import {
    upcoming_strategic, upcoming_training, upcoming_npsi, tribe_fleet, open_tribe_fleet, active_fleet,
    completed_fleet, cancelled_fleet, fleet_with_long_text, bare_fleet, FCS,
} from '../../../fixtures/features/fleets'

export default {
    title: 'Features/Fleets/FleetListItem',
    component: FleetListItem,
    parameters: {
        docs: {
            description: {
                component: [
                    'One fleet card in the Fleets hub (`/fleets/upcoming`) and the history list (`/fleets/history`): the FC portrait with the fleet-type corner flag, FC corporation and fleets led, objective, staging system, the volunteer button, and EVE time with a countdown that alternates with the local time.',
                    'What the card shows depends on the fleet phase: upcoming has EVE time and a countdown, active shows when it started, completed shows the end time and duration, cancelled shows its time and a red label. Tribe group fleets carry the host chip and a Members only or Open tag.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        fleet: { control: 'object', description: 'The fleet row (FleetItem) from the API.' },
        history: { control: 'boolean', description: 'Link to /fleets/history/<id> and hide the volunteer button.' },
    },
    args: { fleet: upcoming_strategic, history: false },
}

const link = (canvas: ReturnType<typeof within>, name: string | RegExp) => canvas.getByRole('link', { name })

export const UpcomingStrategic = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { name: FCS.keldar.name })).toBeVisible()
        await expect(canvas.getByText('Amamake', { selector: 'b' })).toBeVisible()
        await expect(canvas.getByText('Freeport')).toBeVisible()
        await expect(canvas.getByText('18')).toBeVisible()
        await expect(canvas.getByText('41')).toBeVisible()
        await expect(canvasElement.querySelector('[data-tippy-content="Strategic fleet"]')).not.toBeNull()
        await expect(link(canvas, 'View details')).toHaveAttribute('href', '/fleets/upcoming/9401')
        await expect(link(canvas, 'Volunteer')).toHaveAttribute('href', '/fleets/upcoming/9401/volunteer')
        await expect(canvas.getByText('EVE time')).toBeVisible()
        await expect(canvasElement.querySelector('[x-data*="countdown_text"]')).not.toBeNull()
    },
}

export const Training = {
    args: { fleet: upcoming_training },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelector('[data-tippy-content="Training fleet"]')).not.toBeNull()
        await expect(within(canvasElement).getByText(/First-week pilots welcome/)).toBeVisible()
    },
}

export const Npsi = {
    args: { fleet: upcoming_npsi },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelector('[data-tippy-content="NPSI fleet"]')).not.toBeNull()
    },
}

export const TribeGroupMembersOnly = {
    args: { fleet: tribe_fleet },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Skirmishers')).toBeVisible()
        await expect(canvasElement.querySelector('.fleet-host-tags')).not.toBeNull()
    },
}

export const TribeGroupOpenToAlliance = {
    args: { fleet: open_tribe_fleet },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByText('Capital Pilots')).toBeVisible()
        await expect(canvasElement.querySelector('.fleet-host-tags')).not.toBeNull()
    },
}

export const Active = {
    args: { fleet: active_fleet },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Active')).toHaveClass('blink-animation')
        await expect(canvas.getByText('Fleet started')).toBeVisible()
        await expect(canvas.getByText('36')).toBeVisible()
    },
}

export const Completed = {
    args: { fleet: completed_fleet, history: true },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Completed')).toBeVisible()
        await expect(link(canvas, 'View details')).toHaveAttribute('href', '/fleets/history/9390')
        // History rows are read-only: no volunteering for a fleet that is over.
        await expect(canvas.queryByRole('link', { name: 'Volunteer' })).toBeNull()
    },
}

export const Cancelled = {
    args: { fleet: cancelled_fleet },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByText('Cancelled')).toHaveClass('status-text--danger')
    },
}

export const LongNamesAndText = {
    args: { fleet: fleet_with_long_text },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { name: FCS.long_one.name })).toBeVisible()
        await expect(canvas.getByText(/Escort the freight convoy/)).toBeVisible()
    },
}

export const OnlyRequiredFields = {
    args: { fleet: bare_fleet },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { name: FCS.vaenne.name })).toBeVisible()
        // No type: the tooltip wrapper stays but draws no icon. Optional counts and objective are left out.
        await expect(canvasElement.querySelector('[data-tippy-content="Non strategic fleet"] svg')).toBeNull()
        await expect(canvas.queryByText('Fleet started')).toBeNull()
        await expect(link(canvas, 'View details')).toHaveAttribute('href', '/fleets/upcoming/9409')
    },
}
