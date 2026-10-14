import type { OpenCorporationApplication } from '@dtypes/api.minmatar.org'

export function corporations_with_open_application<
    T extends {
        corporation_id: number
        open_application_corporation_name?: string
    },
>(
    corporations: T[],
    open_application: Pick<
        OpenCorporationApplication,
        'corporation_id' | 'corporation_name'
    > | null,
): T[] {
    if (!open_application)
        return corporations

    return corporations.map((corporation) => {
        if (corporation.corporation_id === open_application.corporation_id)
            return corporation

        return {
            ...corporation,
            open_application_corporation_name: open_application.corporation_name,
        }
    })
}

export function open_application_elsewhere_message(
    template: string,
    corporation_name: string,
): string {
    return template.replace('{corporation}', () => corporation_name)
}
