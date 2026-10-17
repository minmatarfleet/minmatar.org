import type { NamesAndCategoriesEvE } from '@dtypes/api.eveonline'
import { esi_request } from '@helpers/api.eveonline/client'

export async function get_names_and_categories_by_ids(ids:number[]) {
    return await esi_request<NamesAndCategoriesEvE[]>('/universe/names/', {
        method: 'POST',
        body: ids,
        error: 'Error fetching names and categories',
    })
}
