import { api_request } from '@helpers/api.minmatar.org/client'
import type {
    ActiveSurvey,
    ChangelogEntry,
    CorpReport,
    MemberContext,
    MyResponse,
    SubmitResult,
    SurveyAnswerInput,
    SurveyCampaign,
    SurveyQuestions,
} from '@dtypes/survey'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/surveys`

// ---- Member ----
export async function get_active_survey(access_token: string) {
    return api_request<ActiveSurvey>(`${API_ENDPOINT}/active`, { token: access_token })
}

export async function get_survey_context(access_token: string, id: number) {
    return api_request<MemberContext>(`${API_ENDPOINT}/${id}/context`, { token: access_token })
}

export async function get_survey_questions(access_token: string, id: number) {
    return api_request<SurveyQuestions>(`${API_ENDPOINT}/${id}/questions`, { token: access_token })
}

export async function get_my_response(access_token: string, id: number) {
    return api_request<MyResponse>(`${API_ENDPOINT}/${id}/response`, { token: access_token })
}

export async function submit_survey_response(
    access_token: string,
    id: number,
    answers: SurveyAnswerInput[],
    context_corrections: Record<string, any> = {},
) {
    return api_request<SubmitResult>(`${API_ENDPOINT}/${id}/responses`, {
        method: 'POST',
        token: access_token,
        body: {
            answers,
            context_corrections,
        },
    })
}

export async function get_changelog(access_token: string, id: number) {
    return api_request<ChangelogEntry[]>(`${API_ENDPOINT}/${id}/changelog`, { token: access_token })
}

// ---- Leadership ----
export async function list_campaigns(access_token: string) {
    return api_request<SurveyCampaign[]>(`${API_ENDPOINT}/`, { token: access_token })
}

export async function create_campaign(
    access_token: string,
    payload: {
        year: number
        quarter: number
        definition_key?: string
        title?: string
        open_now?: boolean
    },
) {
    return api_request<SurveyCampaign>(`${API_ENDPOINT}/`, { method: 'POST', token: access_token, body: payload })
}

export async function get_corp_progress(access_token: string, id: number) {
    return api_request<any>(`${API_ENDPOINT}/${id}/corp-progress`, { token: access_token })
}

export async function update_campaign(
    access_token: string,
    id: number,
    payload: { status?: string; opens_at?: string; closes_at?: string },
) {
    return api_request<SurveyCampaign>(`${API_ENDPOINT}/${id}`, { method: 'PATCH', token: access_token, body: payload })
}

export async function get_corp_report(access_token: string, id: number) {
    return api_request<CorpReport>(`${API_ENDPOINT}/${id}/corp-report`, { token: access_token })
}

export async function get_report(access_token: string, id: number) {
    return api_request<any>(`${API_ENDPOINT}/${id}/report`, { token: access_token })
}
