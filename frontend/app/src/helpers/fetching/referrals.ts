import { useTranslations, useTranslatedPath } from '@i18n/utils';

import { record_referral, get_link_stats } from '@helpers/api.minmatar.org/referrals'
import { get_app_url } from '@helpers/env'

import type { ReferralLink, ExternalReferralLink } from '@dtypes/api.minmatar.org'
import type { PageFinderUI, ReferralLinkStatsUI } from '@dtypes/layout_components'

import sitemap from '@json/sitemap.json'
import external_referrals from '@json/external-referrals.json'

export function is_referral_url(pathname:string, lang:'en') {
    const translatePath = useTranslatedPath(lang)

    try {
        const referrable_pages = get_referrable_pages()
        
        const referral = referrable_pages.find( page => translatePath(page.link ?? '') === pathname)

        return referral !== undefined
    } catch (error) {
        return undefined
    }
}

export async function check_referral_url(current_user_id:number, pathname:string, searchParams:URLSearchParams, clientIP:string, lang:'en') {
    const translatePath = useTranslatedPath(lang)

    const referrable_pages = get_referrable_pages()
    
    const referral = referrable_pages.find( page => translatePath(page.link ?? '') === pathname)
    const user_id = parseInt(searchParams.get('ref') ?? '0')
    const page = referral?.name

    if (user_id === current_user_id)
        return

    if (referral && user_id > 0 && clientIP && page) {
        record_referral(
            page,
            user_id,
            clientIP
        )
        .then(value => {
            console.log('Referral success')
        })
        .catch(err => {
            console.error(err)
        })
    }
}

export async function check_external_referral_url(page_name:string, searchParams:URLSearchParams, clientIP:string, lang:'en') {    
    const referral = external_referrals.find( page => page.name === page_name)
    const user_id = parseInt(searchParams.get('ref') ?? '0')

    if (referral && user_id > 0 && clientIP) {
        record_referral(
            page_name,
            user_id,
            clientIP
        )
        .then(value => {
            console.log('Referral success')
        })
        .catch(err => {
            console.error(err)
        })
    }

    return referral?.target
}

export const get_referral_stats = async (access_token:string, user_id:number, lang:'en') => {
    const t = useTranslations(lang);

    const stats = await get_link_stats(access_token)

    return stats.map(stat => {
        const site_referral = sitemap.find(page => page.slug === stat.name)
        const external_referral = site_referral === undefined ? external_referrals.find(page => page.name === stat.name) : null

        const referral_link = {
            title: site_referral ? t(`${stat.name}.page_title` as any) : external_referral ? external_referral.title : stat.name,
            count: stat.referrals,
        } as ReferralLinkStatsUI

        if (site_referral) referral_link.target = site_referral.path
        if (external_referral) referral_link.target = external_referral.target

        return referral_link
    })
}

export const get_external_referrals = (user_id: number, lang:'en') => {
    const translatePath = useTranslatedPath(lang)

    return external_referrals.map(page => {
        return {
            name: page.title,
            slug: page.name,
            target: page.target,
            link: `${translatePath(`${get_app_url(`/external/${page.name}`)}?ref=${user_id}`)}`,
            decription: page.description,
        } as ExternalReferralLink
    })
}

export const get_referrable_pages = () => {
    const pages = sitemap.filter( (page:PageFinderUI) => {
        if (!page.publish)
            return false

        if (!page?.permissions)
            return true

        if (page.permissions?.auth)
            return true

        if (page.permissions)
            return false

        return true
    })

    return pages.map(page => {
        return {
            name: page.slug,
            link: page.path,
        } as ReferralLink
    })
}