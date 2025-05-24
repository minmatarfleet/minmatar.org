from django.db import connection
from django.contrib.auth.models import User

from eveonline.models import EvePlayer, EveCharacter


def sql_update(sql: str):
    with connection.cursor() as cursor:
        cursor.execute(sql)


def drop_view_if_exists(name: str):
    sql_update(f"DROP VIEW IF EXISTS {name}")


def create_view(name: str, definition: str):
    drop_view_if_exists(name)
    sql_update(f"CREATE VIEW {name} AS {definition}")


def create_primary_character_view():
    # pylint: disable=W0212
    character_table = EveCharacter._meta.db_table
    player_table = EvePlayer._meta.db_table
    user_table = User._meta.db_table
    create_view(
        "primary_character",
        (
            "SELECT "
            "u.id, u.username, "
            "ep.id player_id, ep.nickname, "
            "ec.character_id, ec.character_name, "
            "ec.corporation_id, ec.alliance_id "
            "  FROM " + character_table + " ec "
            "LEFT OUTER JOIN " + player_table + " ep "
            "  ON ep.primary_character_id = ec.id "
            "LEFT OUTER JOIN " + user_table + " u "
            "  ON u.id = ec.user_id "
            "WHERE "
            "  ep.primary_character_id IS NOT NULL"
        ),
    )


def create_all_views():
    create_primary_character_view()


def select_all(view_name: str):
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT * FROM {view_name}")
        return cursor.fetchall()
