import { expect, within } from 'storybook/test'
import Tag from '@components/blocks/Tag.astro'
import LockIcon from '@components/icons/LockIcon.astro'
import { TAG_COLORS, radio_control } from '../../_controls'

type Play = { canvasElement: HTMLElement }

export default {
    title: 'Components/Data display/Tag',
    component: Tag,
    parameters: {
        docs: {
            description: {
                component: [
                    'A small label for a category or state: a doctrine role, a fleet type, a security status. It is a `<span>` with `text`, never a slot, so the string is always escaped.',
                    '`variant="fill"` is a solid colour tag; `variant="outline"` is a bordered tag with no background, neutral unless a `color` is given. Colours come from `TAG_COLORS`: the five brand tokens and the eleven `security-status-*` tokens that mirror EVE system security. Text turns dark on `fleet-yellow`.',
                    'Use `Tag` for a label inside a row. For a count bubble use `NotificationBadge`; for the group-item visibility label use `VisibilityTag`. The outline variant has an `icon` slot.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        text: { control: 'text', description: 'The label.' },
        title: { control: 'text', description: 'Native tooltip.' },
        color: { control: 'select', options: TAG_COLORS, description: 'Background token (fill) or border and text colour (outline).' },
        text_color: { control: 'text', description: 'Override the text colour with any CSS value, such as `var(--background)`.' },
        narrow: { control: 'boolean', description: 'Less padding, for dense tables.' },
        variant: radio_control(['fill', 'outline'] as const, '`fill` solid, `outline` bordered and transparent.'),
    },
    args: {
        text: 'Logistics',
        color: 'fleet-red',
        narrow: false,
        variant: 'fill',
    },
}

const tag = (canvasElement: HTMLElement) => canvasElement.querySelector('.tag') as HTMLElement

export const Default = {
    play: async ({ canvasElement }: Play) => {
        const el = within(canvasElement).getByText('Logistics')
        await expect(el).toHaveClass('tag')
        await expect(el.tagName).toBe('SPAN')
        await expect(el).not.toHaveClass('narrow')
        await expect(el).not.toHaveClass('tag--outline')
    },
}

export const AllianceBlue = {
    args: { color: 'alliance-blue', text: 'Alliance fleet' },
    play: async ({ canvasElement }: Play) => {
        await expect(within(canvasElement).getByText('Alliance fleet')).toHaveClass('tag')
    },
}

export const MilitiaPurple = {
    args: { color: 'militia-purple', text: 'Militia' },
    play: async ({ canvasElement }: Play) => {
        await expect(within(canvasElement).getByText('Militia')).toBeVisible()
    },
}

export const Green = {
    args: { color: 'green', text: 'Approved' },
    play: async ({ canvasElement }: Play) => {
        await expect(within(canvasElement).getByText('Approved')).toBeVisible()
    },
}

export const YellowDarkText = {
    name: 'Fleet yellow (dark text)',
    args: { color: 'fleet-yellow', text: 'Training' },
    play: async ({ canvasElement }: Play) => {
        await expect(within(canvasElement).getByText('Training')).toBeVisible()
    },
}

export const HighSec = {
    name: 'Security status 1.0',
    args: { color: 'security-status-1', text: '1.0 Amarr' },
    play: async ({ canvasElement }: Play) => {
        await expect(within(canvasElement).getByText('1.0 Amarr')).toBeVisible()
    },
}

export const LowSec = {
    name: 'Security status 0.4',
    args: { color: 'security-status-point-4', text: '0.4 Amamake' },
    play: async ({ canvasElement }: Play) => {
        await expect(within(canvasElement).getByText('0.4 Amamake')).toBeVisible()
    },
}

export const NullSec = {
    name: 'Security status null',
    args: { color: 'security-status-null', text: '-0.9 Delve' },
    play: async ({ canvasElement }: Play) => {
        await expect(within(canvasElement).getByText('-0.9 Delve')).toBeVisible()
    },
}

export const SecurityPointNine = {
    name: 'Security status 0.9',
    args: { color: 'security-status-point-9', text: '0.9 Rancer' },
    play: async ({ canvasElement }: Play) => {
        await expect(within(canvasElement).getByText('0.9 Rancer')).toHaveClass('tag')
    },
}

export const SecurityPointEight = {
    name: 'Security status 0.8',
    args: { color: 'security-status-point-8', text: '0.8 Tama' },
    play: async ({ canvasElement }: Play) => {
        await expect(within(canvasElement).getByText('0.8 Tama')).toHaveClass('tag')
    },
}

export const SecurityPointSeven = {
    name: 'Security status 0.7',
    args: { color: 'security-status-point-7', text: '0.7 Jita' },
    play: async ({ canvasElement }: Play) => {
        await expect(within(canvasElement).getByText('0.7 Jita')).toHaveClass('tag')
    },
}

export const SecurityPointSix = {
    name: 'Security status 0.6',
    args: { color: 'security-status-point-6', text: '0.6 Rens' },
    play: async ({ canvasElement }: Play) => {
        await expect(within(canvasElement).getByText('0.6 Rens')).toHaveClass('tag')
    },
}

export const SecurityPointFive = {
    name: 'Security status 0.5',
    args: { color: 'security-status-point-5', text: '0.5 Hek' },
    play: async ({ canvasElement }: Play) => {
        await expect(within(canvasElement).getByText('0.5 Hek')).toHaveClass('tag')
    },
}

export const SecurityPointThree = {
    name: 'Security status 0.3',
    args: { color: 'security-status-point-3', text: '0.3 Old Man Star' },
    play: async ({ canvasElement }: Play) => {
        await expect(within(canvasElement).getByText('0.3 Old Man Star')).toHaveClass('tag')
    },
}

export const SecurityPointTwo = {
    name: 'Security status 0.2',
    args: { color: 'security-status-point-2', text: '0.2 Otela' },
    play: async ({ canvasElement }: Play) => {
        await expect(within(canvasElement).getByText('0.2 Otela')).toHaveClass('tag')
    },
}

export const SecurityPointOne = {
    name: 'Security status 0.1',
    args: { color: 'security-status-point-1', text: '0.1 Uedama' },
    play: async ({ canvasElement }: Play) => {
        await expect(within(canvasElement).getByText('0.1 Uedama')).toHaveClass('tag')
    },
}

export const CustomTextColor = {
    args: { color: 'alliance-blue', text_color: 'var(--fleet-yellow)', text: 'Custom text' },
    play: async ({ canvasElement }: Play) => {
        await expect(within(canvasElement).getByText('Custom text')).toBeVisible()
    },
}

export const Narrow = {
    args: { narrow: true, text: 'x3' },
    play: async ({ canvasElement }: Play) => {
        await expect(within(canvasElement).getByText('x3')).toHaveClass('narrow')
    },
}

export const WithTitle = {
    args: { title: 'Fleet Commander approved this doctrine', text: 'Doctrine' },
    play: async ({ canvasElement }: Play) => {
        await expect(within(canvasElement).getByTitle('Fleet Commander approved this doctrine')).toHaveTextContent('Doctrine')
    },
}

export const Outline = {
    args: { variant: 'outline', color: undefined, text: 'Open fleet' },
    play: async ({ canvasElement }: Play) => {
        const el = within(canvasElement).getByText('Open fleet')
        await expect(el).toHaveClass('tag--outline')
        await expect(el.getAttribute('style')).toContain('--outline_color: var(--highlight)')
    },
}

export const OutlineColored = {
    args: { variant: 'outline', color: 'green', text: 'Joined' },
    play: async ({ canvasElement }: Play) => {
        const el = within(canvasElement).getByText('Joined')
        await expect(el.getAttribute('style')).toContain('--outline_color: var(--green)')
        await expect(el.getAttribute('style')).toContain('color-mix')
    },
}

export const OutlineWithIcon = {
    args: { variant: 'outline', color: 'fleet-yellow', text: 'Members only', slots: { icon: { component: LockIcon, props: { size: 13 } } } },
    play: async ({ canvasElement }: Play) => {
        await expect(tag(canvasElement).querySelector('svg')).not.toBeNull()
        await expect(tag(canvasElement)).toHaveTextContent('Members only')
    },
}
