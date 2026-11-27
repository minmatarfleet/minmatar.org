import type { ExitSurveyForm } from '@dtypes/api.minmatar.org'

export interface ExitSurveyAnswer {
    question_key: string
    value: number | string | string[]
}

const NUMERIC = ['scale5', 'enps', 'agree']

/** The signed link token: rejected before any API call when it can't be one. */
export function is_exit_survey_token(token: string | undefined | null): token is string {
    return typeof token === 'string' && /^[\w\-.:]{20,1000}$/.test(token)
}

/** SurveyField inputs (`q__<key>`) as typed answers; empty fields are left out. */
export function exit_survey_answers(data: FormData, form: ExitSurveyForm): ExitSurveyAnswer[] {
    const answers: ExitSurveyAnswer[] = []
    for (const block of form.blocks) {
        for (const question of block.questions) {
            const name = `q__${question.key}`
            if (question.type === 'multi') {
                const values = data.getAll(name).map(String).filter(Boolean)
                if (values.length) answers.push({ question_key: question.key, value: values })
            } else if (NUMERIC.includes(question.type)) {
                const raw = data.get(name)
                if (raw !== null && raw !== '') answers.push({ question_key: question.key, value: Number(raw) })
            } else {
                const raw = String(data.get(name) ?? '').trim()
                if (raw) answers.push({ question_key: question.key, value: raw })
            }
        }
    }
    return answers
}
