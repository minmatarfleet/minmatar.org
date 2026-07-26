interface NavyFrigateGuideJsonLdOptions {
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

export function buildNavyFrigateGuideJsonLd(options: NavyFrigateGuideJsonLdOptions) {
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
                    name: 'Faction Warfare Frigate Guide (First Edition)',
                    url: originalEditionUrl,
                },
                genre: 'Video game guide',
                keywords: [
                    'EVE Online',
                    'faction warfare',
                    'frigate guide',
                    'navy frigate',
                    'Caldari Navy Hookbill',
                    'Federation Navy Comet',
                    'Imperial Navy Slicer',
                    'Republic Fleet Firetail',
                    'Vigil Fleet Issue',
                    'Tristan',
                    'Breacher',
                    'Scout complex',
                    '1v1',
                    'matchup chart',
                    'solo PvP',
                    'FW plex',
                ].join(', '),
                about: [
                    { '@type': 'Thing', name: 'EVE Online faction warfare' },
                    { '@type': 'Thing', name: 'Faction warfare frigates' },
                ],
                inLanguage: 'en',
                mainEntityOfPage: { '@id': `${canonicalUrl}#webpage` },
                creativeWorkStatus: editionLabel,
            },
        ],
    }
}
