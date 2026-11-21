import { expect } from 'storybook/test'
import TypeSpecimen from '../../components/foundations/TypeSpecimen.astro'

type Ctx = { canvasElement: HTMLElement }

const families = (canvas: HTMLElement) => [...canvas.querySelectorAll<HTMLElement>('[data-family]')].map((el) => el.dataset.family)

export default {
    title: 'Foundations/Typography',
    component: TypeSpecimen,
    parameters: {
        docs: {
            description: {
                component: [
                    'Every font family the site declares, scanned from the source: the root font tokens (`--heading-font`, `--button-font`, `--default-font`, `--countdown-font`, ...), component-scoped tokens (`--chronicle-font`, the guides\' `--*-display-font`), `@font-face`, `@fontsource` packages and Google Fonts imports.',
                    '**Norwester** (self-hosted) sets headings, badges and tags in capitals; **Montserrat** sets buttons and body text; **Qahiri** sets countdowns. The long-form guides add **Orbitron** and **Source Sans 3**, and the chronicle uses **Lora**. Use a token, never a family name.',
                    'The type scale is fluid (Utopia): every `--step-*` grows with the viewport between 320 px and 1240 px.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        sample: { control: 'text', description: 'The specimen sentence.' },
        show_scale: { control: 'boolean', description: 'Show the `--step-*` scale.' },
        show_system: { control: 'boolean', description: 'Also list system fallbacks (serif, monospace, ...).' },
    },
    args: {
        sample: 'Rifter fleet forming in Amamake at 19:00',
        show_scale: true,
        show_system: false,
    },
}

export const AllFonts = {
    name: 'All fonts',
    play: async ({ canvasElement }: Ctx) => {
        const listed = families(canvasElement)
        for (const family of ['Norwester', 'Montserrat Variable', 'Qahiri', 'Orbitron', 'Source Sans 3', 'Lora'])
            await expect(listed).toContain(family)
        const norwester = canvasElement.querySelector<HTMLElement>('[data-family="Norwester"]')!
        await expect(norwester.dataset.source).toBe('self-hosted')
        await expect(norwester.textContent).toContain('--heading-font')
    },
}

export const Scale = {
    name: 'Type scale',
    args: { sample: 'Fleet up' },
    play: async ({ canvasElement }: Ctx) => {
        const rows = [...canvasElement.querySelectorAll<HTMLElement>('.scale [data-token]')]
        await expect(rows.map((row) => row.dataset.token)).toEqual(['--step-5', '--step-4', '--step-3', '--step-2', '--step-1', '--step-0', '--step--1', '--step--2'])
    },
}

export const WithFallbacks = {
    name: 'With system fallbacks',
    args: { show_system: true, show_scale: false },
    play: async ({ canvasElement }: Ctx) => {
        const sources = [...canvasElement.querySelectorAll<HTMLElement>('[data-source]')].map((el) => el.dataset.source)
        await expect(sources).toContain('system')
        await expect(canvasElement.querySelector('.scale')).toBeNull()
    },
}

export const CustomSample = {
    name: 'Custom sample',
    args: { sample: 'Ship replacement approved', show_scale: false },
    play: async ({ canvasElement }: Ctx) => {
        await expect(canvasElement.querySelectorAll('.sample')[0].textContent).toBe('Ship replacement approved')
    },
}
