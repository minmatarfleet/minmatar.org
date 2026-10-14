---
paths:
  - "backend/**/models/**/*.py"
  - "backend/**/models.py"
---
# Soft delete

- New soft-deletable domain models should inherit `MinmatarSoftDeleteModel` from `app.models` (not `SafeDeleteModel` directly).
- Use the default manager (`Model.objects`) in product code (routers, tasks, forms); it excludes soft-deleted rows.
- Use `all_objects` or `deleted_objects` only for admin, restore, imports, or features that explicitly include deleted data.
- For `get_or_create` on these models when a soft-deleted row may already exist (same PK or natural key), use `get_or_create_active` from `app.models`.
