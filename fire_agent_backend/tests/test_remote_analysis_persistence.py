import unittest
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.visual_verification.models import (
    RemoteSensingAnalysisRecord,
    VisualCaseAssetRecord,
    VisualVerificationCaseRecord,
)
from app.visual_verification.remote_analysis_service import (
    complete_remote_analysis,
    fail_remote_analysis,
    get_remote_analysis,
    list_remote_analyses,
    start_remote_analysis,
)
from app.visual_verification.schemas import (
    RemoteSensingAnalysisRequest,
    RemoteSensingAnalysisType,
    RemoteSensingChangeResult,
)
from app.visual_verification.router import run_remote_sensing_analysis


class RemoteAnalysisPersistenceTests(unittest.IsolatedAsyncioTestCase):
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
                    sync_connection,
                    tables=[
                        VisualVerificationCaseRecord.__table__,
                        VisualCaseAssetRecord.__table__,
                        RemoteSensingAnalysisRecord.__table__,
                    ],
                )
            )
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def asyncTearDown(self) -> None:
        await self.engine.dispose()

    @staticmethod
    def case() -> VisualVerificationCaseRecord:
        return VisualVerificationCaseRecord(
            visual_case_id="case-history-001",
            source_candidate_id="candidate-history-001",
            upstream_schema_version="fire.hotspot.candidate.v0.1",
            upstream_status="candidate",
            event_id="event-history",
            event_name="History Test Fire",
            observed_at=datetime(2021, 7, 14, 9, 11, tzinfo=UTC),
            longitude=-121.4,
            latitude=39.8,
            imagery_status="available",
            data_owner={"organization": "test"},
            replay_metadata={"is_replay": True},
            product_fields={},
            upstream_payload_hash="1" * 64,
            status="imagery_ready",
            version=1,
            is_simulated=True,
        )

    @staticmethod
    def request() -> RemoteSensingAnalysisRequest:
        return RemoteSensingAnalysisRequest(
            event_id="event-history",
            analysis_type="burned_area",
            time_range={
                "start_at": "2021-07-01T00:00:00Z",
                "end_at": "2021-10-01T00:00:00Z",
            },
            target_geometry={
                "type": "Polygon",
                "coordinates": [[
                    [-121.5, 39.7],
                    [-121.3, 39.7],
                    [-121.3, 39.9],
                    [-121.5, 39.9],
                    [-121.5, 39.7],
                ]],
            },
            asset_ids=["before-asset", "after-asset"],
            visual_case_id="case-history-001",
        )

    @staticmethod
    def result(analysis_id: str) -> RemoteSensingChangeResult:
        return RemoteSensingChangeResult(
            analysis_id=analysis_id,
            event_id="event-history",
            analysis_type=RemoteSensingAnalysisType.BURNED_AREA,
            before_asset_id="before-asset",
            after_asset_id="after-asset",
            method="dndvi_threshold_v1",
            threshold=0.2,
            minimum_region_pixels=9,
            changed_pixel_count=25,
            valid_pixel_count=100,
            area_hectares=0.25,
            area_geometry_wgs84={"type": "MultiPolygon", "coordinates": []},
            source_crs="EPSG:32610",
            resolution_m=(10, 10),
            output_uris={"area_geojson": "visual-output://area.geojson"},
            warnings=["B12 unavailable in persistence fixture"],
            is_simulated=True,
        )

    async def test_successful_run_can_be_read_and_filtered(self) -> None:
        async with self.sessions() as session:
            session.add(self.case())
            await session.flush()
            record = await start_remote_analysis(
                session,
                payload=self.request(),
                is_simulated=True,
            )
            await complete_remote_analysis(session, record, self.result(record.analysis_id))
            await session.commit()

            loaded = await get_remote_analysis(session, record.analysis_id)
            filtered = await list_remote_analyses(
                session,
                event_id="event-history",
                analysis_type=RemoteSensingAnalysisType.BURNED_AREA,
                run_status="succeeded",
            )

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.run_status, "succeeded")
        self.assertEqual(loaded.result_payload["area_hectares"], 0.25)
        self.assertEqual(loaded.source_asset_ids, ["before-asset", "after-asset"])
        self.assertEqual([item.analysis_id for item in filtered], [record.analysis_id])

    async def test_failed_run_keeps_error_and_request(self) -> None:
        async with self.sessions() as session:
            session.add(self.case())
            await session.flush()
            record = await start_remote_analysis(
                session,
                payload=self.request(),
                is_simulated=True,
            )
            await fail_remote_analysis(
                session,
                record,
                error_code="invalid_raster_band",
                error_message="B8 is missing",
            )
            await session.commit()

            loaded = await get_remote_analysis(session, record.analysis_id)

        self.assertEqual(loaded.run_status, "failed")
        self.assertEqual(loaded.error_code, "invalid_raster_band")
        self.assertEqual(loaded.error_message, "B8 is missing")
        self.assertEqual(loaded.request_payload["analysis_type"], "burned_area")
        self.assertIsNotNone(loaded.finished_at)
        self.assertGreaterEqual(loaded.duration_ms, 0)

    async def test_mismatched_result_is_not_persisted(self) -> None:
        async with self.sessions() as session:
            session.add(self.case())
            await session.flush()
            record = await start_remote_analysis(
                session,
                payload=self.request(),
                is_simulated=True,
            )
            result = self.result("another-analysis-id")

            with self.assertRaisesRegex(ValueError, "result ID"):
                await complete_remote_analysis(session, record, result)

    async def test_unified_route_persists_successful_change_result(self) -> None:
        request = self.request()

        def result_from_call(_function, **kwargs):
            return self.result(kwargs["analysis_id"])

        async with self.sessions() as session:
            case = self.case()
            session.add(case)
            await session.flush()
            session.add_all([
                VisualCaseAssetRecord(
                    visual_case_id=case.visual_case_id,
                    source_asset_id=asset_id,
                    asset_role=role,
                    source_type="sentinel_2",
                    source_name="test",
                    mime_type="image/tiff",
                    acquired_at=datetime(2021, month, 1, tzinfo=UTC),
                    content_uri=f"data://{asset_id}.tif",
                    quality_status="good",
                    is_simulated=True,
                )
                for asset_id, role, month in (
                    ("before-asset", "primary", 7),
                    ("after-asset", "context", 10),
                )
            ])
            await session.commit()

            with patch(
                "app.visual_verification.router.asyncio.to_thread",
                AsyncMock(side_effect=result_from_call),
            ):
                result = await run_remote_sensing_analysis(request, session)

            loaded = await get_remote_analysis(session, result.analysis_id)

        self.assertEqual(result.analysis_id, loaded.analysis_id)
        self.assertEqual(loaded.run_status, "succeeded")
        self.assertEqual(loaded.result_payload["analysis_id"], result.analysis_id)
        self.assertEqual(loaded.result_payload["area_hectares"], 0.25)


if __name__ == "__main__":
    unittest.main()
