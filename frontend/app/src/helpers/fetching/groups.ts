/**
 * Legacy SIG/team helpers removed. Officer/director checks are stubs
 * (historically returned false) retained for Viewport/Neocom permission props.
 */

export function is_director(_access_token: string, _user_id: number) {
    return false
}

export function is_officer(_access_token: string, _user_id: number) {
    return false
}
