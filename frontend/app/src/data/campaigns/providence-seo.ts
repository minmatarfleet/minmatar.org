interface ProvidenceCampaignJsonLdOptions {
    canonicalUrl: string
    siteName: string
    siteOrigin: string
    metaTitle: string
    metaDescription: string
    metaImage: string
}

export function buildProvidenceCampaignJsonLd(options: ProvidenceCampaignJsonLdOptions) {
    const {
        canonicalUrl,
        siteName,
        siteOrigin,
        metaTitle,
        metaDescription,
        metaImage,
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
                        name: siteName,
                        item: siteOrigin,
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
                    '@type': 'Organization',
                    name: 'Minmatar Fleet Alliance',
                    url: siteOrigin,
                },
                publisher: {
                    '@type': 'Organization',
                    name: 'Minmatar Fleet Alliance',
                    url: siteOrigin,
                },
                keywords: [
                    'EVE Online',
                    'Providence',
                    'CVA',
                    'nullsec campaign',
                    'Minmatar Fleet',
                    'campaign report',
                ].join(', '),
                inLanguage: 'en',
                mainEntityOfPage: { '@id': `${canonicalUrl}#webpage` },
            },
        ],
    }
}
