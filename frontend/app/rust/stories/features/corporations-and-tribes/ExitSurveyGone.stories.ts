import { expect, within } from 'storybook/test'
import ExitSurveyGone from '@components/blocks/exit_survey/ExitSurveyGone.astro'

export default {
    title: 'Features/Corporations and tribes/ExitSurveyGone',
    component: ExitSurveyGone,
    parameters: {
        docs: {
            description: {
                component: 'What a used, expired or bad exit survey link shows (#3198): one plain line that never names the survey or the corporation, so a forwarded link leaks nothing.',
            },
        },
    },
    argTypes: {
        message: { control: 'text', description: 'Replaces the default line, e.g. when the survey failed to load.' },
    },
}

export const Expired = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('This link has already been used or has expired.')).toBeVisible()
    },
}

export const LoadError = {
    args: { message: "The survey didn't load. Try the link again in a minute." },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText(/didn't load/)).toBeVisible()
    },
}

export const InAPanel = {
    name: 'Sits in a bordered panel',
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelector('.exit-survey')).toBeTruthy()
    },
}
