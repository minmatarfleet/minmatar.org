import { expect, within } from 'storybook/test'
import FleetInviteBanner from '@components/blocks/FleetInviteBanner.astro'
import {
    invited_fleet, invited_in_fleet, invited_out_fleet, invited_new_pilot_fleet, invited_started_fleet,
} from '../../../fixtures/features/fleets'

export default {
    title: 'Features/Fleets/FleetInviteBanner',
    component: FleetInviteBanner,
    parameters: {
        docs: {
            description: {
                component: [
                    'The invite at the top of a standard fleet page (`/fleets/upcoming/<id>`) for a pilot the FC invited: pick a ship below to say you\'re in, answer "I\'m in, no ship yet", or sit this one out. New pilots also get a link to the first-fleet guide. Private fleets use FleetPrivateBanner instead.',
                    'The answer buttons post to the `fleet_invite_answer_component` partial and swap the banner; they only show while the fleet has not started. The scenarios cover each answer, a new pilot, a started fleet (no buttons) and an error.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        fleet: { control: 'object', description: 'The fleet, with the viewer\'s `my_invite_answer`, `my_invite_source` and `status`.' },
        has_ships: { control: 'boolean', description: 'The viewer has picked a ship, so "You\'re in." replaces the no-ship hint.' },
        error: { control: 'text', description: 'A save error shown under the text.' },
    },
    args: { fleet: invited_fleet, has_ships: false, error: false },
}

const post_buttons = (canvas: ReturnType<typeof within>) => canvas.queryAllByRole('button')

export const Pending = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('note', { name: "Kel'dar Atram invited you" })).toBeVisible()
        await expect(canvas.getByText("Pick a ship below to say you're in.")).toBeVisible()
        const in_button = canvas.getByRole('button', { name: "I'm in, no ship yet" })
        await expect(in_button.getAttribute('hx-post')).toContain('/partials/fleet_invite_answer_component')
        await expect(in_button.getAttribute('hx-post')).toContain('fleet_id=9401')
        await expect(in_button.getAttribute('hx-post')).toContain('answer=in')
        await expect(canvas.getByRole('button', { name: 'Sitting out' })).toHaveAttribute('hx-target', '#fleet-invite-banner')
        await expect(canvas.queryByRole('link')).toBeNull()
    },
}

export const InWithShip = {
    args: { fleet: invited_in_fleet, has_ships: true },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText("You're in.")).toBeVisible()
        // Already in: only Sitting out is offered.
        await expect(canvas.queryByRole('button', { name: "I'm in, no ship yet" })).toBeNull()
        await expect(canvas.getByRole('button', { name: 'Sitting out' })).toBeVisible()
    },
}

export const InWithoutShip = {
    args: { fleet: invited_in_fleet, has_ships: false },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByText(/You're in with no ship yet/)).toBeVisible()
    },
}

export const SittingOut = {
    args: { fleet: invited_out_fleet },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText(/You're sitting this one out/)).toBeVisible()
        await expect(canvas.getByRole('button', { name: "I'm in, no ship yet" })).toBeVisible()
        await expect(canvas.queryByRole('button', { name: 'Sitting out' })).toBeNull()
    },
}

export const NewPilotGetsTheGuide = {
    args: { fleet: invited_new_pilot_fleet },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const guide = within(canvasElement).getByRole('link', { name: 'Your first fleet: what to expect' })
        await expect(guide.getAttribute('href')).toContain('/learning/guides/onboarding-first-fleet/')
    },
}

export const FleetAlreadyStarted = {
    args: { fleet: invited_started_fleet },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        // Once tracking has started the answer is locked in: no buttons.
        await expect(post_buttons(within(canvasElement))).toHaveLength(0)
        await expect(within(canvasElement).getByText("Pick a ship below to say you're in.")).toBeVisible()
    },
}

export const SaveError = {
    args: { error: "Couldn't save your answer. Try again." },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByRole('alert')).toHaveTextContent("Couldn't save your answer. Try again.")
    },
}
