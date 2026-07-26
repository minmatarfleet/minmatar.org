"""Code-defined pilot feature catalog."""

from dataclasses import dataclass, field

from groups.features.types import FeatureScope


@dataclass(frozen=True)
class FeatureDefinition:
    code: str
    label: str
    scope: str
    description: str = ""
    legacy_permission: str = ""
    staff_permission: str = ""
    default_affiliation_names: tuple[str, ...] = field(default_factory=tuple)
    default_tribe_group_codes: tuple[str, ...] = field(default_factory=tuple)
    default_auth_group_names: tuple[str, ...] = field(default_factory=tuple)
    deny_community_statuses: tuple[str, ...] = ("on_leave",)


def _aff(*names: str) -> tuple[str, ...]:
    return names


def _tribe_codes(*codes: str) -> tuple[str, ...]:
    return codes


_INDUSTRY_TRIBE_CODES = (
    "industry.subcapital-production",
    "industry.capital-production",
    "industry.mining",
    "industry.planetary-interaction",
)


FEATURE_DEFINITIONS: dict[str, FeatureDefinition] = {
    "tribes.apply": FeatureDefinition(
        code="tribes.apply",
        label="Apply to tribe groups",
        scope=FeatureScope.TRIBE_GROUP_TARGET,
        description="Submit applications to join tribe groups.",
        legacy_permission="tribes.add_tribegroupmembership",
        default_affiliation_names=_aff("Alliance", "Associate"),
    ),
    "tribes.manage_memberships": FeatureDefinition(
        code="tribes.manage_memberships",
        label="Manage tribe memberships",
        scope=FeatureScope.TRIBE_CHIEF,
        description="Approve, deny, and manage tribe group memberships.",
        legacy_permission="tribes.change_tribegroupmembership",
    ),
    "fleets.view": FeatureDefinition(
        code="fleets.view",
        label="View fleets",
        scope=FeatureScope.RESOURCE_MATCH,
        description="View fleet catalog and participate in fleet roles.",
        legacy_permission="fleets.view_evefleet",
        default_affiliation_names=_aff("Alliance", "Militia", "Associate"),
    ),
    "fleets.create": FeatureDefinition(
        code="fleets.create",
        label="Create fleets",
        scope=FeatureScope.AFFILIATION,
        description="Create and schedule fleets.",
        legacy_permission="fleets.add_evefleet",
        default_affiliation_names=_aff("Alliance"),
    ),
    "fleets.delete": FeatureDefinition(
        code="fleets.delete",
        label="Delete fleets",
        scope=FeatureScope.STAFF,
        description="Delete fleets created by others.",
        legacy_permission="fleets.delete_evefleet",
        staff_permission="fleets.delete_evefleet",
    ),
    "srp.view": FeatureDefinition(
        code="srp.view",
        label="View SRP",
        scope=FeatureScope.AFFILIATION,
        description="View SRP requests, programs, and stats.",
        legacy_permission="srp.view_evefleetshipreimbursement",
        default_affiliation_names=_aff("Alliance", "Militia"),
    ),
    "srp.submit": FeatureDefinition(
        code="srp.submit",
        label="Submit SRP requests",
        scope=FeatureScope.RESOURCE_MATCH,
        description="Submit killmail reimbursement requests.",
        default_affiliation_names=_aff("Alliance"),
    ),
    "srp.resolve": FeatureDefinition(
        code="srp.resolve",
        label="Resolve SRP killmails",
        scope=FeatureScope.STAFF,
        description="Resolve killmail details for SRP.",
        legacy_permission="srp.add_evefleetshipreimbursement",
        staff_permission="srp.add_evefleetshipreimbursement",
    ),
    "srp.process": FeatureDefinition(
        code="srp.process",
        label="Process SRP requests",
        scope=FeatureScope.STAFF,
        description="Approve, deny, and manage SRP reimbursements.",
        legacy_permission="srp.change_evefleetshipreimbursement",
        staff_permission="srp.change_evefleetshipreimbursement",
    ),
    "structures.view": FeatureDefinition(
        code="structures.view",
        label="View structures",
        scope=FeatureScope.AFFILIATION,
        description="View alliance structures.",
        legacy_permission="structures.view_evestructure",
        default_affiliation_names=_aff("Alliance", "Associate"),
    ),
    "structures.timers.view": FeatureDefinition(
        code="structures.timers.view",
        label="View structure timers",
        scope=FeatureScope.AFFILIATION,
        description="View structure timer schedules.",
        legacy_permission="structures.view_evestructuretimer",
        default_affiliation_names=_aff("Alliance", "Associate"),
    ),
    "structures.timers.manage": FeatureDefinition(
        code="structures.timers.manage",
        label="Manage structure timers",
        scope=FeatureScope.AFFILIATION,
        description="Create and update structure timers.",
        legacy_permission="structures.add_evestructuretimer",
        default_affiliation_names=_aff("Alliance"),
    ),
    "mumble.access": FeatureDefinition(
        code="mumble.access",
        label="Mumble access",
        scope=FeatureScope.AFFILIATION,
        description="Access Mumble voice server credentials.",
        legacy_permission="mumble.view_mumbleaccess",
        default_affiliation_names=_aff("Alliance", "Associate"),
    ),
    "moons.view": FeatureDefinition(
        code="moons.view",
        label="View moons",
        scope=FeatureScope.AFFILIATION,
        description="View moon extraction data.",
        legacy_permission="moons.view_evemoon",
        default_affiliation_names=_aff("Alliance"),
    ),
    "moons.manage": FeatureDefinition(
        code="moons.manage",
        label="Manage moons",
        scope=FeatureScope.STAFF,
        description="Add and manage moon records.",
        legacy_permission="moons.add_evemoon",
        staff_permission="moons.add_evemoon",
    ),
    "posts.create": FeatureDefinition(
        code="posts.create",
        label="Create posts",
        scope=FeatureScope.AFFILIATION,
        description="Create blog posts.",
        legacy_permission="posts.add_evepost",
        default_affiliation_names=_aff("Alliance"),
    ),
    "posts.edit": FeatureDefinition(
        code="posts.edit",
        label="Edit posts",
        scope=FeatureScope.AFFILIATION,
        description="Edit own blog posts.",
        legacy_permission="posts.change_evepost",
        default_affiliation_names=_aff("Alliance"),
    ),
    "posts.delete": FeatureDefinition(
        code="posts.delete",
        label="Delete posts",
        scope=FeatureScope.AFFILIATION,
        description="Delete own blog posts.",
        legacy_permission="posts.delete_evepost",
        default_affiliation_names=_aff("Alliance"),
    ),
    "industry.mining.view": FeatureDefinition(
        code="industry.mining.view",
        label="View mining completions",
        scope=FeatureScope.AFFILIATION,
        description="View mining upgrade completion data.",
        legacy_permission="industry.view_miningupgradecompletion",
        default_affiliation_names=_aff("Alliance"),
    ),
    "industry.mining.submit": FeatureDefinition(
        code="industry.mining.submit",
        label="Submit mining completions",
        scope=FeatureScope.AFFILIATION,
        description="Submit mining upgrade completions.",
        legacy_permission="industry.add_miningupgradecompletion",
        default_affiliation_names=_aff("Alliance"),
    ),
    "industry.order.submit": FeatureDefinition(
        code="industry.order.submit",
        label="Submit industry orders",
        scope=FeatureScope.TRIBE_CHIEF,
        description="Submit industry orders as an industry tribe chief.",
        default_tribe_group_codes=_tribe_codes(*_INDUSTRY_TRIBE_CODES),
    ),
    "applications.manage": FeatureDefinition(
        code="applications.manage",
        label="Manage corp applications",
        scope=FeatureScope.STAFF,
        description="Accept and reject corporation applications.",
        legacy_permission="applications.change_evecorporationapplication",
        staff_permission="applications.change_evecorporationapplication",
    ),
    "applications.view": FeatureDefinition(
        code="applications.view",
        label="View corp applications",
        scope=FeatureScope.STAFF,
        description="View corporation applications.",
        legacy_permission="applications.view_evecorporationapplication",
        staff_permission="applications.view_evecorporationapplication",
    ),
    "characters.view_staff": FeatureDefinition(
        code="characters.view_staff",
        label="View characters (staff)",
        scope=FeatureScope.STAFF,
        description="View other users' characters as staff.",
        legacy_permission="eveonline.view_evecharacter",
        staff_permission="eveonline.view_evecharacter",
    ),
    "characters.delete_staff": FeatureDefinition(
        code="characters.delete_staff",
        label="Delete characters (staff)",
        scope=FeatureScope.STAFF,
        description="Delete other users' characters as staff.",
        legacy_permission="eveonline.delete_evecharacter",
        staff_permission="eveonline.delete_evecharacter",
    ),
    "tech.ops": FeatureDefinition(
        code="tech.ops",
        label="Technology operations",
        scope=FeatureScope.AUTH_GROUP,
        description="Access technology team operations endpoints.",
        default_auth_group_names=_aff("Technology Team"),
        deny_community_statuses=(),
    ),
    "fittings.doctrine.approve": FeatureDefinition(
        code="fittings.doctrine.approve",
        label="Approve doctrine changes",
        scope=FeatureScope.STAFF,
        description="Approve doctrine and fitting change requests.",
    ),
    "fittings.doctrine.propose": FeatureDefinition(
        code="fittings.doctrine.propose",
        label="Propose doctrine changes",
        scope=FeatureScope.STAFF,
        description="Propose doctrine and fitting changes.",
    ),
}
