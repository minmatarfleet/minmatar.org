import type {
    IntelAffiliation,
    IntelAffiliationReview,
    IntelBlocDetail,
    IntelBlocPatch,
    IntelBlocSummary,
    IntelDecisionRequest,
    IntelEntityKind,
    IntelEntityProfile,
    IntelEntitySearchResult,
    IntelInvestigation,
    IntelManualAffiliationRequest,
    IntelMemberCrosscheck,
} from '@dtypes/api.minmatar.org'
import { api_request } from '@helpers/api.minmatar.org/client'

// The intel affiliation database (blocs, pets, alts, allies, associates).
// Every endpoint answers 403 without the intel.affiliations feature.
const API_ENDPOINT = `${import.meta.env.API_URL}/api/intel`

// Mutations leave out the `error` label so a form shows the backend's own
// reason ("No alliance by that name.") without a prefix.

export async function get_affiliation_review(access_token: string) {
    return await api_request<IntelAffiliationReview>(`${API_ENDPOINT}/affiliations/review`, {
        token: access_token,
        error: 'Error fetching affiliation suggestions',
    })
}

export async function decide_affiliation(access_token: string, affiliation_id: number, decision: IntelDecisionRequest) {
    return await api_request<IntelAffiliation>(`${API_ENDPOINT}/affiliations/${affiliation_id}/decision`, {
        method: 'POST',
        token: access_token,
        body: decision,
    })
}

export async function add_affiliation(access_token: string, request: IntelManualAffiliationRequest) {
    return await api_request<IntelAffiliation>(`${API_ENDPOINT}/affiliations`, {
        method: 'POST',
        token: access_token,
        body: request,
    })
}

export async function get_member_crosscheck(access_token: string) {
    const response = await api_request<{ members: IntelMemberCrosscheck[] }>(`${API_ENDPOINT}/affiliations/members`, {
        token: access_token,
        error: 'Error fetching members flying with other blocs',
    })
    return response.members
}

export async function get_blocs(access_token: string) {
    const response = await api_request<{ blocs: IntelBlocSummary[] }>(`${API_ENDPOINT}/blocs`, {
        token: access_token,
        error: 'Error fetching blocs',
    })
    return response.blocs
}

export async function get_bloc(access_token: string, bloc_id: number) {
    return await api_request<IntelBlocDetail>(`${API_ENDPOINT}/blocs/${bloc_id}`, {
        token: access_token,
        error: 'Error fetching bloc',
    })
}

export async function update_bloc(access_token: string, bloc_id: number, patch: IntelBlocPatch) {
    return await api_request<IntelBlocSummary>(`${API_ENDPOINT}/blocs/${bloc_id}`, {
        method: 'PATCH',
        token: access_token,
        body: patch,
    })
}

export async function merge_bloc(access_token: string, bloc_id: number, into_bloc_id: number) {
    return await api_request<IntelBlocSummary>(`${API_ENDPOINT}/blocs/${bloc_id}/merge`, {
        method: 'POST',
        token: access_token,
        body: { into_bloc_id },
    })
}

export async function search_intel_entities(access_token: string, query: string) {
    const response = await api_request<{ results: IntelEntitySearchResult[] }>(`${API_ENDPOINT}/entities/search?q=${encodeURIComponent(query)}`, {
        token: access_token,
        error: 'Error searching intel',
    })
    return response.results
}

export async function get_intel_entity(access_token: string, kind: IntelEntityKind, eve_id: number) {
    return await api_request<IntelEntityProfile>(`${API_ENDPOINT}/entities/${kind}/${eve_id}`, {
        token: access_token,
        error: 'Error fetching intel profile',
    })
}

export async function investigate_intel_entity(access_token: string, kind: IntelEntityKind, eve_id: number) {
    return await api_request<IntelInvestigation>(`${API_ENDPOINT}/entities/${kind}/${eve_id}/investigate`, {
        method: 'POST',
        token: access_token,
    })
}
