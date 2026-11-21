import { expect, within } from 'storybook/test'
import IntelEntitySearchResults from '@components/blocks/IntelEntitySearchResults.astro'
import { search_results } from '../../../fixtures/features/intel-and-combat'

export default {
    title: 'Features/Intel and combat/IntelEntitySearchResults',
    component: IntelEntitySearchResults,
    parameters: {
        docs: {
            description: {
                component: [
                    'Name-search results for the affiliation database: each alliance, corporation or pilot links to its intel profile, with its kind, investigation status and bloc. It is the answer to the search box on `/intel/affiliations/` (`intel_affiliation_search_component`).',
                    'Nothing renders until the query is three letters long, and a long-enough query with no matches shows the empty state. The scenarios cover the short query, no match, a mixed list and a single hit.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        results: { control: 'object', description: 'Matches from the search endpoint.' },
        query: { control: 'text', description: 'The search text; under 3 characters renders nothing.' },
    },
    args: { results: search_results, query: 'snuf' },
}

type Ctx = { canvasElement: HTMLElement }

export const MixedResults = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getAllByRole('listitem')).toHaveLength(5)
        await expect(canvas.getByRole('link', { name: 'Snuffed Out' })).toHaveAttribute('href', '/intel/affiliations/alliance/99010079/')
        await expect(canvas.getByRole('link', { name: 'Snuffed Scout' })).toHaveAttribute('href', '/intel/affiliations/character/2119873420/')
        await expect(canvas.getByText('Alliance')).toBeVisible()
        await expect(canvas.getAllByText('Corporation')).toHaveLength(2)
        await expect(canvas.getByText('Investigation failed')).toBeVisible()
        await expect(canvas.getByText('Not investigated')).toBeVisible()
    },
}

export const BlocTagsLinkAndLikely = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('link', { name: 'Goonswarm Federation' })).toHaveAttribute('href', '/intel/affiliations/blocs/11/')
        await expect(canvasElement.querySelectorAll('.intel-bloc-tag--likely')).toHaveLength(1)
    },
}

export const SingleResult = {
    args: { results: [search_results[2]], query: 'Snuffed Scout' },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getAllByRole('listitem')).toHaveLength(1)
        await expect(canvas.getByText('Pilot')).toBeVisible()
        await expect(canvas.getByText('Queued')).toBeVisible()
    },
}

export const NoMatches = {
    args: { results: [], query: 'zzzqx' },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByText('Nothing in the database by that name yet.')).toBeVisible()
        await expect(within(canvasElement).queryByRole('list')).toBeNull()
    },
}

export const QueryTooShort = {
    args: { results: [], query: 'sn' },
    play: async ({ canvasElement }: Ctx) => {
        await expect(canvasElement.textContent?.trim()).toBe('')
    },
}
