/**
 * Server fetches for the exit survey link (#3198). No login: the signed token
 * in the path is the only key, so no Authorization header is sent. A used or
 * expired link answers 410 and a bad one 404; callers show the same "used or
 * expired" screen for both, which never names the survey or the corporation.
 * API_URL stays in this directory; see testing/helpers/api_url_usage.test.ts.
 */
import type { ExitSurveyForm } from '@dtypes/api.minmatar.org'
import { api_response, format_response_detail, read_json } from '@helpers/api.minmatar.org/client' // pragma: allowlist secret
import { is_exit_survey_token, type ExitSurveyAnswer } from '@helpers/exit_survey'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/surveys/exit`

export type ExitSurveyOutcome<Type> =
    | { ok: true, data: Type }
    | { ok: false, status: number, detail: string }

async function exit_survey_call<Type>(token: string, method: string, body?: unknown): Promise<ExitSurveyOutcome<Type>> {
    if (!is_exit_survey_token(token))
        return { ok: false, status: 404, detail: '' }
    const response = await api_response(`${API_ENDPOINT}/${encodeURIComponent(token)}`, {
        method,
        body,
        allow: [400, 404, 410],
        error: 'Error loading the survey',
    })
    const payload = await read_json<Type & { detail?: unknown }>(response)
    if (!response.ok)
        return { ok: false, status: response.status, detail: format_response_detail(payload?.detail) ?? '' }
    return { ok: true, data: payload as Type }
}

export async function get_exit_survey(token: string) {
    return await exit_survey_call<ExitSurveyForm>(token, 'GET')
}

export async function submit_exit_survey(token: string, answers: ExitSurveyAnswer[]) {
    return await exit_survey_call<{ ok: boolean }>(token, 'POST', { answers })
}
