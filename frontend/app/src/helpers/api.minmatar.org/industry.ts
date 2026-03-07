import type {
    IndustryOrder,
    BaseIndustryOrder,
    NestedIndustryOrder,
    Product,
    Blueprint,
    HarvestOverviewItem,
    HarvestDrillDownItem,
    HarvestDrillDownResponse,
    ProductionOverviewItem,
    ProductionDrillDownItem,
    ProductionDrillDownResponse,
    PlanetWithColoniesItem,
} from '@dtypes/api.minmatar.org'
import { get_error_message, query_string, parse_error_message } from '@helpers/string'

const API_ENDPOINT =  `${import.meta.env.API_URL}/api/industry`

export async function get_orders_with_location() {
    const headers = {
        'Content-Type': 'application/json',
    }

    const ENDPOINT = `${API_ENDPOINT}/orders`

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

        return await response.json() as IndustryOrder[];
    } catch (error) {
        throw new Error(`Error fetching industry orders: ${error.message}`);
    }
}

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

export async function get_products() {
    const headers = {
        'Content-Type': 'application/json',
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

export async function get_product_by_id(id:number) {
    const headers = {
        'Content-Type': 'application/json',
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

export async function get_product_breakdown(product_id:number, quantity:number, max_depth?:number) {
    const headers = {
        'Content-Type': 'application/json',
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

export async function get_blueprints(is_copy:boolean = false) {
    const headers = {
        'Content-Type': 'application/json',
    }

    const ENDPOINT = `${API_ENDPOINT}/blueprints${is_copy ? '/copies/copies' : ''}`

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

        return await response.json() as Blueprint[];
    } catch (error) {
        throw new Error(`Error fetching blueprints: ${error.message}`);
    }
}

const PLANETARY_ENDPOINT = `${API_ENDPOINT}/planetary`

export async function get_planetary_harvest(): Promise<HarvestOverviewItem[]> {
    const response = await fetch(PLANETARY_ENDPOINT + '/harvest', {
        headers: { 'Content-Type': 'application/json' },
    })
    if (!response.ok) {
        throw new Error(
            get_error_message(response.status, `GET ${PLANETARY_ENDPOINT}/harvest`)
        )
    }
    return await response.json()
}

export async function get_planetary_harvest_drilldown(
    typeId: number
): Promise<HarvestDrillDownResponse> {
    const response = await fetch(
        `${PLANETARY_ENDPOINT}/harvest/${typeId}`,
        { headers: { 'Content-Type': 'application/json' } }
    )
    if (!response.ok) {
        throw new Error(
            get_error_message(
                response.status,
                `GET ${PLANETARY_ENDPOINT}/harvest/${typeId}`
            )
        )
    }
    return await response.json()
}

export async function get_planetary_production(): Promise<ProductionOverviewItem[]> {
    const response = await fetch(PLANETARY_ENDPOINT + '/production', {
        headers: { 'Content-Type': 'application/json' },
    })
    if (!response.ok) {
        throw new Error(
            get_error_message(
                response.status,
                `GET ${PLANETARY_ENDPOINT}/production`
            )
        )
    }
    return await response.json()
}

export async function get_planetary_production_drilldown(
    typeId: number
): Promise<ProductionDrillDownResponse> {
    const response = await fetch(
        `${PLANETARY_ENDPOINT}/production/${typeId}`,
        { headers: { 'Content-Type': 'application/json' } }
    )
    if (!response.ok) {
        throw new Error(
            get_error_message(
                response.status,
                `GET ${PLANETARY_ENDPOINT}/production/${typeId}`
            )
        )
    }
    return await response.json()
}

export async function get_planetary_planets(params: {
    planet_id?: number
    solar_system_id?: number
}): Promise<PlanetWithColoniesItem[]> {
    const search = new URLSearchParams()
    if (params.planet_id != null) search.set('planet_id', String(params.planet_id))
    if (params.solar_system_id != null) search.set('solar_system_id', String(params.solar_system_id))
    const query = search.toString()
    const url = `${PLANETARY_ENDPOINT}/planets${query ? `?${query}` : ''}`
    const response = await fetch(url, {
        headers: { 'Content-Type': 'application/json' },
    })
    if (!response.ok) {
        throw new Error(
            get_error_message(response.status, `GET ${url}`)
        )
    }
    return await response.json()
}
