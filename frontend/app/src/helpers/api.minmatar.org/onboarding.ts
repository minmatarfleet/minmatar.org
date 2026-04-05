import { parse_response_error } from '@helpers/string'
import type { OnboardingStatusResponse } from '@dtypes/api.minmatar.org'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/onboarding`

/** Path segment for GET/POST `/api/onboarding/{program_type}` — matches `OnboardingProgramType.SRP`. */
export const SRP_ONBOARDING_PROGRAM_TYPE = 'srp'

/** Matches backend `onboarding.srp_gate.SRP_ONBOARDING_REQUIRED_DETAIL`. */
export const SRP_ONBOARDING_REQUIRED_DETAIL = 'srp_onboarding_required'

export function is_srp_onboarding_required_error(error: unknown): boolean {
    if (!(error instanceof Error)) return false
    return (error.message ?? '').includes(SRP_ONBOARDING_REQUIRED_DETAIL)
}

export async function get_onboarding_status(
    access_token: string,
    slug: string,
): Promise<OnboardingStatusResponse> {
    const headers = {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${access_token}`,
    }

    const ENDPOINT = `${API_ENDPOINT}/${encodeURIComponent(slug)}`
    const METHOD = 'GET'

    const response = await fetch(ENDPOINT, { headers, method: METHOD })

    if (!response.ok)
        throw new Error(await parse_response_error(response, `${METHOD} ${ENDPOINT}`), {
            cause: response.status,
        })

    return (await response.json()) as OnboardingStatusResponse
}

export async function post_onboarding_ack(access_token: string, slug: string): Promise<void> {
    const headers = {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${access_token}`,
    }

    const ENDPOINT = `${API_ENDPOINT}/${encodeURIComponent(slug)}/ack`
    const METHOD = 'POST'

    const response = await fetch(ENDPOINT, {
        headers,
        method: METHOD,
        body: '{}',
    })

    if (!response.ok)
        throw new Error(await parse_response_error(response, `${METHOD} ${ENDPOINT}`), {
            cause: response.status,
        })
}
