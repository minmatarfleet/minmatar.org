import { parse_response_error, query_string } from '@helpers/string'
import type {
    ActiveSurvey,
    ChangelogEntry,
    CorpReport,
    GivebackCard,
    MemberContext,
    MyResponse,
    SubmitResult,
    SurveyAnswerInput,
    SurveyCampaign,
    SurveyQuestions,
    SurveyResults,
} from '@dtypes/survey'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/surveys`

function auth_headers(access_token: string) {
    return {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${access_token}`,
    }
}

async function request<T>(
    access_token: string,
    path: string,
    method = 'GET',
    body?: unknown,
): Promise<T> {
    const ENDPOINT = `${API_ENDPOINT}${path}`
    console.log(`Requesting ${method}: ${ENDPOINT}`)
    const response = await fetch(ENDPOINT, {
        headers: auth_headers(access_token),
        method,
        ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    })
    if (!response.ok) {
        throw new Error(
            await parse_response_error(response, `${method} ${ENDPOINT}`),
            { cause: response.status },
        )
    }
    return (await response.json()) as T
}

// ---- Member ----
export async function get_active_survey(access_token: string) {
    return request<ActiveSurvey>(access_token, '/active')
}

export async function get_survey_context(access_token: string, id: number) {
    return request<MemberContext>(access_token, `/${id}/context`)
}

export async function get_survey_questions(access_token: string, id: number) {
    return request<SurveyQuestions>(access_token, `/${id}/questions`)
}

export async function get_my_response(access_token: string, id: number) {
    return request<MyResponse>(access_token, `/${id}/response`)
}

export async function submit_survey_response(
    access_token: string,
    id: number,
    answers: SurveyAnswerInput[],
    context_corrections: Record<string, any> = {},
) {
    return request<SubmitResult>(access_token, `/${id}/responses`, 'POST', {
        answers,
        context_corrections,
    })
}

export async function get_giveback(access_token: string, id: number) {
    return request<GivebackCard>(access_token, `/${id}/giveback`)
}

export async function get_changelog(access_token: string, id: number) {
    return request<ChangelogEntry[]>(access_token, `/${id}/changelog`)
}

// ---- Leadership ----
export async function list_campaigns(access_token: string) {
    return request<SurveyCampaign[]>(access_token, '/')
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
    return request<SurveyCampaign>(access_token, '/', 'POST', payload)
}

export async function get_corp_progress(access_token: string, id: number) {
    return request<any>(access_token, `/${id}/corp-progress`)
}

export async function update_campaign(
    access_token: string,
    id: number,
    payload: { status?: string; opens_at?: string; closes_at?: string },
) {
    return request<SurveyCampaign>(access_token, `/${id}`, 'PATCH', payload)
}

export async function get_results(
    access_token: string,
    id: number,
    segment = 'all',
) {
    const q = query_string({ segment })
    return request<SurveyResults>(
        access_token,
        `/${id}/results${q ? `?${q}` : ''}`,
    )
}

export async function get_corp_report(access_token: string, id: number) {
    return request<CorpReport>(access_token, `/${id}/corp-report`)
}

export async function get_report(access_token: string, id: number) {
    return request<any>(access_token, `/${id}/report`)
}

export async function post_changelog(
    access_token: string,
    id: number,
    payload: {
        heading: string
        body_markdown?: string
        sort_order?: number
        published?: boolean
    },
) {
    return request<any>(access_token, `/${id}/changelog`, 'POST', payload)
}
