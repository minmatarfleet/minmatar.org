import type {
    LearningCertificate,
    LearningCertificateAward,
    LearningMeResponse,
    LearningPersona,
    LearningPersonaRecommendation,
} from '@dtypes/api.minmatar.org'
import { api_request } from '@helpers/api.minmatar.org/client'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/learning`

export async function get_learning_certificates(
    persona?: LearningPersona | string | null,
): Promise<LearningCertificate[]> {
    const params = new URLSearchParams()
    if (persona) params.set('persona', persona)
    const query = params.toString()
    const ENDPOINT = `${API_ENDPOINT}/certificates${query ? `?${query}` : ''}`

    return await api_request<LearningCertificate[]>(ENDPOINT, {
        method: 'GET',
    })
}

export async function get_learning_certificate(slug: string): Promise<LearningCertificate> {
    const ENDPOINT = `${API_ENDPOINT}/certificates/${encodeURIComponent(slug)}`

    return await api_request<LearningCertificate>(ENDPOINT, {
        method: 'GET',
    })
}

export async function get_learning_me(access_token: string): Promise<LearningMeResponse> {
    return await api_request<LearningMeResponse>(`${API_ENDPOINT}/me`, {
        method: 'GET',
        token: access_token,
    })
}

export async function get_learning_persona_recommendation(
    access_token: string,
): Promise<LearningPersonaRecommendation> {
    return await api_request<LearningPersonaRecommendation>(`${API_ENDPOINT}/persona/recommendation`, {
        method: 'GET',
        token: access_token,
    })
}

export type { LearningCertificateAward }
