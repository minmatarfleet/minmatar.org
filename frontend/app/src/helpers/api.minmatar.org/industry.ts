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

export interface PlannerFacilityFitting {
    name: string
    type_id: number
    effects: string[]
    job_class?: string | null
}

export interface PlannerFacilityStructure {
    role: string
    name: string
    kind: string
    type_id: number
    effects: string[]
    rigs: PlannerFacilityFitting[]
}

export interface PlannerFacility {
    key: string
    system_id: number
    system_name: string
    structures: PlannerFacilityStructure[]
    system_cost_bonus: number
    facility_tax: number
    scc_surcharge: number
    reprocessing: {
        structure_name: string
        structure_type_id: number
        rig_name: string
        rig_type_id: number
        facility_base_yield: number
        refine_rate: number
        facility_tax: number
        effects: string[]
    }
}

export interface PlannerFacilityDetail extends PlannerFacility {
    job_classes: {
        job_class: string
        structure_name: string
        structure_type_id: number
        rig_name: string
        rig_type_id: number
        role_me: number
        role_te: number
        rig_me: number
        rig_te: number
        structure_isk_bonus: number
        effects: string[]
    }[]
    cost_indices: {
        manufacturing: number
        reaction: number
    }
    indices_from_esi: boolean
}

export interface PlannerImportLine {
    name: string
    quantity: number
}

export interface PlannerCharacterSkills {
    character_id: number
    character_name: string
    reprocessing_level: number
    reprocessing_efficiency_level: number
    simple_ore_processing_level: number
    coherent_ore_processing_level: number
    ubiquitous_moon_ore_processing_level: number
    ore_processing_level: number
    implant_bonus: number
    implant_type_id: number | null
    implant_name: string | null
    use_reprocessing_implants: boolean
}

export interface PlannerOreRefineYield {
    ore_name: string
    skill_id: number
    skill_name: string
    skill_level: number
    refine_rate: number
}

export interface PlannerCompressedOre {
    refine_rate: number
    refine_rate_source: string
    reprocessing_tax: number
    materials_tsv: string
    import_lines: PlannerImportLine[]
    compression_covered?: string[]
    belt_ore_compressed?: Record<string, number>
    moon_ore_compressed?: Record<string, number>
    ice_compressed?: Record<string, number>
    mineral_imports?: Record<string, number>
    pi_other_imports?: Record<string, number>
    ice_imports?: Record<string, number>
    other_imports?: Record<string, number>
    expected_ice_products?: Record<string, number>
    character_skills: PlannerCharacterSkills | null
    ore_yields?: PlannerOreRefineYield[]
}

export interface PlannerPlanJob {
    product_type_id: number
    product_name: string
    activity_id: number
    job_class: string
    bucket: string
    runs: number
    facility: string
    duration_seconds: number
    job_cost_isk: number
}

export interface PlannerPlanRequest {
    product_type_id: number
    quantity: number
    blueprint_me?: number
    blueprint_te?: number
    facility_key: string
    build_fuel_blocks?: boolean
    exclude_type_ids?: number[]
    compressed?: boolean
    refine_rate?: number | null
    character_id?: number | null
    use_reprocessing_implants?: boolean
}

export interface PlannerCostLineItem {
    key: string
    label: string
    amount_isk: number
}

export interface PlannerCostBreakdown {
    materials_jita_sell_isk: number
    manufacturing_job_costs_isk: number
    reaction_job_costs_isk: number
    total_job_costs_isk: number
    facility_tax_isk: number
    scc_tax_isk: number
    reprocessing_tax_isk: number
    taxes_isk: number
    freight_isk: number
    freight_volume_m3: number
    freight_billable_m3: number
    freight_route_id: number | null
    freight_route_label: string | null
    grand_total_isk: number
    per_unit_isk: number
    output_quantity: number
    line_items: PlannerCostLineItem[]
}

export interface PlannerPlanResponse {
    product: { type_id: number; name: string; quantity: number }
    blueprint_me: number
    blueprint_te: number
    facility: string
    total_job_cost_isk: number
    jobs: PlannerPlanJob[]
    leaf_materials: { type_id: number; name: string; quantity: number }[]
    estimated_materials_buy_isk: number
    materials_tsv: string
    compressed_ore: PlannerCompressedOre | null
    cost_breakdown: PlannerCostBreakdown | null
}

export async function get_planner_facilities(access_token?: string) {
    const ENDPOINT = `${API_ENDPOINT}/planner/facilities`
    const headers: Record<string, string> = {
        'Content-Type': 'application/json',
    }
    if (access_token)
        headers.Authorization = `Bearer ${access_token}`
    const response = await fetch(ENDPOINT, { headers })
    if (!response.ok) {
        throw new Error(
            await parse_response_error(response, `GET ${ENDPOINT}`), {
                cause: response.status
            }
        )
    }
    return await response.json() as PlannerFacility[]
}

export async function get_planner_facility(
    access_token: string | undefined,
    facility_key: string,
) {
    const ENDPOINT = `${API_ENDPOINT}/planner/facilities/${facility_key}`
    const headers: Record<string, string> = {
        'Content-Type': 'application/json',
    }
    if (access_token)
        headers.Authorization = `Bearer ${access_token}`
    const response = await fetch(ENDPOINT, { headers })
    if (!response.ok) {
        throw new Error(
            await parse_response_error(response, `GET ${ENDPOINT}`), {
                cause: response.status
            }
        )
    }
    return await response.json() as PlannerFacilityDetail
}

export async function post_planner_plan(
    access_token: string | undefined,
    body: PlannerPlanRequest,
) {
    const ENDPOINT = `${API_ENDPOINT}/planner/plans`
    const headers: Record<string, string> = {
        'Content-Type': 'application/json',
    }
    if (access_token)
        headers.Authorization = `Bearer ${access_token}`
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
    return await response.json() as PlannerPlanResponse
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