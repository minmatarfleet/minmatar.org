import * as jose from 'jose'
import type { User } from '@dtypes/jwt'

export function account_user_id_query(
    auth_token: string | false | undefined
): string {
    if (!auth_token) return ''
    try {
        const user = jose.decodeJwt(auth_token) as User
        if (!user?.user_id) return ''
        return `&account_user_id=${user.user_id}`
    } catch {
        return ''
    }
}
