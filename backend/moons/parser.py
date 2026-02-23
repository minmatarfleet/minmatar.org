import logging
import re
from typing import List

from pydantic import BaseModel

from bravado.exception import HTTPError

from eveonline.client import EsiClient

from moons.models import EveMoon, EveMoonDistribution

logger = logging.getLogger(__name__)


class ParsedEveMoonQuantity(BaseModel):
    ore: str
    quantity: float
    type_id: int
    system_id: int
    planet_id: int
    moon_id: int


class MoonParsingResult(BaseModel):
    systems_added: int = 0
    systems_ignored: int = 0
    moons_added: int = 0
    moons_ignored: int = 0
    ids_added: List[int] = []
    errors: List[str] = []


def _parse_eve_moon_format(moon_paste: str) -> List[ParsedEveMoonQuantity]:
    """
    Example moon format
    Moon	Moon Product	Quantity	Ore TypeID	SolarSystemID	PlanetID	MoonID
    Rahadalon V - Moon 2
        Bitumens	0.5413627028	45492	30002982	40189228	40189231
        Sylvite	0.2586372793	45491	30002982	40189228	40189231
    Rahadalon VI - Moon 1
        Bitumens	0.2821700573	45492	30002982	40189232	40189233
        Cobaltite	0.08585818857	45494	30002982	40189232	40189233
        Sylvite	0.2980297208	45491	30002982	40189232	40189233
        Vanadinite	0.3339420557	45500	30002982	40189232	40189233

    Parse this format into a dictionary, skipping the system lines and being whitespace agnostic
    """
    moons = []
    for line in moon_paste.split("\n"):
        line = line.strip()
        if not line:
            logger.debug("Skipping empty line")
            continue
        if "Moon" in line:
            logger.debug("Skipping header line")
            continue
        parts = re.split(r"\s+", line)
        if len(parts) == 1:
            logger.debug("Skipping system line")
            continue

        logger.debug(f"Processing line: {parts}")
        moon = ParsedEveMoonQuantity(
            ore=parts[0],
            quantity=float(parts[1]),
            type_id=int(parts[2]),
            system_id=int(parts[3]),
            planet_id=int(parts[4]),
            moon_id=int(parts[5]),
        )
        moons.append(moon)

    logger.info(f"Processed moon lines: {moons}")
    return moons


def process_moon_paste(
    moon_paste: str, user_id: int = None
) -> MoonParsingResult:
    parsed_moons = _parse_eve_moon_format(moon_paste)

    result = MoonParsingResult()

    ignored_moons = {}

    esi = EsiClient(None)

    for parsed_moon in parsed_moons:
        try:
            system = esi.get_solar_system(parsed_moon.system_id)

            # Name comes back as Rahadalon VI
            planet = esi.get_planet(parsed_moon.planet_id)
            planet_number = planet.name.split(" ")[-1]

            # Name comes back as Rahadalon VI - Moon 1
            moon = esi.get_moon(parsed_moon.moon_id)

            moon_number = int(moon.name.split(" ")[-1])
            eve_moon, created = EveMoon.objects.get_or_create(
                system=system.name,
                planet=planet_number,
                moon=moon_number,
                defaults={"reported_by_id": user_id},
            )

            if created:
                result.moons_added += 1
            else:
                ignored_moons[moon.name] = True

            if not EveMoonDistribution.objects.filter(
                moon=eve_moon, ore=parsed_moon.ore
            ).exists():
                EveMoonDistribution.objects.create(
                    moon=eve_moon,
                    ore=parsed_moon.ore,
                    yield_percent=parsed_moon.quantity,
                )

            result.ids_added.append(eve_moon.id)
        except HTTPError as e:
            msg = (
                f"Moon ID {parsed_moon.moon_id} not found in ESI "
                f"(status={e.status_code}). "
                "If pasted from a scan, check for a missing digit in MoonID "
                "(e.g. 40148004 not 4014800)."
            )
            logger.warning(msg, exc_info=True)
            result.errors.append(msg)
        except Exception as e:
            msg = f"Moon ID {parsed_moon.moon_id}: " f"{type(e).__name__}: {e}"
            logger.exception(msg)
            result.errors.append(msg)

    result.moons_ignored = len(ignored_moons)

    return result
