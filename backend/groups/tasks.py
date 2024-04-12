import logging

from django.contrib.auth.models import User
from esi.clients import EsiClientProvider

from app.celery import app
from eveonline.models import EvePrimaryCharacter

from .models import AffiliationType, UserAffiliation

logger = logging.getLogger(__name__)
esi = EsiClientProvider()


@app.task
def update_affiliations():
    for user in User.objects.all():
        logger.info("Checking affiliations for user %s", user)
        if not EvePrimaryCharacter.objects.filter(
            character__token__user=user
        ).exists():
            logger.info("No primary character found for user %s", user)
            continue
        primary_character = EvePrimaryCharacter.objects.get(
            character__token__user=user
        )

        # loop through affiliations in priority to find highest qualifying
        for affiliation in AffiliationType.objects.order_by("priority"):
            logger.info(
                "Checking if qualified for affiliation %s", affiliation
            )
            is_qualifying = False
            if (
                primary_character.character.corporation
                in affiliation.corporations.all()
            ):
                logger.info(
                    "User %s is in corporation %s",
                    user,
                    primary_character.character.corporation,
                )

                is_qualifying = True

            if (
                primary_character.character.alliance
                in affiliation.alliances.all()
            ):
                logger.info(
                    "User %s is in alliance %s",
                    user,
                    primary_character.character.alliance,
                )
                is_qualifying = True

            if (
                primary_character.character.faction
                in affiliation.factions.all()
            ):
                logger.info(
                    "User %s is in faction %s",
                    user,
                    primary_character.character.faction,
                )
                is_qualifying = True

            if is_qualifying:
                logger.info(
                    "User %s qualifies for affiliation %s",
                    user,
                    affiliation,
                )
                if UserAffiliation.objects.filter(
                    user=user, affiliation=affiliation
                ).exists():
                    logger.info(
                        "User %s already has affiliation %s",
                        user,
                        affiliation,
                    )
                    continue

                if UserAffiliation.objects.filter(user=user).exists():
                    logger.info(
                        "User %s already has an affiliation, removing",
                        user,
                    )
                    UserAffiliation.objects.filter(user=user).delete()

                logger.info(
                    "Creating affiliation for user %s with %s",
                    user,
                    affiliation,
                )
                UserAffiliation.objects.create(
                    user=user, affiliation=affiliation
                )
            else:
                logger.info(
                    "User %s does not qualify for affiliation %s",
                    user,
                    affiliation,
                )
                if UserAffiliation.objects.filter(
                    user=user, affiliation=affiliation
                ).exists():
                    logger.info(
                        "User %s has affiliation %s, removing",
                        user,
                        affiliation,
                    )
                    UserAffiliation.objects.filter(
                        user=user, affiliation=affiliation
                    ).delete()
                else:
                    logger.info(
                        "User %s does not have affiliation %s",
                        user,
                        affiliation,
                    )
                    continue
