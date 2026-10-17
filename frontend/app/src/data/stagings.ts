import type { ui } from '@i18n/ui'
import type { StagingType } from '@dtypes/layout_components'

type UiKey = keyof typeof ui['en']

export interface StagingStation {
    system:             string;
    security:           string;
    constellation:      string;
    region:             string;
    station_name:       string;
    description_key:    UiKey;
    /** Pickable in the staging switcher. Stagings without it render a plain card. */
    switcher?: {
        /** Switcher label. Differs from station_name for Sosala today. */
        title:          string;
        type_id:        number;
    };
}

/** Every live staging, keyed by its `staging` cookie value. Adding a slug to `stagings` makes TypeScript require a row here. */
export const STAGINGS: Record<StagingType, StagingStation> = {
    amamake: {
        system: 'Amamake',
        security: '0.4',
        constellation: 'Hed',
        region: 'Heimatar',
        station_name: 'Amamake - 5 times nearly AT winners',
        description_key: 'fw_hq_description',
        switcher: {
            title: 'Amamake - 5 times nearly AT winners',
            type_id: 35834,
        },
    },
    watermellon: {
        system: 'Sosala',
        security: '0.4',
        constellation: 'Vaarma',
        region: 'The Bleak Lands',
        station_name: 'Sosala – WATERMELON',
        description_key: 'watermellon_description',
        switcher: {
            title: 'Sosala - WATERMELLON',
            type_id: 35833,
        },
    },
    amarr: {
        system: 'Amarr',
        security: '1.0',
        constellation: 'Throne Worlds',
        region: 'Domain',
        station_name: 'Amarr VIII (Oris) - Emperor Family Academy',
        description_key: 'amarr_hq_description',
    },
}

export interface StagingSwitcherOption {
    slug:               StagingType | 'random';
    title:              string;
    description_key:    UiKey;
    type_id:            number;
}

export const RANDOM_STAGING_OPTION: StagingSwitcherOption = {
    slug: 'random',
    title: 'Random',
    description_key: 'random_staging',
    type_id: 76312,
}

/** Switcher entries in display order: every pickable staging, then "Random". */
export const STAGING_SWITCHER_OPTIONS: StagingSwitcherOption[] = [
    ...(Object.entries(STAGINGS) as [StagingType, StagingStation][])
        .filter(([, station]) => station.switcher)
        .map(([slug, station]) => ({
            slug,
            title: station.switcher!.title,
            description_key: station.description_key,
            type_id: station.switcher!.type_id,
        })),
    RANDOM_STAGING_OPTION,
]

/** Staging to show for a `staging` value; unknown values fall back to Sosala, as the home page always has. */
export function known_staging(slug: string): StagingType {
    return Object.hasOwn(STAGINGS, slug) ? slug as StagingType : 'watermellon'
}
