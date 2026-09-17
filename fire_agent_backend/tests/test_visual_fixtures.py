import hashlib
import json
import unittest
from pathlib import Path

from pydantic import ValidationError

from app.visual_verification.schemas import (
    CandidateInputEnvelope,
    ConfirmedFirePoint,
    HotspotCandidate,
    ImageryAssetsEnvelope,
    VisualAnalysisFailure,
    VisualAnalysisResult,
)


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "visual_verification"


def load_json(name: str) -> dict:
    with (FIXTURE_DIR / name).open(encoding="utf-8") as stream:
        return json.load(stream)


class VisualFixtureTests(unittest.TestCase):
    def test_all_fixed_contracts_validate(self) -> None:
        candidates = CandidateInputEnvelope.model_validate(load_json("candidate_input.json"))
        assets = ImageryAssetsEnvelope.model_validate(load_json("imagery_assets.json"))
        confirmed = VisualAnalysisResult.model_validate(
            load_json("visual_analysis_confirmed.json")
        )
        rejected = VisualAnalysisResult.model_validate(
            load_json("visual_analysis_rejected.json")
        )
        uncertain = VisualAnalysisResult.model_validate(
            load_json("visual_analysis_uncertain.json")
        )
        failed = VisualAnalysisFailure.model_validate(load_json("visual_analysis_failed.json"))
        handoff = ConfirmedFirePoint.model_validate(load_json("confirmed_fire_handoff.json"))

        self.assertEqual(len(candidates.candidates), 3)
        self.assertEqual(len(assets.assets), 4)
        self.assertEqual(confirmed.decision.value, "confirmed")
        self.assertEqual(rejected.decision.value, "rejected")
        self.assertEqual(uncertain.decision.value, "uncertain")
        self.assertEqual(failed.run_status, "timeout")
        self.assertTrue(handoff.is_simulated)

    def test_candidate_asset_references_are_complete(self) -> None:
        candidates = CandidateInputEnvelope.model_validate(load_json("candidate_input.json"))
        assets = ImageryAssetsEnvelope.model_validate(load_json("imagery_assets.json"))
        available_ids = {asset.asset_id for asset in assets.assets}
        referenced_ids = {
            reference.asset_id
            for candidate in candidates.candidates
            for reference in candidate.imagery_refs
        }
        self.assertEqual(referenced_ids, available_ids)

    def test_fixture_files_match_frozen_sha256(self) -> None:
        assets = ImageryAssetsEnvelope.model_validate(load_json("imagery_assets.json"))
        for asset in assets.assets:
            fixture_path = FIXTURE_DIR / asset.local_fixture_path
            self.assertTrue(fixture_path.is_file(), fixture_path)
            digest = hashlib.sha256(fixture_path.read_bytes()).hexdigest()
            self.assertEqual(digest, asset.sha256)

    def test_invalid_candidate_coordinate_is_rejected(self) -> None:
        payload = load_json("candidate_input.json")
        payload["candidates"][0]["location"]["longitude"] = 181
        with self.assertRaises(ValidationError):
            CandidateInputEnvelope.model_validate(payload)

    def test_unknown_analysis_field_is_rejected(self) -> None:
        payload = load_json("visual_analysis_confirmed.json")
        payload["uncontracted_field"] = "must not pass silently"
        with self.assertRaises(ValidationError):
            VisualAnalysisResult.model_validate(payload)

    def test_confirmed_handoff_requires_evidence(self) -> None:
        payload = load_json("confirmed_fire_handoff.json")
        payload["evidence_ids"] = []
        with self.assertRaises(ValidationError):
            ConfirmedFirePoint.model_validate(payload)

    def test_member_a_pending_historical_replay_is_not_simulated(self) -> None:
        candidate = HotspotCandidate.model_validate(
            load_json("member_a_historical_candidate.json")
        )
        self.assertEqual(candidate.imagery_status.value, "pending")
        self.assertEqual(candidate.imagery_refs, [])
        self.assertTrue(candidate.replay.is_replay)
        self.assertFalse(candidate.is_simulated)
        self.assertEqual(candidate.product_fields["firms"]["confidence"], "n")

    def test_available_candidate_requires_imagery_reference(self) -> None:
        payload = load_json("candidate_input.json")["candidates"][0]
        payload["imagery_refs"] = []
        with self.assertRaises(ValidationError):
            HotspotCandidate.model_validate(payload)

    def test_embedded_base64_image_is_rejected(self) -> None:
        payload = load_json("candidate_input.json")["candidates"][0]
        payload["imagery_refs"][0]["uri"] = "data:image/jpeg;base64,AAAA"
        with self.assertRaises(ValidationError):
            HotspotCandidate.model_validate(payload)
