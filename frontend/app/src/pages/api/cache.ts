import { useTranslations, useTranslatedPath } from '@i18n/utils'
import { HTTP_200_Success } from '@helpers/http_responses'

export async function DELETE({ params, cookies }) {
    const lang = params.lang ?? 'en'
    const t = useTranslations(lang)
    
    cookies.delete('primary_pilot', { path: '/' })

    const translatePath = useTranslatedPath(lang)

    return HTTP_200_Success()
}