
import { getLangFromUrl, useTranslations, useTranslatedPath } from '@i18n/utils';

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