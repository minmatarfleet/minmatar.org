import { parse_response_error } from '@helpers/string'
import type {
    LearningCertificate,
    LearningCertificateAward,
    LearningCompleteResponse,
    LearningImportResponse,
    LearningMeResponse,
    LearningPersona,
    LearningPersonaRecommendation,
    LearningPersonaResponse,
} from '@dtypes/api.minmatar.org'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/learning`

export async function get_learning_certificates(
    persona?: LearningPersona | string | null,
): Promise<LearningCertificate[]> {
    const params = new URLSearchParams()
    if (persona) params.set('persona', persona)
    const query = params.toString()
    const ENDPOINT = `${API_ENDPOINT}/certificates${query ? `?${query}` : ''}`
    const METHOD = 'GET'

    const response = await fetch(ENDPOINT, { method: METHOD })
    if (!response.ok)
        throw new Error(await parse_response_error(response, `${METHOD} ${ENDPOINT}`), {
            cause: response.status,
        })

    return (await response.json()) as LearningCertificate[]
}

export async function get_learning_certificate(slug: string): Promise<LearningCertificate> {
    const ENDPOINT = `${API_ENDPOINT}/certificates/${encodeURIComponent(slug)}`
    const METHOD = 'GET'

    const response = await fetch(ENDPOINT, { method: METHOD })
    if (!response.ok)
        throw new Error(await parse_response_error(response, `${METHOD} ${ENDPOINT}`), {
            cause: response.status,
        })

    return (await response.json()) as LearningCertificate
}

export async function get_learning_me(access_token: string): Promise<LearningMeResponse> {
    const headers = {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${access_token}`,
    }
    const ENDPOINT = `${API_ENDPOINT}/me`
    const METHOD = 'GET'

    const response = await fetch(ENDPOINT, { headers, method: METHOD })
    if (!response.ok)
        throw new Error(await parse_response_error(response, `${METHOD} ${ENDPOINT}`), {
            cause: response.status,
        })

    return (await response.json()) as LearningMeResponse
}

export async function get_learning_persona_recommendation(
    access_token: string,
): Promise<LearningPersonaRecommendation> {
    const headers = {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${access_token}`,
    }
    const ENDPOINT = `${API_ENDPOINT}/persona/recommendation`
    const METHOD = 'GET'

    const response = await fetch(ENDPOINT, { headers, method: METHOD })
    if (!response.ok)
        throw new Error(await parse_response_error(response, `${METHOD} ${ENDPOINT}`), {
            cause: response.status,
        })

    return (await response.json()) as LearningPersonaRecommendation
}

export async function put_learning_persona(
    access_token: string,
    persona: LearningPersona,
): Promise<LearningPersonaResponse> {
    const headers = {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${access_token}`,
    }
    const ENDPOINT = `${API_ENDPOINT}/persona`
    const METHOD = 'PUT'

    const response = await fetch(ENDPOINT, {
        headers,
        method: METHOD,
        body: JSON.stringify({ persona }),
    })
    if (!response.ok)
        throw new Error(await parse_response_error(response, `${METHOD} ${ENDPOINT}`), {
            cause: response.status,
        })

    return (await response.json()) as LearningPersonaResponse
}

export async function post_learning_complete(
    access_token: string,
    slug: string,
): Promise<LearningCompleteResponse> {
    const headers = {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${access_token}`,
    }
    const ENDPOINT = `${API_ENDPOINT}/learnings/${encodeURIComponent(slug)}/complete`
    const METHOD = 'POST'

    const response = await fetch(ENDPOINT, { headers, method: METHOD })
    if (!response.ok)
        throw new Error(await parse_response_error(response, `${METHOD} ${ENDPOINT}`), {
            cause: response.status,
        })

    return (await response.json()) as LearningCompleteResponse
}

export async function post_learning_import(
    access_token: string,
    payload: {
        completed_learning_slugs: string[]
        persona?: LearningPersona | null
    },
): Promise<LearningImportResponse> {
    const headers = {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${access_token}`,
    }
    const ENDPOINT = `${API_ENDPOINT}/import`
    const METHOD = 'POST'

    const response = await fetch(ENDPOINT, {
        headers,
        method: METHOD,
        body: JSON.stringify({
            completed_learning_slugs: payload.completed_learning_slugs,
            persona: payload.persona ?? null,
        }),
    })
    if (!response.ok)
        throw new Error(await parse_response_error(response, `${METHOD} ${ENDPOINT}`), {
            cause: response.status,
        })

    return (await response.json()) as LearningImportResponse
}

export type { LearningCertificateAward }
