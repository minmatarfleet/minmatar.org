"""Moved to ``eveonline.esi_budget``; this name stays as an alias.

The ESI budget is app-wide, so it lives next to the ESI client. Aliasing
the module (rather than re-exporting names) keeps ``patch()`` targets on
either path pointing at the same objects.
"""

import sys

from eveonline import esi_budget

sys.modules[__name__] = esi_budget
