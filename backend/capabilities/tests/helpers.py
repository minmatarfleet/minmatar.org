import gzip
import json
from functools import lru_cache
from pathlib import Path

from capabilities.engine import sde as sde_mod

FIXTURES = Path(__file__).parent / "fixtures"


@lru_cache(maxsize=1)
def fixture_snapshot() -> dict:
    """A real SDE subset (build 3646012): every skill plus the fixture fits."""
    with gzip.open(
        FIXTURES / "sde_subset.json.gz", "rt", encoding="utf8"
    ) as fh:
        return sde_mod.int_keys(json.load(fh))


def fixture_sde() -> sde_mod.SdeData:
    return sde_mod.SdeData(fixture_snapshot())


def fixture_eft(name: str) -> str:
    return (FIXTURES / f"{name}.eft").read_text()


def all_skills_at(sde: sde_mod.SdeData, level: int) -> dict[int, int]:
    return {
        t: level
        for t, (_, g) in sde.types.items()
        if sde.groups[g][1] == sde_mod.CAT_SKILL
    }


def store_fixture_snapshot():
    # pylint: disable=import-outside-toplevel
    from capabilities import services

    return services.store_snapshot(fixture_snapshot())
