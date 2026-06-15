"""Report bindings keyed by TribeGroup.code."""

from tribes.reports.queries.capitals import run_capitals_report
from tribes.reports.queries.fleet_commanders import run_fleet_commanders_report
from tribes.reports.queries.freight import run_freight_report
from tribes.reports.queries.industry_orders import run_industry_orders_report
from tribes.reports.queries.manual import run_manual_report
from tribes.reports.queries.mining import run_mining_report
from tribes.reports.queries.pi import run_pi_report
from tribes.reports.types import (
    QuerySpec,
    ReportBinding,
    ReportScope,
    ReportView,
)

QUERY_RUNNERS = {
    "mining_by_user": run_mining_report,
    "pi_by_user": run_pi_report,
    "industry_orders_by_user": run_industry_orders_report,
    "freight_program": run_freight_report,
    "fleet_commanders": run_fleet_commanders_report,
    "capitals_activity": run_capitals_report,
    "manual": run_manual_report,
}

# Prefix → capitals binding template
_CAPITALS_CODES = (
    "capitals.dreads",
    "capitals.carriers",
    "capitals.faxes",
)

_MANUAL_PULSE_CODES = (
    "pulse.technology",
    "pulse.thinkspeak",
    "pulse.readiness",
    "pulse.advocates",
    "pulse.tournaments",
)


def _production_binding(code: str) -> ReportBinding:
    spec = QuerySpec(
        query_key="industry_orders_by_user",
        scope=ReportScope.ROSTER,
    )
    return ReportBinding(
        code=code,
        views={
            ReportView.TOWN_HALL.value: spec,
            ReportView.MEMBER.value: spec,
        },
    )


REPORT_BINDINGS: dict[str, ReportBinding] = {
    "industry.mining": ReportBinding(
        code="industry.mining",
        views={
            ReportView.TOWN_HALL.value: QuerySpec(
                "mining_by_user", ReportScope.ALLIANCE
            ),
            ReportView.MEMBER.value: QuerySpec(
                "mining_by_user", ReportScope.ROSTER
            ),
        },
        presentation={"town_hall": {"top_n": 5, "sort": "volume_m3"}},
    ),
    "industry.planetary-interaction": ReportBinding(
        code="industry.planetary-interaction",
        views={
            ReportView.TOWN_HALL.value: QuerySpec(
                "pi_by_user",
                ReportScope.ROSTER,
                {"pi_tax_rate": 0.01},
            ),
            ReportView.MEMBER.value: QuerySpec(
                "pi_by_user",
                ReportScope.ROSTER,
                {"pi_tax_rate": 0.01},
            ),
        },
    ),
    "industry.subcapital-production": _production_binding(
        "industry.subcapital-production"
    ),
    "industry.capital-production": _production_binding(
        "industry.capital-production"
    ),
    "market.freighters": ReportBinding(
        code="market.freighters",
        views={
            ReportView.TOWN_HALL.value: QuerySpec(
                "freight_program", ReportScope.PROGRAM
            ),
            ReportView.MEMBER.value: QuerySpec(
                "freight_program", ReportScope.PROGRAM
            ),
        },
    ),
    "market.contracts": ReportBinding(
        code="market.contracts",
        manual=True,
        manual_message="Contracts tribe metrics are manual / narrative.",
    ),
    "market.market-orders": ReportBinding(
        code="market.market-orders",
        manual=True,
        manual_message="Market orders tribe metrics are manual / narrative.",
    ),
    "market.loyalty-points": ReportBinding(
        code="market.loyalty-points",
        manual=True,
        manual_message="Loyalty points tribe metrics are manual / narrative.",
    ),
    "pulse.fleet-commanders": ReportBinding(
        code="pulse.fleet-commanders",
        views={
            ReportView.TOWN_HALL.value: QuerySpec(
                "fleet_commanders", ReportScope.ALLIANCE
            ),
            ReportView.MEMBER.value: QuerySpec(
                "fleet_commanders", ReportScope.ROSTER
            ),
        },
        presentation={"town_hall": {"top_n": 5, "sort": "fleet_count"}},
    ),
}

for _code in _CAPITALS_CODES:
    REPORT_BINDINGS[_code] = ReportBinding(
        code=_code,
        views={
            ReportView.TOWN_HALL.value: QuerySpec(
                "capitals_activity", ReportScope.ALLIANCE
            ),
            ReportView.MEMBER.value: QuerySpec(
                "capitals_activity", ReportScope.ROSTER
            ),
        },
    )

for _code in _MANUAL_PULSE_CODES:
    REPORT_BINDINGS[_code] = ReportBinding(
        code=_code,
        manual=True,
        manual_message=f"{_code} uses manual town hall content.",
    )


def get_binding(code: str) -> ReportBinding | None:
    return REPORT_BINDINGS.get(code)


def binding_for_group(tribe_group) -> ReportBinding | None:
    return get_binding(tribe_group.code)
