import { expect, within } from 'storybook/test'
import ApplicationAllianceHistory from '@components/blocks/ApplicationAllianceHistory.astro'
import { history_flagged, history_inactive_only } from '../../../fixtures/features/corporations-and-tribes'

export default {
    title: 'Features/Corporations and tribes/ApplicationAllianceHistory',
    component: ApplicationAllianceHistory,
    parameters: {
        docs: {
            description: {
                component: [
                    'The Alliance history panel on a recruiter\'s application page (#3198, `docs/exits/exit-flow-design.md` section 06): every alliance corporation the applicant, or a character on their account, left, newest first, with the CEO\'s reason and note.',
                    'An active can\'t-rejoin flag tags the entry "Can\'t rejoin". The page passes entries only to recruiters of the corporation applied to (the API returns 403 to anyone else, the applicant included), and an empty list renders nothing.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        entries: { control: 'object', description: 'History entries, newest first.' },
    },
    args: { entries: history_flagged },
}

export const Flagged = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { name: 'Alliance history' })).toBeVisible()
        await expect(canvas.getByText("Can't rejoin")).toBeVisible()
        await expect(canvas.getByText('Example Corp')).toBeVisible()
        await expect(canvas.getByText(/Awoxed a corp Orca/)).toBeVisible()
        await expect(canvas.getAllByRole('listitem')).toHaveLength(3)
    },
}

export const InactiveKickOnly = {
    args: { entries: history_inactive_only },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Inactive kick')).toBeVisible()
        await expect(canvas.queryByText("Can't rejoin")).toBeNull()
        await expect(canvas.getByText(/Sela Morn \(CEO\)/)).toBeVisible()
    },
}

export const LeftOnTheirOwn = {
    name: 'Left on their own (no note)',
    args: { entries: [history_flagged[2]] },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Left')).toBeVisible()
        await expect(canvas.getByText('Third Corp')).toBeVisible()
        await expect(canvas.queryByText(/\(CEO\)/)).toBeNull()
    },
}
