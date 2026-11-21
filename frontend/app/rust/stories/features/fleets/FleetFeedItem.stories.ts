import { expect, within } from 'storybook/test'
import FleetFeedItem from '@components/blocks/FleetFeedItem.astro'
import {
    upcoming_strategic, upcoming_training, upcoming_npsi, active_fleet, completed_fleet, cancelled_fleet,
    fleet_on_alt, tribe_fleet, fleet_with_long_text, FCS,
} from '../../../fixtures/features/fleets'

export default {
    title: 'Features/Fleets/FleetFeedItem',
    component: FleetFeedItem,
    parameters: {
        docs: {
            description: {
                component: [
                    'A compact fleet row in the home page feed and the sidebar of upcoming fleets: the FC badge with the fleet type, the host tags for tribe fleets, and the phase on the right (a countdown for upcoming fleets, Active, Completed or Cancelled). The whole row links to the fleet page.',
                    'The scenarios show one row per fleet type and phase, an FC running on an alt ("X as Y"), a tribe group fleet and an over-long FC name.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        fleet: { control: 'object', description: 'The fleet row (FleetItem).' },
    },
    args: { fleet: upcoming_strategic },
}

const row = (canvasElement: HTMLElement) => canvasElement.querySelector('a') as HTMLAnchorElement

export const UpcomingStrategic = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(row(canvasElement)).toHaveAttribute('href', '/fleets/upcoming/9401/')
        await expect(canvas.getByText(FCS.keldar.name)).toBeVisible()
        await expect(canvas.getByText('Strategic fleet')).toBeVisible()
        await expect(canvasElement.querySelector('[x-data*="countdown_text"]')).not.toBeNull()
        await expect(canvas.queryByText('Active')).toBeNull()
    },
}

export const Training = {
    args: { fleet: upcoming_training },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByText('Training fleet')).toBeVisible()
        await expect(within(canvasElement).getByText(FCS.vaenne.name)).toBeVisible()
    },
}

export const Npsi = {
    args: { fleet: upcoming_npsi },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByText('NPSI fleet')).toBeVisible()
    },
}

export const Active = {
    args: { fleet: active_fleet },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByText('Active')).toHaveClass('blink-animation')
        // The countdown stays in the DOM for the ticker but is hidden once the fleet runs.
        await expect(canvasElement.querySelector('.hidden [x-data*="countdown_text"]')).not.toBeNull()
    },
}

export const Completed = {
    args: { fleet: completed_fleet },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByText('Completed')).toBeVisible()
    },
}

export const Cancelled = {
    args: { fleet: cancelled_fleet },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByText('Cancelled')).toHaveClass('status-text--danger')
    },
}

export const FcRunningOnAnAlt = {
    args: { fleet: fleet_on_alt },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByText("Kel'dar Atram as Kel Scout Alt")).toBeVisible()
    },
}

export const TribeGroupFleet = {
    args: { fleet: tribe_fleet },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByText('Skirmishers')).toBeVisible()
        await expect(canvasElement.querySelector('.fleet-host-tags')).not.toBeNull()
    },
}

export const LongFcName = {
    args: { fleet: fleet_with_long_text },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByText(FCS.long_one.name)).toBeVisible()
    },
}
