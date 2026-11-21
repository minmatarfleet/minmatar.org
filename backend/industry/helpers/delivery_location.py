"""Facts about an order's delivery location for the order pages."""

from industry.helpers.facility_api import facility_key_for_system
from structures import dock_access


def location_costed(location) -> bool:
    """Profit is planned with a facility profile. The staging always counts
    (orders there are costed today); elsewhere the system needs one."""
    if location.staging_active:
        return True
    return facility_key_for_system(location.solar_system_id) is not None


def order_location_fields(location) -> dict:
    return {
        "location_id": location.location_id,
        "location_name": location.location_name,
        "short_name": location.short_name or location.location_name,
        "solar_system_name": location.solar_system_name,
        "staging": location.staging_active,
        "deployment": location.deployment_active,
        "costed": location_costed(location),
        "dock_tickers": dock_access.dock_tickers(location),
    }
