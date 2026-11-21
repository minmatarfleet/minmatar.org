import { expect, within } from 'storybook/test'
import PageTitle from '@components/page/PageTitle.astro'

export default {
    title: 'Page/PageTitle',
    component: PageTitle,
    parameters: {
        docs: {
            description: {
                component: [
                    'The `<h1>` at the top of a page, linked to the page itself by default (so reloading or copying the URL from the title works). Pages render it inside the page header next to `PageSubheader` and `PageActions`.',
                    'Pass `path` to point the link somewhere other than the current URL, `no_link` for a plain heading (dialogs, partials) and `is_landing` for the large landing-page size.',
                    'Extra attributes are spread on the `<h1>`, not on the wrapper. In stories the current URL is fixed, so a `path` is passed to show a realistic link.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        is_landing: { control: 'boolean', description: 'Large `--step-5` heading used on landing pages.' },
        no_link: { control: 'boolean', description: 'Render the text without wrapping it in a link to the current page.' },
        path: { control: 'text', description: 'Link target; defaults to the current pathname, search and hash.' },
    },
    args: {
        is_landing: false,
        no_link: false,
        path: '/fleets/92221/',
        slots: { default: 'Rifter Armada: Tuesday Roam' },
    },
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        const heading = canvas.getByRole('heading', { level: 1 })
        await expect(heading).toHaveTextContent('Rifter Armada: Tuesday Roam')
        await expect(heading).not.toHaveClass('is-landing')
        await expect(within(heading).getByRole('link')).toHaveAttribute('href', '/fleets/92221/')
        await expect(canvasElement.querySelector('.page-title')).not.toBeNull()
    },
}

export const NoLink = {
    args: { no_link: true, slots: { default: 'Fleet history' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { level: 1, name: 'Fleet history' })).toBeVisible()
        await expect(canvas.queryByRole('link')).toBeNull()
    },
}

export const Landing = {
    args: { is_landing: true, path: '/', slots: { default: 'Minmatar Fleet' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const heading = within(canvasElement).getByRole('heading', { level: 1 })
        await expect(heading).toHaveClass('is-landing')
        await expect(within(heading).getByRole('link', { name: 'Minmatar Fleet' })).toHaveAttribute('href', '/')
    },
}

export const CustomPath = {
    args: { path: '/doctrines/?tab=logistics#kikimora', slots: { default: 'Kikimora logistics' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const link = within(canvasElement).getByRole('link', { name: 'Kikimora logistics' })
        await expect(link).toHaveAttribute('href', '/doctrines/?tab=logistics#kikimora')
    },
}

export const LongTitle = {
    args: {
        slots: { default: 'Strategic Operation: Defend the Amamake Freeport Against the Amarr Navy Armada Push, Second Wave' },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const heading = within(canvasElement).getByRole('heading', { level: 1 })
        await expect(heading.textContent).toContain('Second Wave')
        await expect(canvasElement.querySelector('.page-title')).not.toBeNull()
    },
}

export const WithAttributes = {
    args: { id: 'page-title', 'data-fleet-id': '92221', slots: { default: 'Fleet 92221' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const heading = within(canvasElement).getByRole('heading', { level: 1 })
        await expect(heading).toHaveAttribute('id', 'page-title')
        await expect(heading).toHaveAttribute('data-fleet-id', '92221')
    },
}
