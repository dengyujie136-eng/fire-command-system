"""Adapters connecting specialist wildfire modules to the command agents."""

from app.integrations.spatial_risk import SpatialRiskAdapter
from app.integrations.spread import SpreadAdapter
from app.integrations.trusted_ignition import TrustedIgnitionAdapter

__all__ = ["SpatialRiskAdapter", "SpreadAdapter", "TrustedIgnitionAdapter"]
