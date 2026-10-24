import type {
    IndustryOrder,
    Product,
    ProductInsights,
    ProductBuild,
    Blueprint,
    IndustrySingleOrder,
    OrderAssignment,
    OrdersProfitSummary,
    OrderBlueprintCoordinator,
    OrderBlueprintCoordinatorEveType,
    RootSingleItem,
    BuildPack,
    IndustryOrderCharacterStatistics,
    OrderCapabilities,
    CreateOrderRequest,
    CreateOrderResponse,
} from '@dtypes/api.minmatar.org'
import { query_string } from '@helpers/string'
import { api_request, api_response } from '@helpers/api.minmatar.org/client'

const API_ENDPOINT =  `${import.meta.env.API_URL}/api/industry`

export async function get_order_capabilities(access_token: string) {
    const ENDPOINT = `${API_ENDPOINT}/orders/capabilities`

    return await api_request<OrderCapabilities>(ENDPOINT, {
        token: access_token,
        error: 'Error fetching order capabilities',
    })
}

export async function create_order(
    access_token: string,
    body: CreateOrderRequest,
) {
    const ENDPOINT = `${API_ENDPOINT}/orders`

    return await api_request<CreateOrderResponse>(ENDPOINT, {
        method: 'POST',
        token: access_token,
        body: body,
        error: 'Error creating order',
    })
}

export async function get_orders_with_location() {
    const ENDPOINT = `${API_ENDPOINT}/orders`

    return await api_request<IndustryOrder[]>(ENDPOINT, {
        error: 'Error fetching industry orders',
    })
}

export async function get_orders_character_statistics() {
    const ENDPOINT = `${API_ENDPOINT}/orders/character-statistics`

    return await api_request<IndustryOrderCharacterStatistics[]>(ENDPOINT, {
        error: 'Error fetching industry order character statistics',
    })
}

export type OrdersProfitSummaryParams = {
    needed_by_from?: string
    needed_by_to?: string
    open_only?: boolean
    order_ids?: string | number[]
}

export async function get_orders_profit_summary(
    params: OrdersProfitSummaryParams = {},
): Promise<OrdersProfitSummary> {
    const raw: Record<string, string> = {}
    if (params.needed_by_from) raw.needed_by_from = params.needed_by_from
    if (params.needed_by_to) raw.needed_by_to = params.needed_by_to
    if (params.open_only !== undefined)
        raw.open_only = params.open_only ? 'true' : 'false'
    if (params.order_ids !== undefined) {
        raw.order_ids = Array.isArray(params.order_ids)
            ? params.order_ids.join(',')
            : String(params.order_ids)
    }

    const qs = query_string(raw)
    const ENDPOINT = `${API_ENDPOINT}/orders/profit-summary${qs ? `?${qs}` : ''}`

    return await api_request<OrdersProfitSummary>(ENDPOINT, {
        error: 'Error fetching orders profit summary',
    })
}

export async function get_products() {
    const ENDPOINT = `${API_ENDPOINT}/products`

    return await api_request<Product[]>(ENDPOINT, {
        error: 'Error fetching products',
    })
}

export async function get_product_by_id(id:number) {
    const ENDPOINT = `${API_ENDPOINT}/products/${id}`

    return await api_request<Product>(ENDPOINT, {
        error: 'Error fetching products',
    })
}

export async function get_product_insights(access_token:string, id:number) {
    const ENDPOINT = `${API_ENDPOINT}/products/${id}/insights`

    return await api_request<ProductInsights>(ENDPOINT, {
        token: access_token,
        error: 'Error fetching product insights',
    })
}

export async function get_product_build(id:number) {
    const ENDPOINT = `${API_ENDPOINT}/products/${id}/build`

    return await api_request<ProductBuild>(ENDPOINT, {
        error: 'Error fetching product build',
    })
}

export async function get_blueprints(query:string, is_copy:boolean = false) {
    const ENDPOINT = `${API_ENDPOINT}/blueprints${is_copy ? '/copies/copies' : ''}?q=${query}`

    return await api_request<Blueprint[]>(ENDPOINT, {
        error: 'Error fetching blueprints',
    })
}

export async function post_order_item_assignment(
    access_token: string,
    order_id: number,
    order_item_id: number,
    body: { character_id: number; quantity: number; has_blueprints?: boolean },
) {
    const ENDPOINT = `${API_ENDPOINT}/orders/${order_id}/orderitems/${order_item_id}/assignments`

    return await api_request<any>(ENDPOINT, {
        method: 'POST',
        token: access_token,
        body: {
            character_id: body.character_id,
            quantity: body.quantity,
            has_blueprints: body.has_blueprints ?? false,
        },
    })
}

export async function post_order_blueprint_coordinator(
    access_token: string,
    order_id: number,
    body: { character_id: number; eve_type_ids: number[] },
): Promise<OrderBlueprintCoordinator> {
    const ENDPOINT = `${API_ENDPOINT}/orders/${order_id}/blueprint-coordinators`

    return await api_request<OrderBlueprintCoordinator>(ENDPOINT, {
        method: 'POST',
        token: access_token,
        body: body,
    })
}

export async function delete_order_blueprint_coordinator(
    access_token: string,
    order_id: number,
    coordinator_id: number,
): Promise<void> {
    const ENDPOINT = `${API_ENDPOINT}/orders/${order_id}/blueprint-coordinators/${coordinator_id}`

    await api_response(ENDPOINT, {
        method: 'DELETE',
        token: access_token,
    })
}

export async function post_order_mineral_coordinator(
    access_token: string,
    order_id: number,
    body: { character_id: number; eve_type_ids: number[] },
): Promise<OrderBlueprintCoordinator> {
    const ENDPOINT = `${API_ENDPOINT}/orders/${order_id}/mineral-coordinators`

    return await api_request<OrderBlueprintCoordinator>(ENDPOINT, {
        method: 'POST',
        token: access_token,
        body: body,
    })
}

export async function delete_order_mineral_coordinator(
    access_token: string,
    order_id: number,
    coordinator_id: number,
): Promise<void> {
    const ENDPOINT = `${API_ENDPOINT}/orders/${order_id}/mineral-coordinators/${coordinator_id}`

    await api_response(ENDPOINT, {
        method: 'DELETE',
        token: access_token,
    })
}

export async function post_order_pi_coordinator(
    access_token: string,
    order_id: number,
    body: { character_id: number; eve_type_ids: number[] },
): Promise<OrderBlueprintCoordinator> {
    const ENDPOINT = `${API_ENDPOINT}/orders/${order_id}/pi-coordinators`

    return await api_request<OrderBlueprintCoordinator>(ENDPOINT, {
        method: 'POST',
        token: access_token,
        body: body,
    })
}

export async function delete_order_pi_coordinator(
    access_token: string,
    order_id: number,
    coordinator_id: number,
): Promise<void> {
    const ENDPOINT = `${API_ENDPOINT}/orders/${order_id}/pi-coordinators/${coordinator_id}`

    await api_response(ENDPOINT, {
        method: 'DELETE',
        token: access_token,
    })
}

export async function get_order_by_id(order_id: number) {
    const ENDPOINT = `${API_ENDPOINT}/orders/${order_id}`

    return await api_request<IndustrySingleOrder>(ENDPOINT, {
        error: 'Error fetching industry orders',
    })
}

export async function get_order_orderitems(order_id: number) {
    const ENDPOINT = `${API_ENDPOINT}/orders/${order_id}/orderitems`

    return await api_request<RootSingleItem[]>(ENDPOINT, {
        error: 'Error fetching order items',
    })
}

export async function get_order_item_build_packs(order_id: number, order_item_id: number) {
    const ENDPOINT = `${API_ENDPOINT}/orders/${order_id}/orderitems/${order_item_id}/build-packs`

    return await api_request<BuildPack[]>(ENDPOINT, {
        error: 'Error fetching order build packs',
    })
}

export async function get_order_material_options(order_id: number) {
    const ENDPOINT = `${API_ENDPOINT}/orders/${order_id}/material-options`

    return await api_request<{
        mineral_options: OrderBlueprintCoordinatorEveType[]
        pi_options: OrderBlueprintCoordinatorEveType[]
    }>(ENDPOINT, {
        error: 'Error fetching order material options',
    })
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

export interface PlannerStockApplied {
    type_id: number
    name: string
    needed: number
    owned: number
    used: number
    remaining: number
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
    stock_paste?: string | null
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
    stock_applied?: PlannerStockApplied[]
    stock_unresolved?: string[]
}

export async function get_planner_facilities(access_token?: string) {
    const ENDPOINT = `${API_ENDPOINT}/planner/facilities`
    return await api_request<PlannerFacility[]>(ENDPOINT, {
        token: access_token,
    })
}

export interface PlannerRefineRate {
    facility_key: string
    refine_rate: number
    refine_rate_source: string
    character_skills: PlannerCharacterSkills | null
    ore_yields: PlannerOreRefineYield[]
}

export async function post_planner_refine_rate(
    access_token: string | undefined,
    body: {
        facility_key: string
        character_id?: number | null
        use_reprocessing_implants?: boolean
    },
) {
    const ENDPOINT = `${API_ENDPOINT}/planner/refine-rate`
    return await api_request<PlannerRefineRate>(ENDPOINT, {
        method: 'POST',
        token: access_token,
        body: {
            facility_key: body.facility_key,
            character_id: body.character_id ?? null,
            use_reprocessing_implants: body.use_reprocessing_implants ?? false,
        },
    })
}

export async function mark_assignment(
    access_token: string,
    order_id: number,
    order_item_id: number,
    assignment_id: number,
    delivered: boolean
) {
    const ENDPOINT = `${API_ENDPOINT}/orders/${order_id}/orderitems/${order_item_id}/assignments/${assignment_id}`

    return await api_request<OrderAssignment>(ENDPOINT, {
        method: 'PATCH',
        token: access_token,
        body: {
            delivered: delivered
        },
        error: 'Error marking assignment',
    })
}