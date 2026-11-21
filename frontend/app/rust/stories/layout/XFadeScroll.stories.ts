import { expect, within } from 'storybook/test'
import XFadeScroll from '@components/compositions/XFadeScroll.astro'
import { space_control } from '../_controls'

// The site defines `edge_fade` in FooterScripts, which Storybook's head does not load: register the same
// component here so the fade works in the browser.
const register_edge_fade = () => {
    const w = window as any
    if (w.edge_fade) return
    w.edge_fade = () => ({
        init() {
            const el = (this as any).$el as HTMLElement
            const update = () => {
                el.classList.toggle('fade-start', el.scrollLeft > 0)
                el.classList.toggle('fade-end', el.scrollLeft + el.clientWidth < el.scrollWidth - 1)
            }
            update()
            const ro = new ResizeObserver(update)
            ro.observe(el)
            if (el.firstElementChild) ro.observe(el.firstElementChild)
            el.addEventListener('scroll', update, { passive: true })
        },
    })
}

const el_of = (canvasElement: HTMLElement) => canvasElement.querySelector('.xfade-scroll') as HTMLElement

const chip = (label: string) => `<span class="rust-demo-box shrink-0">${label}</span>`
const doctrine_chips = [
    'Muninn', 'Cerberus', 'Osprey Navy Issue', 'Scimitar', 'Huginn', 'Rapier', 'Stabber Fleet Issue', 'Vagabond',
    'Hurricane', 'Tempest Fleet Issue', 'Claw', 'Slasher', 'Probe', 'Wolf', 'Jaguar', 'Rifter',
].map(chip).join('')

const srp_table = `
<table class="min-w-max">
    <thead><tr><th>Pilot</th><th>Ship</th><th>Fleet</th><th>System</th><th>Loss value</th><th>Payout</th><th>Status</th><th>Reviewed by</th></tr></thead>
    <tbody>
        <tr><td>Kel'dar Atram</td><td>Muninn</td><td>Home defense</td><td>Amamake</td><td>312,400,000 ISK</td><td>312,400,000 ISK</td><td>Approved</td><td>Fleet Commander</td></tr>
        <tr><td>Ashen Vael</td><td>Scimitar</td><td>Stratop</td><td>Hek</td><td>187,900,000 ISK</td><td>187,900,000 ISK</td><td>Pending</td><td>Unassigned</td></tr>
        <tr><td>Torvik Dren</td><td>Rifter</td><td>Roam</td><td>Vard</td><td>1,200,000 ISK</td><td>1,200,000 ISK</td><td>Approved</td><td>Fleet Commander</td></tr>
    </tbody>
</table>`

export default {
    title: 'Layout/XFadeScroll',
    component: XFadeScroll,
    parameters: {
        docs: {
            description: {
                component: [
                    'A horizontal scroll container that fades its left and right edges when there is more content that way. Use it for wide tables and chip rows instead of a hand-rolled `overflow-x: auto` (docs/frontend-design.md §4).',
                    'The fade is driven by the global Alpine `edge_fade()` component, which toggles `fade-start` / `fade-end` from the scroll position and watches resizes, so it needs a real browser. Without overflow no fade shows. Set `flex` for a row of chips (`display: flex`); leave it off for a table.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        flex: { control: 'boolean', description: 'Lay children out in a flex row (chip rows). Leave off for tables.' },
        fade_size: space_control('Width of each edge fade, a space token.'),
    },
    decorators: [
        (story: () => unknown) => {
            if (typeof window !== 'undefined') register_edge_fade()
            return story()
        },
    ],
    args: {
        flex: true,
        fade_size: 'var(--space-s)',
        slots: { default: doctrine_chips },
    },
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const el = el_of(canvasElement)
        await expect(el).toHaveClass('xfade-scroll', 'flex')
        await expect(el).toHaveAttribute('x-data', 'edge_fade()')
        await expect(el.getAttribute('style')?.replace(/\s+/g, '')).toContain('--xfade_size:var(--space-s)')
        await expect(within(canvasElement).getByText('Muninn')).toBeInTheDocument()
    },
}

export const ChipRow = {
    name: 'Chip row fades at the end',
    args: { class: 'max-w-xl' },
    tags: ['browser'],
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const el = el_of(canvasElement)
        await expect(el.scrollWidth).toBeGreaterThan(el.clientWidth)
        await expect(el).toHaveClass('fade-end')
        await expect(el).not.toHaveClass('fade-start')
    },
}

export const ScrolledToMiddle = {
    name: 'Scrolled: fades both sides',
    args: { class: 'max-w-xl' },
    tags: ['browser'],
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const el = el_of(canvasElement)
        el.scrollLeft = 120
        el.dispatchEvent(new Event('scroll'))
        await expect(el).toHaveClass('fade-start')
        await expect(el).toHaveClass('fade-end')
    },
}

export const ScrolledToEnd = {
    name: 'Scrolled to the end: fades the start only',
    args: { class: 'max-w-xl' },
    tags: ['browser'],
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const el = el_of(canvasElement)
        el.scrollLeft = el.scrollWidth
        el.dispatchEvent(new Event('scroll'))
        await expect(el).toHaveClass('fade-start')
        await expect(el).not.toHaveClass('fade-end')
    },
}

export const WideTable = {
    name: 'Wide table',
    args: { flex: false, class: 'max-w-xl', slots: { default: srp_table } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const el = el_of(canvasElement)
        await expect(el).not.toHaveClass('flex')
        await expect(within(el).getByRole('table')).toBeInTheDocument()
        await expect(within(el).getByRole('columnheader', { name: 'Payout' })).toBeVisible()
    },
}

export const BigFade = {
    args: { fade_size: 'var(--space-2xl)', class: 'max-w-xl' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(el_of(canvasElement).getAttribute('style')?.replace(/\s+/g, '')).toContain('--xfade_size:var(--space-2xl)')
    },
}

export const NoOverflow = {
    name: 'Fits: no fade',
    args: { slots: { default: [chip('Rifter'), chip('Slasher')].join('') } },
    tags: ['browser'],
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const el = el_of(canvasElement)
        await expect(el).not.toHaveClass('fade-start')
        await expect(el).not.toHaveClass('fade-end')
    },
}
