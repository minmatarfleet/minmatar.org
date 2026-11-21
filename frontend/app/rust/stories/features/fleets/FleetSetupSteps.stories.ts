import { expect, within } from 'storybook/test'
import FleetSetupSteps from '@components/blocks/FleetSetupSteps.astro'
import { steps_fresh, steps_no_ships, steps_tracking, steps_all_done } from '../../../fixtures/features/fleets'

export default {
    title: 'Features/Fleets/FleetSetupSteps',
    component: FleetSetupSteps,
    parameters: {
        docs: {
            description: {
                component: [
                    'The FC\'s checklist on the fleet\'s Command tab (`/fleets/upcoming/<id>`): every step from scheduling to the in-game checks. Done steps are ticked, the next one is highlighted with how to fix it, later ones wait. It reloads from `fleet_command_steps_component` when tracking starts, and every minute while tracking.',
                    'The scenarios walk a fleet through its life: fresh (waiting for form-up), no ships set, tracking with a failing in-game check, and everything done.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        fleet_id: { control: 'number', description: 'Fleet whose steps reload.' },
        steps: { control: 'object', description: 'The steps in order, each with `state`: done, next or todo.' },
        refresh: { control: 'boolean', description: 'Reload every minute (tracking is running).' },
    },
    args: { fleet_id: 9401, steps: steps_fresh, refresh: false },
}

const states = (canvasElement: HTMLElement) =>
    [...canvasElement.querySelectorAll('li')].map((li) => li.className.replace('fleet-setup__', ''))

export const FormUpNext = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { name: 'Getting to form-up' })).toBeVisible()
        await expect(canvas.getByText('2 of 6 done')).toBeVisible()
        await expect(states(canvasElement)).toEqual(['done', 'done', 'next', 'todo', 'todo', 'todo'])
        await expect(canvas.getAllByRole('listitem')).toHaveLength(6)
        // Screen readers get Done / To do, not just the tick.
        await expect(canvas.getAllByText('Done:')).toHaveLength(2)
        const section = canvasElement.querySelector('section') as HTMLElement
        await expect(section.getAttribute('hx-get')).toContain('/partials/fleet_command_steps_component')
        await expect(section.getAttribute('hx-get')).toContain('fleet_id=9401')
        await expect(section).toHaveAttribute('hx-trigger', 'tracking_started from:body')
    },
}

export const ShipsNotSet = {
    args: { steps: steps_no_ships },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('1 of 6 done')).toBeVisible()
        await expect(states(canvasElement)[1]).toBe('next')
        await expect(canvas.getByText(/Not set: choose a doctrine or a custom lineup/)).toBeVisible()
    },
}

export const TrackingWithFailingCheck = {
    args: { steps: steps_tracking, refresh: true },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('4 of 6 done')).toBeVisible()
        await expect(canvas.getByText('Pinged and tracking')).toBeVisible()
        await expect(canvas.getByText(/Off: turn on Free-move/)).toBeVisible()
        await expect(canvasElement.querySelector('section')).toHaveAttribute('hx-trigger', 'every 60s, tracking_started from:body')
    },
}

export const AllDone = {
    args: { steps: steps_all_done, refresh: true },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByText('6 of 6 done')).toBeVisible()
        await expect(states(canvasElement).every((state) => state === 'done')).toBe(true)
        await expect(canvasElement.querySelectorAll('.fleet-setup__mark')[0].textContent).toBe('✓')
    },
}
