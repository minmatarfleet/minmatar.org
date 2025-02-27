import { parse_response_error, query_string } from '@helpers/string'
import type { SRP, SRPStatus, SRPRequest } from '@dtypes/api.minmatar.org'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/srp`

export async function get_fleet_srp(access_token:string, srp_request:SRPRequest) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }
    
    const { fleet_id, status } = srp_request

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

export async function create_fleet_srp(access_token:string, fleet_id:number, external_killmail_link:string, is_corp_ship:boolean) {
    const data = JSON.stringify({
        fleet_id: fleet_id,
        external_killmail_link: external_killmail_link,
        is_corp_ship: is_corp_ship,
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