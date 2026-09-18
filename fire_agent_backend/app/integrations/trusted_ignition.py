from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.integrations.schemas import TrustedIgnition
from app.visual_verification.models import (
    FireConfirmationRecord,
    VisualVerificationCaseRecord,
)


class TrustedIgnitionAdapter:
    """Resolve a current visual confirmation into the spread ignition contract."""

    async def resolve(
        self,
        db: AsyncSession,
        *,
        event_id: str,
        confirmation_id: str | None = None,
        candidate_id: str | None = None,
    ) -> TrustedIgnition:
        statement = (
            select(FireConfirmationRecord, VisualVerificationCaseRecord)
            .join(
                VisualVerificationCaseRecord,
                FireConfirmationRecord.visual_case_id
                == VisualVerificationCaseRecord.visual_case_id,
            )
            .where(
                VisualVerificationCaseRecord.event_id == event_id,
                FireConfirmationRecord.status == "confirmed",
                FireConfirmationRecord.is_current.is_(True),
            )
        )
        if confirmation_id:
            statement = statement.where(
                FireConfirmationRecord.confirmation_id == confirmation_id
            )
        if candidate_id:
            statement = statement.where(
                FireConfirmationRecord.source_candidate_id == candidate_id
            )
        row = (
            await db.execute(
                statement.order_by(FireConfirmationRecord.confirmed_at.desc()).limit(1)
            )
        ).first()
        if row is None:
            raise AppError(
                "A current confirmed visual fire point is required.",
                code="confirmed_fire_point_required",
                status_code=409,
            )
        confirmation, case = row
        if confirmation.longitude is None or confirmation.latitude is None:
            raise AppError(
                "Confirmed fire point has no usable location.",
                code="confirmed_fire_point_location_missing",
                status_code=409,
            )
        return TrustedIgnition(
            event_id=event_id,
            confirmation_id=confirmation.confirmation_id,
            visual_case_id=case.visual_case_id,
            source_candidate_id=confirmation.source_candidate_id,
            longitude=confirmation.longitude,
            latitude=confirmation.latitude,
            observed_at=case.observed_at,
            confirmed_at=confirmation.confirmed_at,
            confidence=confirmation.confidence,
            evidence_ids=list(confirmation.evidence_ids or []),
            confirmation_method=confirmation.confirmation_method,
            is_simulated=confirmation.is_simulated,
        )
