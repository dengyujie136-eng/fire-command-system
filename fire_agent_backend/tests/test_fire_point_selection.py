import unittest
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.main import create_app
from app.visual_verification.models import (
    FireConfirmationRecord,
    VisualVerificationCaseRecord,
)
from app.visual_verification.schemas import FirePointSelectionRequest
from app.visual_verification.selection_service import (
    list_confirmed_fire_points,
    select_event_fire_points,
)


TABLES = [
    VisualVerificationCaseRecord.__table__,
    FireConfirmationRecord.__table__,
]


class GenericFirePointSelectionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with self.engine.begin() as connection:
            await connection.run_sync(
                lambda sync_connection: Base.metadata.create_all(
                    sync_connection,
                    tables=TABLES,
                )
            )
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def asyncTearDown(self) -> None:
        await self.engine.dispose()

    @staticmethod
    def candidate(
        event_id: str,
        candidate_id: str,
        observed_at: datetime,
        longitude: float,
        latitude: float,
        *,
        confidence: float = 0.7,
        frp: float = 10.0,
    ) -> VisualVerificationCaseRecord:
        return VisualVerificationCaseRecord(
            visual_case_id=f"case-{candidate_id}",
            source_candidate_id=candidate_id,
            upstream_schema_version="fire.hotspot.candidate.v0.1",
            upstream_status="candidate",
            event_id=event_id,
            event_name=f"Historical fire {event_id}",
            observed_at=observed_at,
            longitude=longitude,
            latitude=latitude,
            imagery_status="available",
            data_owner={"organization": "global-fire-database"},
            replay_metadata={"is_replay": True},
            product_fields={"confidence_score": confidence, "frp_mw": frp},
            upstream_payload_hash=(candidate_id[0] * 64),
            status="imagery_ready",
            version=1,
            is_simulated=False,
        )

    async def test_selects_each_event_independently_without_event_specific_rules(self) -> None:
        start = datetime(2020, 8, 1, tzinfo=UTC)
        async with self.sessions() as session:
            session.add_all(
                [
                    self.candidate("event-alpha", "a1", start, -120.0, 40.0),
                    self.candidate("event-alpha", "a2", start + timedelta(minutes=4), -120.01, 40.0),
                    self.candidate("event-beta", "b1", start, 151.0, -33.0),
                    self.candidate("event-beta", "b2", start + timedelta(minutes=3), 151.01, -33.0),
                ]
            )
            await session.commit()

            alpha = await select_event_fire_points(
                session,
                event_id="event-alpha",
                request=FirePointSelectionRequest(),
            )
            beta = await select_event_fire_points(
                session,
                event_id="event-beta",
                request=FirePointSelectionRequest(),
            )

            self.assertEqual(alpha.selected[0].source_candidate_id, "a1")
            self.assertEqual(beta.selected[0].source_candidate_id, "b1")
            self.assertEqual(alpha.selected[0].cluster_point_count, 2)
            self.assertEqual(beta.selected[0].cluster_point_count, 2)
            self.assertFalse(alpha.used_singleton_fallback)
            self.assertFalse(beta.used_singleton_fallback)

    async def test_filters_by_time_and_falls_back_to_earliest_singleton(self) -> None:
        start = datetime(2019, 1, 1, tzinfo=UTC)
        async with self.sessions() as session:
            session.add_all(
                [
                    self.candidate("event-gamma", "g1", start, 10.0, 10.0),
                    self.candidate("event-gamma", "g2", start + timedelta(days=1), 20.0, 20.0),
                ]
            )
            await session.commit()
            result = await select_event_fire_points(
                session,
                event_id="event-gamma",
                request=FirePointSelectionRequest(
                    start_at=start,
                    end_at=start + timedelta(hours=1),
                ),
            )
            self.assertTrue(result.used_singleton_fallback)
            self.assertEqual(result.evaluated_candidate_count, 1)
            self.assertEqual(result.selected[0].source_candidate_id, "g1")

    async def test_confirmed_point_query_is_event_scoped(self) -> None:
        now = datetime.now(UTC)
        async with self.sessions() as session:
            alpha = self.candidate("event-alpha", "a1", now, -120.0, 40.0)
            beta = self.candidate("event-beta", "b1", now, 151.0, -33.0)
            session.add_all([alpha, beta])
            await session.flush()
            session.add_all(
                [
                    FireConfirmationRecord(
                        confirmation_id="confirmation-alpha",
                        visual_case_id=alpha.visual_case_id,
                        source_candidate_id=alpha.source_candidate_id,
                        version=1,
                        is_current=True,
                        status="confirmed",
                        confidence=0.8,
                        reason_codes=["course-demo"],
                        evidence_ids=["qwen-alpha"],
                        longitude=alpha.longitude,
                        latitude=alpha.latitude,
                        confirmation_method="course_demo_qwen_assisted_v1",
                        rule_version="course-demo-qwen-assisted-v1",
                        confirmed_at=now,
                        is_simulated=False,
                    ),
                    FireConfirmationRecord(
                        confirmation_id="confirmation-beta",
                        visual_case_id=beta.visual_case_id,
                        source_candidate_id=beta.source_candidate_id,
                        version=1,
                        is_current=True,
                        status="confirmed",
                        confidence=0.75,
                        reason_codes=["course-demo"],
                        evidence_ids=["qwen-beta"],
                        longitude=beta.longitude,
                        latitude=beta.latitude,
                        confirmation_method="course_demo_qwen_assisted_v1",
                        rule_version="course-demo-qwen-assisted-v1",
                        confirmed_at=now,
                        is_simulated=False,
                    ),
                ]
            )
            await session.commit()

            alpha_points = await list_confirmed_fire_points(
                session,
                event_id="event-alpha",
            )
            beta_points = await list_confirmed_fire_points(
                session,
                event_id="event-beta",
            )

            self.assertEqual([item.confirmation_id for item in alpha_points], ["confirmation-alpha"])
            self.assertEqual([item.confirmation_id for item in beta_points], ["confirmation-beta"])
            self.assertEqual(alpha_points[0].ignition_point.coordinates, (-120.0, 40.0))
            self.assertEqual(beta_points[0].ignition_point.coordinates, (151.0, -33.0))

    def test_generic_pipeline_routes_are_exposed(self) -> None:
        paths = create_app().openapi()["paths"]
        self.assertIn(
            "/api/visual-verification/events/{event_id}/select-fire-points",
            paths,
        )
        self.assertIn(
            "/api/visual-verification/events/{event_id}/auto-confirm-fire-points",
            paths,
        )
        self.assertIn(
            "/api/visual-verification/events/{event_id}/confirmed-fire-points",
            paths,
        )
