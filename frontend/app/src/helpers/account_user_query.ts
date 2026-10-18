import { read_request_user } from '@helpers/request_user'

export function account_user_id_query(
    auth_token: string | false | undefined
): string {
    const { user } = read_request_user(auth_token || undefined)
    if (!user || !user.user_id) return ''
    return `&account_user_id=${user.user_id}`
}
