import { expect, within } from 'storybook/test'
import GuidePostCard from '@components/blocks/GuidePostCard.astro'
import { guide_onboarding, guide_cruiser, guide_capitals, guide_long, guide_custom_path } from '../../../fixtures/features/content'

export default {
    title: 'Features/Content/GuidePostCard',
    component: GuidePostCard,
    parameters: {
        docs: {
            description: {
                component: [
                    'A guide card: the category cover, a category tag, the title, an excerpt and a View button. The cover comes from the guide slug or, failing that, its category.',
                    'It fills the guide catalogue on `/guides/` and the guide hubs. The scenarios show an onboarding guide, a ship guide, a capital guide, long text and a guide that lives at a custom path.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        guide: { control: 'object', description: 'The guide metadata (GuideMeta).' },
    },
    args: { guide: guide_onboarding },
}

export const Onboarding = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { name: 'Your first fleet' })).toBeVisible()
        await expect(canvas.getByText('Onboarding')).toBeVisible()
        const view = canvas.getByRole('link', { name: 'View' })
        await expect(view).toHaveAttribute('href', '/guides/onboarding-first-fleet/')
    },
}

export const ShipGuide = {
    args: { guide: guide_cruiser },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByText('Faction Warfare Ships')).toBeVisible()
        await expect(within(canvasElement).getByRole('link', { name: 'View' })).toHaveAttribute('href', '/guides/faction-warfare-cruiser-guide/')
    },
}

export const CapitalGuide = {
    args: { guide: guide_capitals },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelector('img')).toHaveAttribute('src', expect.stringContaining('capitals-cover'))
    },
}

export const LongText = {
    args: { guide: guide_long },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByRole('heading', { name: guide_long.title })).toBeVisible()
        await expect(canvasElement.querySelector('.guide-excerpt')?.textContent?.length).toBeGreaterThan(300)
    },
}

export const CustomPath = {
    args: { guide: guide_custom_path },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByRole('link', { name: 'View' })).toHaveAttribute('href', '/alliance/town-halls/')
    },
}
