import { parse_response_error } from '@helpers/string'
import type { ReferralLinkStats, ReferralLink } from '@dtypes/api.minmatar.org'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/referrals`

export async function get_link_stats(access_token:string) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/stats`
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
        
        return await response.json() as ReferralLinkStats[]
    } catch (error) {
        throw new Error(`Error fetching links stats: ${error.message}`);
    }
}

export async function record_referral(page:string, user_id:number, client_ip:string) {
    const data = JSON.stringify({
        page: page,
        user_id: user_id,
        client_ip: client_ip,
    })

    console.log(data)

    const headers = {
        'Content-Type': 'application/json',
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
        
        return (response.status === 201)
    } catch (error) {
        throw new Error(`Error recording referral: ${error.message}`);
    }
}

export async function get_links(access_token:string) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/links`
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
        
        return await response.json() as ReferralLink[]
    } catch (error) {
        throw new Error(`Error fetching links stats: ${error.message}`);
    }
}