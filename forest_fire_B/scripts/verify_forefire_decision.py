from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.forefire_decision import generate_forefire_decision, load_forefire_input


DATA_FILE = "data/forefire-output/forefire_prediction_result_20260603_135229.json"


def main() -> int:
    payload, source_path = load_forefire_input(DATA_FILE)
    result = generate_forefire_decision(payload, source_path=source_path, include_coordinates=False)

    assert result["status"] == "decision_generated"
    assert result["task_id"] == "13357085-ae9c-4acf-bd6e-730abf35c7f3"
    assert result["recommended_plan"], "recommended_plan is required"
    assert len(result["candidate_plans"]) >= 3, "at least 3 candidate plans are required"
    assert result["input_summary"]["final_area_km2"] == 8.234856
    assert result["input_summary"]["risk_level"] in {"high", "extreme"}
    assert result["warnings"], "missing optional data should produce warnings"

    plan_statuses = {plan["status"] for plan in result["candidate_plans"]}
    assert "recommended" in plan_statuses
    assert plan_statuses.intersection({"downgraded", "blocked"}), (
        "at least one plan should be downgraded or blocked by safety rules"
    )

    print("ForeFire decision verification passed.")
    print(f"recommended_plan={result['recommended_plan']['plan_id']}")
    print(f"final_area_km2={result['input_summary']['final_area_km2']}")
    print(f"risk_level={result['input_summary']['risk_level']}")
    print(f"candidate_plans={len(result['candidate_plans'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
