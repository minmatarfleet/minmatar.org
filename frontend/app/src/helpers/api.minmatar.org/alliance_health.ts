import { parse_response_error, query_string } from '@helpers/string'
import type {
    AllianceHealthAttention,
    AllianceHealthAttentionBucket,
    AllianceHealthCohorts,
    AllianceHealthCorporations,
    AllianceHealthOverview,
} from '@dtypes/api.minmatar.org'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/alliance/health`

async function get_json<T>(access_token: string, path: string): Promise<T> {
    const headers = {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${access_token}`,
    }
    const ENDPOINT = `${API_ENDPOINT}${path}`
    const METHOD = 'GET'
    console.log(`Requesting ${METHOD}: ${ENDPOINT}`)
    try {
        const response = await fetch(ENDPOINT, {
            headers,
            method: METHOD,
        })
        if (!response.ok) {
            throw new Error(
                await parse_response_error(response, `${METHOD} ${ENDPOINT}`),
                { cause: response.status },
            )
        }
        return (await response.json()) as T
    } catch (error) {
        throw new Error(`Error fetching alliance health${path}: ${error.message}`, {
            cause: error.cause,
        })
    }
}

export async function get_alliance_health_overview(access_token: string) {
    return get_json<AllianceHealthOverview>(access_token, '/overview')
}

export async function get_alliance_health_attention(
    access_token: string,
    bucket: AllianceHealthAttentionBucket = 'fading',
) {
    const query = query_string({ bucket })
    return get_json<AllianceHealthAttention>(
        access_token,
        `/attention${query ? `?${query}` : ''}`,
    )
}

export async function get_alliance_health_corporations(access_token: string) {
    return get_json<AllianceHealthCorporations>(access_token, '/corporations')
}

export async function get_alliance_health_cohorts(access_token: string) {
    return get_json<AllianceHealthCohorts>(access_token, '/cohorts')
}
