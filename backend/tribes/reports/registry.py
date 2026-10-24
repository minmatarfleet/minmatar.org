"""Report bindings keyed by TribeGroup.code."""

from tribes.reports.queries.advocates import (
    advocates_highlights,
    run_advocates_report,
)
from tribes.reports.queries.blops import blops_highlights, run_blops_report
from tribes.reports.queries.capitals import run_capitals_report
from tribes.reports.queries.fleet_commanders import run_fleet_commanders_report
from tribes.reports.queries.freight import run_freight_report
from tribes.reports.queries.help_desk import (
    help_desk_highlights,
    run_help_desk_report,
)
from tribes.reports.queries.industry_orders import run_industry_orders_report
from tribes.reports.queries.lp_buyback import (
    lp_buyback_highlights,
    run_lp_buyback_report,
)
from tribes.reports.queries.manual import run_manual_report
from tribes.reports.queries.market_sales import (
    market_sales_highlights,
    run_market_sales_report,
)
from tribes.reports.queries.mining import run_mining_report
from tribes.reports.queries.pi import run_pi_report
from tribes.reports.queries.publishing import (
    publishing_highlights,
    run_publishing_report,
)
from tribes.reports.queries.readiness import run_readiness_report
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
    "market_sales": run_market_sales_report,
    "lp_buyback": run_lp_buyback_report,
    "advocates": run_advocates_report,
    "readiness": run_readiness_report,
    "help_desk": run_help_desk_report,
    "publishing": run_publishing_report,
    "blops": run_blops_report,
    "manual": run_manual_report,
}

# Group-page extras (records, all-time totals, showcase lists) by binding.
HIGHLIGHT_RUNNERS = {
    "market_sales": market_sales_highlights,
    "lp_buyback": lp_buyback_highlights,
    "advocates": advocates_highlights,
    "help_desk": help_desk_highlights,
    "publishing": publishing_highlights,
    "blops": blops_highlights,
}

# Prefix → capitals binding template
_CAPITALS_CODES = (
    "capitals.dreads",
    "capitals.carriers",
    "capitals.faxes",
)

# Nothing stored to measure yet; the group page shows these as coming soon.
_MANUAL_PULSE_CODES = ("pulse.tournaments",)


def _activity_binding(
    code: str,
    query_key: str,
    scope: ReportScope,
    contributor_metric: str,
    *,
    params: dict | None = None,
    showcase_period: str | None = None,
    highlights: bool = True,
) -> ReportBinding:
    """One query for both views; contributors ranked by one metric."""
    spec = QuerySpec(query_key, scope, params or {})
    showcase = {"metric": contributor_metric}
    if showcase_period:
        showcase["period"] = showcase_period
    return ReportBinding(
        code=code,
        views={
            ReportView.TOWN_HALL.value: spec,
            ReportView.MEMBER.value: spec,
        },
        presentation={
            "town_hall": {"top_n": 5, "sort": contributor_metric},
            "showcase": showcase,
        },
        highlights=query_key if highlights else "",
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
        presentation={
            "town_hall": {"top_n": 5, "sort": "delivered_profit"},
        },
    )


REPORT_BINDINGS: dict[str, ReportBinding] = {
    "supply.mining": ReportBinding(
        code="supply.mining",
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
    "supply.planetary-interaction": ReportBinding(
        code="supply.planetary-interaction",
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
        presentation={
            "town_hall": {"top_n": 5, "sort": "isk_pi_30d_estimate"},
        },
    ),
    "supply.subcapital-production": _production_binding(
        "supply.subcapital-production"
    ),
    "supply.capital-production": _production_binding(
        "supply.capital-production"
    ),
    "supply.freighters": ReportBinding(
        code="supply.freighters",
        views={
            ReportView.TOWN_HALL.value: QuerySpec(
                "freight_program", ReportScope.PROGRAM
            ),
            ReportView.MEMBER.value: QuerySpec(
                "freight_program", ReportScope.PROGRAM
            ),
        },
    ),
    "supply.market": _activity_binding(
        "supply.market", "market_sales", ReportScope.ROSTER, "fits_sold"
    ),
    "supply.loyalty-points": _activity_binding(
        "supply.loyalty-points", "lp_buyback", ReportScope.PROGRAM, "lp"
    ),
    "pulse.advocates": _activity_binding(
        "pulse.advocates",
        "advocates",
        ReportScope.PROGRAM,
        "applications_accepted",
    ),
    "pulse.readiness": _activity_binding(
        "pulse.readiness",
        "readiness",
        ReportScope.PROGRAM,
        "doctrine_changes",
        highlights=False,
    ),
    "pulse.technology": _activity_binding(
        "pulse.technology",
        "help_desk",
        ReportScope.PROGRAM,
        "tickets_resolved",
        params={"desktop_app": True},
    ),
    "pulse.thinkspeak": _activity_binding(
        "pulse.thinkspeak",
        "publishing",
        ReportScope.ROSTER,
        "pieces",
        showcase_period="90d",
    ),
    "pulse.fishermen": _activity_binding(
        "pulse.fishermen", "blops", ReportScope.ROSTER, "kill_count"
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
        presentation={
            "town_hall": {"top_n": 5, "sort": "kill_count"},
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
