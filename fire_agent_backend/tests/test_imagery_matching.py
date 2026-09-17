import json
import unittest
from datetime import timedelta
from pathlib import Path

from app.visual_verification.imagery_matching import match_candidate_imagery
from app.visual_verification.schemas import (
    HotspotCandidate,
    HotspotCandidateEnvelope,
    ImageryAssetsEnvelope,
)


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "visual_verification"


def load_json(name: str) -> dict:
    with (FIXTURE_DIR / name).open(encoding="utf-8") as stream:
        return json.load(stream)


class ImageryMatchingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.candidates = HotspotCandidateEnvelope.model_validate(
            load_json("candidate_input.json")
        ).candidates
        self.assets = ImageryAssetsEnvelope.model_validate(
            load_json("imagery_assets.json")
        ).assets

    def test_good_explicit_references_match(self) -> None:
        result = match_candidate_imagery(
            self.candidates[0],
            self.assets,
            max_time_delta=timedelta(days=4000),
        )
        self.assertEqual(result.match_status.value, "matched")
        self.assertEqual(result.primary_asset_ids, ["asset-wildfire-smoke"])
        self.assertEqual(result.context_asset_ids, ["asset-wildfire-false-color"])
        self.assertEqual(result.rejected_asset_ids, [])

    def test_out_of_time_fixture_is_retained_with_warning(self) -> None:
        result = match_candidate_imagery(self.candidates[0], self.assets)
        self.assertEqual(result.match_status.value, "partially_matched")
        self.assertTrue(
            any(item.startswith("ASSET_OUTSIDE_TIME_WINDOW") for item in result.warnings)
        )

    def test_low_quality_cloud_is_only_partial(self) -> None:
        result = match_candidate_imagery(self.candidates[2], self.assets)
        self.assertEqual(result.match_status.value, "partially_matched")
        self.assertIn("LOW_QUALITY_ASSET:asset-cloud-cover", result.warnings)

    def test_pending_imagery_does_not_fail_or_reject_fire(self) -> None:
        candidate = HotspotCandidate.model_validate(
            load_json("member_a_historical_candidate.json")
        )
        result = match_candidate_imagery(candidate, [])
        self.assertEqual(result.match_status.value, "pending")
        self.assertEqual(result.primary_asset_ids, [])
        self.assertIn("IMAGERY_PENDING", result.warnings)

    def test_unavailable_imagery_has_distinct_result(self) -> None:
        payload = load_json("member_a_historical_candidate.json")
        payload["imagery_status"] = "unavailable"
        candidate = HotspotCandidate.model_validate(payload)
        result = match_candidate_imagery(candidate, [])
        self.assertEqual(result.match_status.value, "unavailable")
        self.assertIn("NO_IMAGERY_AVAILABLE", result.warnings)

    def test_unknown_asset_reference_is_rejected(self) -> None:
        result = match_candidate_imagery(self.candidates[0], [])
        self.assertEqual(result.match_status.value, "invalid_reference")
        self.assertEqual(
            result.rejected_asset_ids,
            ["asset-wildfire-smoke", "asset-wildfire-false-color"],
        )

    def test_asset_bound_to_another_candidate_is_rejected(self) -> None:
        wrong_asset = self.assets[0].model_copy(
            update={"candidate_id": "another-candidate"}
        )
        result = match_candidate_imagery(self.candidates[0], [wrong_asset])
        self.assertEqual(result.match_status.value, "invalid_reference")
        self.assertIn(
            "ASSET_CANDIDATE_MISMATCH:asset-wildfire-smoke",
            result.warnings,
        )

    def test_asset_outside_known_spatial_coverage_is_rejected(self) -> None:
        outside_asset = self.assets[0].model_copy(
            update={"coverage_bbox": (-120.1, 38.0, -120.0, 38.1)}
        )
        result = match_candidate_imagery(self.candidates[0], [outside_asset])
        self.assertEqual(result.match_status.value, "invalid_reference")
        self.assertIn(
            "ASSET_OUTSIDE_SPATIAL_COVERAGE:asset-wildfire-smoke",
            result.warnings,
        )
