import { useTranslations } from '@i18n/utils';

import { prod_error_messages } from '@helpers/env'

import type { LocationMarketData } from '@dtypes/api.minmatar.org'
import { fetch_market_locations_with_doctrines } from '@helpers/fetching/market'

export interface ContractsData {
    market_locations?:          LocationMarketData[];
}

export async function get_contracts_data(lang:'en' = 'en') {
    const t = useTranslations(lang)

    let market_locations:LocationMarketData[] = []

    try {
        // Fetch both old format (for backwards compatibility) and new format
        market_locations = await fetch_market_locations_with_doctrines()
    } catch (error) {
        throw new Error(prod_error_messages() ? t('fetch_contract_error') : error.message)
    }

    return {
        market_locations: market_locations,
    } as ContractsData
}