import { expect, within } from 'storybook/test'
import StructureTimerList from '@components/blocks/StructureTimerList.astro'
import { timers_typical, timers_busy, timer_unknown_owner, timer_long_name, timer_expired } from '../../../fixtures/features/intel-and-combat'

export default {
    title: 'Features/Intel and combat/StructureTimerList',
    component: StructureTimerList,
    parameters: {
        docs: {
            description: {
                component: [
                    'The grid of structure timer cards on `/intel/timers/`. Each card shows the structure, owner, state, EVE time with a local-time and countdown toggle, a copy-to-clipboard line and, for members who can, a Verify button and a Create fleet link.',
                    'Timers are relative to the moment you open the story so countdowns and "Expired" stay true. The scenarios cover a typical list, a busy grid, an expired timer, a structure with an unknown owner, a very long name, the verifier view and the empty list.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        structure_timers: { control: 'object', description: 'Timers from the API, already mapped to the UI shape.' },
        can_verify_timer: { control: 'boolean', description: 'Show Verify on timers that are not verified yet.' },
        create_fleet: { control: 'boolean', description: 'Show "Create fleet" linking to /fleets/add/ with the timer.' },
    },
    args: { structure_timers: timers_typical, can_verify_timer: false, create_fleet: false },
}

type Ctx = { canvasElement: HTMLElement }

export const Typical = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvasElement.querySelectorAll('.structure-timer-list-item')).toHaveLength(3)
        await expect(canvas.getAllByText('Rattini Hold', { exact: false }).length).toBeGreaterThan(0)
        await expect(canvas.getByText('Armor timer')).toBeVisible()
        await expect(canvas.getByText('Hull timer')).toBeVisible()
        await expect(canvas.getByText('Verified')).toBeVisible()
        await expect(canvas.queryByRole('button', { name: 'Verify timer' })).toBeNull()
    },
}

export const ExpiredTimer = {
    args: { structure_timers: [timer_expired] },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Expired')).toBeVisible()
        await expect(canvas.getByText('Anchoring timer')).toBeVisible()
        await expect(canvas.queryByText('Local time')).toBeNull()
    },
}

export const VerifierView = {
    args: { structure_timers: timers_typical, can_verify_timer: true, create_fleet: true },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        // Only the unverified timers (one upcoming, one expired) offer Verify.
        await expect(canvas.getAllByRole('button', { name: 'Verify timer' })).toHaveLength(2)
        const fleet_links = canvas.getAllByRole('link', { name: 'Create fleet' })
        await expect(fleet_links).toHaveLength(3)
        await expect(fleet_links[0].getAttribute('href')).toContain('/fleets/add/?timer=')
    },
}

export const UnknownOwner = {
    args: { structure_timers: [timer_unknown_owner], can_verify_timer: true },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getAllByText('Old Man Star', { exact: false }).length).toBeGreaterThan(0)
        await expect(canvas.getByRole('button', { name: 'Verify timer' })).toBeVisible()
    },
}

export const LongName = {
    args: { structure_timers: [timer_long_name] },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getAllByText(/The Imperial Fedo Navy Reserve Auxiliary Logistics Staging Citadel Alpha/).length).toBeGreaterThan(0)
    },
}

export const Busy = {
    args: { structure_timers: timers_busy, can_verify_timer: true },
    play: async ({ canvasElement }: Ctx) => {
        await expect(canvasElement.querySelectorAll('.structure-timer-list-item')).toHaveLength(12)
        await expect(within(canvasElement).getAllByText('Verified')).toHaveLength(8)
    },
}

export const Empty = {
    args: { structure_timers: [] },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByText('No structure timers found')).toBeVisible()
        await expect(canvasElement.querySelectorAll('.structure-timer-list-item')).toHaveLength(0)
    },
}
