import type { Contract, Character, MarketCorporation, MarketExpectation, MarketLocation } from '@dtypes/api.minmatar.org'
import { get_error_message, parse_error_message } from '@helpers/string'

const API_ENDPOINT =  `${import.meta.env.API_URL}/api/market`

export async function get_market_contracts() {
    const headers = {
        'Content-Type': 'application/json',
    }

    const ENDPOINT = `${API_ENDPOINT}/contracts`

    console.log(`Requesting: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `GET ${ENDPOINT}`
            ))
        }

        return await response.json() as Contract[];
    } catch (error) {
        throw new Error(`Error fetching contracts: ${error.message}`);
    }
}


export async function get_market_contract_by_id(expectation_id:number) {
    const headers = {
        'Content-Type': 'application/json',
    }

    const ENDPOINT = `${API_ENDPOINT}/contracts/${expectation_id}`

    console.log(`Requesting: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `GET ${ENDPOINT}`
            ))
        }

        return await response.json() as Contract;
    } catch (error) {
        throw new Error(`Error fetching contract: ${error.message}`);
    }
}

export async function create_market_contract_responsability(access_token:string, expectation_id:number, entity_id:number) {
    const data = JSON.stringify({
        expectation_id: expectation_id,
        entity_id: entity_id
    })

    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }
    
    const ENDPOINT = `${API_ENDPOINT}/responsibilities`

    console.log(`Requesting POST: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers,
            body: data,
            method: 'POST'
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `POST ${ENDPOINT}`
            ))
        }

        return await response.json() as Contract;
    } catch (error) {
        throw new Error(`Error creating responsability: ${error.message}`);
    }
}

export async function get_market_characters(access_token:string) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }
    
    const ENDPOINT = `${API_ENDPOINT}/characters`

    console.log(`Requesting: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers
        })

        // console.log(response)

        if (!response.ok) {
            let error = await response.json()
            const error_msg = parse_error_message(error.detail)
            error = error_msg ? error_msg : error?.detail

            throw new Error(error ? error : get_error_message(response.status, `GET ${ENDPOINT}`))
        }

        return await response.json() as Character[];
    } catch (error) {
        throw new Error(`Error fetching market characters: ${error.message}`);
    }
}

export async function get_market_corporations(access_token:string) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/corporations`

    console.log(`Requesting: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `GET ${ENDPOINT}`
            ))
        }

        return await response.json() as MarketCorporation[];
    } catch (error) {
        throw new Error(`Error fetching market corporations: ${error.message}`);
    }
}

export async function get_market_expectation(access_token:string) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/expectations`

    console.log(`Requesting: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers
        })

        console.log(response)

        if (!response.ok) {
            let error = await response.json()
            const error_msg = parse_error_message(error.detail)
            error = error_msg ? error_msg : error?.detail

            throw new Error(error ? error : get_error_message(response.status, `GET ${ENDPOINT}`))
        }

        return await response.json() as MarketExpectation[];
    } catch (error) {
        throw new Error(`Error fetching market expectations: ${error.message}`);
    }
}