import { expect, waitFor, within, userEvent } from 'storybook/test'
import LearningSkillsets from '@components/blocks/LearningSkillsets.astro'
import { skillsets_typical, pilot } from '../../../fixtures/features/content'

export default {
    title: 'Features/Content/LearningSkillsets',
    component: LearningSkillsets,
    parameters: {
        docs: {
            description: {
                component: [
                    'The Skillsets section of the learning centre: a heading, a lead, filter chips by category and a grid of skillset cards with the pilot\'s progress. A signed-out visitor gets a log-in button; a manager also gets a link to edit the skillsets.',
                    'It is the `#skillsets` section of `/guides/learning-center/`. Filtering is Alpine-only and works over the cards already rendered. The scenarios show a pilot with progress, a pilot with no skillsets, a signed-out visitor and the admin link.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        heading: { control: 'text' },
        lead: { control: 'text', description: 'One line under the heading.' },
        empty_text: { control: 'text', description: 'Shown when there is nothing to list and no login button.' },
        skillsets: { control: 'object', description: 'The pilot\'s skillsets with progress and missing skills.' },
        character: { control: 'object', description: 'The pilot whose progress is shown; null when signed out.' },
        login_href: { control: 'text', description: 'ESI login link for a signed-out visitor.' },
        login_label: { control: 'text' },
        admin_href: { control: 'text', description: 'Link to manage the skillsets, for managers.' },
        admin_label: { control: 'text' },
    },
    args: {
        heading: 'Skillsets',
        lead: 'Track doctrine skill progress for your pilots.',
        empty_text: 'No skillsets',
        skillsets: skillsets_typical,
        character: pilot,
        login_href: null,
        login_label: 'Log in to view skillsets',
        admin_href: null,
        admin_label: 'Manage skillsets',
    },
}

export const WithProgress = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { name: 'Skillsets' })).toBeVisible()
        await expect(canvas.getByText('Magic 14')).toBeVisible()
        await expect(canvasElement.querySelectorAll('.skillsets-catalog__item').length).toBe(6)
        await expect(canvas.getByText('Completed')).toBeVisible()
        await expect(canvas.getByText('Revelation/RNI')).toBeVisible()
    },
}

// Browser only: Alpine's x-bind on aria-pressed does not settle under happy-dom, so the filter is exercised in Chromium.
export const FilterByCategory = {
    tags: ['browser'],
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        const visible = () => Array.from(canvasElement.querySelectorAll<HTMLElement>('.skillsets-catalog__item')).filter(el => el.style.display !== 'none')
        await waitFor(() => expect(canvas.getByRole('button', { name: /All categories/ })).toHaveAttribute('aria-pressed', 'true'))
        await expect(visible().length).toBe(6)
        // Filters are Alpine-only: they hide cards already on the page.
        await userEvent.click(canvas.getByRole('button', { name: /Capitals/ }))
        await waitFor(() => expect(visible().length).toBe(2))
        await expect(canvas.getByRole('button', { name: /Capitals/ })).toHaveAttribute('aria-pressed', 'true')
        await userEvent.click(canvas.getByRole('button', { name: /New Players/ }))
        await waitFor(() => expect(visible().length).toBe(2))
    },
}

export const NoSkillsets = {
    args: { skillsets: [] },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByText('No skillsets')).toBeVisible()
    },
}

export const SignedOut = {
    args: { skillsets: [], character: null, login_href: '/auth/sso/?scopes=skills' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const login = within(canvasElement).getByRole('link', { name: 'Log in to view skillsets' })
        await expect(login).toHaveAttribute('href', '/auth/sso/?scopes=skills')
    },
}

export const ManagerWithAdminLink = {
    args: { admin_href: '/admin/skillsets/' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const link = within(canvasElement).getByRole('link', { name: 'Manage skillsets' })
        await expect(link).toHaveAttribute('href', '/admin/skillsets/')
        await expect(link).toHaveAttribute('target', '_blank')
    },
}
