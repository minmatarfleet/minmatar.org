import { get_user_by_name } from '@helpers/api.minmatar.org/authentication'
import type { UserProfile } from '@dtypes/api.minmatar.org'

export async function get_user_profile(user_name: string): Promise<UserProfile | null> {
    try {
        return await get_user_by_name(user_name)
    } catch (error) {
        return null
    }
}