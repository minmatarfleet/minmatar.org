"""Recent killmail involvement without touching killmail rows.

Killmail rows carry the full attacker and item JSON (several KB each), so
joining attackers to killmails to filter by time forces a random read of
every big row and took about a minute on production. The killmail_time
index already holds (killmail_time, id), so recent killmails come from an
index-only scan and attackers are matched against those ids instead.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from eveonline.models import EveCharacterKillmail, EveCharacterKillmailAttacker

ACTIVITY_DAYS = 90
_CHUNK = 5000


class RecentKills:
    """Killmails from the last `days` that any of `character_ids` was on.

    Load once for every character you will ask about (e.g. all allied
    corps in a refresh run), then slice per corporation.
    """

    def __init__(self, character_ids, days: int = ACTIVITY_DAYS):
        cutoff = timezone.now() - timedelta(days=days)
        self.times = dict(
            EveCharacterKillmail.objects.filter(
                killmail_time__gte=cutoff
            ).values_list("id", "killmail_time")
        )
        self._by_character: dict[int, set[int]] = defaultdict(set)
        self._attackers: dict[int, int] | None = None
        ids = list({int(cid) for cid in character_ids if cid})
        if not self.times or not ids:
            return
        for chunk in _chunks(list(self.times), _CHUNK):
            rows = EveCharacterKillmailAttacker.objects.filter(
                killmail_id__in=chunk, character_id__in=ids
            ).values_list("killmail_id", "character_id")
            for killmail_id, character_id in rows:
                self._by_character[character_id].add(killmail_id)

    def killmails_for(self, character_ids) -> set[int]:
        killmails: set[int] = set()
        for character_id in character_ids:
            killmails |= self._by_character.get(character_id, set())
        return killmails

    def kills_by_character(self, character_ids) -> dict[int, int]:
        return {
            character_id: len(self._by_character.get(character_id, ()))
            for character_id in character_ids
        }

    def attacker_counts(self, killmail_ids) -> dict[int, int]:
        """Total attackers on each killmail (every pilot, not just ours)."""
        if self._attackers is None:
            self._attackers = {}
            every = set().union(set(), *self._by_character.values())
            for chunk in _chunks(list(every), _CHUNK):
                rows = (
                    EveCharacterKillmailAttacker.objects.filter(
                        killmail_id__in=chunk
                    )
                    .values("killmail_id")
                    .annotate(attackers=Count("killmail_id"))
                    .values_list("killmail_id", "attackers")
                )
                self._attackers.update(rows)
        return {
            killmail_id: self._attackers.get(killmail_id, 0)
            for killmail_id in killmail_ids
        }


def _chunks(items: list, size: int):
    for start in range(0, len(items), size):
        yield items[start : start + size]
