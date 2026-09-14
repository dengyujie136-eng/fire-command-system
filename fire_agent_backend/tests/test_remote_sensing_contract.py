import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from pydantic import ValidationError

from app.core.errors import AppError
from app.main import create_app
from app.visual_verification.router import (
    _remote_sensing_capabilities,
    run_remote_sensing_analysis,
)
from app.visual_verification.schemas import (
    ConfirmationDecision,
    FindingSupport,
    ProfessionalDetection,
    RemoteSensingAnalysisRequest,
    RemoteSensingAnalysisType,
    RemoteSensingChangeResult,
    VisualAnalysisFailure,
    VisualReviewResult,
)
from app.visual_verification.states import VisualCaseStatus


class RemoteSensingRequestSchemaTests(unittest.TestCase):
    def test_fire_confirmation_is_event_neutral(self) -> None:
        request = RemoteSensingAnalysisRequest(
            event_id="australia_black_summer_2019",
            analysis_type="fire_confirmation",
            target_time=datetime(2019, 12, 31, 3, 0, tzinfo=UTC),
            target_geometry={"type": "Point", "coordinates": [149.1, -35.3]},
            asset_ids=["sentinel-scene-001"],
            hotspot_ids=["hotspot-001"],
        )

        self.assertEqual(request.event_id, "australia_black_summer_2019")
        self.assertEqual(
            request.analysis_type,
            RemoteSensingAnalysisType.FIRE_CONFIRMATION,
        )

    def test_temporal_change_accepts_before_and_after_assets(self) -> None:
        request = RemoteSensingAnalysisRequest(
            event_id="event-002",
            analysis_type="temporal_change",
            time_range={
                "start_at": "2021-07-01T00:00:00Z",
                "end_at": "2021-08-01T00:00:00Z",
            },
            asset_ids=["before-scene", "after-scene"],
        )

        self.assertEqual(request.analysis_type, RemoteSensingAnalysisType.TEMPORAL_CHANGE)

    def test_burned_area_requires_two_assets(self) -> None:
        with self.assertRaisesRegex(ValidationError, "exactly two imagery assets"):
            RemoteSensingAnalysisRequest(
                event_id="event-003",
                analysis_type="burned_area",
                time_range={
                    "start_at": "2021-07-01T00:00:00Z",
                    "end_at": "2021-08-01T00:00:00Z",
                },
                asset_ids=["after-only"],
            )

    def test_change_analysis_rejects_point_geometry(self) -> None:
        with self.assertRaisesRegex(ValidationError, "Polygon or MultiPolygon"):
            RemoteSensingAnalysisRequest(
                event_id="event-geometry",
                analysis_type="temporal_change",
                time_range={
                    "start_at": "2021-07-01T00:00:00Z",
                    "end_at": "2021-08-01T00:00:00Z",
                },
                target_geometry={"type": "Point", "coordinates": [120, 30]},
                asset_ids=["before-scene", "after-scene"],
            )

    def test_fire_confirmation_requires_target_time(self) -> None:
        with self.assertRaisesRegex(ValidationError, "requires target_time"):
            RemoteSensingAnalysisRequest(
                event_id="event-004",
                analysis_type="fire_confirmation",
                asset_ids=["scene-001"],
            )

    def test_time_range_must_be_forward(self) -> None:
        with self.assertRaisesRegex(ValidationError, "later than start_at"):
            RemoteSensingAnalysisRequest(
                event_id="event-005",
                analysis_type="temporal_change",
                time_range={
                    "start_at": "2021-08-01T00:00:00Z",
                    "end_at": "2021-07-01T00:00:00Z",
                },
                asset_ids=["before-scene", "after-scene"],
            )

    def test_identifier_lists_reject_duplicates(self) -> None:
        with self.assertRaisesRegex(ValidationError, "cannot contain duplicates"):
            RemoteSensingAnalysisRequest(
                event_id="event-006",
                analysis_type="fire_confirmation",
                target_time="2021-07-14T09:11:00Z",
                asset_ids=["scene-001", "scene-001"],
            )


class RemoteSensingAgentContractTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def failed_review() -> VisualReviewResult:
        return VisualReviewResult(
            visual_case_id="case-generic-001",
            visual=VisualAnalysisFailure(
                analysis_run_id="run-generic-001",
                visual_case_id="case-generic-001",
                run_status="provider_error",
                error_code="test_provider_error",
                error_message="Isolated dispatch fixture.",
                retryable=True,
                attempted_model_name="test-model",
                attempted_model_version="test-version",
                prompt_version="test-prompt",
                used_evidence_ids=["derivative-generic-001"],
                is_fallback=False,
            ),
            professional_run=None,
            professional=ProfessionalDetection(
                support=FindingSupport.UNAVAILABLE,
                evidence_ids=[],
                summary="Detector omitted in isolated dispatch test.",
            ),
            confirmation=ConfirmationDecision(
                status=VisualCaseStatus.FAILED,
                confidence=0,
                reason_codes=["test_provider_error"],
                evidence_ids=["derivative-generic-001"],
            ),
            confirmation_id="confirmation-generic-001",
            warnings=[],
            is_simulated=True,
        )

    def test_capabilities_publish_three_tasks_and_two_tools(self) -> None:
        result = _remote_sensing_capabilities()

        self.assertEqual(len(result.capabilities), 3)
        self.assertEqual(
            {item.analysis_type for item in result.capabilities},
            set(RemoteSensingAnalysisType),
        )
        self.assertEqual(
            {item.tool_name for item in result.capabilities},
            {"analyze_fire_imagery", "analyze_temporal_change"},
        )
        self.assertTrue(
            all(item.execution_status == "available" for item in result.capabilities)
        )

    def test_openapi_exposes_generic_analysis_endpoints(self) -> None:
        paths = create_app().openapi()["paths"]

        self.assertIn("/api/visual-verification/analyses/capabilities", paths)
        self.assertIn("/api/visual-verification/analyses", paths)
        self.assertIn("/api/visual-verification/analyses/{analysis_id}", paths)
        self.assertIn(
            "/api/visual-verification/analyses/{analysis_id}/artifacts/{artifact_name}",
            paths,
        )
        self.assertIn("/api/visual-verification/analyses/run", paths)

    async def test_missing_prepared_image_has_explicit_error(self) -> None:
        request = RemoteSensingAnalysisRequest(
            event_id="event-without-prepared-imagery",
            analysis_type="fire_confirmation",
            target_time="2021-07-14T09:11:00Z",
            asset_ids=["scene-001"],
            visual_case_id="case-001",
        )

        with self.assertRaises(AppError) as context:
            await run_remote_sensing_analysis(request, None)  # type: ignore[arg-type]

        self.assertEqual(context.exception.status_code, 409)
        self.assertEqual(context.exception.code, "imagery_not_prepared")

    async def test_change_analysis_requires_registered_case(self) -> None:
        request = RemoteSensingAnalysisRequest(
            event_id="event-007",
            analysis_type="temporal_change",
            time_range={
                "start_at": "2021-07-01T00:00:00Z",
                "end_at": "2021-08-01T00:00:00Z",
            },
            asset_ids=["before-scene", "after-scene"],
        )

        with self.assertRaises(AppError) as context:
            await run_remote_sensing_analysis(request, None)  # type: ignore[arg-type]

        self.assertEqual(context.exception.status_code, 409)
        self.assertEqual(context.exception.code, "visual_case_required")

    async def test_non_dixie_event_dispatches_to_existing_review_pipeline(self) -> None:
        request = RemoteSensingAnalysisRequest(
            event_id="australia_black_summer_2019",
            analysis_type="fire_confirmation",
            target_time="2019-12-31T03:00:00Z",
            asset_ids=["scene-generic-001"],
            hotspot_ids=["hotspot-generic-001"],
            visual_case_id="case-generic-001",
            prepared_image_ids=["derivative-generic-001"],
        )
        case = SimpleNamespace(
            event_id="australia_black_summer_2019",
            is_simulated=True,
        )
        derivative = SimpleNamespace(
            derivative_id="derivative-generic-001",
            visual_case_id="case-generic-001",
            source_asset_id="scene-generic-001",
            is_simulated=True,
        )
        run_record = SimpleNamespace(analysis_id="remote-analysis-fire-001")

        with (
            patch(
                "app.visual_verification.router.get_visual_case",
                AsyncMock(return_value=case),
            ),
            patch(
                "app.visual_verification.router.get_derivative",
                AsyncMock(return_value=derivative),
            ),
            patch(
                "app.visual_verification.router._execute_complete_review",
                AsyncMock(return_value=self.failed_review()),
            ) as execute,
            patch(
                "app.visual_verification.router.start_remote_analysis",
                AsyncMock(return_value=run_record),
            ),
            patch(
                "app.visual_verification.router.complete_remote_analysis",
                AsyncMock(),
            ),
        ):
            result = await run_remote_sensing_analysis(request, AsyncMock())

        self.assertEqual(result.event_id, "australia_black_summer_2019")
        self.assertEqual(result.tool_name, "analyze_fire_imagery")
        self.assertEqual(result.analysis_id, "remote-analysis-fire-001")
        self.assertEqual(result.source_asset_ids, ["scene-generic-001"])
        execute.assert_awaited_once()

    async def test_temporal_change_dispatches_registered_asset_pair(self) -> None:
        request = RemoteSensingAnalysisRequest(
            event_id="australia_black_summer_2019",
            analysis_type="temporal_change",
            time_range={
                "start_at": "2019-12-01T00:00:00Z",
                "end_at": "2020-01-31T00:00:00Z",
            },
            asset_ids=["scene-before", "scene-after"],
            visual_case_id="case-change-001",
            change_threshold=0.25,
            minimum_region_pixels=12,
        )
        case = SimpleNamespace(
            event_id="australia_black_summer_2019",
            is_simulated=False,
        )
        assets = [
            SimpleNamespace(
                source_asset_id="scene-before",
                content_uri="data://before.tif",
                is_simulated=False,
            ),
            SimpleNamespace(
                source_asset_id="scene-after",
                content_uri="data://after.tif",
                is_simulated=False,
            ),
        ]
        change_result = RemoteSensingChangeResult(
            analysis_id="remote-analysis-change-001",
            event_id="australia_black_summer_2019",
            analysis_type="temporal_change",
            before_asset_id="scene-before",
            after_asset_id="scene-after",
            method="dndvi_threshold_v1",
            threshold=0.25,
            minimum_region_pixels=12,
            changed_pixel_count=100,
            valid_pixel_count=900,
            area_hectares=1.0,
            area_geometry_wgs84={"type": "MultiPolygon", "coordinates": []},
            source_crs="EPSG:32655",
            resolution_m=(10.0, 10.0),
            output_uris={"area_geojson": "visual-output://result.geojson"},
            warnings=["synthetic route fixture"],
            is_simulated=False,
        )
        run_record = SimpleNamespace(analysis_id="remote-analysis-change-001")

        with (
            patch(
                "app.visual_verification.router.get_visual_case",
                AsyncMock(return_value=case),
            ),
            patch(
                "app.visual_verification.router.list_case_assets",
                AsyncMock(return_value=assets),
            ),
            patch(
                "app.visual_verification.router.asyncio.to_thread",
                AsyncMock(return_value=change_result),
            ) as execute,
            patch(
                "app.visual_verification.router.start_remote_analysis",
                AsyncMock(return_value=run_record),
            ),
            patch(
                "app.visual_verification.router.complete_remote_analysis",
                AsyncMock(),
            ),
        ):
            result = await run_remote_sensing_analysis(request, AsyncMock())

        self.assertEqual(result.event_id, "australia_black_summer_2019")
        self.assertEqual(result.tool_name, "analyze_temporal_change")
        self.assertEqual(result.before_asset_id, "scene-before")
        self.assertEqual(result.after_asset_id, "scene-after")
        execute.assert_awaited_once()
        call = execute.await_args
        self.assertEqual(call.kwargs["threshold"], 0.25)
        self.assertEqual(call.kwargs["minimum_region_pixels"], 12)
        self.assertEqual(call.kwargs["analysis_id"], "remote-analysis-change-001")


if __name__ == "__main__":
    unittest.main()
