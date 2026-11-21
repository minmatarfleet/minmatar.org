import { expect, within } from 'storybook/test'
import FleetHostStrip from '@components/blocks/FleetHostStrip.astro'
import { skirmishers, capitals } from '../../../fixtures/features/fleets'

export default {
    title: 'Features/Fleets/FleetHostStrip',
    component: FleetHostStrip,
    parameters: {
        docs: {
            description: {
                component: [
                    'The line under the title of a tribe group fleet (`/fleets/upcoming/<id>`): who hosts it, who can see it, where it pinged, and a link to the group\'s Fleets tab. Alliance fleets do not render it.',
                    'The scenarios are the visibility combinations: members only (with and without a member count), open to the whole alliance, open and listed on #schedule, and a group with no ping role.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        group: { control: 'object', description: 'The hosting tribe group (id, code, name, tribe).' },
        open_to_alliance: { control: 'boolean', description: 'Everyone can see the fleet, tagged with the group; otherwise members only.' },
        on_schedule: { control: 'boolean', description: 'Also listed on #schedule (only meaningful when open).' },
        member_count: { control: 'number', description: 'Members who can see a members-only fleet; adds the count to the line.' },
        role_name: { control: 'text', description: 'The Discord role the ping used; unset says "Pinged in the group\'s channel".' },
    },
    args: { group: skirmishers, open_to_alliance: false, on_schedule: false, member_count: null, role_name: 'Skirmishers' },
}

export const MembersOnly = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Skirmishers', { selector: 'b' })).toBeVisible()
        await expect(canvasElement.textContent).toContain('Hosted by Skirmishers · Pulse tribe')
        await expect(canvas.getByText(/Visible to Skirmishers members only\./)).toBeVisible()
        await expect(canvas.getByText(/Pinged as @Skirmishers/)).toBeVisible()
        await expect(canvas.getByRole('img', { name: 'Crest of Skirmishers' })).toBeVisible()
        await expect(canvas.getByRole('link', { name: /Skirmishers page/ })).toHaveAttribute('href', '/alliance/tribes/4/21/#fleets')
    },
}

export const MembersOnlyWithCount = {
    args: { member_count: 64 },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByText(/Visible to the 64 Skirmishers members only\./)).toBeVisible()
    },
}

export const OpenToAlliance = {
    args: { group: capitals, open_to_alliance: true, role_name: 'Capital Pilots' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText(/Open to the whole alliance\./)).toBeVisible()
        await expect(canvas.queryByText(/Listed on #schedule/)).toBeNull()
        await expect(canvas.getByRole('link', { name: /Capital Pilots page/ })).toHaveAttribute('href', '/alliance/tribes/2/7/#fleets')
    },
}

export const OpenAndOnSchedule = {
    args: { group: capitals, open_to_alliance: true, on_schedule: true },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByText(/Listed on #schedule under Tribe fleets\./)).toBeVisible()
    },
}

export const NoPingRole = {
    args: { role_name: null },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText(/Pinged in the group's channel\./)).toBeVisible()
        await expect(canvas.queryByText(/Pinged as @/)).toBeNull()
    },
}
