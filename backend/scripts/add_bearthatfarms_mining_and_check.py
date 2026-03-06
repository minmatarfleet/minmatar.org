#!/usr/bin/env python
"""
Add BearThatFarms to the mining tribe and verify mining activity is created.
Run from backend: pipenv run python manage.py shell < scripts/add_bearthatfarms_mining_and_check.py
"""
from django.utils import timezone
from eveonline.models import EveCharacter, EveCharacterMiningEntry
from eveuniverse.models import EveType
from tribes.models import (
    Tribe,
    TribeGroup,
    TribeGroupActivity,
    TribeGroupActivityRecord,
    TribeGroupMembership,
    TribeGroupMembershipCharacter,
)
from tribes.helpers.activity_processors import process_all_for_tribe_group
from django.contrib.auth import get_user_model

User = get_user_model()

# 1) Find BearThatFarms (character name or username bearthatcares)
character = EveCharacter.objects.filter(character_name__icontains="BearThatFarms").first()
if character:
    user = character.user
    if not user:
        print("Character BearThatFarms has no linked user.")
        raise SystemExit(1)
else:
    user = User.objects.filter(username__icontains="bearthatfarms").first() or User.objects.filter(username__icontains="bearthatcares").first()
    if not user:
        print("User/character BearThatFarms not found. Available users (first 20):")
        for u in User.objects.all()[:20]:
            print(f"  {u.username}")
        raise SystemExit(1)
    characters = EveCharacter.objects.filter(user=user)
    if not characters:
        print("No EveCharacter found for this user.")
        raise SystemExit(1)
    character = characters.first()

print(f"User: {user.username} (pk={user.pk})")
print(f"Character: {character.character_name} (id={character.character_id}, pk={character.pk})")

# 2) Find a tribe that has at least one group (prefer Mining)
tribe = Tribe.objects.filter(slug="mining").first() or Tribe.objects.filter(name__icontains="Mining").first()
if tribe:
    group = tribe.groups.filter(is_active=True).first() or tribe.groups.first()
if not tribe or not group:
    tribe = Tribe.objects.filter(groups__isnull=False).distinct().first()
    if tribe:
        group = tribe.groups.filter(is_active=True).first() or tribe.groups.first()
if not tribe or not group:
    print("No tribe with groups found in DB.")
    raise SystemExit(1)
print(f"Tribe: {tribe.name}, Group: {group.name} (pk={group.pk})")

# 3) Add BearThatFarms to the mining group (membership + character)
membership, created = TribeGroupMembership.objects.get_or_create(
    user=user,
    tribe_group=group,
    defaults={"status": TribeGroupMembership.STATUS_PENDING},
)
if created:
    print(f"Created membership: {membership} (pending)")
else:
    print(f"Existing membership: {membership} (status={membership.status})")

# Approve if pending
if membership.status == TribeGroupMembership.STATUS_PENDING:
    membership.status = TribeGroupMembership.STATUS_ACTIVE
    membership.approved_at = timezone.now()
    membership.save(update_fields=["status", "approved_at"])
    print("Approved membership.")

# Add character to roster if not already
_, char_created = TribeGroupMembershipCharacter.objects.get_or_create(
    membership=membership,
    character=character,
)
if char_created:
    print(f"Added character {character.character_name} to roster.")

# 4) Ensure TribeGroupActivity for mining exists
activity, act_created = TribeGroupActivity.objects.get_or_create(
    tribe_group=group,
    activity_type=TribeGroupActivity.MINING,
    defaults={"is_active": True, "description": "Mining ledger"},
)
if act_created:
    print(f"Created TribeGroupActivity: {activity}")
else:
    print(f"TribeGroupActivity (mining): {activity} (pk={activity.pk})")

# 5) Ensure character has at least one mining entry so we have something to record
#    (If they already have ESI-synced mining data, skip creation.)
mining_entries = EveCharacterMiningEntry.objects.filter(character=character)
if not mining_entries.exists():
    # Create one mining entry so the processor has something to pick up
    # Veldspar type_id is 1230 (common ore)
    veldspar = EveType.objects.filter(id=1230).first()
    if not veldspar:
        # Fallback: any type that exists (e.g. first type)
        veldspar = EveType.objects.first()
    if veldspar:
        entry, entry_created = EveCharacterMiningEntry.objects.get_or_create(
            character=character,
            eve_type=veldspar,
            date=timezone.now().date(),
            solar_system_id=30000142,  # Jita
            defaults={"quantity": 100},
        )
        if entry_created:
            print(f"Created test mining entry: {entry} (100 units)")
        else:
            print(f"Existing mining entry: {entry}")
    else:
        print("No EveType found; cannot create mining entry. Processor may find no data.")
else:
    print(f"Character already has {mining_entries.count()} mining entry/entries.")

# 6) Run the activity processor for this tribe group
new_count = process_all_for_tribe_group(group)
print(f"Processor created {new_count} new TribeGroupActivityRecord(s).")

# 7) Fetch and display tribe activity (mining records for this group)
records = TribeGroupActivityRecord.objects.filter(
    tribe_group_activity__tribe_group=group,
    tribe_group_activity__activity_type=TribeGroupActivity.MINING,
).select_related("character", "user", "tribe_group_activity")
print(f"\nMining activity records for group '{group.name}':")
for r in records:
    print(f"  {r}: character={r.character_id} user={r.user_id} quantity={r.quantity} {r.unit} ref={r.reference_type}:{r.reference_id}")

if not records.exists():
    print("  (none)")
print("\nDone.")
