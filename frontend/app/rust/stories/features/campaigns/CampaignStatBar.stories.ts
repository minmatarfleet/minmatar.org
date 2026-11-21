import { expect, within } from 'storybook/test'
import CampaignStatBar from '@components/blocks/CampaignStatBar.astro'
import { radio_control } from '../../_controls'
import { stat_bar_stats as stats } from '../../../fixtures/features/campaigns'

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'Features/Campaigns/CampaignStatBar',
    component: CampaignStatBar,
    parameters: {
        docs: {
            description: {
                component: [
                    'A row of label and value figures summarising a campaign: the hero of `/campaigns/<slug>/` uses the boxed grid, the compact headers on the roster and corporation pages use the inline variant. A stat with a `title` shows it as a tooltip, typically the unabbreviated number.',
                    'Scenarios: the boxed hero with six totals, the inline variant, a single stat, and a wide mix of long labels and big values.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        stats: { control: 'object', description: 'Label and value pairs, with an optional tooltip `title`.' },
        variant: radio_control(['boxed', 'inline'], '`boxed` is a translucent grid of tiles; `inline` is a flat row.'),
    },
    args: { stats, variant: 'boxed' },
}

export const Boxed = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvasElement.querySelectorAll('.campaign-stat')).toHaveLength(6)
        await expect(canvas.getByText('1,904')).toBeVisible()
        await expect(canvas.getByText('Kills')).toBeVisible()
        await expect(canvasElement.querySelector('.campaign-stat-bar-boxed')).not.toBeNull()
        await expect(canvas.getByText('128.4b').closest('.campaign-stat')).toHaveAttribute('title', '128,400,000,000 ISK')
    },
}

export const Inline = {
    args: { variant: 'inline' },
    play: async ({ canvasElement }: Ctx) => {
        await expect(canvasElement.querySelector('.campaign-stat-bar-inline')).not.toBeNull()
        await expect(canvasElement.querySelector('.campaign-stat-bar-boxed')).toBeNull()
        await expect(canvasElement.querySelectorAll('.campaign-stat')).toHaveLength(6)
    },
}

export const SingleStat = {
    args: { stats: [{ label: 'Pilots', value: '1' }] },
    play: async ({ canvasElement }: Ctx) => {
        await expect(canvasElement.querySelectorAll('.campaign-stat')).toHaveLength(1)
        await expect(within(canvasElement).getByText('Pilots')).toBeVisible()
    },
}

export const LongLabelsAndValues = {
    args: {
        stats: [
            { label: 'ISK destroyed this campaign across all enlisted pilots', value: '1,284,000,000,000,000' },
            { label: 'Strategic structure kills', value: '12' },
            { label: 'Capital hulls killed', value: '2' },
        ],
    },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('1,284,000,000,000,000')).toBeVisible()
        await expect(canvas.getByText('Capital hulls killed')).toBeVisible()
    },
}

export const NoStats = {
    args: { stats: [] },
    parameters: { rust: { allow_empty: true } },
    play: async ({ canvasElement }: Ctx) => {
        await expect(canvasElement.querySelectorAll('.campaign-stat')).toHaveLength(0)
    },
}
