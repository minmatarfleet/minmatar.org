import { getLangFromUrl, useTranslations, useTranslatedPath, type TranslationKey } from '@i18n/utils';

export type { TranslationKey };

export function i18n(url:URL) {
    const lang = getLangFromUrl(url);
    const t = useTranslations(lang);
    const translatePath = useTranslatedPath(lang);

    return {
        lang: lang,
        t: t,
        translatePath: translatePath,
    }
}

/** Keys of one family: `KeyFamily<'burst_kind_'>` is every key starting with `burst_kind_`. */
export type KeyFamily<P extends string, S extends string = ''> = Extract<TranslationKey, `${P}${string}${S}`>

/** What `t_key` returns when no key has that prefix and suffix; `t()` rejects it, so the typo fails `astro check`. */
export interface NoTranslationKeyFamily<P extends string, S extends string> {
    no_translation_key_matches: `${P}*${S}`
}

type DynamicPart = string | number | null | undefined

/**
 * A key built from data, e.g. `t(t_key('burst_kind_', kind))` or `t(t_key('', page.slug, '.page_title'))`.
 * The prefix and suffix are checked against ui.ts at compile time; the middle part can only be checked
 * by a test over its values. Same string as the template literal it replaces, so `t()` behaves the same:
 * a missing key still returns undefined.
 */
export function t_key<P extends string, S extends string = ''>(
    prefix: P,
    value: DynamicPart,
    suffix?: S,
): NoInfer<[KeyFamily<P, S>] extends [never] ? NoTranslationKeyFamily<P, S> : KeyFamily<P, S>> {
    return `${prefix}${value}${suffix ?? ''}` as never
}

/**
 * A whole key that comes from data (an API enum, a prop). Nothing about it can be checked at compile
 * time, so prefer `t_key` whenever the key has a fixed prefix or suffix.
 */
export function dynamic_key(key: DynamicPart): TranslationKey {
    return key as TranslationKey
}
