// Shared Storybook controls for the design tokens components take as props.
// Option lists mirror the types in src/types/layout_components.ts.
import type { ButtonColors, ButtonSizes, BadgeColors, TagColors, FlexInlineJustify, spaces } from '@dtypes/layout_components'

export const SPACES: spaces[] = [
    '0', 'var(--space-3xs)', 'var(--space-2xs)', 'var(--space-xs)', 'var(--space-s)', 'var(--space-m)',
    'var(--space-l)', 'var(--space-xl)', 'var(--space-2xl)', 'var(--space-3xl)',
    'var(--space-3xs-2xs)', 'var(--space-2xs-xs)', 'var(--space-xs-s)', 'var(--space-s-m)', 'var(--space-m-l)',
    'var(--space-l-xl)', 'var(--space-xl-2xl)', 'var(--space-2xl-3xl)', 'var(--space-s-l)',
    'var(--component-block-gap)',
]

export const BUTTON_COLORS: ButtonColors[] = ['fleet-red', 'alliance-blue', 'militia-purple', 'green', 'transparent']
export const BUTTON_SIZES: ButtonSizes[] = ['lg', 'sm']
export const BADGE_COLORS: BadgeColors[] = ['fleet-red', 'alliance-blue', 'militia-purple', 'green', 'fleet-yellow']
export const TAG_COLORS: TagColors[] = [
    'fleet-red', 'alliance-blue', 'militia-purple', 'green', 'fleet-yellow',
    'security-status-1', 'security-status-point-9', 'security-status-point-8', 'security-status-point-7',
    'security-status-point-6', 'security-status-point-5', 'security-status-point-4', 'security-status-point-3',
    'security-status-point-2', 'security-status-point-1', 'security-status-null',
]
export const JUSTIFY: FlexInlineJustify[] = ['flex-start', 'center', 'flex-end', 'space-between', 'space-around']

export const space_control = (description?: string) => ({
    control: 'select' as const,
    options: SPACES,
    description,
})

export const select_control = <T extends string | number>(options: readonly T[], description?: string) => ({
    control: 'select' as const,
    options,
    description,
})

export const radio_control = <T extends string | number>(options: readonly T[], description?: string) => ({
    control: 'inline-radio' as const,
    options,
    description,
})

// Placeholder content for layout stories: one token-styled box per item.
export const demo_box = (label: string, extra = '') =>
    `<div class="rust-demo-box"${extra}>${label}</div>`

export const demo_boxes = (count: number, prefix = 'Item') =>
    Array.from({ length: count }, (_, i) => demo_box(`${prefix} ${i + 1}`)).join('')

// Real EVE ids used across stories (the image server serves these publicly).
export const EVE = {
    character_id:       2112954532,
    character_name:     "Kel'dar Atram",
    corporation_id:     98726134,
    corporation_name:   'Rattini Tribe',
    corporation_ticker: 'A-RAT',
    alliance_id:        99011978,
    alliance_name:      'Minmatar Fleet Alliance',
    alliance_ticker:    'FL33T',
    rifter_type_id:     587,
    rifter_name:        'Rifter',
    stabber_type_id:    622,
    stabber_name:       'Stabber',
} as const
