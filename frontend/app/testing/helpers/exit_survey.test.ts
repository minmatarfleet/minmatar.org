import { expect, test } from 'vitest'
import { exit_survey_answers, is_exit_survey_token } from '@helpers/exit_survey'
import type { ExitSurveyForm } from '@dtypes/api.minmatar.org'

const form = {
    blocks: [
        {
            key: 'exit.ratings', title: 'Ratings', description: '',
            questions: [
                { key: 'exit.enjoyment', type: 'scale5', label: 'Enjoy', help: '', choices: [], rows: [], required: true, trendable: false, group: '', scale_labels: null, scale_kind: '', context: null },
                { key: 'exit.why_left', type: 'multi', label: 'Why', help: '', choices: ['Timezone', 'Other'], rows: [], required: false, trendable: false, group: '', scale_labels: null, scale_kind: '', context: null },
                { key: 'exit.problem', type: 'text', label: 'Problem', help: '', choices: [], rows: [], required: false, trendable: false, group: '', scale_labels: null, scale_kind: '', context: null },
            ],
        },
    ],
} as unknown as ExitSurveyForm

test('form fields become typed answers', () => {
    const data = new FormData()
    data.append('q__exit.enjoyment', '4')
    data.append('q__exit.why_left', 'Timezone')
    data.append('q__exit.why_left', 'Other')
    data.append('q__exit.problem', ' late fleets ')
    expect(exit_survey_answers(data, form)).toEqual([
        { question_key: 'exit.enjoyment', value: 4 },
        { question_key: 'exit.why_left', value: ['Timezone', 'Other'] },
        { question_key: 'exit.problem', value: 'late fleets' },
    ])
})

test('empty fields are left out', () => {
    expect(exit_survey_answers(new FormData(), form)).toEqual([])
})

test('only plausible tokens reach the API', () => {
    expect(is_exit_survey_token('eyJpIjoxfQ:1tA2bC:abcdefghijklmnopqrstuv')).toBe(true)
    expect(is_exit_survey_token('../etc/passwd')).toBe(false)
    expect(is_exit_survey_token('')).toBe(false)
    expect(is_exit_survey_token(undefined)).toBe(false)
})
