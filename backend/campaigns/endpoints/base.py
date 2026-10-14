"""The single Router every campaigns endpoint module registers on.

Ninja resolves a URL to one view, so two routers cannot both claim the same
path with different verbs. Sharing one router keeps GET "" and POST "" on the
same operation.
"""

from ninja import Router

router = Router(tags=["Campaigns"])
