# Seed the Fleet Roles guides and their drills as learnings, so the guides
# can track which drills a pilot has marked done. The guides have no
# certificates. Optional drills stay out.
#
# The frontend's src/data/fleet-roles/*.ts holds the same guides and drill
# ids; learning/tests/test_fleet_role_learnings.py keeps them in step.

from django.db import migrations

FLEET_ROLES = [
    {
        "role": "damage",
        "guide_slug": "damage-guide",
        "guide_title": "Damage Guide",
        "guide_summary": (
            "Kill what the FC calls, fast: target calling, applied damage, "
            "the ammo our ships carry, utility slots and overheating."
        ),
        "minutes": 20,
        "drills": [
            (
                "fleet-basics-sim",
                "Fly Fleet Basics: DPS",
                "In EVE Combat Sim: anchor up, follow the broadcasts and "
                "switch on the call.",
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
                "Fly a strategic op in a doctrine damage ship",
                "Any hull from Ships we fly, in the doctrine the MOTD calls.",
            ),
        ],
    },
    {
        "role": "remote-repair",
        "guide_slug": "remote-repair-guide",
        "guide_title": "Remote Repair Guide",
        "guide_summary": (
            "Keep the fleet alive: anchoring, broadcasts, capacitor chains "
            "and the modules on our logi fits."
        ),
        "minutes": 15,
        "drills": [
            (
                "cap-chain-sim",
                "Fly Cap Chain Logistics",
                "In EVE Combat Sim: hold the chain while the fleet takes damage.",
            ),
            (
                "fleet-logi",
                "Fly logi on a fleet",
                "Any logistics hull from Ships we fly, repairing from broadcasts.",
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
        "guide_title": "Capacitor Warfare Guide",
        "guide_summary": (
            "Drain the enemy: neuts and nos, who to neut, and the modules "
            "on our neut fits."
        ),
        "minutes": 12,
        "drills": [
            (
                "neuts-sim",
                "Fly Energy Neutralizers",
                "In EVE Combat Sim: empty the Brutix’s capacitor before it kills your drones.",
            ),
            (
                "nos-sim",
                "Fly Nosferatu (Nos)",
                "In EVE Combat Sim: keep your own capacitor up with nos.",
            ),
            (
                "fleet-neut",
                "Neut on a fleet",
                "Fly a neut ship on any fleet and drain the targets the FC calls.",
            ),
        ],
    },
    {
        "role": "electronic-warfare",
        "guide_slug": "electronic-warfare-guide",
        "guide_title": "Electronic Warfare Guide",
        "guide_summary": (
            "Stop the enemy doing their job: ECM, damps, who to target "
            "and staying alive."
        ),
        "minutes": 12,
        "drills": [
            (
                "ecm-sim",
                "Fly ECM",
                "In EVE Combat Sim: jam the enemy and watch their locks drop.",
            ),
            (
                "fleet-ewar",
                "Fly EWAR on a fleet",
                "Fly a ship from Ships for this role and work the targets the FC calls.",
            ),
        ],
    },
    {
        "role": "fleet-support",
        "guide_slug": "fleet-support-guide",
        "guide_title": "Fleet Support Guide",
        "guide_summary": (
            "Hold the enemy in place: points, scrams, webs, painters and "
            "heavy tackle."
        ),
        "minutes": 12,
        "drills": [
            (
                "spiral-sim",
                "Fly Spiral Approach",
                "In EVE Combat Sim: spiral in and get tackle without being hit.",
            ),
            (
                "webs-sim",
                "Fly Webs",
                "In EVE Combat Sim: web targets and watch them slow down.",
            ),
            (
                "fleet-tackle",
                "Hold the anchor on a fleet",
                "Point the called target on a fleet and call it on comms.",
            ),
        ],
    },
    {
        "role": "fleet-disruption",
        "guide_slug": "fleet-disruption-guide",
        "guide_title": "Fleet Disruption Guide",
        "guide_summary": (
            "Break up the enemy fleet: anchor tackle, booshing, bubbles "
            "and firewalls."
        ),
        "minutes": 12,
        "drills": [
            (
                "spiral-sim",
                "Fly Spiral Approach",
                "In EVE Combat Sim: spiral in and get tackle without being hit.",
            ),
            (
                "drag-bubbles-sim",
                "Fly Drag Bubbles",
                "In EVE Combat Sim: get through a bubble camp to the gate.",
            ),
            (
                "fleet-disrupt",
                "Fly disruption on a fleet",
                "Fly a ship from Ships for this role and work the FC’s calls.",
            ),
        ],
    },
]

FIRST_SORT_ORDER = 10


def drill_slug(role, drill_id):
    return f"{role}-drill-{drill_id}"


def seed_fleet_roles(apps, schema_editor):
    Learning = apps.get_model("learning", "Learning")

    for role in FLEET_ROLES:
        guide_url = f"/learning/guides/{role['guide_slug']}/"
        Learning.objects.update_or_create(
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
        for drill_id, title, how in role["drills"]:
            Learning.objects.update_or_create(
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


def unseed_fleet_roles(apps, schema_editor):
    Learning = apps.get_model("learning", "Learning")

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
