import type { APIRoute } from 'astro'
import { HTTP_403_Forbidden } from '@helpers/http_responses'
import { get_corporation_members } from '@helpers/api.minmatar.org/corporations'
import {
    build_member_roster,
    corporation_members_csv,
    group_corporation_members,
    parse_member_params,
} from '@helpers/corporations/detail'

// The roster table's CSV: same filters, sort and (optionally) picked rows.
// The API decides who may read the roster; this route only reformats it.
export const GET: APIRoute = async ({ cookies, url }) => {
    const auth_token = cookies.has('auth_token') ? cookies.get('auth_token')?.value : null
    if (!auth_token)
        return HTTP_403_Forbidden()

    const corporation_id = Number.parseInt(url.searchParams.get('corporation_id') ?? '', 10)
    if (!corporation_id)
        return HTTP_403_Forbidden()

    const members = await get_corporation_members(auth_token, corporation_id).catch(() => null)
    if (!members)
        return HTTP_403_Forbidden()

    const roster = build_member_roster(
        group_corporation_members(members),
        parse_member_params(url.searchParams),
    )
    const stamp = new Date().toISOString().slice(0, 10).replaceAll('-', '')
    return new Response(corporation_members_csv(roster), {
        status: 200,
        headers: {
            'Content-Type': 'text/csv; charset=utf-8',
            'Content-Disposition': `attachment; filename="corporation-${corporation_id}-members-${stamp}.csv"`,
        },
    })
}
