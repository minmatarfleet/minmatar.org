"""The site's curated cover art, shared by every page that lets an admin pick
a background (campaigns, mentor classes).

Paths are under ``frontend/app/public``. Pages show them as-is; the Django
admin picker turns them into absolute URLs with ``app.links.site_url``.
"""

SITE_COVERS: list[tuple[str, str]] = [
    ("/images/home-auga-cover.jpg", "Auga"),
    ("/images/home-amamake-cover.jpg", "Amamake"),
    ("/images/home-cover-og.jpg", "Watermellon"),
    ("/images/home-vard-cover.jpg", "Vard"),
    ("/images/home-evati-cover.jpg", "Evati"),
    ("/images/home-nakah-cover.jpg", "Nakah"),
    ("/images/home-r6-2-cover.jpg", "R-6KYM"),
    ("/images/home-amarr-cover.jpg", "Amarr"),
    ("/images/warzone-card.jpg", "Warzone card"),
    ("/images/warzone-cover.jpg", "Warzone"),
    ("/images/etherium-campaign.webp", "Etherium Reach"),
    ("/images/providence-campaign.webp", "Providence"),
    ("/images/scalding-campaign.webp", "Scalding Pass"),
    ("/images/hek-campaign.webp", "Hek"),
]
