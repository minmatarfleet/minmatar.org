interface NavyDestroyerMetagameJsonLdOptions {
    canonicalUrl: string
    siteName: string
    siteOrigin: string
    metaTitle: string
    headline: string
    metaDescription: string
    metaImage: string
    guidesUrl: string
    authorName: string
    publisherName: string
    editionLabel: string
    originalEditionUrl: string
}

export function buildNavyDestroyerMetagameJsonLd(options: NavyDestroyerMetagameJsonLdOptions) {
    const {
        canonicalUrl,
        siteName,
        siteOrigin,
        metaTitle,
        headline,
        metaDescription,
        metaImage,
        guidesUrl,
        authorName,
        publisherName,
        editionLabel,
        originalEditionUrl,
    } = options

    return {
        '@context': 'https://schema.org',
        '@graph': [
            {
                '@type': 'WebSite',
                '@id': `${siteOrigin}/#website`,
                name: siteName,
                url: siteOrigin,
            },
            {
                '@type': 'WebPage',
                '@id': `${canonicalUrl}#webpage`,
                url: canonicalUrl,
                name: metaTitle,
                description: metaDescription,
                isPartOf: { '@id': `${siteOrigin}/#website` },
                primaryImageOfPage: { '@type': 'ImageObject', url: metaImage },
                breadcrumb: { '@id': `${canonicalUrl}#breadcrumb` },
                mainEntity: { '@id': `${canonicalUrl}#article` },
                inLanguage: 'en',
            },
            {
                '@type': 'BreadcrumbList',
                '@id': `${canonicalUrl}#breadcrumb`,
                itemListElement: [
                    {
                        '@type': 'ListItem',
                        position: 1,
                        name: 'Guides',
                        item: guidesUrl,
                    },
                    {
                        '@type': 'ListItem',
                        position: 2,
                        name: headline,
                        item: canonicalUrl,
                    },
                ],
            },
            {
                '@type': 'Article',
                '@id': `${canonicalUrl}#article`,
                headline,
                description: metaDescription,
                image: metaImage,
                author: {
                    '@type': 'Person',
                    name: authorName,
                },
                publisher: {
                    '@type': 'Organization',
                    name: publisherName,
                    url: siteOrigin,
                },
                isBasedOn: {
                    '@type': 'CreativeWork',
                    name: 'Navy Destroyer Metagame Guide (First Edition)',
                    url: originalEditionUrl,
                },
                genre: 'Video game guide',
                keywords: [
                    'EVE Online',
                    'faction warfare',
                    'destroyer guide',
                    'navy destroyer',
                    'Catalyst Navy Issue',
                    'Coercer Navy Issue',
                    'Thrasher Fleet Issue',
                    'Cormorant Navy Issue',
                    'Talwar Fleet Issue',
                    'Algos',
                    'Thrasher',
                    'Coercer',
                    'Dragoon',
                    '1v1',
                    'matchup chart',
                    'ship fittings',
                    'FW plex',
                ].join(', '),
                about: [
                    { '@type': 'Thing', name: 'EVE Online faction warfare' },
                    { '@type': 'Thing', name: 'Faction warfare destroyers' },
                ],
                inLanguage: 'en',
                mainEntityOfPage: { '@id': `${canonicalUrl}#webpage` },
                version: editionLabel,
            },
        ],
    }
}
