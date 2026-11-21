import { expect, within } from 'storybook/test'
import SecurityStatus from '@components/blocks/sde/SecurityStatus.astro'
import { radio_control } from '../../_controls'
import { system } from './_fixtures'

type Ctx = { canvasElement: HTMLElement }

const status = (canvasElement: HTMLElement) => canvasElement.querySelector('.security-status') as HTMLElement

export default {
    title: 'EVE/SDE/SecurityStatus',
    component: SecurityStatus,
    parameters: {
        docs: {
            description: {
                component: [
                    'A solar system\'s security status as the EVE client shows it, coloured with the `--security-status-*` tokens. Pass the raw SDE value: the component rounds it (`display_security()` in `helpers/sde/display.ts`), including the client\'s rule that 0.0–0.05 shows as 0.1, so Egbinger (0.035) reads as low-sec, not null.',
                    '`text` is coloured text for sentences and lists; `outline` is a small bordered tag for table cells and chips. `data-security-band` (high, low, null, wormhole) is set for filters and styles; pass `system_id` so J-space systems get `wormhole`.',
                    'Screen readers hear "Security status 0.4"; turn `sr_label` off when a column header already says it. Use this instead of `sec_status_class()` + `toFixed(1)` in new code: `toFixed` shows 0.035 as 0.0.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        security: { control: { type: 'number', step: 0.01, min: -1, max: 1 }, description: 'Raw SDE security status (-1 to 1).' },
        system_id: { control: 'number', description: 'Solar system id; 31xxxxxx marks a J-space system.' },
        variant: radio_control(['text', 'outline'] as const, '`text` for prose and lists, `outline` for table cells and chips.'),
        sr_label: { control: 'boolean', description: 'Prefix "Security status" for screen readers.' },
    },
    args: {
        security: system('Amamake').security,
        system_id: system('Amamake').system_id,
        variant: 'text',
        sr_label: true,
    },
}

export const Default = {
    name: 'Low-sec (Amamake 0.4)',
    play: async ({ canvasElement }: Ctx) => {
        const element = status(canvasElement)
        await expect(element).toHaveTextContent('Security status 0.4')
        await expect(element).toHaveAttribute('data-security', '0.4')
        await expect(element).toHaveAttribute('data-security-band', 'low')
        await expect(element.getAttribute('style')).toContain('var(--security-status-point-4)')
        await expect(element.querySelector('.visually-hidden')).toHaveTextContent('Security status')
    },
}

export const HighSec = {
    name: 'High-sec (Jita 0.9)',
    args: { security: system('Jita').security, system_id: system('Jita').system_id },
    play: async ({ canvasElement }: Ctx) => {
        const element = status(canvasElement)
        await expect(element).toHaveAttribute('data-security', '0.9')
        await expect(element).toHaveAttribute('data-security-band', 'high')
        await expect(element.getAttribute('style')).toContain('var(--security-status-point-9)')
    },
}

export const FullSecurity = {
    name: 'High-sec 1.0 (Amarr)',
    args: { security: system('Amarr').security, system_id: system('Amarr').system_id },
    play: async ({ canvasElement }: Ctx) => {
        const element = status(canvasElement)
        await expect(element).toHaveAttribute('data-security', '1.0')
        await expect(element.getAttribute('style')).toContain('var(--security-status-1)')
    },
}

export const RoundsUpNearZero = {
    name: '0.0–0.05 shows 0.1 (Egbinger)',
    args: { security: system('Egbinger').security, system_id: system('Egbinger').system_id },
    play: async ({ canvasElement }: Ctx) => {
        const element = status(canvasElement)
        await expect(system('Egbinger').security).toBeLessThan(0.05)
        await expect(element).toHaveAttribute('data-security', '0.1')
        await expect(element).toHaveAttribute('data-security-band', 'low')
        await expect(element.getAttribute('style')).toContain('var(--security-status-point-1)')
    },
}

export const NullSec = {
    name: 'Null-sec (HED-GP -0.1)',
    args: { security: system('HED-GP').security, system_id: system('HED-GP').system_id },
    play: async ({ canvasElement }: Ctx) => {
        const element = status(canvasElement)
        await expect(element).toHaveAttribute('data-security', '-0.1')
        await expect(element).toHaveAttribute('data-security-band', 'null')
        await expect(element.getAttribute('style')).toContain('var(--security-status-null)')
    },
}

export const Wormhole = {
    name: 'J-space (J164104)',
    args: { security: system('J164104').security, system_id: system('J164104').system_id },
    play: async ({ canvasElement }: Ctx) => {
        const element = status(canvasElement)
        await expect(element).toHaveAttribute('data-security', '-1.0')
        await expect(element).toHaveAttribute('data-security-band', 'wormhole')
    },
}

export const Outline = {
    args: { variant: 'outline' },
    play: async ({ canvasElement }: Ctx) => {
        const element = status(canvasElement)
        await expect(element).toHaveClass('tag', 'tag--outline')
        await expect(element).toHaveTextContent('0.4')
        await expect(element.getAttribute('style')).toContain('--outline_color: var(--security-status-point-4)')
        await expect(element).toHaveAttribute('title', 'Security status')
        await expect(within(element).getByText('Security status')).toHaveClass('visually-hidden')
    },
}

export const WithoutScreenReaderLabel = {
    name: 'Without screen-reader label',
    args: { sr_label: false },
    play: async ({ canvasElement }: Ctx) => {
        const element = status(canvasElement)
        await expect(element.textContent?.trim()).toBe('0.4')
        await expect(element.querySelector('.visually-hidden')).toBeNull()
    },
}
