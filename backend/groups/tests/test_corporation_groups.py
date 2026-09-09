import factory
from django.contrib.auth.models import Group, User
from django.db.models import signals

from app.test import TestCase
from eveonline.models import EveCharacter, EveCorporation
from groups.helpers import (
    RECRUITER_APPLICATION_PERMISSION_CODENAMES,
    ensure_corporation_groups_for_corp,
)
from groups.models import EveCorporationGroup
from groups.tasks import sync_eve_corporation_groups


class CorporationGroupPermissionTestCase(TestCase):
    """Recruiter groups need application perms for associate (non-Alliance) users."""

    def _recruiter_codenames(self, group):
        return set(
            group.permissions.filter(
                content_type__app_label="applications",
                codename__in=RECRUITER_APPLICATION_PERMISSION_CODENAMES,
            ).values_list("codename", flat=True)
        )

    @factory.django.mute_signals(
        signals.pre_save, signals.post_save, signals.m2m_changed
    )
    def test_ensure_grants_application_permissions_to_recruiter_group(self):
        corp = EveCorporation.objects.create(
            corporation_id=98838663,
            name="Minmatar Extraction Company",
            ticker="M-EXC",
            generate_corporation_groups=True,
        )

        groups = ensure_corporation_groups_for_corp(corp)
        by_type = {g.group_type: g for g in groups}

        self.assertEqual(
            set(RECRUITER_APPLICATION_PERMISSION_CODENAMES),
            self._recruiter_codenames(by_type["recruiter"].group),
        )
        self.assertEqual(
            set(), self._recruiter_codenames(by_type["member"].group)
        )
        self.assertEqual(
            set(), self._recruiter_codenames(by_type["director"].group)
        )
        self.assertEqual(
            set(), self._recruiter_codenames(by_type["gunner"].group)
        )

    @factory.django.mute_signals(
        signals.pre_save, signals.post_save, signals.m2m_changed
    )
    def test_sync_heals_recruiter_group_permissions_for_associate_user(self):
        corp = EveCorporation.objects.create(
            corporation_id=98838664,
            name="Associate Recruiter Corp",
            ticker="A-REC",
        )
        recruiter_group = Group.objects.create(name="Corp A-REC Recruiter")
        EveCorporationGroup.objects.create(
            corporation=corp,
            group=recruiter_group,
            group_type=EveCorporationGroup.GROUP_TYPE_RECRUITER,
        )
        user = User.objects.create(username="associate_recruiter")
        char = EveCharacter.objects.create(
            character_id=2117531911,
            character_name="Parv the IV",
            corporation_id=corp.corporation_id,
            user=user,
        )
        corp.recruiters.add(char)

        self.assertFalse(
            user.has_perm("applications.change_evecorporationapplication")
        )

        sync_eve_corporation_groups()
        user = User.objects.get(pk=user.pk)

        self.assertEqual(
            set(RECRUITER_APPLICATION_PERMISSION_CODENAMES),
            self._recruiter_codenames(recruiter_group),
        )
        self.assertTrue(
            user.has_perm("applications.change_evecorporationapplication")
        )
        self.assertTrue(
            user.has_perm("applications.view_evecorporationapplication")
        )
