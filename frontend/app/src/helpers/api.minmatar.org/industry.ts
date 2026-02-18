import type { BaseIndustryOrder, NestedIndustryOrder, Product } from '@dtypes/api.minmatar.org'
import { get_error_message, query_string, parse_error_message } from '@helpers/string'

const API_ENDPOINT =  `${import.meta.env.API_URL}/api/industry`

export async function get_orders_summary_nested() {
    const headers = {
        'Content-Type': 'application/json',
    }

    const ENDPOINT = `${API_ENDPOINT}/summary/nested`

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

        return await response.json() as { roots: NestedIndustryOrder[] };
    } catch (error) {
        throw new Error(`Error fetching contracts: ${error.message}`);
    }
}

export async function get_orders_summary_flat() {
    const headers = {
        'Content-Type': 'application/json',
    }

    const ENDPOINT = `${API_ENDPOINT}/summary/flat`

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

        return await response.json() as { items: BaseIndustryOrder[] };
    } catch (error) {
        throw new Error(`Error fetching contracts: ${error.message}`);
    }
}

export async function get_products(access_token:string) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/products`
    
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

        return await response.json() as Product[];
    } catch (error) {
        throw new Error(`Error fetching products: ${error.message}`);
    }
}

export async function get_product_by_id(access_token:string, id:number) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/products/${id}`

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

        return await response.json() as Product;
    } catch (error) {
        throw new Error(`Error fetching products: ${error.message}`);
    }
}

export async function get_product_breakdown(access_token:string, product_id:number, quantity:number, max_depth?:number) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const query_params = {
        product_id: product_id,
        quantity: quantity,
        ...(max_depth && { max_depth }),
    }

    const query = query_string(query_params)

    const ENDPOINT = `${API_ENDPOINT}/products${query ? `?${query}` : '/'}`

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

        return await response.json() as Product[];
    } catch (error) {
        throw new Error(`Error fetching product breakdown: ${error.message}`);
    }
}