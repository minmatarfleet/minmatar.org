import { expect, within } from 'storybook/test'
import FleetPrivateBanner from '@components/blocks/FleetPrivateBanner.astro'
import {
    private_fleet, private_fleet_manager, private_fleet_sitting_out, private_fleet_no_thread,
} from '../../../fixtures/features/fleets'

export default {
    title: 'Features/Fleets/FleetPrivateBanner',
    component: FleetPrivateBanner,
    parameters: {
        docs: {
            description: {
                component: [
                    'The opsec line at the top of a private, invite-only fleet page until it is declassified: do not mention the fleet anywhere. Invited pilots also see their invite wave, a "sitting this one out" button and the private coordination thread; the FC and Strategic FCs see the thread only.',
                    'The scenarios are the invited pilot, a manager who was not invited, a pilot who is sitting out, an invited pilot while no Discord thread exists yet, and a save error.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        fleet: { control: 'object', description: 'The fleet with the viewer\'s `my_invite_answer`, `my_invite_wave` and the `discord_thread_url`.' },
        error: { control: 'text', description: 'A save error shown under the text.' },
    },
    args: { fleet: private_fleet, error: false },
}

export const InvitedPilot = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('note', { name: 'Private' })).toBeVisible()
        await expect(canvas.getByText(/Invite only\. Don't mention this fleet/)).toBeVisible()
        await expect(canvas.getByText("Kel'dar Atram invited you in wave 2. Only invited pilots can open this page.")).toBeVisible()
        await expect(canvas.getByText('Sitting out clears your ships and tells the FC.')).toBeVisible()
        await expect(canvas.getByRole('link', { name: 'Open coordination thread' })).toHaveAttribute('href', 'https://discord.com/channels/1000000000000000000/1100000000000000000')
        const sit_out = canvas.getByRole('button', { name: "I'm sitting this one out" })
        await expect(sit_out.getAttribute('hx-post')).toContain('fleet_id=9401')
        await expect(sit_out).toHaveAttribute('hx-target', '#fleet-private-banner')
    },
}

export const ManagerNotInvited = {
    args: { fleet: private_fleet_manager },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Only invited pilots, you and Strategic FCs can open this page.')).toBeVisible()
        await expect(canvas.getByRole('link', { name: 'Open coordination thread' })).toBeVisible()
        // Managers have no answer to withdraw.
        await expect(canvas.queryByRole('button')).toBeNull()
    },
}

export const SittingOut = {
    args: { fleet: private_fleet_sitting_out },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText(/You're sitting this one out\. Pick ships to change your mind\./)).toBeVisible()
        await expect(canvas.queryByRole('button')).toBeNull()
    },
}

export const NoThreadYet = {
    args: { fleet: private_fleet_no_thread },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.queryByRole('link', { name: 'Open coordination thread' })).toBeNull()
        await expect(canvas.getByRole('button', { name: "I'm sitting this one out" })).toBeVisible()
    },
}

export const SaveError = {
    args: { error: "Couldn't save your answer. Try again." },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByRole('alert')).toHaveTextContent("Couldn't save your answer")
    },
}
