import { parse_response_error, query_string } from '@helpers/string'
import type { SRP, SRPStatus, SRPFilter, SRPRequest } from '@dtypes/api.minmatar.org'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/srp`

export async function get_fleet_srp(access_token:string, srp_filter:SRPFilter) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }
    
    const { fleet_id, status } = srp_filter

    const query_params = {
        ...(fleet_id && { fleet_id }),
        ...(status && { status }),
    };

    const query = query_string(query_params)

    const ENDPOINT = `${API_ENDPOINT}${query ? `?${query}` : ''}`
    const METHOD = 'GET'

    console.log(`Requesting ${METHOD}: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers,
            method: METHOD,
        })

        // console.log(response)

        if (!response.ok)
            throw new Error(await parse_response_error(response, `${METHOD} ${ENDPOINT}`))
        
        return await response.json() as SRP[]
    } catch (error) {
        throw new Error(`Error fetching fleet SRPs: ${error.message}`);
    }
}

export async function create_fleet_srp(access_token:string, srp_request:SRPRequest) {
    const fleet_id = srp_request.fleet_id
    
    const data = JSON.stringify({
        external_killmail_link: srp_request.external_killmail_link,
        is_corp_ship: srp_request.is_corp_ship,
        category: srp_request.category,
        comments: srp_request.comments,
        ...(fleet_id && { fleet_id }),
    })

    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = API_ENDPOINT
    const METHOD = 'POST'

    console.log(`Requesting ${METHOD}: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers,
            method: METHOD,
            body: data,
        })

        // console.log(response)

        if (!response.ok)
            throw new Error(await parse_response_error(response, `${METHOD} ${ENDPOINT}`))
                
        return (response.status === 200)
    } catch (error) {
        throw new Error(`Error creating fleet SRP: ${error.message}`);
    }
}

export async function update_fleet_srp(access_token:string, status:SRPStatus, reimbursement_id:number) {
    const data = JSON.stringify({
        status: status,
    })

    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/${reimbursement_id}`
    const METHOD = 'PATCH'

    console.log(`Requesting ${METHOD}: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers,
            method: METHOD,
            body: data,
        })

        // console.log(response)

        if (!response.ok)
            throw new Error(await parse_response_error(response, `${METHOD} ${ENDPOINT}`))
        
        return (response.status === 200);
    } catch (error) {
        throw new Error(`Error updating fleet SRP: ${error.message}`);
    }
}