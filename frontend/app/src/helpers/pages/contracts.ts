import { useTranslations } from '@i18n/utils';

import { prod_error_messages } from '@helpers/env'

import { fetch_market_contracts } from '@helpers/fetching/market'
import { get_market_characters, get_market_corporations } from '@helpers/api.minmatar.org/market'
import type { Character, MarketCorporation } from '@dtypes/api.minmatar.org'
import type { TradeHub, SelectOptions } from '@dtypes/layout_components'
import { fitting_ship_types } from '@dtypes/layout_components'

export interface ContractsData {
    contracts_trade_hubs?:      TradeHub[];
    characters_options?:        SelectOptions[];
    corporations_options?:      SelectOptions[];
}

export async function get_contracts_data(auth_token:string | false, lang:'en' = 'en') {
    const t = useTranslations(lang)

    let contracts_trade_hubs:TradeHub[] = []
    let market_characters:Character[] = []
    let market_corporations:MarketCorporation[] = []
    let characters_options:SelectOptions[] = []
    let corporations_options:SelectOptions[] = []

    try {
        contracts_trade_hubs = await fetch_market_contracts()
        
        if (auth_token) {
            market_characters = await get_market_characters(auth_token)
            characters_options = market_characters.map(character => {
                return {
                    value: character.character_id,
                    label: character.character_name,
                } as SelectOptions
            })

            market_corporations = await get_market_corporations(auth_token)
            corporations_options = market_corporations.map(corporation => {
                return {
                    value: corporation.corporation_id,
                    label: corporation.corporation_name,
                } as SelectOptions
            })
        }
    } catch (error) {
        throw new Error(prod_error_messages() ? t('fetch_contract_error') : error.message)
    }

    return {
        contracts_trade_hubs: contracts_trade_hubs,
        characters_options: characters_options,
        corporations_options: corporations_options,
    } as ContractsData
}