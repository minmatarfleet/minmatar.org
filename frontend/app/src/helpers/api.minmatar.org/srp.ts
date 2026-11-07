import { query_string } from '@helpers/string'
import { api_request, api_status_is } from '@helpers/api.minmatar.org/client'
import type {
    SRP,
    SRPStatus,
    SRPFilter,
    SRPRequest,
    KillmailResolve,
    SRPProgram,
    SRPStatsOverview,
    SRPStatsHistory,
    SRPProgramAmount,
    SRPRecalculationPreview,
    SRPRecalculationResult,
} from '@dtypes/api.minmatar.org'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/srp`

export async function get_fleet_srp(access_token:string, srp_filter:SRPFilter) {
    const { fleet_id, status } = srp_filter

    const query_params = {
        ...(fleet_id && { fleet_id }),
        ...(status && { status }),
    };

    const query = query_string(query_params)

    const ENDPOINT = `${API_ENDPOINT}${query ? `?${query}` : ''}`

    return await api_request<SRP[]>(ENDPOINT, {
        token: access_token,
        error: 'Error fetching fleet SRPs',
    })
}

export async function create_fleet_srp(access_token:string, srp_request:SRPRequest) {
    const fleet_id = srp_request.fleet_id
    const combat_log_id = srp_request.combat_log_id

    return await api_status_is(API_ENDPOINT, {
        method: 'POST',
        token: access_token,
        body: {
            external_killmail_link: srp_request.external_killmail_link,
            is_corp_ship: srp_request.is_corp_ship,
            category: srp_request?.category ?? 'dps',
            comments: srp_request?.comments ?? '',
            ...(fleet_id && { fleet_id }),
            ...(combat_log_id && { combat_log_id }),
        },
        error: 'Error creating fleet SRP',
    })
}

export async function update_fleet_srp(access_token:string, status:SRPStatus, reimbursement_id:number) {
    return await api_status_is(`${API_ENDPOINT}/${reimbursement_id}`, {
        method: 'PATCH',
        token: access_token,
        body: {
            status: status,
        },
        error: 'Error updating fleet SRP',
    })
}

export async function resolve_killmail(access_token:string, external_killmail_link:string) {
    return await api_request<KillmailResolve>(`${API_ENDPOINT}/resolve-killmail`, {
        method: 'POST',
        token: access_token,
        body: {
            external_killmail_link: external_killmail_link,
        },
        error: 'Error resolving killmail',
    })
}

export async function get_srp_programs(access_token:string) {
    return await api_request<SRPProgram[]>(`${API_ENDPOINT}/programs`, {
        token: access_token,
        error: 'Error reading SRP programs',
    })
}

export async function get_srp_stats(access_token:string) {
    return await api_request<SRPStatsOverview>(`${API_ENDPOINT}/stats/overview`, {
        token: access_token,
        error: 'Error reading SRP stats overview',
    })
}

export async function get_srp_stats_history(access_token:string) {
    return await api_request<SRPStatsHistory>(`${API_ENDPOINT}/stats/history`, {
        token: access_token,
        error: 'Error reading SRP stats history',
    })
}

export async function set_srp_program_amount(access_token:string, program_id:number, srp_value:number) {
    return await api_request<SRPProgramAmount>(`${API_ENDPOINT}/programs/${program_id}/amount`, {
        method: 'POST',
        token: access_token,
        body: { srp_value },
        error: 'Error saving SRP amount',
    })
}

export async function get_srp_recalculation_preview(access_token:string) {
    return await api_request<SRPRecalculationPreview>(`${API_ENDPOINT}/programs/recalculate`, {
        token: access_token,
        error: 'Error previewing SRP recalculation',
    })
}

export async function recalculate_outstanding_srp(access_token:string) {
    return await api_request<SRPRecalculationResult>(`${API_ENDPOINT}/programs/recalculate`, {
        method: 'POST',
        token: access_token,
        error: 'Error recalculating SRP',
    })
}

/** One hull's outstanding requests filed at an amount it no longer pays. */
export async function get_srp_hull_recalculation_preview(access_token:string, ship_type_id:number) {
    return await api_request<SRPRecalculationPreview>(`${API_ENDPOINT}/programs/recalculate?${query_string({ ship_type_id: String(ship_type_id) })}`, {
        token: access_token,
        error: 'Error previewing SRP recalculation',
    })
}

/** Pay one hull's requests filed at an old amount at the current amount. */
export async function recalculate_srp_hull(access_token:string, ship_type_id:number) {
    return await api_request<SRPRecalculationResult>(`${API_ENDPOINT}/programs/recalculate?${query_string({ ship_type_id: String(ship_type_id) })}`, {
        method: 'POST',
        token: access_token,
        error: 'Error recalculating SRP',
    })
}

/** Keep one hull's requests at the amounts they were filed at. */
export async function keep_srp_filed_amounts(access_token:string, ship_type_id:number) {
    return await api_request<SRPRecalculationResult>(`${API_ENDPOINT}/programs/recalculate/keep?${query_string({ ship_type_id: String(ship_type_id) })}`, {
        method: 'POST',
        token: access_token,
        error: 'Error keeping SRP amounts',
    })
}

/** Add a hull to SRP with its first amount. */
export async function add_srp_program(access_token:string, eve_type_id:number, srp_value:number) {
    return await api_request<SRPProgramAmount>(`${API_ENDPOINT}/programs`, {
        method: 'POST',
        token: access_token,
        body: { eve_type_id, srp_value },
        error: 'Error adding the hull',
    })
}
