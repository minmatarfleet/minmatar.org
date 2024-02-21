import { useTranslations } from '@i18n/utils';
import type { Locales } from '@dtypes/layout_components'

const datetime_options = JSON.parse(import.meta.env.DATETIME_FORMAT)
const date_options = JSON.parse(import.meta.env.DATE_FORMAT ?? '{"weekday":"short","year":"numeric","month":"short","day":"numeric"}')

export const format_date_time = (locale, date):string => {
    return new Date(date).toLocaleDateString(locale, datetime_options)
}

export const format_date = (locale, date):string => {
    return new Date(date).toLocaleDateString(locale, date_options)
}

export const days_diff_text = (locale:Locales = 'en', from:Date, to:Date):string => {
    const t = useTranslations(locale);
    
    const diff_days = days_diff(from, to)
    
    return `${diff_days} ${diff_days != 1 ? t('days') : t('day')}`
}

export const days_diff = (from:Date, to:Date):number => {
    const _from = new Date(from)
    const _to = new Date(to)
    const diff_time = Math.abs(_to.valueOf() - _from.valueOf());
    const diff_days = Math.floor(diff_time / (1000 * 60 * 60 * 24));

    return diff_days
}

export const from_to_text = (locale:Locales = 'en', from:Date, to:Date):string => {
    const t = useTranslations(locale);

    return `${format_date(locale, from)} ${t('to')} ${format_date(locale, to)} (${days_diff_text(locale, from, to)})`
}

export const from_to_now_text = (locale:Locales = 'en', from:Date):string => {
    const t = useTranslations(locale);
    const to = new Date()
    
    return `${format_date(locale, from)} ${t('to_this_day')} (${days_diff_text(locale, from, to)})`
}