from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.integrations.schemas import TrustedIgnition
from app.models.observation import TrustedFirePoint
from app.visual_verification.models import (
    FireConfirmationRecord,
    VisualVerificationCaseRecord,
)


class TrustedIgnitionAdapter:
    """Resolve a current visual confirmation into the spread ignition contract."""

    @staticmethod
    def _level(confidence: float) -> str:
        if confidence >= 0.85:
            return "high"
        if confidence >= 0.65:
            return "medium"
        return "low"

    async def sync_trusted_fire_point(
        self,
        db: AsyncSession,
        ignition: TrustedIgnition,
    ) -> TrustedFirePoint:
        fusion_id = f"visual_confirmation:{ignition.confirmation_id}"
        trusted = await db.scalar(
            select(TrustedFirePoint).where(
                TrustedFirePoint.event_id == ignition.event_id,
                TrustedFirePoint.fusion_id == fusion_id,
            )
        )
        if trusted is None:
            trusted = TrustedFirePoint(
                trusted_point_id=f"tfp_{uuid4().hex}",
                event_id=ignition.event_id,
                fusion_id=fusion_id,
                longitude=ignition.longitude,
                latitude=ignition.latitude,
                confidence=ignition.confidence,
                level=self._level(ignition.confidence),
                description="Human-confirmed visual fire point synchronized from the verification workflow.",
                is_simulated=ignition.is_simulated,
                data_source_mode="visual_confirmation",
            )
            db.add(trusted)
        else:
            trusted.longitude = ignition.longitude
            trusted.latitude = ignition.latitude
            trusted.confidence = ignition.confidence
            trusted.level = self._level(ignition.confidence)
            trusted.is_simulated = ignition.is_simulated
            trusted.data_source_mode = "visual_confirmation"
        await db.flush()
        return trusted

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
        ignition = TrustedIgnition(
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
        await self.sync_trusted_fire_point(db, ignition)
        return ignition
