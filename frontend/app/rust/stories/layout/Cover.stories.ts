import { expect, within } from 'storybook/test'
import Cover from '@components/compositions/Cover.astro'
import { space_control, demo_box } from '../_controls'

const el_of = (canvasElement: HTMLElement) => canvasElement.querySelector('.cover') as HTMLElement
const style_of = (canvasElement: HTMLElement) => el_of(canvasElement).getAttribute('style')?.replace(/\s+/g, '') ?? ''

export default {
    title: 'Layout/Cover',
    component: Cover,
    parameters: {
        docs: {
            description: {
                component: [
                    'A full-height column with an optional `header` slot at the top, an optional `footer` slot at the bottom, and the default slot vertically centered between them. Used for landing and sign-in style screens.',
                    '`neocom` (default on) keeps extra room on the inline end for the Neocom rail. The block size is `100vh`, so in Storybook it fills the whole preview frame. `minHeight` and `noPad` are declared in `Props` but not used by the component.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        space: space_control('Padding around the cover (inline end is overridden when `neocom` is on).'),
        minHeight: { control: 'text', description: 'Declared but unused by the component.' },
        noPad: { control: 'boolean', description: 'Declared but unused by the component.' },
        neocom: { control: 'boolean', description: 'Reserve `--space-l-xl` on the inline end for the Neocom rail instead of `space`.' },
    },
    args: {
        space: 'var(--space-2xl-3xl)',
        neocom: true,
        slots: {
            header: demo_box('Header: Minmatar Fleet'),
            default: demo_box('Body: sign in with EVE Online'),
            footer: demo_box('Footer: terms and privacy'),
        },
    },
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const el = el_of(canvasElement)
        const canvas = within(canvasElement)
        await expect(el).toHaveClass('cover')
        await expect(canvas.getByText('Header: Minmatar Fleet')).toBeVisible()
        await expect(canvas.getByText('Footer: terms and privacy')).toBeVisible()
        await expect(el.querySelector('.cover-body')).toContainElement(canvas.getByText('Body: sign in with EVE Online'))
        const style = style_of(canvasElement)
        await expect(style).toContain('--cover_space:var(--space-2xl-3xl)')
        await expect(style).toContain('--cover_space_inline_end:var(--space-l-xl)')
    },
}

export const WithoutNeocom = {
    args: { neocom: false, space: 'var(--space-m)' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const style = style_of(canvasElement)
        await expect(style).toContain('--cover_space:var(--space-m)')
        await expect(style).toContain('--cover_space_inline_end:var(--space-m)')
    },
}

export const BodyOnly = {
    args: {
        slots: {
            default: '<h1>Join the Minmatar Fleet</h1><p>Sign in with EVE Online to see your fleets, doctrines and SRP.</p>',
        },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const el = el_of(canvasElement)
        await expect(within(el).getByRole('heading', { name: 'Join the Minmatar Fleet' })).toBeVisible()
        await expect(el.children).toHaveLength(1)
        await expect(el.firstElementChild).toHaveClass('cover-body')
    },
}

export const HeaderAndBody = {
    args: {
        slots: {
            header: '<nav aria-label="Account"><a href="/account/">Account</a></nav>',
            default: demo_box('Body'),
        },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const el = el_of(canvasElement)
        await expect(within(el).getByRole('navigation', { name: 'Account' })).toBeVisible()
        await expect(el.lastElementChild).toHaveClass('cover-body')
    },
}

export const FooterAndBody = {
    args: {
        slots: {
            default: demo_box('Body'),
            footer: '<small>Minmatar Fleet Alliance, FL33T</small>',
        },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const el = el_of(canvasElement)
        await expect(within(el).getByText('Minmatar Fleet Alliance, FL33T')).toBeVisible()
        await expect(el.firstElementChild).toHaveClass('cover-body')
    },
}

export const FillsViewport = {
    name: 'Fills the viewport height',
    tags: ['browser'],
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(el_of(canvasElement).getBoundingClientRect().height).toBeGreaterThanOrEqual(window.innerHeight - 1)
    },
}
