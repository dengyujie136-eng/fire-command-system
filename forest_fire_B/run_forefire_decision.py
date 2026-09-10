from __future__ import annotations

import argparse
import json
import sys

from services.environment_context import build_environment_dem_input, build_environment_weather_input, load_local_environment_context
from services.forefire_decision import ForeFireDataError, generate_forefire_decision, load_forefire_input


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate an emergency decision JSON from ForeFire output.")
    parser.add_argument("--file", required=True, help="ForeFire summary JSON, GeoJSON, or output directory.")
    parser.add_argument(
        "--include-coordinates",
        action="store_true",
        help="Keep raw fire-line coordinates in the output.",
    )
    parser.add_argument(
        "--environment-dir",
        default="data/environment",
        help="Local DEM/Fuel/NetCDF environment directory.",
    )
    parser.add_argument(
        "--no-local-environment",
        action="store_true",
        help="Skip loading the local environment summary.",
    )
    args = parser.parse_args()

    try:
        payload, source_path = load_forefire_input(args.file)
        environment_context = None
        if not args.no_local_environment:
            environment_context = load_local_environment_context(args.environment_dir)
        result = generate_forefire_decision(
            payload,
            source_path=source_path,
            weather=build_environment_weather_input(None, environment_context),
            dem=build_environment_dem_input(None, environment_context),
            environment_context=environment_context,
            include_coordinates=args.include_coordinates,
        )
    except (FileNotFoundError, ForeFireDataError, json.JSONDecodeError) as e:
        print(json.dumps({"status": "error", "detail": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
