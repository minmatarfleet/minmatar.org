from django.db import migrations


def _normalize_pod_text(text: str) -> str:
    if not text:
        return ""
    lines = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        stripped = line.strip()
        if stripped:
            lines.append(stripped)
    return "\n".join(lines)


def migrate_legacy_pod_text(apps, schema_editor):
    EveFitting = apps.get_model("fittings", "EveFitting")
    EveFittingPod = apps.get_model("fittings", "EveFittingPod")
    pod_by_format: dict[str, object] = {}

    for fitting in EveFitting.objects.filter(deleted__isnull=True):
        for field_name, label, priority in (
            ("minimum_pod", "Minimum", 10),
            ("recommended_pod", "Recommended", 20),
        ):
            pod_format = _normalize_pod_text(
                getattr(fitting, field_name) or ""
            )
            if not pod_format:
                continue

            pod = pod_by_format.get(pod_format)
            if pod is None:
                pod = EveFittingPod.objects.create(
                    name=f"{fitting.name} — {label}",
                    priority=priority,
                    description=f"Migrated from EveFitting.{field_name}",
                    pod_format=pod_format,
                )
                pod_by_format[pod_format] = pod

            fitting.pods.add(pod)


class Migration(migrations.Migration):

    dependencies = [
        ("fittings", "0026_evefittingpod_evefitting_pods"),
    ]

    operations = [
        migrations.RunPython(
            migrate_legacy_pod_text, migrations.RunPython.noop
        ),
    ]
