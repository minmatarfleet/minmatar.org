"""The affiliation database: who really flies for whom.

Groups we keep seeing (``sightings``) are queued for an investigation of
their zKillboard history (``investigate``). Each month of kills and losses
becomes evidence rows: who was on the group's kills, and who shot its
losses. ``score`` turns the evidence into suggested affiliations to a bloc
(a pet leans on a bigger group; a character keeps flying with one), the
intel team confirms or rejects them, and ``resolve`` is the one lookup every
tool uses to put a pilot or group in its bloc.
"""
