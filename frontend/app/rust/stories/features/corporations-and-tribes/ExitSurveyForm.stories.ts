import { expect, within } from 'storybook/test'
import ExitSurveyForm from '@components/blocks/exit_survey/ExitSurveyForm.astro'
import { alliance_move_survey_form, exit_survey_form } from '../../../fixtures/features/corporations-and-tribes'

export default {
    title: 'Features/Corporations and tribes/ExitSurveyForm',
    component: ExitSurveyForm,
    parameters: {
        docs: {
            description: {
                component: [
                    'The no-login survey behind the Eve mail a pilot gets after leaving a tracked corporation on their own (#3198, `docs/exits/exit-flow-design.md` section 07), at `/exit-survey/<token>/`.',
                    'Exit and alliance move are two definitions with the same four required ratings. The notice says only the Alliance Executor reads the answers. Questions render with SurveyField; the form posts to `exit_survey_component` with the link token. A used or expired link renders ExitSurveyGone instead.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        form: { control: 'object', description: 'The API form: corporation, pilot, membership dates and the question blocks.' },
        token: { control: 'text' },
        partial_url: { control: 'text' },
        error: { control: 'text', description: 'Shown above the questions when the answers were refused.' },
    },
    args: {
        form: exit_survey_form,
        token: 'eyJpIjoxfQ:story-token-not-real',
        partial_url: '/partials/exit_survey_component/',
    },
}

export const Exit = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { name: 'Your time in Example Corp' })).toBeVisible()
        await expect(canvas.getByText(/Only the Minmatar Fleet Alliance Executor reads these answers/)).toBeVisible()
        await expect(canvas.getByText('Overall, how much did you enjoy Example Corp?')).toBeVisible()
        await expect(canvas.getByText('Why did you leave?')).toBeVisible()
        await expect(canvas.getByRole('button', { name: 'Send answers' })).toBeVisible()
        const token = canvasElement.querySelector('input[name="token"]') as HTMLInputElement
        await expect(token.value).toBe('eyJpIjoxfQ:story-token-not-real')
    },
}

export const AllianceMove = {
    args: { form: alliance_move_survey_form },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Why did you move to Tribal Liberation Force?')).toBeVisible()
        await expect(canvas.queryByText('Why did you leave?')).toBeNull()
        await expect(canvas.getByText(/member until/)).toBeVisible()
    },
}

export const RefusedAnswers = {
    name: 'Answers refused (a rating missing)',
    args: { error: "That didn't send. Check the ratings and try again." },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('alert')).toHaveTextContent("That didn't send")
    },
}
