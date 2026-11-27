from unittest.mock import MagicMock

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from eveonline.models import EveCharacter
from surveys.admin import ExitSurveyInviteAdmin, ExitSurveyResponseAdmin
from surveys.definitions import SURVEY_DEFINITIONS
from surveys.definitions.exit import (
    ALLIANCE_MOVE_SURVEY,
    EXIT_DEFINITION_VERSION,
    EXIT_DEFINITIONS,
    EXIT_SURVEY,
)
from surveys.models import ExitSurveyInvite, ExitSurveyResponse

EXECUTOR_CHARACTER = 2112000900


class ExitDefinitionTest(TestCase):
    def test_exit_definitions_not_in_campaigns(self):
        self.assertEqual(set(EXIT_DEFINITIONS), {"exit", "alliance_move"})
        self.assertNotIn("exit", SURVEY_DEFINITIONS)
        self.assertNotIn("alliance_move", SURVEY_DEFINITIONS)
        self.assertEqual(EXIT_DEFINITION_VERSION, 1)

    def test_ratings_are_required(self):
        for definition in (EXIT_SURVEY, ALLIANCE_MOVE_SURVEY):
            required = [q for q in definition.all_questions() if q.required]
            self.assertEqual(len(required), 4)
            self.assertEqual(
                {q.key for q in required},
                {
                    "exit.enjoyment",
                    "exit.leadership",
                    "exit.activity",
                    "exit.welcome",
                },
            )
            self.assertTrue(all(q.type == "scale5" for q in required))

    def test_question_keys_are_unique(self):
        for definition in (EXIT_SURVEY, ALLIANCE_MOVE_SURVEY):
            keys = [q.key for q in definition.all_questions()]
            self.assertEqual(len(keys), len(set(keys)))

    def test_exit_survey_asks_why_they_left(self):
        keys = {q.key for q in EXIT_SURVEY.all_questions()}
        self.assertIn("exit.why_left", keys)
        move_keys = {q.key for q in ALLIANCE_MOVE_SURVEY.all_questions()}
        self.assertIn("move.why", move_keys)
        self.assertIn("move.onboarding", move_keys)


@override_settings(ALLIANCE_EXECUTOR_CHARACTER_ID=EXECUTOR_CHARACTER)
class ExitSurveyAdminTest(TestCase):
    def setUp(self):
        self.executor = User.objects.create(
            username="executor", is_superuser=True, is_staff=True
        )
        EveCharacter.objects.create(
            character_id=EXECUTOR_CHARACTER,
            character_name="Executor",
            user=self.executor,
        )
        self.other = User.objects.create(
            username="admin", is_superuser=True, is_staff=True
        )

    def test_admin_hidden_from_other_superusers(self):
        for model, admin_class in (
            (ExitSurveyInvite, ExitSurveyInviteAdmin),
            (ExitSurveyResponse, ExitSurveyResponseAdmin),
        ):
            model_admin = admin_class(model, AdminSite())
            self.assertTrue(
                model_admin.has_view_permission(MagicMock(user=self.executor))
            )
            self.assertTrue(
                model_admin.has_module_permission(
                    MagicMock(user=self.executor)
                )
            )
            self.assertFalse(
                model_admin.has_view_permission(MagicMock(user=self.other))
            )
            self.assertFalse(
                model_admin.has_module_permission(MagicMock(user=self.other))
            )
            self.assertFalse(
                model_admin.has_change_permission(
                    MagicMock(user=self.executor)
                )
            )
            self.assertFalse(
                model_admin.has_delete_permission(
                    MagicMock(user=self.executor)
                )
            )
