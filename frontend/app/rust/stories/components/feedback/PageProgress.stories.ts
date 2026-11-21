import { expect, within } from 'storybook/test'
import PageProgress from '@components/blocks/PageProgress.astro'

type Play = { canvasElement: HTMLElement }

const sections = ['overview', 'positioning', 'comms', 'after-action']

export default {
    title: 'Components/Feedback/PageProgress',
    component: PageProgress,
    parameters: {
        docs: {
            description: {
                component: [
                    'Drop-in "how much of this page have you read" bar for long guides. It wraps `PageProgressTracker`, which watches each section with an `IntersectionObserver` and stores progress in localStorage for anonymous visitors (merged to the account on login).',
                    'Build the props with `pageProgressFromMarkdown` or `pageProgressFromSections` from `@helpers/pageProgress`, mount the component inside a `[data-page-progress-root]` wrapper and mark every section with `data-section-id`. It renders nothing when `section_ids` is empty.',
                    'Needs the signed-in cookie (`auth_token`) from the request, so in Storybook it always shows the anonymous, localStorage flavour. `require_ack` adds a "Mark as read" button once every section has been seen.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        page_key: { control: 'text', description: 'Stable key for the page, used in localStorage and the API path.' },
        page_title: { control: 'text', description: 'Human title stored with the progress entry.' },
        version: { control: 'text', description: 'Content hash. A new version resets progress for that page.' },
        section_ids: { control: 'object', description: 'Ids of the sections to track, in reading order. Empty renders nothing.' },
        require_ack: { control: 'boolean', description: 'Show a "Mark as read" button once all sections are read.' },
    },
    args: {
        page_key: 'guides/fleet-roles',
        page_title: 'Fleet roles',
        version: 'v1',
        section_ids: sections,
        require_ack: true,
    },
}

export const Default = {
    play: async ({ canvasElement }: Play) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Progress:', { exact: false })).toBeVisible()
        const root = canvasElement.querySelector('.page-progress-tracker') as HTMLElement
        const config = JSON.parse(root.getAttribute('data-config') ?? '{}')
        await expect(config.pageKey).toBe('guides/fleet-roles')
        await expect(config.sectionIds).toEqual(sections)
    },
}

export const WithoutAcknowledgement = {
    args: { require_ack: false },
    play: async ({ canvasElement }: Play) => {
        const root = canvasElement.querySelector('.page-progress-tracker') as HTMLElement
        await expect(JSON.parse(root.getAttribute('data-config') ?? '{}').requireAck).toBe(false)
    },
}

export const WithAcknowledgement = {
    args: { require_ack: true },
    play: async ({ canvasElement }: Play) => {
        const root = canvasElement.querySelector('.page-progress-tracker') as HTMLElement
        await expect(JSON.parse(root.getAttribute('data-config') ?? '{}').requireAck).toBe(true)
        await expect(within(canvasElement).getByText('Progress:', { exact: false })).toBeVisible()
    },
}

export const SingleSection = {
    args: { page_key: 'guides/cyno-basics', page_title: 'Cyno basics', section_ids: ['cyno-basics'] },
    play: async ({ canvasElement }: Play) => {
        const root = canvasElement.querySelector('.page-progress-tracker') as HTMLElement
        await expect(JSON.parse(root.getAttribute('data-config') ?? '{}').sectionIds).toEqual(['cyno-basics'])
    },
}

export const NoSections = {
    name: 'No sections (renders nothing)',
    args: { section_ids: [] },
    parameters: { rust: { allow_empty: true } },
    play: async ({ canvasElement }: Play) => {
        await expect(canvasElement.querySelector('.page-progress-tracker')).toBeNull()
    },
}
