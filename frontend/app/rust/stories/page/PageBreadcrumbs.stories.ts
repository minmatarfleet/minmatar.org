import { expect, within } from 'storybook/test'
import PageBreadcrumbs from '@components/page/PageBreadcrumbs.astro'

const FLEET_TRAIL = [
    { accumulated_path: '/fleets/', page_title: 'Fleets' },
    { accumulated_path: '/fleets/upcoming/', page_title: 'Upcoming' },
    { accumulated_path: '/fleets/92221/', page_title: 'Fleet 92221' },
]

export default {
    title: 'Page/PageBreadcrumbs',
    component: PageBreadcrumbs,
    parameters: {
        docs: {
            description: {
                component: [
                    'The breadcrumb bar under the site header: a quick-navigation button (opens the page finder) and one arrow per path segment. By default the trail is generated from the URL and sitemap; pass `breadcrumbs` to set it by hand.',
                    'Segments with child pages become a `BreadcrumbHub` dropdown unless `links_only` is set. Stories pass `breadcrumbs` because the generated trail depends on the current URL and the signed-in pilot (gates, sitemap permissions).',
                    'Use `breadcrumb_page_title` to rename the last generated segment (a fleet name instead of its id).',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        breadcrumbs: { control: 'object', description: 'Manual trail: `{ accumulated_path, page_title }[]`. Generated from the URL when omitted.' },
        breadcrumb_page_title: { control: 'text', description: 'Title for the last generated segment.' },
        path: { control: 'text', description: 'Path to build the trail from instead of the current URL.' },
        is_landing_page: { control: 'boolean', description: 'Remove the inline padding and neocom offset used on landing pages.' },
        links_only: { control: 'boolean', description: 'Render plain links, never hub dropdowns.' },
    },
    args: {
        breadcrumbs: FLEET_TRAIL,
        is_landing_page: false,
        links_only: true,
    },
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('link', { name: 'Fleets' })).toHaveAttribute('href', '/fleets/')
        await expect(canvas.getByRole('link', { name: 'Upcoming' })).toHaveAttribute('href', '/fleets/upcoming/')
        await expect(canvas.getByRole('link', { name: 'Fleet 92221' })).toHaveAttribute('href', '/fleets/92221/')
        await expect(canvasElement.querySelector('.breadcrumbs')).not.toBeNull()
    },
}

export const OrderIsPreserved = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const labels = Array.from(canvasElement.querySelectorAll('.breadcrumbs a small')).map(el => el.textContent?.trim())
        await expect(labels).toEqual(['Fleets', 'Upcoming', 'Fleet 92221'])
    },
}

export const QuickNavigationButton = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const button = canvasElement.querySelector('.breadcrumbs button')
        await expect(button).not.toBeNull()
        await expect(button?.getAttribute('x-on:click')).toBe('show_pages_finder()')
        await expect(button?.querySelector('svg, img')).not.toBeNull()
    },
}

export const QuickNavigationHasAccessibleName = {
    name: 'Quick navigation button has an accessible name',
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        // The button is an icon only: its name comes from aria-label.
        await expect(within(canvasElement).getByRole('button', { name: 'Quick navigation' })).toBeInTheDocument()
    },
}

export const SingleLevel = {
    args: { breadcrumbs: [{ accumulated_path: '/doctrines/', page_title: 'Doctrines' }] },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getAllByRole('link')).toHaveLength(1)
        await expect(within(canvasElement).getByRole('link', { name: 'Doctrines' })).toBeVisible()
    },
}

export const LandingPage = {
    args: { is_landing_page: true, breadcrumbs: [{ accumulated_path: '/ships/', page_title: 'Ships' }] },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelector('.component')).toHaveClass('is-landing-page')
    },
}

export const DeepTrail = {
    args: {
        breadcrumbs: [
            { accumulated_path: '/alliance/', page_title: 'Alliance' },
            { accumulated_path: '/alliance/corporations/', page_title: 'Corporations' },
            { accumulated_path: '/alliance/corporations/rattini-tribe/', page_title: 'Rattini Tribe' },
            { accumulated_path: '/alliance/corporations/rattini-tribe/members/', page_title: 'Members' },
        ],
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getAllByRole('link')).toHaveLength(4)
        await expect(within(canvasElement).getByRole('link', { name: 'Rattini Tribe' })).toHaveAttribute('href', '/alliance/corporations/rattini-tribe/')
    },
}
