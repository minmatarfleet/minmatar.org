import { expect, within } from 'storybook/test'
import BreadcrumbLink from '@components/page/BreadcrumbLink.astro'

export default {
    title: 'Page/BreadcrumbLink',
    component: BreadcrumbLink,
    parameters: {
        docs: {
            description: {
                component: [
                    'One arrow-shaped step of the breadcrumb trail, drawn with a `clip-path` over a `--fleet-red` background. `PageBreadcrumbs` renders one per path segment that has a page.',
                    'The href goes through `translatePath`, so pass the language-less path (`/fleets/`). Use `PageBreadcrumbs` rather than placing these by hand; they are not meant for in-content links.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        accumulated_path: { control: 'text', description: 'Path of the page this step links to, with leading and trailing slash.' },
        page_title: { control: 'text', description: 'Label shown in the arrow.' },
    },
    args: {
        accumulated_path: '/fleets/',
        page_title: 'Fleets',
    },
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const link = within(canvasElement).getByRole('link', { name: 'Fleets' })
        await expect(link).toHaveAttribute('href', '/fleets/')
        await expect(link.querySelector('small')).toHaveTextContent('Fleets')
    },
}

export const Nested = {
    args: { accumulated_path: '/fleets/upcoming/', page_title: 'Upcoming' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByRole('link', { name: 'Upcoming' })).toHaveAttribute('href', '/fleets/upcoming/')
    },
}

export const NumericSegment = {
    args: { accumulated_path: '/fleets/92221/', page_title: '#92221' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByRole('link', { name: '#92221' })).toHaveAttribute('href', '/fleets/92221/')
    },
}

export const LongTitle = {
    args: { accumulated_path: '/alliance/corporations/', page_title: 'Corporations of the Minmatar Fleet Alliance' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const link = within(canvasElement).getByRole('link')
        await expect(link).toHaveTextContent('Corporations of the Minmatar Fleet Alliance')
    },
}
