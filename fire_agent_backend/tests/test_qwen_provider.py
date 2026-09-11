import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PIL import Image
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.core.config import Settings
from app.visual_verification.analysis_service import execute_and_persist_visual_analysis
from app.visual_verification.models import (
    VisualAnalysisRunRecord,
    VisualFindingRecord,
    VisualVerificationCaseRecord,
)
from app.visual_verification.providers.qwen import (
    QwenProviderError,
    QwenVisualProvider,
)
from app.visual_verification.qwen_prompt import QWEN_FIRE_PROMPT_VERSION
from app.visual_verification.provider_factory import (
    QwenConfigurationError,
    build_qwen_provider,
)
from app.visual_verification.schemas import ImageAnalysisRequest, VisualAnalysisFailure


VALID_ASSESSMENT = {
    "fire_detected": True,
    "flame_detected": True,
    "smoke_detected": True,
    "burn_scar_detected": False,
    "wildfire_likelihood": 0.91,
    "image_quality": "good",
    "scene_type": "forest_wildfire",
    "alternative_explanations": [],
    "decision": "confirmed",
    "reasoning_summary": "可见火焰与上升烟羽。",
}


def response_with(content: Any) -> dict[str, Any]:
    import json

    encoded = json.dumps(content, ensure_ascii=False) if isinstance(content, dict) else content
    return {"choices": [{"message": {"content": encoded}}], "model": "qwen3-vl-plus"}


class FakeTransport:
    def __init__(self, outcomes: list[Any]) -> None:
        self.outcomes = outcomes
        self.calls = 0
        self.payloads: list[dict[str, Any]] = []

    async def complete(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.payloads.append(payload)
        outcome = self.outcomes[min(self.calls, len(self.outcomes) - 1)]
        self.calls += 1
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class QwenProviderTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.source_root = root / "data"
        self.output_root = root / "visual-output"
        image_path = self.output_root / "case-001" / "asset-001" / "model.jpg"
        image_path.parent.mkdir(parents=True)
        Image.new("RGB", (128, 96), (220, 70, 30)).save(image_path)
        self.request = ImageAnalysisRequest(
            visual_case_id="case-001",
            image_asset_ids=["derivative-001"],
            image_uris={
                "derivative-001": "visual-output://case-001/asset-001/model.jpg"
            },
            prompt_version=QWEN_FIRE_PROMPT_VERSION,
        )

    async def asyncTearDown(self) -> None:
        self.temporary.cleanup()

    def provider(self, transport: FakeTransport, **updates: Any) -> QwenVisualProvider:
        return QwenVisualProvider(
            transport=transport,
            source_root=self.source_root,
            output_root=self.output_root,
            timeout_seconds=1,
            **updates,
        )

    async def test_builds_official_compatible_multimodal_json_request(self) -> None:
        transport = FakeTransport([response_with(VALID_ASSESSMENT)])
        result = await self.provider(transport).analyze(self.request)

        payload = transport.payloads[0]
        self.assertEqual(payload["response_format"], {"type": "json_object"})
        image_url = payload["messages"][0]["content"][0]["image_url"]["url"]
        self.assertTrue(image_url.startswith("data:image/jpeg;base64,"))
        self.assertEqual(result.wildfire_likelihood, 0.91)
        self.assertFalse(result.is_fallback)

    async def test_retries_retryable_transport_error(self) -> None:
        transport = FakeTransport([
            QwenProviderError("qwen_http_error", "temporary", retryable=True),
            response_with(VALID_ASSESSMENT),
        ])
        result = await self.provider(transport, max_attempts=2).analyze(self.request)
        self.assertTrue(result.fire_detected)
        self.assertEqual(transport.calls, 2)

    async def test_invalid_json_is_not_retried(self) -> None:
        transport = FakeTransport([response_with("not-json")])
        with self.assertRaises(QwenProviderError) as context:
            await self.provider(transport, max_attempts=3).analyze(self.request)
        self.assertEqual(context.exception.code, "qwen_invalid_output")
        self.assertEqual(transport.calls, 1)

    async def test_inconsistent_confirmed_output_is_rejected(self) -> None:
        invalid = dict(VALID_ASSESSMENT)
        invalid.update(
            fire_detected=False,
            flame_detected=False,
            smoke_detected=False,
        )
        transport = FakeTransport([response_with(invalid)])
        with self.assertRaises(QwenProviderError) as context:
            await self.provider(transport).analyze(self.request)
        self.assertEqual(context.exception.code, "qwen_invalid_output")

    async def test_missing_derivative_uri_is_rejected_before_transport(self) -> None:
        transport = FakeTransport([response_with(VALID_ASSESSMENT)])
        request = ImageAnalysisRequest(
            visual_case_id="case-001",
            image_asset_ids=["derivative-001"],
            prompt_version=QWEN_FIRE_PROMPT_VERSION,
        )
        with self.assertRaises(QwenProviderError) as context:
            await self.provider(transport).analyze(request)
        self.assertEqual(context.exception.code, "qwen_image_uri_missing")
        self.assertEqual(transport.calls, 0)


class QwenProviderFactoryTests(unittest.TestCase):
    def test_rejects_missing_api_key_without_exposing_secret(self) -> None:
        settings = Settings(qwen_vl_api_key=SecretStr(""))
        with self.assertRaisesRegex(QwenConfigurationError, "not configured"):
            build_qwen_provider(settings)

    def test_builds_provider_from_dedicated_qwen_settings(self) -> None:
        settings = Settings(
            qwen_vl_api_key=SecretStr("test-secret-value"),
            qwen_vl_base_url="https://example.invalid/compatible-mode/v1",
            qwen_vl_model="qwen3-vl-flash",
            qwen_vl_timeout_seconds=15,
            qwen_vl_max_attempts=1,
        )
        provider = build_qwen_provider(settings)
        self.assertEqual(provider.model_name, "qwen3-vl-flash")
        self.assertEqual(provider.max_attempts, 1)
        self.assertNotIn("test-secret-value", repr(settings.qwen_vl_api_key))

    def test_rejects_non_https_base_url(self) -> None:
        settings = Settings(
            qwen_vl_api_key=SecretStr("test-secret-value"),
            qwen_vl_base_url="http://example.invalid/v1",
        )
        with self.assertRaisesRegex(QwenConfigurationError, "HTTPS"):
            build_qwen_provider(settings)


class QwenPersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.source_root = root / "data"
        self.output_root = root / "visual-output"
        image_path = self.output_root / "case-001" / "asset-001" / "model.jpg"
        image_path.parent.mkdir(parents=True)
        Image.new("RGB", (128, 96), (220, 70, 30)).save(image_path)
        self.request = ImageAnalysisRequest(
            visual_case_id="case-001",
            image_asset_ids=["derivative-001"],
            image_uris={
                "derivative-001": "visual-output://case-001/asset-001/model.jpg"
            },
            prompt_version=QWEN_FIRE_PROMPT_VERSION,
        )
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with self.engine.begin() as connection:
            await connection.run_sync(lambda sync: Base.metadata.create_all(
                sync,
                tables=[
                    VisualVerificationCaseRecord.__table__,
                    VisualAnalysisRunRecord.__table__,
                    VisualFindingRecord.__table__,
                ],
            ))
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def asyncTearDown(self) -> None:
        await self.engine.dispose()
        self.temporary.cleanup()

    async def add_case(self, session) -> None:
        session.add(VisualVerificationCaseRecord(
            visual_case_id="case-001",
            source_candidate_id="candidate-001",
            upstream_schema_version="fire.hotspot.candidate.v0.1",
            upstream_status="candidate",
            event_id="dixie_fire_2021",
            event_name="Dixie Fire",
            observed_at=datetime(2021, 7, 14, 9, 11, tzinfo=UTC),
            longitude=-121.38241,
            latitude=39.87194,
            imagery_status="available",
            data_owner={"organization": "fixture"},
            replay_metadata={"is_replay": True},
            product_fields={},
            upstream_payload_hash="0" * 64,
            status="imagery_ready",
            version=1,
            is_simulated=True,
        ))
        await session.flush()

    def provider(self, transport: FakeTransport) -> QwenVisualProvider:
        return QwenVisualProvider(
            transport=transport,
            source_root=self.source_root,
            output_root=self.output_root,
            timeout_seconds=1,
            max_attempts=1,
        )

    async def test_success_persists_raw_run_and_four_findings(self) -> None:
        async with self.sessions() as session:
            await self.add_case(session)
            result = await execute_and_persist_visual_analysis(
                session,
                provider=self.provider(FakeTransport([response_with(VALID_ASSESSMENT)])),
                request=self.request,
            )
            self.assertTrue(result.fire_detected)
            run_count = await session.scalar(select(func.count(VisualAnalysisRunRecord.id)))
            finding_count = await session.scalar(select(func.count(VisualFindingRecord.id)))
            self.assertEqual(run_count, 1)
            self.assertEqual(finding_count, 4)

    async def test_invalid_output_persists_structured_failure(self) -> None:
        async with self.sessions() as session:
            await self.add_case(session)
            result = await execute_and_persist_visual_analysis(
                session,
                provider=self.provider(FakeTransport([response_with("bad-json")])),
                request=self.request,
            )
            self.assertIsInstance(result, VisualAnalysisFailure)
            self.assertEqual(result.run_status, "invalid_output")
            run = await session.scalar(select(VisualAnalysisRunRecord))
            self.assertEqual(run.error_code, "qwen_invalid_output")
            self.assertIsNotNone(run.raw_response)


if __name__ == "__main__":
    unittest.main()
