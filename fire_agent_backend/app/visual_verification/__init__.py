"""Candidate-centred visual wildfire verification domain.

This package deliberately has no dependency on the upstream candidate database or
the public API router.  An integration adapter can be added after member A freezes
the hand-off contract.
"""

from app.visual_verification.confirmation_rules import (
    build_confirmed_fire_handoff,
    evaluate_confirmation,
)
from app.visual_verification.states import VisualCaseStatus

__all__ = [
    "VisualCaseStatus",
    "build_confirmed_fire_handoff",
    "evaluate_confirmation",
]
