import type {
    IndustryOrder,
    BaseIndustryOrder,
    NestedIndustryOrder,
    Product,
    Blueprint,
    BlueprintDetail,
    HarvestOverviewItem,
    HarvestDrillDownResponse,
    ProductionOverviewItem,
    ProductionDrillDownResponse,
    PlanetWithColoniesItem,
    OrderAssignmentsBreakdown,
    IndustrySingleOrder,
    OrderAssignment,
} from '@dtypes/api.minmatar.org'
import {
    get_error_message,
    query_string,
    parse_error_message,
    parse_response_error,
} from '@helpers/string'

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
            ), {
                cause: response.status
            })
        }

        return await response.json() as IndustryOrder[];
    } catch (error) {
        throw new Error(`Error fetching industry orders: ${error.message}`, { cause: error.cause });
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
            ), {
                cause: response.status
            })
        }

        return await response.json() as { roots: NestedIndustryOrder[] };
    } catch (error) {
        throw new Error(`Error fetching contracts: ${error.message}`, { cause: error.cause });
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
            ), {
                cause: response.status
            })
        }

        return await response.json() as { items: BaseIndustryOrder[] };
    } catch (error) {
        throw new Error(`Error fetching contracts: ${error.message}`, { cause: error.cause });
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
            ), {
                cause: response.status
            })
        }

        return await response.json() as Product[];
    } catch (error) {
        throw new Error(`Error fetching products: ${error.message}`, { cause: error.cause });
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
            ), {
                cause: response.status
            })
        }

        return await response.json() as Product;
    } catch (error) {
        throw new Error(`Error fetching products: ${error.message}`, { cause: error.cause });
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
            ), {
                cause: response.status
            })
        }

        return await response.json() as Product[];
    } catch (error) {
        throw new Error(`Error fetching product breakdown: ${error.message}`, { cause: error.cause });
    }
}

export async function get_blueprints(query:string, is_copy:boolean = false) {
    const headers = {
        'Content-Type': 'application/json',
    }

    const ENDPOINT = `${API_ENDPOINT}/blueprints${is_copy ? '/copies/copies' : ''}?q=${query}`

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
            ), {
                cause: response.status
            })
        }

        return await response.json() as Blueprint[];
    } catch (error) {
        throw new Error(`Error fetching blueprints: ${error.message}`, { cause: error.cause });
    }
}

export async function get_blueprint(item_id: number): Promise<BlueprintDetail> {
    const ENDPOINT = `${API_ENDPOINT}/blueprints/${item_id}`
    const response = await fetch(ENDPOINT, {
        headers: { 'Content-Type': 'application/json' },
    })

    if (!response.ok) {
        throw new Error(
            get_error_message(response.status, `GET ${ENDPOINT}`), {
                cause: response.status
            }
        )
    }

    return await response.json() as BlueprintDetail
}

const PLANETARY_ENDPOINT = `${API_ENDPOINT}/planetary`

export async function get_planetary_harvest(): Promise<HarvestOverviewItem[]> {
    const response = await fetch(PLANETARY_ENDPOINT + '/harvest', {
        headers: { 'Content-Type': 'application/json' },
    })
    if (!response.ok) {
        throw new Error(
            get_error_message(response.status, `GET ${PLANETARY_ENDPOINT}/harvest`), {
                cause: response.status
            }
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
            ), {
                cause: response.status
            }
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
            ), {
                cause: response.status
            }
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
            ), {
                cause: response.status
            }
        )
    }
    return await response.json()
}

export async function get_planetary_planets(params: {
    planet_id?: number
    solar_system_id?: number
} = {}): Promise<PlanetWithColoniesItem[]> {
    const { planet_id, solar_system_id } = params

    const query_params = {
        ...(planet_id && { planet_id }),
        ...(solar_system_id && { solar_system_id }),
    };

    const query = query_string(query_params)

    const ENDPOINT = `${PLANETARY_ENDPOINT}/planets${query ? `?${query}` : ''}`

    const response = await fetch(ENDPOINT, {
        headers: { 'Content-Type': 'application/json' },
    })

    if (!response.ok) {
        throw new Error(
            get_error_message(response.status, `GET ${ENDPOINT}`), {
                cause: response.status
            }
        )
    }
    
    return await response.json()
}

export async function get_order_assignments_breakdown(order_id: number, order_item_id: number) {
    const headers = {
        'Content-Type': 'application/json',
    }

    const ENDPOINT = `${API_ENDPOINT}/orders/${order_id}/orderitems/${order_item_id}/assignments/breakdown`
    
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
            ), {
                cause: response.status
            })
        }

        return await response.json() as { assignments: OrderAssignmentsBreakdown[] };
    } catch (error) {
        throw new Error(`Error fetching contracts: ${error.message}`, { cause: error.cause });
    }
}

export async function post_order_item_assignment(
    access_token: string,
    order_id: number,
    order_item_id: number,
    body: { character_id: number; quantity: number },
) {
    const headers = {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${access_token}`,
    }

    const ENDPOINT = `${API_ENDPOINT}/orders/${order_id}/orderitems/${order_item_id}/assignments`

    const response = await fetch(ENDPOINT, {
        method: 'POST',
        headers,
        body: JSON.stringify(body),
    })

    if (!response.ok) {
        throw new Error(
            await parse_response_error(response, `POST ${ENDPOINT}`), {
                cause: response.status
            }
        )
    }

    return await response.json()
}

export async function get_order_by_id(order_id: number) {
    const headers = {
        'Content-Type': 'application/json',
    }

    const ENDPOINT = `${API_ENDPOINT}/orders/${order_id}`

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
            ), {
                cause: response.status
            })
        }

        return await response.json() as IndustrySingleOrder;
    } catch (error) {
        throw new Error(`Error fetching industry orders: ${error.message}`, { cause: error.cause });
    }
}

export async function mark_assignment(
    access_token: string,
    order_id: number,
    order_item_id: number,
    assignment_id: number,
    delivered: boolean
) {
    const headers = {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${access_token}`,
    }

    const ENDPOINT = `${API_ENDPOINT}/orders/${order_id}/orderitems/${order_item_id}/assignments/${assignment_id}`
    
    console.log(`Requesting: PATCH ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            method: 'PATCH',
            headers: headers,
            body: JSON.stringify({
                delivered: delivered
            }),
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `PATCH ${ENDPOINT}`
            ), {
                cause: response.status
            })
        }

        return await response.json() as OrderAssignment;
    } catch (error) {
        throw new Error(`Error marking assignment: ${error.message}`, { cause: error.cause });
    }
}