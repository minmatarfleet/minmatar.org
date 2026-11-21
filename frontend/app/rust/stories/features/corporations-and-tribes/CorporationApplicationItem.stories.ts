import { expect, within } from 'storybook/test'
import CorporationApplicationItem from '@components/blocks/CorporationApplicationItem.astro'
import {
    application_corporation,
    application_orphan,
    application_pending,
    application_second,
} from '../../../fixtures/features/corporations-and-tribes'

export default {
    title: 'Features/Corporations and tribes/CorporationApplicationItem',
    component: CorporationApplicationItem,
    // The item binds its root id to `id`, which the parent block's x-data supplies per application.
    decorators: [(Story: () => string) => `<div x-data="{ id: 'corporation-application-item-1' }">${Story()}</div>`],
    parameters: {
        docs: {
            description: {
                component: [
                    'One pending application in the recruiter view of a corporation (`/alliance/corporations/applications/`): the applicant\'s badge with their current corporation, and a button to open the application.',
                    'An application whose character no longer resolves (id 0) cannot be opened, so only a Deny button is shown; it opens a confirm dialog that posts to a partial. Scenarios cover both, plus an applicant coming from the New Eden NPC university.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        application: { control: 'object' },
        corporation: { control: 'object', description: 'The corporation being applied to.' },
    },
    args: { application: application_pending, corporation: application_corporation },
}

export const PendingApplication = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText("Kel'dar Atram")).toBeVisible()
        await expect(canvas.getByText('Minmatar Fleet Academy')).toBeVisible()
        const view = canvas.getByRole('link', { name: 'View application' })
        await expect(view.getAttribute('href')).toContain('/alliance/corporations/application/98726134/4412')
        await expect(canvas.queryByRole('button', { name: 'Deny' })).toBeNull()
    },
}

export const FromNpcUniversity = {
    args: { application: application_second },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Vaska Tennen')).toBeVisible()
        await expect(canvas.getByText('University of Caille')).toBeVisible()
        await expect(canvas.getByRole('link', { name: 'View application' }).getAttribute('href')).toContain('/4413')
    },
}

export const PilotGoneDenyOnly = {
    args: { application: application_orphan },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('button', { name: 'Deny' })).toBeVisible()
        await expect(canvas.queryByRole('link', { name: 'View application' })).toBeNull()
    },
}
