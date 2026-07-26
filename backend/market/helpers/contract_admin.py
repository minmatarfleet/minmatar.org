from django.urls import reverse
from django.utils.html import format_html

from market.models import EveMarketContract


def contract_needs_attention(contract: EveMarketContract) -> bool:
    if contract.match_is_flagged:
        return True
    if contract.match_score is None:
        return False
    return contract.match_score < 1.0


def _match_percent_display(score: float | None) -> str:
    if score is None:
        return "—"
    return f"{round(score * 100)}%"


def build_location_contracts_context(location) -> dict:
    outstanding = EveMarketContract.objects.filter(
        location=location, status="outstanding"
    ).select_related("fitting")

    attention_rows = []
    for contract in outstanding.order_by("match_score", "title"):
        if not contract_needs_attention(contract):
            continue
        edit_url = reverse(
            "admin:market_evemarketcontract_change", args=[contract.pk]
        )
        attention_rows.append(
            {
                "contract": contract,
                "contract_id": contract.pk,
                "title": contract.title,
                "title_link": format_html(
                    '<a href="{}">{}</a>',
                    edit_url,
                    contract.title,
                ),
                "fitting_name": (
                    contract.fitting.name if contract.fitting else "—"
                ),
                "match_score": contract.match_score,
                "match_percent": _match_percent_display(contract.match_score),
                "match_is_flagged": contract.match_is_flagged,
                "is_public": contract.is_public,
                "price": contract.price,
                "issuer_external_id": contract.issuer_external_id,
                "edit_url": edit_url,
            }
        )

    return {
        "attention_rows": attention_rows,
        "attention_count": len(attention_rows),
    }


def count_mismatched_contracts(location) -> int:
    return build_location_contracts_context(location)["attention_count"]
