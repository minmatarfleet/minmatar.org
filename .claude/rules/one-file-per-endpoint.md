---
paths:
  - "backend/**/endpoints/*.py"
---
# One File Per Endpoint

In **endpoints** packages (e.g. `industry/endpoints/` and future packages that are not legacy), use **one file per endpoint**.

- One HTTP method + path = one module (e.g. `post_order.py`, `delete_order.py`).
- Each file defines its own `Router`, schemas, and the single endpoint handler.
- The package `__init__.py` (or app router) composes these routers under the desired path prefix.

**Do not** put multiple endpoints in one file (e.g. a single `orders.py` with both POST and DELETE). The legacy pattern of grouping several routes in one module is not used for industry and new endpoint packages.
