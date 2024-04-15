import logging
import os
import shutil

from django.db.models import Q
from esi.clients import EsiClientProvider
from git import Repo

from app.celery import app

from .models import EveFitting

logger = logging.getLogger(__name__)

esi = EsiClientProvider()

valid_file_prefixes = [
    "[FL33T]",
    "[NVY-1]",
    "[NVY-5]",
    "[NVY-30]",
    "[ADV-5]",
    "[ADV-30]",
    "[POCHVEN]",
]


@app.task()
def update_fittings():  # noqa
    PATH = "./exports/fittings"  # pylint: disable=invalid-name
    shutil.rmtree(PATH, ignore_errors=True)
    repo = Repo.clone_from(
        "https://github.com/Minmatar-Fleet-Alliance/FL33T-Fits", PATH
    )
    files = [
        os.path.join(dp, f)
        for dp, dn, filenames in os.walk(PATH)
        for f in filenames
        if os.path.splitext(f)[1] == ".md"
    ]

    current_version = repo.head.object.hexsha

    # resolve names to save ESI calls
    names = set()
    for file in files:
        # skip files that contain no valid prefixes
        if not any(prefix in file for prefix in valid_file_prefixes):
            continue

        if "Archived" in file:
            continue

        # open and read file
        with open(  # noqa # pylint: disable=unspecified-encoding
            file, "r"
        ) as f:
            data = f.readlines()
            line = data.pop(0)
            if line.startswith("#"):
                names.add(line.replace("#", "").strip())

    # parse files for fittings
    names = set()
    for file in files:
        # skip files that contain no valid prefixes
        if not any(prefix in file for prefix in valid_file_prefixes):
            continue

        if "Archived" in file:
            continue
        # get file name and strip md extension
        fitting_name = os.path.basename(file).replace(".md", "")

        # open and read file
        name = None
        description = None
        fitting = None

        with open(file, "r") as f:  # pylint: disable=unspecified-encoding
            data = f.readlines()

            try:
                while name is None:
                    line = data.pop(0)
                    if line.startswith("#"):
                        name = line.replace("#", "").strip()
                    while not line.startswith("## Description"):
                        line = data.pop(0)

                while description is None:
                    if line.startswith("## Description"):
                        description = ""
                        line = data.pop(0)
                        while not line.startswith("## Fit"):
                            description += line
                            line = data.pop(0)

                while fitting is None:
                    if line.startswith("## Fit"):
                        while (
                            line.startswith("```")
                            or line.startswith("##")
                            or line.startswith("\n")
                        ):
                            line = data.pop(0)
                        fitting = ""
                        while not line.startswith("```"):
                            fitting += line
                            line = data.pop(0)
            except Exception as e:
                print(e)
                pass

        if name and description and fitting:
            ship_name = fitting.split("\n")[0].split(",")[0].replace("[", "")
            # resolve from ESI
            ship_id = None
            try:
                response = esi.client.Universe.post_universe_ids(
                    names=[ship_name]
                ).results()
                ship_id = response["inventory_types"][0]["id"]
            except Exception as e:
                logger.error(
                    "Failed to resolve ship %s for fitting %s: %s",
                    ship_name,
                    fitting_name,
                    e,
                )
                continue
            if not ship_id:
                logger.error(
                    "Failed to resolve ship %s for fitting %s",
                    ship_name,
                    fitting_name,
                )
                continue
            names.add(fitting_name)
            if EveFitting.objects.filter(name=fitting_name).exists():
                current_fitting = EveFitting.objects.get(name=fitting_name)
                if current_version != current_fitting.latest_version:
                    logger.info(
                        "fitting out of date. updating fitting: %s",
                        fitting_name,
                    )
                    current_fitting.eft_format = fitting
                    current_fitting.latest_version = current_version
                else:
                    logger.info(
                        "fitting up to date. skipping fitting: %s",
                        fitting_name,
                    )
            else:
                logger.info("new fitting. creating fitting: %s", fitting_name)
                print(f"creating fitting: {fitting_name}")
                fitting = EveFitting.objects.create(
                    name=fitting_name,
                    ship_id=ship_id,
                    description=description,
                    eft_format=fitting,
                    latest_version=current_version,
                )
        else:
            logger.error("failed to parse fitting: %s", fitting_name)

    names = list(names)
    EveFitting.objects.filter(~Q(name__in=names)).delete()
