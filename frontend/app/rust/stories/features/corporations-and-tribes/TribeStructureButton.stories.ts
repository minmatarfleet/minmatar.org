import { expect, within } from 'storybook/test'
import TribeStructureButton from '@components/blocks/TribeStructureButton.astro'

// The dialog sits in an Alpine x-teleport <template> until it opens.
const dialog = (canvasElement: HTMLElement) =>
    (canvasElement.querySelector('template') as HTMLTemplateElement).content

export default {
    title: 'Features/Corporations and tribes/TribeStructureButton',
    component: TribeStructureButton,
    parameters: {
        docs: {
            description: {
                component: [
                    'Structure managers (the `tribes.structure.manage` gate, People Team) create, rename, archive and restore tribes and groups. The button opens a dialog whose form posts to `/partials/tribe_structure_component`, which sends the pilot to the changed page or shows why the change was refused.',
                    'It sits on the tribes list (New tribe), a tribe page (Rename, New group, Archive or Restore) and a group page (Rename, Archive or Restore). Scenarios show each mode.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        mode: { control: 'inline-radio', options: ['new_tribe', 'new_group', 'rename', 'archive', 'restore'] },
    },
}

export const NewTribe = {
    args: { mode: 'new_tribe' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByRole('button').textContent).toContain('New tribe')
        const form = dialog(canvasElement).querySelector('form') as HTMLFormElement
        await expect(form.getAttribute('hx-post')).toContain('action=new_tribe')
        await expect(form.querySelector('input[name=name]')).not.toBeNull()
        await expect(form.querySelector('input[name=slug]')).not.toBeNull()
        await expect(form.querySelector('textarea[name=description]')).not.toBeNull()
    },
}

export const RenameGroup = {
    args: { mode: 'rename', tribe_id: 4, group_id: 9, name: 'Haulers' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const form = dialog(canvasElement).querySelector('form') as HTMLFormElement
        await expect(form.getAttribute('hx-post')).toContain('group_id=9')
        await expect((form.querySelector('input[name=name]') as HTMLInputElement).value).toBe('Haulers')
        await expect(form.querySelector('input[name=slug]')).toBeNull()
        await expect(form.textContent).toContain('Rename Haulers')
    },
}

export const ArchiveTribe = {
    args: { mode: 'archive', tribe_id: 4, name: 'Supply' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const form = dialog(canvasElement).querySelector('form') as HTMLFormElement
        await expect(form.getAttribute('hx-post')).toContain('action=archive')
        await expect(form.querySelector('input[name=name]')).toBeNull()
        await expect(form.textContent).toContain('Archive Supply?')
    },
}

export const RestoreGroup = {
    args: { mode: 'restore', tribe_id: 4, group_id: 9, name: 'Haulers' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByRole('button').textContent).toContain('Restore')
        const form = dialog(canvasElement).querySelector('form') as HTMLFormElement
        await expect(form.textContent).toContain('shows on the site again')
    },
}
