import { expect, within } from 'storybook/test'
import FleetStatus from '@components/blocks/FleetStatus.astro'
import { in_hours, hours_ago, active_fleet, completed_fleet, FCS } from '../../../fixtures/features/fleets'

export default {
    title: 'Features/Fleets/FleetStatus',
    component: FleetStatus,
    parameters: {
        docs: {
            description: {
                component: [
                    'The status block on a fleet page (`/fleets/upcoming/<id>`): the phase word (Active, Completed, Cancelled) and what the FC can do next. In the 30 minutes before form-up an FC sees the Ping fleet button, with "as {main}" and a Change menu to start on another character; while the fleet is tracked the FC sees Stop tracking. Pilots only see the phase.',
                    'The block reloads itself from `fleet_status_component` every minute until the fleet has ended, so FC actions and tracking changes show up without a page reload. The scenarios cover each phase and the FC and pilot views.',
                ].join('\n\n'),
            },
        },
        htmx: {
            '/partials/fleet_status_component': '<div id="fleet-status"><p>Reloaded</p></div>',
            '/partials/fleet_start_characters_component': '<p>Characters</p>',
        },
    },
    argTypes: {
        fleet_id: { control: 'number', description: 'Fleet whose status reloads.' },
        start_time: { control: 'date', description: 'Scheduled start; the Start button appears 30 minutes before.' },
        fleet_tracking: { control: 'object', description: 'Tracking record once the fleet has started; `end_time` set means completed.' },
        fleet_status: { control: 'select', options: ['pending', 'active', 'complete', 'cancelled', 'unknown'], description: 'Backend status; `cancelled` wins over tracking.' },
        is_fleet_commander: { control: 'boolean', description: 'The viewer is the FC and gets the Start and Stop controls.' },
        start_tracking: { control: 'boolean', description: 'The fleet was just started: shows the tracking-on-alt note when the FC started on an alt.' },
        fleet_tracking_texts: { control: 'object', description: 'Completed fleets: end time, duration and hint texts.' },
        main_character_id: { control: 'number', description: 'The FC main, for "as {main}" under Start.' },
        main_character_name: { control: 'text', description: 'The FC main name.' },
        alt_character_name: { control: 'text', description: 'The character tracking runs on, when not the main.' },
    },
    args: {
        fleet_id: 9401,
        start_time: in_hours(30),
        is_fleet_commander: false,
        main_character_id: FCS.keldar.id,
        main_character_name: FCS.keldar.name,
    },
}

const block = (canvasElement: HTMLElement) => canvasElement.querySelector('#fleet-status') as HTMLElement

export const UpcomingAsPilot = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        // Before the fleet starts the countdown above carries the state, so a pilot sees no label or controls.
        await expect(within(canvasElement).queryByRole('button')).toBeNull()
        await expect(canvasElement.querySelector('.status-text')).toBeNull()
        await expect(block(canvasElement).getAttribute('hx-get')).toContain('/partials/fleet_status_component?id=9401')
        await expect(block(canvasElement)).toHaveAttribute('hx-trigger', 'load delay:60s')
    },
}

export const FcWithinThirtyMinutes = {
    args: { is_fleet_commander: true, start_time: in_hours(0.25) },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('button', { name: 'Ping fleet' })).toBeVisible()
        await expect(canvas.getByText(FCS.keldar.name)).toBeVisible()
        await expect(canvas.getByText('Change')).toBeVisible()
    },
}

export const FcOnTime = {
    args: { is_fleet_commander: true, start_time: hours_ago(0.1) },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByRole('button', { name: 'Ping fleet' })).toBeVisible()
    },
}

export const FcTooEarly = {
    args: { is_fleet_commander: true, start_time: in_hours(30) },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        // More than 30 minutes out the controls wait in a template until the clock reaches form-up time.
        await expect(within(canvasElement).queryByRole('button', { name: 'Ping fleet' })).toBeNull()
        await expect(canvasElement.querySelector('template#fleet-tick')).not.toBeNull()
    },
}

export const ActiveAsFc = {
    args: { is_fleet_commander: true, start_time: active_fleet.start_time, fleet_tracking: active_fleet.tracking, fleet_status: 'active' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Active')).toHaveClass('blink-animation')
        await expect(canvas.getByRole('button', { name: 'Stop tracking' })).toBeVisible()
        await expect(canvas.queryByRole('button', { name: 'Ping fleet' })).toBeNull()
    },
}

export const ActiveAsPilot = {
    args: { start_time: active_fleet.start_time, fleet_tracking: active_fleet.tracking, fleet_status: 'active' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Active')).toBeVisible()
        await expect(canvas.queryByRole('button')).toBeNull()
    },
}

export const JustStartedOnAnAlt = {
    args: {
        is_fleet_commander: true,
        start_time: active_fleet.start_time,
        fleet_tracking: active_fleet.tracking,
        fleet_status: 'active',
        start_tracking: true,
        alt_character_name: 'Kel Scout Alt',
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const note = within(canvasElement).getByRole('status')
        await expect(note).toHaveTextContent('Tracking on Kel Scout Alt')
    },
}

export const Completed = {
    args: {
        start_time: completed_fleet.start_time,
        fleet_tracking: completed_fleet.tracking,
        fleet_status: 'complete',
        fleet_tracking_texts: {
            fleet_end_eve_time_text: 'Nov 14, 2026, 21:31',
            fleet_duration_text: '2h 27m',
            fleet_tracking_hint: 'From Nov 14, 2026, 19:04 to Nov 14, 2026, 21:31',
        },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Completed')).toBeVisible()
        await expect(canvas.getByText('2h 27m')).toBeVisible()
        // An ended fleet no longer reloads.
        await expect(block(canvasElement).hasAttribute('hx-get')).toBe(false)
    },
}

export const Cancelled = {
    args: { is_fleet_commander: true, fleet_status: 'cancelled', start_time: in_hours(8) },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Cancelled')).toHaveClass('status-text--danger')
        await expect(canvas.queryByRole('button', { name: 'Ping fleet' })).toBeNull()
    },
}
