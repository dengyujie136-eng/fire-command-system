import unittest
from datetime import UTC, datetime

from sqlalchemy import create_engine, event, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.visual_verification.models import (
    FireConfirmationRecord,
    RemoteSensingAnalysisRecord,
    VisualAnalysisRunRecord,
    VisualCaseAssetRecord,
    VisualFindingRecord,
    VisualImageDerivativeRecord,
    VisualVerificationCaseRecord,
)


VISUAL_TABLES = [
    VisualVerificationCaseRecord.__table__,
    VisualCaseAssetRecord.__table__,
    VisualImageDerivativeRecord.__table__,
    VisualAnalysisRunRecord.__table__,
    VisualFindingRecord.__table__,
    FireConfirmationRecord.__table__,
    RemoteSensingAnalysisRecord.__table__,
]


class VisualPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")

        @event.listens_for(self.engine, "connect")
        def enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        Base.metadata.create_all(self.engine, tables=VISUAL_TABLES)

    def tearDown(self) -> None:
        self.engine.dispose()

    def new_case(self, *, visual_case_id: str = "visual-case-fire-001", version: int = 1):
        return VisualVerificationCaseRecord(
            visual_case_id=visual_case_id,
            source_candidate_id="cresta-dam-visual-demo-firms-viirs_snpp-20260909T020000Z-39.842700--121.382100",
            upstream_schema_version="fire.hotspot.candidate.v0.1",
            upstream_status="candidate",
            event_id="cresta-dam-visual-demo",
            event_name="Cresta Dam Visual Demo",
            observation_id="sim-observation-20260909-001",
            observed_at=datetime(2026, 9, 9, 2, 0, tzinfo=UTC),
            longitude=-121.3821,
            latitude=39.8427,
            imagery_status="available",
            data_owner={
                "organization": "NASA FIRMS reference fixture",
                "source_product": "VIIRS_SNPP_SP",
            },
            replay_metadata={"is_replay": False},
            product_fields={"firms": {"confidence": "h"}},
            upstream_payload_hash="0" * 64,
            status="received",
            version=version,
            is_simulated=True,
        )

    def test_only_seven_owned_tables_are_created(self) -> None:
        self.assertEqual(
            set(inspect(self.engine).get_table_names()),
            {
                "visual_verification_cases",
                "visual_case_assets",
                "visual_image_derivatives",
                "visual_analysis_runs",
                "visual_findings",
                "fire_confirmations",
                "remote_sensing_analyses",
            },
        )

    def test_full_evidence_chain_can_be_written_and_read(self) -> None:
        with Session(self.engine) as session:
            case = self.new_case()
            session.add(case)
            session.flush()
            session.add_all(
                [
                    VisualCaseAssetRecord(
                        visual_case_id=case.visual_case_id,
                        source_asset_id="asset-wildfire-smoke",
                        asset_role="primary",
                        source_type="satellite_natural_color",
                        source_name="NASA Earth Observatory",
                        mime_type="image/jpeg",
                        acquired_at=datetime(2020, 12, 3, 18, 44, tzinfo=UTC),
                        content_uri="fixtures/images/wildfire_smoke_nasa.jpg",
                        quality_status="good",
                        checksum_sha256="9b1d652427c2413a85b1b7062c75aeb3124cc70892219db9a827e63d0e73cdf5",
                        is_simulated=True,
                    ),
                    VisualImageDerivativeRecord(
                        derivative_id="derivative-fire-crop-001",
                        visual_case_id=case.visual_case_id,
                        source_asset_id="asset-wildfire-smoke",
                        derivative_type="candidate_crop",
                        file_uri="generated/candidate-fire-001-crop.jpg",
                        crs="EPSG:4326",
                        extent_geojson={"type": "Polygon", "coordinates": []},
                        processing_parameters={"padding_pixels": 32},
                        is_simulated=True,
                    ),
                ]
            )
            run = VisualAnalysisRunRecord(
                analysis_run_id="run-confirmed-001",
                visual_case_id=case.visual_case_id,
                provider="deterministic_fixture",
                model_name="deterministic-fixture",
                model_version="day2-v1",
                prompt_version="visual-fire-v1",
                run_status="succeeded",
                started_at=datetime(2026, 9, 9, 2, 4, tzinfo=UTC),
                finished_at=datetime(2026, 9, 9, 2, 4, 1, tzinfo=UTC),
                duration_ms=1000,
                raw_response={"decision": "confirmed"},
                is_fallback=True,
            )
            session.add(run)
            session.flush()
            session.add(
                VisualFindingRecord(
                    finding_id="finding-smoke-001",
                    analysis_run_id=run.analysis_run_id,
                    finding_type="smoke",
                    detected=True,
                    confidence=0.96,
                    attributes={"plume": "visible"},
                    evidence_source="asset-wildfire-smoke",
                )
            )
            session.add(
                FireConfirmationRecord(
                    confirmation_id="confirmation-fire-001-v1",
                    visual_case_id=case.visual_case_id,
                    source_candidate_id=case.source_candidate_id,
                    version=1,
                    is_current=True,
                    status="confirmed",
                    confidence=0.94,
                    reason_codes=["MODEL_AND_DETECTOR_AGREE"],
                    evidence_ids=["asset-wildfire-smoke", "finding-smoke-001"],
                    longitude=case.longitude,
                    latitude=case.latitude,
                    confirmation_method="visual_verification_v1",
                    rule_version="confirmation-rule-v1",
                    confirmed_at=datetime(2026, 9, 9, 2, 5, tzinfo=UTC),
                    is_simulated=True,
                )
            )
            case.status = "confirmed"
            session.commit()

        with Session(self.engine) as session:
            stored_case = session.scalar(
                select(VisualVerificationCaseRecord).where(
                    VisualVerificationCaseRecord.visual_case_id == "visual-case-fire-001"
                )
            )
            confirmation = session.scalar(select(FireConfirmationRecord))
            finding = session.scalar(select(VisualFindingRecord))
            self.assertEqual(stored_case.status, "confirmed")
            self.assertEqual(stored_case.upstream_status, "candidate")
            self.assertEqual(stored_case.imagery_status, "available")
            self.assertEqual(stored_case.product_fields["firms"]["confidence"], "h")
            self.assertEqual(confirmation.evidence_ids[-1], "finding-smoke-001")
            self.assertEqual(finding.evidence_source, "asset-wildfire-smoke")

    def test_case_versions_preserve_history_and_reject_duplicates(self) -> None:
        with Session(self.engine) as session:
            session.add(self.new_case())
            session.add(self.new_case(visual_case_id="visual-case-fire-001-v2", version=2))
            session.commit()
            versions = session.scalars(
                select(VisualVerificationCaseRecord).order_by(
                    VisualVerificationCaseRecord.version
                )
            ).all()
            self.assertEqual([record.version for record in versions], [1, 2])

            session.add(self.new_case(visual_case_id="visual-case-fire-duplicate", version=2))
            with self.assertRaises(IntegrityError):
                session.commit()
            session.rollback()

    def test_confirmed_record_requires_location_and_time(self) -> None:
        with Session(self.engine) as session:
            case = self.new_case()
            session.add(case)
            session.flush()
            session.add(
                FireConfirmationRecord(
                    confirmation_id="invalid-confirmation",
                    visual_case_id=case.visual_case_id,
                    source_candidate_id=case.source_candidate_id,
                    version=1,
                    is_current=True,
                    status="confirmed",
                    confidence=0.9,
                    reason_codes=["TEST"],
                    evidence_ids=["asset-test"],
                    longitude=None,
                    latitude=None,
                    confirmation_method="visual_verification_v1",
                    rule_version="confirmation-rule-v1",
                    confirmed_at=None,
                    is_simulated=True,
                )
            )
            with self.assertRaises(IntegrityError):
                session.commit()
