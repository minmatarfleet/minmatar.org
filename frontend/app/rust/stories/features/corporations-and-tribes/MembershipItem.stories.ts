import { expect, within } from 'storybook/test'
import MembershipItem from '@components/blocks/MembershipItem.astro'
import {
    membership_no_alts,
    membership_no_rank,
    membership_with_alts,
} from '../../../fixtures/features/corporations-and-tribes'

export default {
    title: 'Features/Corporations and tribes/MembershipItem',
    component: MembershipItem,
    parameters: {
        docs: {
            description: {
                component: [
                    "One member row on a tribe group's Members management view (`/alliance/tribes/<tribe>/<group>/`, visible to the group's chiefs): main pilot, rank, join date, committed characters with a qualified / not qualified marker, and remove buttons.",
                    'Scenarios show a member whose alts are qualified, missing skills, missing assets and missing a token, a member with no committed alts, and a member with no rank or portrait and a very long name.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        membership: { control: 'object', description: 'TribeMembership from the memberships API.' },
        required_token_type: { control: 'text', description: 'ESI token the group requires; named in the missing-token tooltip.' },
    },
    args: { membership: membership_with_alts, required_token_type: null },
}

export const WithAlts = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { name: "Kel'dar Atram" })).toBeVisible()
        await expect(canvas.getByText('Capital Pilot')).toBeVisible()
        // Four committed characters, one marker each: 1 qualified, 3 not.
        await expect(canvasElement.querySelectorAll('.membership-status').length).toBe(4)
        await expect(canvasElement.querySelectorAll('.membership-status.text-green').length).toBe(1)
        await expect(canvasElement.querySelectorAll('.membership-status.text-red').length).toBe(3)
        await expect(canvas.getByText('Hela Brutori')).toBeInTheDocument()
    },
}

export const NoAlts = {
    args: { membership: membership_no_alts },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelectorAll('.membership-status').length).toBe(0)
        await expect(within(canvasElement).getByRole('heading', { name: "Kel'dar Atram" })).toBeVisible()
    },
}

export const NoRankLongName = {
    args: { membership: membership_no_rank },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { name: /Ashen Rattini-Sebiestor/ })).toBeVisible()
        await expect(canvas.queryByText('Capital Pilot')).toBeNull()
    },
}
