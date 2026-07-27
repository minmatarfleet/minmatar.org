from django.core.management.base import BaseCommand

from learning.models import Certificate, CertificateLearning, Learning


def upsert_learning(**fields) -> Learning:
    slug = fields.pop("slug")
    learning, _ = Learning.objects.update_or_create(slug=slug, defaults=fields)
    return learning


def upsert_certificate(
    *,
    slug,
    title,
    summary,
    personas,
    sort_order,
    learning_slugs,
    published=True,
):
    certificate, _ = Certificate.objects.update_or_create(
        slug=slug,
        defaults={
            "title": title,
            "summary": summary,
            "personas": personas,
            "sort_order": sort_order,
            "published": published,
        },
    )
    CertificateLearning.objects.filter(certificate=certificate).delete()
    for order, learning_slug in enumerate(learning_slugs):
        learning = Learning.objects.get(slug=learning_slug)
        CertificateLearning.objects.create(
            certificate=certificate,
            learning=learning,
            order=order,
        )
    return certificate


LEARNINGS = [
    {
        "slug": "new-player-fleet-guide",
        "title": "New Player Fleet Guide",
        "summary": (
            "Everything you need for your first militia fleet: doctrines, "
            "support ships, fleet UI, and FAQ."
        ),
        "url": "/guides/new-player-fleet-guide/",
        "content_kind": "guide",
        "estimated_minutes": 15,
    },
    {
        "slug": "alliance-values",
        "title": "Alliance Values",
        "summary": "Who we are and how we expect pilots to show up.",
        "url": "/alliance/values/",
        "content_kind": "page",
        "estimated_minutes": 5,
    },
    {
        "slug": "alliance-playstyle",
        "title": "Alliance Playstyle",
        "summary": "How Minmatar Fleet fights and organizes content.",
        "url": "/alliance/playstyle/",
        "content_kind": "page",
        "estimated_minutes": 10,
    },
    {
        "slug": "faction-warfare-basics",
        "title": "Faction Warfare Basics",
        "summary": "An overview of the basic mechanics of faction warfare.",
        "url": "/guides/faction-warfare-basics/",
        "content_kind": "guide",
        "estimated_minutes": 5,
    },
    {
        "slug": "faction-warfare-plexing",
        "title": "Faction Warfare Complexes",
        "summary": "In-depth breakdown for capturing complexes in FW space.",
        "url": "/guides/faction-warfare-plexing/",
        "content_kind": "guide",
        "estimated_minutes": 10,
    },
    {
        "slug": "faction-warfare-advantage",
        "title": "Faction Warfare Advantage",
        "summary": "How advantage works and why it matters in the warzone.",
        "url": "/guides/faction-warfare-advantage/",
        "content_kind": "guide",
        "estimated_minutes": 5,
    },
    {
        "slug": "navy-frigate-guide",
        "title": "Faction Warfare Frigate Guide",
        "summary": "Fittings, roles, and 1v1 matchups for frigates in FW.",
        "url": "/guides/navy-frigate-guide/",
        "content_kind": "guide",
        "estimated_minutes": 20,
    },
    {
        "slug": "navy-destroyer-metagame",
        "title": "Faction Warfare Destroyer Guide",
        "summary": "Fittings, roles, and 1v1 matchups for destroyers in FW.",
        "url": "/guides/navy-destroyer-metagame/",
        "content_kind": "guide",
        "estimated_minutes": 30,
    },
    {
        "slug": "faction-warfare-cruiser-guide",
        "title": "Faction Warfare Cruiser Guide",
        "summary": "Fittings, roles, and 1v1 matchups for cruisers in FW.",
        "url": "/guides/faction-warfare-cruiser-guide/",
        "content_kind": "guide",
        "estimated_minutes": 40,
    },
    {
        "slug": "abyssals",
        "title": "Farming the Abyss",
        "summary": "Abyssal deadspace overview: filaments, weather, and fit guides.",
        "url": "/guides/abyssals/",
        "content_kind": "guide",
        "estimated_minutes": 5,
    },
    {
        "slug": "level5-missions",
        "title": "L5 Mission Farming",
        "summary": "Blitz Minmatar level 5 missions: tactics and ship fits.",
        "url": "/guides/level5-missions/",
        "content_kind": "guide",
        "estimated_minutes": 15,
    },
    {
        "slug": "zohar-hunting",
        "title": "Zohar Hunting",
        "summary": "How to hunt Zohars for ISK in Minmatar space.",
        "url": "/guides/zohar-hunting/",
        "content_kind": "guide",
        "estimated_minutes": 15,
    },
]

CERTIFICATES = [
    {
        "slug": "alliance-onboarding",
        "title": "Alliance Onboarding",
        "summary": (
            "Get oriented with our alliance, Minmatar Fleet. Learn about our "
            "values, playstyles, and history."
        ),
        "personas": ["alliance"],
        "sort_order": 1,
        # Hidden from Learning Center hub / persona flows for now.
        "published": False,
        "learning_slugs": [
            "alliance-values",
            "alliance-playstyle",
            "new-player-fleet-guide",
        ],
    },
    {
        "slug": "faction-warfare",
        "title": "Faction Warfare",
        "summary": (
            "Learn about faction warfare mechanics and the ships that win "
            "fights."
        ),
        "personas": ["alliance", "militia"],
        "sort_order": 2,
        "learning_slugs": [
            "faction-warfare-basics",
            "faction-warfare-plexing",
            "faction-warfare-advantage",
            "navy-frigate-guide",
            "navy-destroyer-metagame",
            "faction-warfare-cruiser-guide",
        ],
    },
    {
        "slug": "isk-generation",
        "title": "ISK Generation",
        "summary": (
            "Tired of your current ISK generation method? Mix it up with one of these best-in-class sources. We only share high income methods."
        ),
        "personas": ["alliance", "militia", "other"],
        "sort_order": 3,
        "learning_slugs": [
            "abyssals",
            "level5-missions",
            "zohar-hunting",
        ],
    },
]


class Command(BaseCommand):
    help = "Seed initial Learning Center certificates and learnings."

    def handle(self, *args, **options):
        for fields in LEARNINGS:
            learning = upsert_learning(**fields)
            self.stdout.write(f"Learning: {learning.slug}")

        for fields in CERTIFICATES:
            certificate = upsert_certificate(**fields)
            self.stdout.write(
                f"Certificate: {certificate.slug} "
                f"({certificate.learnings.count()} learnings)"
            )

        self.stdout.write(self.style.SUCCESS("Learning Center seed complete."))
