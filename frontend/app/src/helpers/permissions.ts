import { get_user_by_name } from '@helpers/api.minmatar.org/authentication'

export async function get_user_permissions(user_name:string) {
    try {
        const profile = await get_user_by_name(user_name)
        return profile?.permissions ?? []
    } catch (error) {
        return []
    }
}