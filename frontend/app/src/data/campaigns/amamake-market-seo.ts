interface AmamakeMarketJsonLdOptions {
    canonical_url: string
    site_name: string
    site_origin: string
    meta_title: string
    meta_description: string
    meta_image: string
}

export function build_amamake_market_json_ld(options: AmamakeMarketJsonLdOptions) {
    const {
        canonical_url,
        site_name,
        site_origin,
        meta_title,
        meta_description,
        meta_image,
    } = options

    return {
        '@context': 'https://schema.org',
        '@graph': [
            {
                '@type': 'WebSite',
                '@id': `${site_origin}/#website`,
                name: site_name,
                url: site_origin,
            },
            {
                '@type': 'WebPage',
                '@id': `${canonical_url}#webpage`,
                url: canonical_url,
                name: meta_title,
                description: meta_description,
                isPartOf: { '@id': `${site_origin}/#website` },
                primaryImageOfPage: { '@type': 'ImageObject', url: meta_image },
                breadcrumb: { '@id': `${canonical_url}#breadcrumb` },
                mainEntity: { '@id': `${canonical_url}#article` },
            },
            {
                '@type': 'BreadcrumbList',
                '@id': `${canonical_url}#breadcrumb`,
                itemListElement: [
                    {
                        '@type': 'ListItem',
                        position: 1,
                        name: site_name,
                        item: site_origin,
                    },
                    {
                        '@type': 'ListItem',
                        position: 2,
                        name: meta_title,
                        item: canonical_url,
                    },
                ],
            },
            {
                '@type': 'Article',
                '@id': `${canonical_url}#article`,
                headline: meta_title,
                description: meta_description,
                image: meta_image,
                author: {
                    '@type': 'Organization',
                    name: 'Minmatar Fleet Alliance',
                    url: site_origin,
                },
                publisher: {
                    '@type': 'Organization',
                    name: 'Minmatar Fleet Alliance',
                    url: site_origin,
                },
                keywords: [
                    'EVE Online',
                    'Amamake',
                    'Amamake market',
                    'YC128',
                    'faction warfare',
                    'structure market',
                    'Minmatar Fleet',
                    'market report',
                ].join(', '),
                inLanguage: 'en',
                mainEntityOfPage: { '@id': `${canonical_url}#webpage` },
            },
        ],
    }
}
