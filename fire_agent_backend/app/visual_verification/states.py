from enum import Enum


class VisualCaseStatus(str, Enum):
    RECEIVED = "received"
    IMAGERY_SEARCHING = "imagery_searching"
    IMAGERY_READY = "imagery_ready"
    ANALYZING = "analyzing"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    UNCERTAIN = "uncertain"
    FAILED = "failed"


class AnalysisRunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    TIMEOUT = "timeout"
    INVALID_OUTPUT = "invalid_output"
    PROVIDER_ERROR = "provider_error"
    CANCELLED = "cancelled"


ALLOWED_VISUAL_CASE_TRANSITIONS: dict[VisualCaseStatus, frozenset[VisualCaseStatus]] = {
    VisualCaseStatus.RECEIVED: frozenset(
        {VisualCaseStatus.IMAGERY_SEARCHING, VisualCaseStatus.FAILED}
    ),
    VisualCaseStatus.IMAGERY_SEARCHING: frozenset(
        {VisualCaseStatus.IMAGERY_READY, VisualCaseStatus.FAILED}
    ),
    VisualCaseStatus.IMAGERY_READY: frozenset(
        {VisualCaseStatus.ANALYZING, VisualCaseStatus.FAILED}
    ),
    VisualCaseStatus.ANALYZING: frozenset(
        {
            VisualCaseStatus.CONFIRMED,
            VisualCaseStatus.REJECTED,
            VisualCaseStatus.UNCERTAIN,
            VisualCaseStatus.FAILED,
        }
    ),
    VisualCaseStatus.UNCERTAIN: frozenset(
        {VisualCaseStatus.IMAGERY_SEARCHING, VisualCaseStatus.ANALYZING}
    ),
    VisualCaseStatus.FAILED: frozenset(
        {VisualCaseStatus.IMAGERY_SEARCHING, VisualCaseStatus.ANALYZING}
    ),
    # Confirmed and rejected records are immutable. Re-review creates a new version.
    VisualCaseStatus.CONFIRMED: frozenset(),
    VisualCaseStatus.REJECTED: frozenset(),
}


class InvalidVisualCaseTransition(ValueError):
    pass


def ensure_visual_case_transition(
    current: VisualCaseStatus,
    target: VisualCaseStatus,
) -> None:
    if target not in ALLOWED_VISUAL_CASE_TRANSITIONS[current]:
        raise InvalidVisualCaseTransition(
            f"Visual verification case cannot transition from {current.value!r} "
            f"to {target.value!r}."
        )
