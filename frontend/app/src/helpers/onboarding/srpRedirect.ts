import {
    get_onboarding_status,
    SRP_ONBOARDING_PROGRAM_TYPE,
} from '@helpers/api.minmatar.org/onboarding'

export function safe_onboarding_return_path(raw: string | null, fallback: string): string {
    if (raw === null || raw === undefined || typeof raw !== 'string') return fallback
    const trimmed = raw.trim()
    if (!trimmed.startsWith('/') || trimmed.startsWith('//')) return fallback
    if (trimmed.includes('..')) return fallback
    return trimmed
}

/** Non-superuser accounts with `srp.change_evefleetshipreimbursement` only (matches backend gate). */
export async function should_redirect_to_srp_onboarding(
    auth_token: string,
    has_explicit_srp_change_permission: boolean,
): Promise<boolean> {
    if (has_explicit_srp_change_permission) return false
    const st = await get_onboarding_status(auth_token, SRP_ONBOARDING_PROGRAM_TYPE)
    return !st.is_current
}
