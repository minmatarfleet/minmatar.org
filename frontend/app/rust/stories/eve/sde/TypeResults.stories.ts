import { expect, within, userEvent } from 'storybook/test'
import TypeResults from '@components/blocks/sde/TypeResults.astro'
import { MODULES, SHIPS, ship } from './_fixtures'

type Ctx = { canvasElement: HTMLElement }

const T1_HULLS = ['Rifter', 'Breacher', 'Thrasher', 'Stabber', 'Rupture', 'Hurricane', 'Cyclone', 'Tempest', 'Typhoon'].map(ship)

export default {
    title: 'EVE/SDE/TypeResults',
    component: TypeResults,
    parameters: {
        docs: {
            description: {
                component: [
                    'A list of inventory types: the results TypeSearch\'s partial renders, or any hull or module list a page already has. Rows are TypeRow. Plain rows are read-only; `href_template` links each row (`{type_id}`, `{type_name}`, same-site paths only, anything else is ignored); `selectable` makes each row a button that dispatches `sde-type-select` with `{ type_id, type_name }` for an Alpine parent.',
                    'No rows renders EmptyState, naming the query when there is one. A visually-hidden "N results" line is announced when the list sits in an aria-live region (TypeSearch\'s results region is one).',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        types: { control: 'object', description: 'The `SdeType` rows to list.' },
        query: { control: 'text', description: 'What was searched; named in the empty state.' },
        href_template: { control: 'text', description: 'Same-site link per row, e.g. `/market/types/{type_id}/`.' },
        selectable: { control: 'boolean', description: 'Rows are buttons that dispatch `sde-type-select`.' },
        size: { control: 'select', options: [32, 48, 64], description: 'Icon width in px.' },
        show_slots: { control: 'boolean', description: 'Slot layout under each hull.' },
        empty_title: { control: 'text', description: 'Replaces the default empty message.' },
    },
    args: {
        types: T1_HULLS,
        selectable: false,
        size: 32,
        show_slots: false,
    },
}

export const Default = {
    name: 'Minmatar T1 hulls',
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        const items = within(canvas.getByRole('list')).getAllByRole('listitem')
        await expect(items).toHaveLength(9)
        await expect(items[0]).toHaveTextContent('Rifter')
        await expect(items[8]).toHaveTextContent('Typhoon')
        await expect(canvas.getByText('9 results')).toHaveClass('visually-hidden')
        await expect(canvas.queryByRole('link')).toBeNull()
        await expect(canvas.queryByRole('button')).toBeNull()
    },
}

export const WithSlots = {
    name: 'Hulls with slots',
    args: { types: SHIPS.filter((type) => type.meta_group_name !== 'Tech I').slice(0, 6), size: 48, show_slots: true },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getAllByRole('list', { name: 'Slot layout' })).toHaveLength(6)
        await expect(canvas.getByText('Jaguar')).toBeVisible()
    },
}

export const ModulesByMetaGroup = {
    name: 'Modules across meta groups',
    args: { types: MODULES },
    play: async ({ canvasElement }: Ctx) => {
        const groups = [...canvasElement.querySelectorAll('.meta-group-tag')].map((tag) => tag.getAttribute('data-meta-group'))
        for (const token of ['tech-i', 'tech-ii', 'tech-iii', 'faction', 'storyline', 'deadspace', 'officer'])
            await expect(groups).toContain(token)
    },
}

export const Linked = {
    args: { types: MODULES.slice(0, 4), href_template: '/market/types/{type_id}/?name={type_name}' },
    play: async ({ canvasElement }: Ctx) => {
        const links = within(canvasElement).getAllByRole('link')
        await expect(links).toHaveLength(4)
        await expect(links[0]).toHaveAttribute('href', '/market/types/486/?name=200mm%20AutoCannon%20I')
        await expect(links[3]).toHaveAttribute('href', "/market/types/85010/?name=Ramaku's%20Modified%20200mm%20AutoCannon")
    },
}

export const OffSiteTemplateIgnored = {
    name: 'Off-site link template is ignored',
    args: { types: T1_HULLS.slice(0, 2), href_template: '//evil.example/{type_id}' },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).queryByRole('link')).toBeNull()
    },
}

export const Selectable = {
    args: { types: T1_HULLS.slice(0, 5), selectable: true },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        const picked: unknown[] = []
        canvasElement.addEventListener('sde-type-select', (event) => picked.push((event as CustomEvent).detail))
        const stabber = canvas.getByRole('button', { name: /Stabber/ })
        await expect(stabber).toHaveAttribute('type', 'button')
        await expect(stabber).toHaveAttribute('data-type-id', '622')
        await userEvent.click(stabber)
        await expect(picked).toEqual([{ type_id: 622, type_name: 'Stabber' }])
    },
}

export const EmptyWithQuery = {
    name: 'Empty: no match',
    args: { types: [], query: 'Nidhoggur Fleet Issue' },
    play: async ({ canvasElement }: Ctx) => {
        const empty = within(canvasElement).getByText('No items match “Nidhoggur Fleet Issue”')
        await expect(empty).toHaveClass('empty-state')
        await expect(canvasElement.querySelector('[role="list"]')).toBeNull()
    },
}

export const Empty = {
    args: { types: [] },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByText('No items found')).toHaveClass('empty-state')
    },
}
