"""Shared helpers for atomic delete-and-bulk-insert sync patterns."""

import time

from django.db import IntegrityError, OperationalError, transaction

DEADLOCK_MAX_ATTEMPTS = 3
BULK_CREATE_BATCH = 500
MYSQL_DEADLOCK_ERRNO = 1213
MYSQL_DUPLICATE_ERRNO = 1062


def replace_with_bulk_create(*, delete_queryset, instances):
    """
    Delete rows matching delete_queryset, then bulk_create instances inside
    one transaction. Retries on MySQL deadlock (1213) and duplicate-key
    races (1062) from concurrent syncs.
    Returns the number of rows created.
    """
    model = delete_queryset.model
    for attempt in range(DEADLOCK_MAX_ATTEMPTS):
        try:
            with transaction.atomic():
                delete_queryset.delete()
                if instances:
                    for offset in range(0, len(instances), BULK_CREATE_BATCH):
                        model.objects.bulk_create(
                            instances[offset : offset + BULK_CREATE_BATCH]
                        )
            return len(instances)
        except OperationalError as exc:
            errno = exc.args[0] if exc.args else None
            if errno != MYSQL_DEADLOCK_ERRNO or attempt >= (
                DEADLOCK_MAX_ATTEMPTS - 1
            ):
                raise
            time.sleep(0.1 * (attempt + 1))
        except IntegrityError as exc:
            errno = exc.args[0] if exc.args else None
            if errno != MYSQL_DUPLICATE_ERRNO or attempt >= (
                DEADLOCK_MAX_ATTEMPTS - 1
            ):
                raise
            time.sleep(0.1 * (attempt + 1))
    return 0
