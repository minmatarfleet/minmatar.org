import { expect, within } from 'storybook/test'
import ChangeDiff from '@components/blocks/ChangeDiff.astro'
import { diff_name, diff_description, diff_fit } from '../../../fixtures/features/content'

export default {
    title: 'Features/Content/ChangeDiff',
    component: ChangeDiff,
    parameters: {
        docs: {
            description: {
                component: [
                    'A line diff for a proposed doctrine or fitting edit: one labelled block per changed field, each line marked + (added, green), - (removed, red) or unchanged.',
                    'It renders inside ChangeRequestCard in the review queue at `/ships/doctrine-changes/` and in the edit dialogs\' preview. The scenarios show a one-line rename, a description with context lines, a fit change and several fields together.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        diffs: { control: 'object', description: 'The changed fields, each with its labelled lines (DoctrineChangeDiff).' },
    },
    args: { diffs: [diff_name] },
}

export const Rename = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('name')).toBeVisible()
        const lines = canvasElement.querySelectorAll('.change-diff__line')
        await expect(lines.length).toBe(2)
        await expect(lines[0]).toHaveAttribute('data-kind', 'del')
        await expect(lines[0].textContent).toBe('- Rifter Fleet Issue (Amamake)')
        await expect(lines[1]).toHaveAttribute('data-kind', 'add')
        await expect(lines[1].textContent).toBe('+ Rifter Fleet Issue (Amamake v2)')
    },
}

export const ContextLines = {
    args: { diffs: [diff_description] },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const kinds = Array.from(canvasElement.querySelectorAll('.change-diff__line')).map(l => l.getAttribute('data-kind'))
        await expect(kinds).toEqual(['same', 'del', 'add', 'same'])
    },
}

export const FitChange = {
    args: { diffs: [diff_fit] },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByText('+ Small Nosferatu II')).toBeVisible()
        await expect(canvasElement.querySelectorAll('[data-kind="add"]').length).toBe(2)
    },
}

export const SeveralFields = {
    args: { diffs: [diff_name, diff_description, diff_fit] },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelectorAll('.change-diff__label').length).toBe(3)
        await expect(canvasElement.querySelectorAll('.change-diff__lines').length).toBe(3)
    },
}

export const NoChanges = {
    args: { diffs: [] },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelectorAll('.change-diff__label').length).toBe(0)
    },
}
