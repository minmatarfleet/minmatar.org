import { expect, within } from 'storybook/test'
import CorporationItem from '@components/blocks/CorporationItem.astro'
import {
    a_rat,
    corporation_no_alliance,
    corporation_trial,
} from '../../../fixtures/features/corporations-and-tribes'

export default {
    title: 'Features/Corporations and tribes/CorporationItem',
    component: CorporationItem,
    parameters: {
        docs: {
            description: {
                component: [
                    'One corporation row: logo, name (optionally linking to its page), alliance line and the join status or application button on the right. It is the unit of the list on `/alliance/corporations/`.',
                    'Scenarios show a corporation open for enlisting, one the pilot already belongs to, a trial corporation, a corporation outside the alliance with a very long name, and applications switched off. The status area reads the `primary_pilot` cookie, so signed-out stories show the "enlist today" prompt.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        corporation: { control: 'object', description: 'CorporationObject from the corporations API.' },
        is_user_corporation: { control: 'boolean', description: 'The viewer is a member: shows the Joined tag.' },
        disable_applications: { control: 'boolean', description: 'Hide the apply controls (view-only pages).' },
        link_to_page: { control: 'boolean', description: "Link the name to the corporation's detail page." },
    },
    args: { corporation: a_rat, is_user_corporation: false, disable_applications: false, link_to_page: false },
}

export const OpenForApplications = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Rattini Tribe')).toBeVisible()
        await expect(canvas.getByText('Minmatar Fleet Alliance')).toBeVisible()
        await expect(canvas.getByRole('img', { name: /Rattini Tribe/ })).toBeVisible()
        await expect(canvas.queryByRole('link', { name: 'Rattini Tribe' })).toBeNull()
    },
}

export const Joined = {
    args: { is_user_corporation: true },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByText('Joined')).toBeVisible()
    },
}

export const LinkedToPage = {
    args: { link_to_page: true },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const link = within(canvasElement).getByRole('link', { name: 'Rattini Tribe' })
        await expect(link.getAttribute('href')).toContain('/alliance/corporations/rattini-tribe/')
    },
}

export const TrialCorporation = {
    args: { corporation: corporation_trial, link_to_page: true },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Minmatar Fleet Academy')).toBeVisible()
        await expect(canvas.getByText('Trial')).toBeVisible()
    },
}

export const NoAllianceLongName = {
    args: { corporation: corporation_no_alliance },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText(/The Quiet Moon Hauling/)).toBeVisible()
        await expect(canvas.queryByText('Minmatar Fleet Alliance')).toBeNull()
    },
}

export const ApplicationsDisabled = {
    args: { disable_applications: true },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Rattini Tribe')).toBeVisible()
        await expect(canvas.queryByRole('button')).toBeNull()
    },
}
