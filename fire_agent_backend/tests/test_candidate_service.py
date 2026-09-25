import json
import unittest
from pathlib import Path

from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.visual_verification.candidate_service import (
    CandidateConflictError,
    create_reverification_version,
    ingest_candidate,
    ingest_candidate_envelope,
    list_candidate_history,
    list_case_assets,
    list_visual_cases,
)
from app.visual_verification.models import (
    CandidateImageryMatchRecord,
    FireConfirmationRecord,
    ImageryAssetCatalogRecord,
    VisualAnalysisRunRecord,
    VisualCaseAssetRecord,
    VisualFindingRecord,
    VisualImageDerivativeRecord,
    VisualVerificationCaseRecord,
)
from app.visual_verification.schemas import HotspotCandidate, HotspotCandidateEnvelope


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "visual_verification"
VISUAL_TABLES = [
    VisualVerificationCaseRecord.__table__,
    ImageryAssetCatalogRecord.__table__,
    CandidateImageryMatchRecord.__table__,
    VisualCaseAssetRecord.__table__,
    VisualImageDerivativeRecord.__table__,
    VisualAnalysisRunRecord.__table__,
    VisualFindingRecord.__table__,
    FireConfirmationRecord.__table__,
]


def load_json(name: str) -> dict:
    with (FIXTURE_DIR / name).open(encoding="utf-8") as stream:
        return json.load(stream)


class CandidateServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")

        @event.listens_for(self.engine.sync_engine, "connect")
        def enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        async with self.engine.begin() as connection:
            await connection.run_sync(
                lambda sync_connection: Base.metadata.create_all(
                    sync_connection, tables=VISUAL_TABLES
                )
            )
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def asyncTearDown(self) -> None:
        await self.engine.dispose()

    async def test_batch_ingest_creates_cases_and_assets(self) -> None:
        envelope = HotspotCandidateEnvelope.model_validate(load_json("candidate_input.json"))
        async with self.sessions() as session:
            result = await ingest_candidate_envelope(session, envelope)
            await session.commit()

            self.assertEqual([item.action.value for item in result.items], ["created"] * 3)
            self.assertEqual([item.asset_count for item in result.items], [2, 1, 1])
            self.assertTrue(all(item.case.status.value == "imagery_ready" for item in result.items))

            case_count = await session.scalar(select(func.count(VisualVerificationCaseRecord.id)))
            asset_count = await session.scalar(select(func.count(VisualCaseAssetRecord.id)))
            self.assertEqual(case_count, 3)
            self.assertEqual(asset_count, 4)

    async def test_identical_replay_is_idempotent(self) -> None:
        envelope = HotspotCandidateEnvelope.model_validate(load_json("candidate_input.json"))
        async with self.sessions() as session:
            await ingest_candidate_envelope(session, envelope)
            second = await ingest_candidate_envelope(session, envelope)
            await session.commit()

            self.assertTrue(all(item.action.value == "duplicate" for item in second.items))
            case_count = await session.scalar(select(func.count(VisualVerificationCaseRecord.id)))
            asset_count = await session.scalar(select(func.count(VisualCaseAssetRecord.id)))
            self.assertEqual(case_count, 3)
            self.assertEqual(asset_count, 4)

    async def test_pending_candidate_can_receive_imagery_as_new_version(self) -> None:
        payload = load_json("member_a_historical_candidate.json")
        pending = HotspotCandidate.model_validate(payload)
        async with self.sessions() as session:
            first = await ingest_candidate(session, pending)
            self.assertEqual(first.case.status.value, "imagery_searching")
            self.assertEqual(first.asset_count, 0)

            payload["imagery_status"] = "available"
            payload["imagery_refs"] = [
                {
                    "asset_id": "dixie-sentinel2-20210715",
                    "uri": "data/raw/sentinel2/dixie_during.tif",
                    "source": "Sentinel-2",
                    "mime_type": "image/tiff",
                    "acquired_at": "2021-07-15T18:20:00Z",
                }
            ]
            available = HotspotCandidate.model_validate(payload)
            second = await ingest_candidate(session, available)
            await session.commit()

            self.assertEqual(second.action.value, "versioned")
            self.assertEqual(second.case.version, 2)
            self.assertEqual(second.case.status.value, "imagery_ready")
            self.assertEqual(second.asset_count, 1)
            latest = await list_visual_cases(session, event_id="dixie_fire_2021")
            versions = await list_visual_cases(
                session, event_id="dixie_fire_2021", include_history=True
            )
            history = await list_candidate_history(
                session,
                event_id="dixie_fire_2021",
                source_candidate_id=pending.candidate_id,
            )
            self.assertEqual([item.version for item in latest], [2])
            self.assertEqual(sorted(item.version for item in versions), [1, 2])
            self.assertEqual([item.version for item in history], [1, 2])

    async def test_reverification_creates_new_case_and_copies_assets(self) -> None:
        envelope = HotspotCandidateEnvelope.model_validate(load_json("candidate_input.json"))
        async with self.sessions() as session:
            ingested = await ingest_candidate_envelope(session, envelope)
            original = await session.scalar(
                select(VisualVerificationCaseRecord).where(
                    VisualVerificationCaseRecord.visual_case_id == ingested.items[0].case.visual_case_id
                )
            )
            self.assertIsNotNone(original)
            original.status = "confirmed"
            await session.flush()

            versioned = await create_reverification_version(session, original)
            await session.commit()

            self.assertEqual(versioned.version, 2)
            self.assertEqual(versioned.status, "imagery_ready")
            self.assertEqual(versioned.upstream_status, "candidate")
            self.assertEqual(
                versioned.product_fields["reverification_parent_case_id"],
                original.visual_case_id,
            )
            original_assets = await list_case_assets(session, original.visual_case_id)
            versioned_assets = await list_case_assets(session, versioned.visual_case_id)
            self.assertEqual(len(versioned_assets), len(original_assets))
            self.assertEqual(
                [item.source_asset_id for item in versioned_assets],
                [item.source_asset_id for item in original_assets],
            )

    async def test_immutable_identity_conflict_is_rejected(self) -> None:
        payload = load_json("member_a_historical_candidate.json")
        original = HotspotCandidate.model_validate(payload)
        async with self.sessions() as session:
            await ingest_candidate(session, original)
            payload["data_owner"]["source_product"] = "OTHER_PRODUCT"
            payload["location"]["longitude"] = -120.5
            conflicting = HotspotCandidate.model_validate(payload)
            with self.assertRaises(CandidateConflictError):
                await ingest_candidate(session, conflicting)

    async def test_list_filters_and_asset_detail(self) -> None:
        envelope = HotspotCandidateEnvelope.model_validate(load_json("candidate_input.json"))
        async with self.sessions() as session:
            result = await ingest_candidate_envelope(session, envelope)
            filtered = await list_visual_cases(
                session,
                event_id="cresta-dam-visual-demo",
                visual_status="imagery_ready",
                upstream_status="candidate",
                imagery_status="available",
            )
            self.assertEqual(len(filtered), 3)
            assets = await list_case_assets(session, result.items[0].case.visual_case_id)
            self.assertEqual([asset.asset_role for asset in assets], ["primary", "context"])
