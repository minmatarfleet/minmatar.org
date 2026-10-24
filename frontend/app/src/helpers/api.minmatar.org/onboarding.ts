import { api_request, api_response } from '@helpers/api.minmatar.org/client'
import type { OnboardingStatusResponse } from '@dtypes/api.minmatar.org'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/onboarding`

/** Path segment for GET/POST `/api/onboarding/{program_type}` — matches `OnboardingProgramType.SRP`. */
export const SRP_ONBOARDING_PROGRAM_TYPE = 'srp'

/** Path segment matching `OnboardingProgramType.ORDERS`. */
export const ORDERS_ONBOARDING_PROGRAM_TYPE = 'orders'

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
    return await api_request<OnboardingStatusResponse>(`${API_ENDPOINT}/${encodeURIComponent(slug)}`, {
        token: access_token,
    })
}

export async function post_onboarding_ack(access_token: string, slug: string): Promise<void> {
    await api_response(`${API_ENDPOINT}/${encodeURIComponent(slug)}/ack`, {
        method: 'POST',
        token: access_token,
        body: {},
    })
}
