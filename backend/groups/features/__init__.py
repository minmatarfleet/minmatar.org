"""Pilot feature catalog and authorization scopes."""

from groups.features.registry import FEATURE_DEFINITIONS, FeatureDefinition
from groups.features.types import FeatureScope

__all__ = [
    "FEATURE_DEFINITIONS",
    "FeatureDefinition",
    "FeatureScope",
]
