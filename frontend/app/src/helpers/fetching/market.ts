import { useTranslations } from '@i18n/utils';

const t = useTranslations('en');

import { get_market_contracts } from '@helpers/api.minmatar.org/market'
import { get_fittings } from '@helpers/api.minmatar.org/ships'
import type { TradeHub, MarketShipGroup, ContractUI } from '@dtypes/layout_components'
import { get_ship_info } from '@helpers/sde/ships'

const CAPSULE_TYPE_ID = 670

export async function fetch_market_contracts() {
    const trade_hubs = {}
    
    const api_fittings = await get_fittings()
    const api_contracts = await get_market_contracts()

    await Promise.all(api_contracts.map(async api_contract => {
        if (!(api_contract.location_name in trade_hubs)) {
            trade_hubs[api_contract.location_name] = {
                name: api_contract.location_name,
                contract_groups: [],
            } as TradeHub
        }

        const fitting = api_fittings.find(api_fitting => api_fitting.name === api_contract.title)
        const ship_info = fitting?.ship_id ? await get_ship_info(fitting?.ship_id) : null
        const ship_type = ship_info?.type ?? t('unknown')

        if (!(ship_type in trade_hubs[api_contract.location_name].contract_groups)) {
            trade_hubs[api_contract.location_name].contract_groups[ship_type] = {
                ship_type: ship_type,
                contracts: [],
            } as MarketShipGroup
        }

        trade_hubs[api_contract.location_name].contract_groups[ship_type].contracts.push({
            expectation_id: api_contract.expectation_id,
            title: api_contract.title,
            eve_type_id: fitting !== undefined ? fitting.ship_id : CAPSULE_TYPE_ID,
            ship_type: ship_type,
            fitting_id: api_contract.fitting_id,
            eft_format: fitting?.eft_format,
            trend_x_axis: api_contract.historical_quantity.map(point => point.date),
            trend_y_axis: api_contract.historical_quantity.map(point => point.quantity),
            current_quantity: api_contract.current_quantity,
            desired_quantity: api_contract.desired_quantity,
            responsabilities: api_contract.responsibilities,
            entities: api_contract.responsibilities.length,
        } as ContractUI)
    }))

    const trade_hubs_array:TradeHub[] = []
    for (let location_name in trade_hubs) {
        let contract_groups:MarketShipGroup[] = []

        for (let ship_type in trade_hubs[location_name].contract_groups) {
            contract_groups.push({
                ship_type: ship_type,
                contracts: trade_hubs[location_name].contract_groups[ship_type].contracts,
            } as MarketShipGroup)
        }

        trade_hubs_array.push({
            name: location_name,
            contract_groups: contract_groups
        })
    }

    return trade_hubs_array
}