# Seed the Fleet Roles certificates: one per role guide, each holding the
# guide and the drills that count toward it. Optional drills stay out.
#
# The frontend's src/data/fleet-roles/*.ts holds the same guides and drill
# ids; learning/tests/test_fleet_role_certificates.py keeps them in step.

from django.db import migrations

FLEET_ROLES = [
    {
        "role": "damage",
        "guide_slug": "damage-guide",
        "title": "Damage",
        "guide_title": "Damage Guide",
        "guide_summary": (
            "Kill what the FC calls, fast: applied damage, target calling, "
            "ammo and overheating."
        ),
        "minutes": 20,
        "summary": (
            "Kill what the FC calls, fast. Read the guide, beat the applied "
            "damage simulator, and prove the habits on fleets."
        ),
        "drills": [
            (
                "applied-sim",
                "Beat the applied damage simulator",
                "Land most of your paper DPS on a moving cruiser.",
            ),
            (
                "fleet-lock-ahead",
                "Lock ahead on a fleet",
                "Have the next target locked when the switch is called, every time.",
            ),
            (
                "setup-broadcasts",
                "Set up broadcast hotkeys",
                "Lock broadcast, align and warp to broadcast, on keys you can reach.",
            ),
            (
                "fleet-strategic",
                "Fly a strategic op in a doctrine battleship",
                "Any hull from the ladder, in the doctrine the MOTD calls.",
            ),
        ],
    },
    {
        "role": "remote-repair",
        "guide_slug": "remote-repair-guide",
        "title": "Remote Repair",
        "guide_title": "Remote Repair Guide",
        "guide_summary": (
            "Keep the fleet alive: broadcasts, capacitor chains, anchoring "
            "and the Zarmazd."
        ),
        "minutes": 25,
        "summary": (
            "Keep the fleet alive. Read the guide, beat the rep race, and "
            "hold a capacitor chain through a whole fleet."
        ),
        "drills": [
            (
                "rep-race-sim",
                "Beat the rep race simulator",
                "Keep the anchor alive for 60 seconds.",
            ),
            (
                "fleet-logi",
                "Fly logi on a fleet",
                "Any logistics hull on an Academy or kitchen-sink fleet, repairing from broadcasts.",
            ),
            (
                "fleet-chain",
                "Hold a capacitor chain for a whole fleet",
                "With the same partner from form-up to dock.",
            ),
        ],
    },
    {
        "role": "capacitor-warfare",
        "guide_slug": "capacitor-warfare-guide",
        "title": "Capacitor Warfare",
        "guide_title": "Capacitor Warfare Guide",
        "guide_summary": (
            "Drain the enemy: the capacitor curve, neut versus nos, range "
            "and target priority."
        ),
        "minutes": 20,
        "summary": (
            "Make an enemy ship useless by draining it. Read the guide, "
            "beat both capacitor simulators, and neut the logi on a fleet."
        ),
        "drills": [
            (
                "curve-sim",
                "Beat the capacitor curve simulator",
                "Find the peak and hold a target under it.",
            ),
            (
                "pressure-sim",
                "Beat the neut pressure simulator",
                "Empty one Guardian of a chained pair.",
            ),
            (
                "fleet-neut",
                "Neut the logi on a fleet",
                "Fly a neut ship on any fleet and drain the logi the FC calls.",
            ),
        ],
    },
    {
        "role": "electronic-warfare",
        "guide_slug": "electronic-warfare-guide",
        "title": "Electronic Warfare",
        "guide_title": "Electronic Warfare Guide",
        "guide_summary": (
            "Stop the enemy locking: jam chance, spreading ECM, bursts and "
            "staying alive."
        ),
        "minutes": 20,
        "summary": (
            "Stop the enemy locking what they want. Read the guide, beat "
            "both ECM simulators, and jam the logi on a fleet."
        ),
        "drills": [
            (
                "jam-chance-sim",
                "Beat the jam chance simulator",
                "Pick the right jammer for three hulls.",
            ),
            (
                "spread-sim",
                "Beat the ECM spread simulator",
                "Keep two of three logi jammed on average.",
            ),
            (
                "fleet-griffin",
                "Fly ECM on a fleet",
                "Fly a Griffin on an Academy or kitchen-sink fleet and jam the logi.",
            ),
        ],
    },
    {
        "role": "positioning-warfare",
        "guide_slug": "positioning-warfare-guide",
        "title": "Positioning Warfare",
        "guide_title": "Positioning Warfare Guide",
        "guide_summary": (
            "Decide where the enemy fleet is: points, booshes, bumps, and "
            "bubbles where they work."
        ),
        "minutes": 25,
        "summary": (
            "Decide where the enemy fleet is and whether it can leave. Read "
            "the guide, beat the bubble and boosh simulators, and hold the "
            "anchor on a fleet."
        ),
        "drills": [
            ("bubble-sim", "Beat the bubble simulator", "All three targets."),
            (
                "mjfg-sim",
                "Beat the Micro Jump Field simulator",
                "Boosh their logi off grid and leave your own behind.",
            ),
            (
                "fleet-tackle",
                "Hold the anchor on a fleet",
                "Point the called target on an Academy or kitchen-sink fleet and call it on comms.",
            ),
        ],
    },
]

FIRST_SORT_ORDER = 10


def certificate_slug(role):
    return f"fleet-role-{role}"


def drill_slug(role, drill_id):
    return f"{role}-drill-{drill_id}"


def seed_fleet_roles(apps, schema_editor):
    Learning = apps.get_model("learning", "Learning")
    Certificate = apps.get_model("learning", "Certificate")
    CertificateLearning = apps.get_model("learning", "CertificateLearning")

    for index, role in enumerate(FLEET_ROLES):
        guide_url = f"/learning/guides/{role['guide_slug']}/"
        guide, _ = Learning.objects.update_or_create(
            slug=role["guide_slug"],
            defaults={
                "title": role["guide_title"],
                "summary": role["guide_summary"],
                "url": guide_url,
                "content_kind": "guide",
                "estimated_minutes": role["minutes"],
                "published": True,
            },
        )
        learnings = [guide]
        for drill_id, title, how in role["drills"]:
            learning, _ = Learning.objects.update_or_create(
                slug=drill_slug(role["role"], drill_id),
                defaults={
                    "title": title,
                    "summary": how,
                    "url": f"{guide_url}#drills",
                    "content_kind": "page",
                    "estimated_minutes": 10,
                    "published": True,
                },
            )
            learnings.append(learning)

        certificate, _ = Certificate.objects.update_or_create(
            slug=certificate_slug(role["role"]),
            defaults={
                "title": role["title"],
                "summary": role["summary"],
                "personas": ["alliance", "militia"],
                "sort_order": FIRST_SORT_ORDER + index,
                "published": True,
            },
        )
        CertificateLearning.objects.filter(certificate=certificate).delete()
        for order, learning in enumerate(learnings):
            CertificateLearning.objects.create(
                certificate=certificate, learning=learning, order=order
            )


def unseed_fleet_roles(apps, schema_editor):
    Learning = apps.get_model("learning", "Learning")
    Certificate = apps.get_model("learning", "Certificate")

    Certificate.objects.filter(
        slug__in=[certificate_slug(r["role"]) for r in FLEET_ROLES]
    ).delete()
    slugs = [r["guide_slug"] for r in FLEET_ROLES]
    for role in FLEET_ROLES:
        slugs += [drill_slug(role["role"], d[0]) for d in role["drills"]]
    Learning.objects.filter(slug__in=slugs).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("learning", "0005_mentor_class_cover"),
    ]

    operations = [
        migrations.RunPython(seed_fleet_roles, unseed_fleet_roles),
    ]
