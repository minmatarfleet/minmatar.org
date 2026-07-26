interface FactionWarfareCruiserGuideJsonLdOptions {
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
}

export function buildFactionWarfareCruiserGuideJsonLd(options: FactionWarfareCruiserGuideJsonLdOptions) {
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
                genre: 'Video game guide',
                keywords: [
                    'EVE Online',
                    'faction warfare',
                    'cruiser',
                    'navy cruiser',
                    'Exequror Navy Issue',
                    'Vexor Navy Issue',
                    'Stabber Fleet Issue',
                    'Scythe Fleet Issue',
                    '1v1',
                    'matchup chart',
                    'ship fittings',
                ].join(', '),
                inLanguage: 'en',
                mainEntityOfPage: { '@id': `${canonicalUrl}#webpage` },
                version: editionLabel,
            },
        ],
    }
}
