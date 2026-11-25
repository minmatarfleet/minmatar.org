import { expect, within } from 'storybook/test'
import VoiceProgress from '@components/blocks/VoiceProgress.astro'
import { voice_steps_sign_in, voice_steps_install, voice_steps_connect } from '../../../fixtures/features/voice'

export default {
    title: 'Features/Voice/VoiceProgress',
    component: VoiceProgress,
    parameters: {
        docs: {
            description: {
                component: [
                    'The fleet voice setup bar on `/voice`: Sign in, Access, Install, Connect, Keys, as dots joined by hairlines. Done steps are green, the current one red, later ones grey. The signed-out page renders it with Sign in current; the setup flow (`voice_status_component`) moves the marker with Alpine (`x_done` / `x_now`) as the pilot clicks through.',
                    'The scenarios show the pilot about to sign in, installing Mumble, and ready to connect.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        steps: { control: 'object', description: 'The steps in order, each with a label and `state`: done, now or todo.' },
        label: { control: 'text', description: 'Accessible name of the list.' },
    },
    args: { steps: voice_steps_sign_in },
}

const states = (canvasElement: HTMLElement) =>
    [...canvasElement.querySelectorAll('li')].map((li) => li.classList.contains('done') ? 'done' : li.classList.contains('now') ? 'now' : 'todo')

export const SignInNext = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('list', { name: 'Setup progress' })).toBeVisible()
        await expect(canvas.getAllByRole('listitem')).toHaveLength(5)
        await expect(states(canvasElement)).toEqual(['now', 'todo', 'todo', 'todo', 'todo'])
        await expect(canvas.getByText('Sign in').closest('li')).toHaveAttribute('aria-current', 'step')
    },
}

export const Installing = {
    args: { steps: voice_steps_install },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(states(canvasElement)).toEqual(['done', 'done', 'now', 'todo', 'todo'])
        await expect(within(canvasElement).getByText('Install').closest('li')).toHaveAttribute('aria-current', 'step')
    },
}

export const ReadyToConnect = {
    args: { steps: voice_steps_connect },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(states(canvasElement)).toEqual(['done', 'done', 'done', 'now', 'todo'])
        await expect(canvasElement.querySelectorAll('[aria-current="step"]')).toHaveLength(1)
    },
}
