import { expect, within, userEvent } from 'storybook/test'
import SolarSystemResults from '@components/blocks/sde/SolarSystemResults.astro'
import { SYSTEMS, system } from './_fixtures'

type Ctx = { canvasElement: HTMLElement }

const WARZONE = ['Amamake', 'Huola', 'Auga', 'Vard', 'Old Man Star', 'Tama'].map(system)

export default {
    title: 'EVE/SDE/SolarSystemResults',
    component: SolarSystemResults,
    parameters: {
        docs: {
            description: {
                component: [
                    'A list of solar systems: the results SolarSystemSearch\'s partial renders, or any system list a page already has (stagings, cyno spots). Rows are SolarSystemTag with the star icon. Plain rows are read-only; `href_template` links each row (`{system_id}`, `{system_name}`, same-site paths only); `selectable` makes each row a button that dispatches `sde-system-select` with `{ system_id, system_name }`.',
                    'No rows renders EmptyState, naming the query when there is one. The fixture systems cover every security band, the 0.0–0.05 rounding edge (Egbinger), null-sec and J-space.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        systems: { control: 'object', description: 'The `SdeSolarSystem` rows to list.' },
        query: { control: 'text', description: 'What was searched; named in the empty state.' },
        href_template: { control: 'text', description: 'Same-site link per row, e.g. `/intel/moons/{system_name}`.' },
        selectable: { control: 'boolean', description: 'Rows are buttons that dispatch `sde-system-select`.' },
        empty_title: { control: 'text', description: 'Replaces the default empty message.' },
    },
    args: {
        systems: WARZONE,
        selectable: false,
    },
}

export const Default = {
    name: 'Minmatar warzone',
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        const items = within(canvas.getByRole('list')).getAllByRole('listitem')
        await expect(items).toHaveLength(6)
        await expect(items[0]).toHaveTextContent('Amamake')
        await expect(canvas.getByText('6 results')).toHaveClass('visually-hidden')
        const bands = [...canvasElement.querySelectorAll('.solar-system-tag')].map((tag) => tag.getAttribute('data-security-band'))
        await expect(new Set(bands)).toEqual(new Set(['low']))
    },
}

export const EverySecurityBand = {
    args: { systems: SYSTEMS },
    play: async ({ canvasElement }: Ctx) => {
        const shown = [...canvasElement.querySelectorAll('.security-status')].map((element) => element.getAttribute('data-security'))
        for (const value of ['1.0', '0.9', '0.8', '0.7', '0.6', '0.5', '0.4', '0.3', '0.2', '0.1', '-0.1', '-0.4', '-1.0'])
            await expect(shown).toContain(value)
        const bands = new Set([...canvasElement.querySelectorAll('.solar-system-tag')].map((tag) => tag.getAttribute('data-security-band')))
        await expect(bands).toEqual(new Set(['high', 'low', 'null', 'wormhole']))
    },
}

export const Linked = {
    args: { systems: WARZONE.slice(0, 3), href_template: '/intel/moons/{system_name}' },
    play: async ({ canvasElement }: Ctx) => {
        const links = within(canvasElement).getAllByRole('link')
        await expect(links).toHaveLength(3)
        await expect(links[0]).toHaveAttribute('href', '/intel/moons/Amamake')
    },
}

export const Selectable = {
    args: { systems: WARZONE.slice(0, 3), selectable: true },
    play: async ({ canvasElement }: Ctx) => {
        const picked: unknown[] = []
        canvasElement.addEventListener('sde-system-select', (event) => picked.push((event as CustomEvent).detail))
        const huola = within(canvasElement).getByRole('button', { name: /Huola/ })
        await expect(huola).toHaveAttribute('data-system-id', '30003067')
        await userEvent.click(huola)
        await expect(picked).toEqual([{ system_id: 30003067, system_name: 'Huola' }])
    },
}

export const EmptyWithQuery = {
    name: 'Empty: no match',
    args: { systems: [], query: 'Amamakee' },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByText('No systems match “Amamakee”')).toHaveClass('empty-state')
    },
}

export const Empty = {
    args: { systems: [] },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByText('No systems found')).toHaveClass('empty-state')
    },
}
