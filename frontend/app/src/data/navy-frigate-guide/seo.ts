interface NavyFrigateGuideJsonLdOptions {
    canonicalUrl: string
    siteName: string
    siteOrigin: string
    metaTitle: string
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
                        name: metaTitle,
                        item: canonicalUrl,
                    },
                ],
            },
            {
                '@type': 'Article',
                '@id': `${canonicalUrl}#article`,
                headline: metaTitle,
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
                    name: 'Frigate Guide (First Edition)',
                    url: originalEditionUrl,
                },
                genre: 'Video game guide',
                keywords: [
                    'EVE Online',
                    'faction warfare',
                    'navy frigate',
                    'Caldari Navy Hookbill',
                    'Federation Navy Comet',
                    'Imperial Navy Slicer',
                    'Republic Fleet Firetail',
                    'Vigil Fleet Issue',
                    '1v1',
                    'matchup chart',
                    'solo PvP',
                    'Scout complex',
                ],
                about: {
                    '@type': 'Thing',
                    name: 'Faction warfare navy frigates',
                },
                creativeWorkStatus: editionLabel,
            },
        ],
    }
}
