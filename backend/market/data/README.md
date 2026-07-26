# Market data files

## `amamake_inferred_sales.csv`

Public backfill of Amamake structure inferred sell fills (order-book diffs).

| Column | Meaning |
|--------|---------|
| `location_id` | Structure location (`1022167642188` = Amamake) |
| `type_id` | ESI type ID |
| `quantity` | Units inferred sold |
| `price` | ISK unit price |
| `inferred_at` | UTC ISO-8601 timestamp |

Source window: 2026-06-26 → 2026-07-26. Loaded as `EveMarketInferredSale` with `reason=imported`.

```bash
pipenv run python manage.py import_amamake_inferred_sales --dry-run
pipenv run python manage.py import_amamake_inferred_sales
```
