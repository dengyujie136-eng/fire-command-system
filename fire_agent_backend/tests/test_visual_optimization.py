import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.spatial import SPATIAL_COLUMNS, SPATIAL_INDEXES
from app.visual_verification.candidate_service import ingest_candidate_envelope
from app.visual_verification.evidence_fusion_service import persist_evidence_fusion
from app.visual_verification.models import (
    CandidateImageryMatchRecord,
    EvidenceFusionRunRecord,
    ImageryAssetCatalogRecord,
    VisualVerificationCaseRecord,
)
from app.visual_verification.providers.qwen import QwenVisualProvider
from app.visual_verification.qwen_prompt import QWEN_FIRE_PROMPT_VERSION
from app.visual_verification.schemas import (
    FindingSupport,
    HotspotCandidateEnvelope,
    ImageAnalysisRequest,
    ImageQuality,
    ProfessionalDetection,
    SceneType,
    VisualAnalysisResult,
    VisualDecision,
    FirePointSelectionRequest,
)
from app.visual_verification.selection_service import select_event_fire_points


ROOT = Path(__file__).resolve().parents[2]


class UnusedTransport:
    async def complete(self, payload):  # pragma: no cover
        raise AssertionError("transport should not be called while building payload")


class VisualOptimizationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def asyncTearDown(self) -> None:
        await self.engine.dispose()

    async def test_upstream_cluster_catalog_matching_and_fusion_are_persisted(self) -> None:
        payload = json.loads(
            (ROOT / "data/manifests/dixie_fire_2021_visual_candidates.json").read_text(encoding="utf-8")
        )
        payload["candidates"] = [payload["candidates"][0]]
        envelope = HotspotCandidateEnvelope.model_validate(payload)
        async with self.sessions() as session:
            result = await ingest_candidate_envelope(session, envelope)
            await session.commit()
            case = await session.scalar(select(VisualVerificationCaseRecord))
            catalogs = list((await session.scalars(select(ImageryAssetCatalogRecord))).all())
            matches = list((await session.scalars(select(CandidateImageryMatchRecord))).all())
            self.assertEqual(result.items[0].asset_count, 3)
            self.assertEqual(case.source_cluster_id, "dixie_fire_2021-cluster-20210714T0910Z--6070-1993")
            self.assertEqual(len(catalogs), 3)
            self.assertEqual(len(matches), 3)
            self.assertTrue(all(item.matching_score > 0.5 for item in matches))

            selection = await select_event_fire_points(
                session,
                event_id="dixie_fire_2021",
                request=FirePointSelectionRequest(),
            )
            self.assertEqual(selection.selection_method, "upstream_cluster_v1")
            self.assertEqual(selection.selected[0].cluster_point_count, 4)

            visual = VisualAnalysisResult(
                analysis_run_id="analysis-multi",
                visual_case_id=case.visual_case_id,
                fire_detected=False,
                flame_detected=False,
                smoke_detected=False,
                burn_scar_detected=True,
                wildfire_likelihood=0.45,
                image_quality=ImageQuality.USABLE,
                scene_type=SceneType.FOREST_WILDFIRE,
                alternative_explanations=[],
                decision=VisualDecision.UNCERTAIN,
                reasoning_summary="灾后影像出现变化，但灾中未见清晰烟火。",
                used_evidence_ids=["pre", "during", "post"],
                model_name="qwen3-vl-plus",
                model_version="qwen3-vl-plus",
                prompt_version=QWEN_FIRE_PROMPT_VERSION,
            )
            fusion = await persist_evidence_fusion(
                session,
                case=case,
                visual=visual,
                professional=ProfessionalDetection(
                    support=FindingSupport.UNAVAILABLE,
                    summary="detector unavailable",
                ),
            )
            await session.commit()
            self.assertIsNotNone(await session.scalar(select(EvidenceFusionRunRecord)))
            self.assertGreater(fusion.component_scores["cluster"], 0.7)
            self.assertIn(fusion.decision, {"confirmed_thermal", "uncertain"})

    def test_qwen_payload_labels_pre_during_post_images(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "output"
            uris = {}
            for phase in ("pre", "during", "post"):
                path = output / f"{phase}.jpg"
                path.parent.mkdir(parents=True, exist_ok=True)
                Image.new("RGB", (32, 32), (120, 80, 40)).save(path)
                uris[phase] = f"visual-output://{phase}.jpg"
            provider = QwenVisualProvider(
                transport=UnusedTransport(),
                source_root=Path(temporary) / "data",
                output_root=output,
            )
            payload = provider.build_payload(ImageAnalysisRequest(
                visual_case_id="case-multi",
                image_asset_ids=["pre", "during", "post"],
                image_uris=uris,
                image_labels={"pre": "灾前", "during": "灾中", "post": "灾后"},
                prompt_version=QWEN_FIRE_PROMPT_VERSION,
            ))
            content = payload["messages"][0]["content"]
            labels = [item["text"] for item in content if item["type"] == "text"]
            self.assertIn("影像证据：灾前", labels)
            self.assertIn("影像证据：灾中", labels)
            self.assertIn("影像证据：灾后", labels)
            self.assertIn("灾前、灾中、灾后", labels[-1])

    def test_postgis_visual_columns_and_indexes_are_declared(self) -> None:
        ddl = "\n".join((*SPATIAL_COLUMNS, *SPATIAL_INDEXES))
        self.assertIn("visual_verification_cases", ddl)
        self.assertIn("fire_confirmations", ddl)
        self.assertIn("imagery_catalog", ddl)
        self.assertIn("USING GIST", ddl)


if __name__ == "__main__":
    unittest.main()

