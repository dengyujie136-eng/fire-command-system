from uuid import uuid4

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.simulated_evidence_fusion import SimulatedEvidenceFusionAdapter
from app.adapters.simulated_satellite_detection import SimulatedSatelliteDetectionAdapter
from app.adapters.simulated_sensor_network import SimulatedSensorNetworkAdapter
from app.models.observation import EvidenceChain, FusionResult, Observation, TrustedFirePoint
from app.services.event_service import append_timeline, get_event_or_404
from app.services.websocket_manager import websocket_manager


def _level_from_confidence(confidence: float) -> str:
    if confidence >= 0.9:
        return "high"
    if confidence >= 0.78:
        return "medium"
    return "low"


async def simulate_observation_workflow(db: AsyncSession, event_id: str) -> dict:
    """Generate the legacy stage-three batch observation set.

    Stage four replaces this with clock-driven generation. Keep this function
    only as a compatibility/debug path so earlier acceptance checks remain
    reproducible.
    """
    event = await get_event_or_404(db, event_id)

    # Keep this endpoint idempotent for the current event by clearing prior stage-3 records.
    for model in (TrustedFirePoint, FusionResult, EvidenceChain, Observation):
        existing = await db.execute(select(model).where(model.event_id == event_id))
        for item in existing.scalars().all():
            await db.delete(item)
    await db.flush()

    simulated_inputs = [
        *SimulatedSatelliteDetectionAdapter().collect(event),
        *SimulatedSensorNetworkAdapter().collect(event),
    ]

    observations: list[Observation] = []
    for item in simulated_inputs:
        obs = Observation(
            observation_id=f"obs_{uuid4().hex}",
            event_id=event_id,
            source_type=item.source_type,
            source_name=item.source_name,
            stage=item.stage,
            longitude=item.longitude,
            latitude=item.latitude,
            confidence=item.confidence,
            observed_at=item.observed_at,
            attributes=item.attributes,
            is_simulated=item.is_simulated,
            data_source_mode=item.data_source_mode,
        )
        db.add(obs)
        observations.append(obs)
    await db.flush()

    fusion = SimulatedEvidenceFusionAdapter().fuse(observations)

    evidence_items: list[EvidenceChain] = []
    for contribution in fusion.contributions:
        evidence = EvidenceChain(
            evidence_id=f"evd_{uuid4().hex}",
            event_id=event_id,
            observation_id=contribution.observation_id,
            source_type=contribution.source_type,
            reliability=contribution.reliability,
            weight=contribution.weight,
            contribution=contribution.contribution,
            explanation=contribution.explanation,
        )
        db.add(evidence)
        evidence_items.append(evidence)
    await db.flush()

    fusion_result = FusionResult(
        fusion_id=f"fus_{uuid4().hex}",
        event_id=event_id,
        confirmed=fusion.confirmed,
        confidence=fusion.confidence,
        longitude=fusion.longitude,
        latitude=fusion.latitude,
        evidence_count=len(evidence_items),
        evidence_sources=sorted({item.source_type for item in observations}),
        decision=fusion.decision,
        quality=fusion.quality,
        is_simulated=True,
        data_source_mode="simulation",
    )
    db.add(fusion_result)
    await db.flush()

    trusted_point = TrustedFirePoint(
        trusted_point_id=f"tfp_{uuid4().hex}",
        event_id=event_id,
        fusion_id=fusion_result.fusion_id,
        longitude=fusion.longitude,
        latitude=fusion.latitude,
        confidence=fusion.confidence,
        level=_level_from_confidence(fusion.confidence),
        description="Trusted fire point generated from satellite, UAV, watchtower, canopy, and ground sensor evidence.",
        is_simulated=True,
        data_source_mode="simulation",
    )
    db.add(trusted_point)

    event.status = "confirmed" if fusion.confirmed else "observing"
    await append_timeline(
        db,
        event_id=event_id,
        event_type="observations.processed",
        status=event.status,
        title="Processed observations generated",
        message="Satellite detection, four-layer sensing, and evidence fusion produced a trusted fire point candidate.",
        payload={
            "observation_count": len(observations),
            "evidence_count": len(evidence_items),
            "fusion_confidence": fusion.confidence,
            "confirmed": fusion.confirmed,
            "is_simulated": True,
            "generation_mode": "legacy_batch",
        },
        broadcast=True,
    )
    await db.commit()

    for item in [*observations, *evidence_items, fusion_result, trusted_point, event]:
        await db.refresh(item)

    await websocket_manager.broadcast_event(
        event_id,
        "observations.processed",
        {
            "observation_count": len(observations),
            "evidence_count": len(evidence_items),
            "fusion_id": fusion_result.fusion_id,
            "trusted_point_id": trusted_point.trusted_point_id,
            "confidence": fusion_result.confidence,
            "confirmed": fusion_result.confirmed,
            "generation_mode": "legacy_batch",
        },
    )

    return {
        "observations": observations,
        "evidence_chain": evidence_items,
        "fusion_result": fusion_result,
        "trusted_fire_point": trusted_point,
    }


async def list_observations(db: AsyncSession, event_id: str) -> list[Observation]:
    await get_event_or_404(db, event_id)
    result = await db.execute(select(Observation).where(Observation.event_id == event_id).order_by(Observation.observed_at, Observation.id))
    return list(result.scalars().all())


async def list_evidence_chain(db: AsyncSession, event_id: str) -> list[EvidenceChain]:
    await get_event_or_404(db, event_id)
    result = await db.execute(select(EvidenceChain).where(EvidenceChain.event_id == event_id).order_by(EvidenceChain.id))
    return list(result.scalars().all())


async def latest_fusion_result(db: AsyncSession, event_id: str) -> FusionResult | None:
    await get_event_or_404(db, event_id)
    result = await db.execute(select(FusionResult).where(FusionResult.event_id == event_id).order_by(desc(FusionResult.created_at), desc(FusionResult.id)).limit(1))
    return result.scalar_one_or_none()


async def latest_trusted_fire_point(db: AsyncSession, event_id: str) -> TrustedFirePoint | None:
    await get_event_or_404(db, event_id)
    result = await db.execute(select(TrustedFirePoint).where(TrustedFirePoint.event_id == event_id).order_by(desc(TrustedFirePoint.created_at), desc(TrustedFirePoint.id)).limit(1))
    return result.scalar_one_or_none()
