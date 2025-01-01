import { useTranslations } from '@i18n/utils';
import type { Locales } from '@dtypes/layout_components'
import { semantic_list } from '@helpers/array'
import moment from 'moment';

const datetime_options = JSON.parse(import.meta.env.DATETIME_FORMAT)
const date_options = JSON.parse(import.meta.env.DATE_FORMAT ?? '{"weekday":"short","year":"numeric","month":"short","day":"numeric"}')
const date_short_options = JSON.parse(import.meta.env.DATE_FORMAT_SHORT ?? '{"year":"numeric","month":"short","day":"numeric"}')
const date_shortest_options = JSON.parse(import.meta.env.DATE_FORMAT_SHORTEST ?? '{"year":"numeric","month":"long"}')

export const format_date_time = (locale, date):string => {
    return new Date(date).toLocaleDateString(locale, datetime_options)
}

export const format_date = (locale, date):string => {
    return new Date(date).toLocaleDateString(locale, date_options)
}

export const format_date_short = (locale, date):string => {
    return new Date(date).toLocaleDateString(locale, date_short_options)
}

export const format_date_shortest = (locale, date):string => {
    return new Date(date).toLocaleDateString(locale, date_shortest_options)
}

export const days_diff_text = (locale:Locales = 'en', from:Date, to:Date):string => {
    const t = useTranslations(locale);
    
    const diff_days = days_diff(from, to)
    
    return `${diff_days} ${diff_days != 1 ? t('days') : t('day')}`
}

export const from_now_diff = (locale:Locales, to:Date):string => {
    return moment(to).fromNow()
}

export const humanize_date_diff = (locale:Locales, from:Date, to:Date):string => {
    const t = useTranslations(locale)
    var from_moment = moment(new Date(from))
    var to_moment = moment(new Date(to))
    const duration = moment.duration(to_moment.diff(from_moment))
    const durations:string[] = []
    
    if (duration.years() > 0)
        durations.push(`${duration.years()} ${duration.years() != 1 ? t('years') : t('year') }`)
    
    if (duration.months() > 0)
        durations.push(`${duration.months()} ${duration.months() != 1 ? t('months') : t('month') }`)
    
    if (duration.days() > 0)
        durations.push(`${duration.days()} ${duration.days() != 1 ? t('days').toLowerCase() : t('day').toLowerCase() }`)
    
    return semantic_list(locale, durations)
}

export const minutes_to = (datetime:Date):number => {
    var from_moment = moment(new Date(datetime))
    var to_moment = moment(new Date())
    return Math.ceil(moment.duration(to_moment.diff(from_moment)).asMinutes())
}

export const days_diff = (from:Date, to:Date):number => {
    var from_moment = moment(new Date(from))
    var to_moment = moment(new Date(to))
    return Math.floor(moment.duration(to_moment.diff(from_moment)).asDays())
}

export const hours_diff = (from:Date, to:Date):number => {
    var from_moment = moment(new Date(from))
    var to_moment = moment(new Date(to))
    return Math.floor(moment.duration(to_moment.diff(from_moment)).asHours())
}

export const month_diff = (from:Date, to:Date):number => {
    var from_moment = moment(new Date(from))
    var to_moment = moment(new Date(to))
    return moment.duration(to_moment.diff(from_moment)).months()
}

export const year_diff = (from:Date, to:Date):number => {
    var from_moment = moment(new Date(from))
    var to_moment = moment(new Date(to))
    return moment.duration(to_moment.diff(from_moment)).years()
}

export const from_to_text = (locale:Locales = 'en', from:Date, to:Date):string => {
    const t = useTranslations(locale);

    return `${format_date_short(locale, from)} ${t('to')} ${format_date_short(locale, to)} (${days_diff_text(locale, from, to)})`
}

export const from_to_now_text = (locale:Locales = 'en', from:Date):string => {
    const t = useTranslations(locale);
    const to = new Date()
    
    return `${format_date_short(locale, from)} ${t('to_this_day')} (${days_diff_text(locale, from, to)})`
}

export const generate_timeline = (start_date, end_date) => {
    const dates:Date[] = []
    const step = 10 * 1000 // 10 seconds in milliseconds

    let current_date = new Date(start_date)
    const end = new Date(end_date)

    while (current_date <= end) {
        dates.push(new Date(current_date)) // Add the current date to the array
        current_date = new Date(current_date.getTime() + step) // Increment by 10 seconds
    }

    return dates.map(date => date.toISOString().replace('T', ' ').replace('.000Z', '').replaceAll('-', '.'))
}

export const is_birthday = (date:Date) => {
    const birthdate = new Date(date)
    const today = new Date()

    if (!(birthdate instanceof Date) || birthdate.toString() === 'Invalid Date')
        return false

    const birth_month = birthdate.getMonth()
    const birthday = birthdate.getDate()

    const today_month = today.getMonth()
    const today_day = today.getDate()

    return (birth_month === today_month && birthday === today_day)
}

export const is_seasonal_date = (start_date:string, end_date:string) => {
    const today = new Date()
    const [startMonth, startDay] = start_date.split("-").map(Number)
    const [endMonth, endDay] = end_date.split("-").map(Number)

    const start = new Date(today.getFullYear(), startMonth - 1, startDay)
    const end = new Date(today.getFullYear(), endMonth - 1, endDay)

    if (end < start) {
        if (today >= start || today <= new Date(today.getFullYear() + 1, endMonth - 1, endDay))
            return true
    } else {
        if (today >= start && today <= end)
            return true
    }

    return false
}