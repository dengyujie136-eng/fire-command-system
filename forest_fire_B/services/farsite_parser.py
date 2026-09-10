from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def detect_time_field(columns: list) -> str:
    """自动识别属性表中的时间字段。"""
    candidates = {"PERIMETER", "ELAPSED_MIN", "TIME", "MINUTES", "ELAPSED", "MIN", "HOUR", "HOURS"}
    for col in columns:
        col_upper = str(col).upper()
        if col_upper in candidates or "TIME" in col_upper or "ELAPSED" in col_upper or "MIN" in col_upper:
            return str(col)
    return str(columns[0]) if columns else "PERIMETER"


def _build_mock_manifest(scene_id: str, reason: str = "graceful_fallback") -> dict[str, Any]:
    logger.warning("Using mock Farsite manifest for scene_id=%s reason=%s", scene_id, reason)
    slices = {
        "10m": {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[114.3, 30.5], [114.31, 30.5], [114.31, 30.51], [114.3, 30.51], [114.3, 30.5]]],
                    },
                    "properties": {"time_key": "10m", "scene_id": scene_id, "mock": True},
                }
            ],
        },
        "30m": {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[114.29, 30.49], [114.32, 30.49], [114.32, 30.52], [114.29, 30.52], [114.29, 30.49]]],
                    },
                    "properties": {"time_key": "30m", "scene_id": scene_id, "mock": True},
                }
            ],
        },
    }
    return {
        "scene_id": scene_id,
        "fire_points": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [114.3, 30.5]},
                "properties": {"type": "ignition_point", "mock": True},
            }
        ],
        "slices": slices,
        "time_series": [
            {"time_minutes": 10, "area_km2": 0.3, "perimeter_km": 2.1},
            {"time_minutes": 30, "area_km2": 1.2, "perimeter_km": 5.8},
        ],
        "metadata": {
            "total_steps": len(slices),
            "time_field": "PERIMETER",
            "available_times": sorted(slices.keys()),
            "fallback": True,
            "reason": reason,
        },
    }


def parse_farsite_output(scene_id: str, results_dir: str) -> dict[str, Any]:
    results_path = Path(results_dir)
    perimeters_path = results_path / "Farsite_Perimeters.shp"
    ignitions_path = results_path / "Farsite_Ignitions.shp"
    csv_path = results_path / "Fire_Growth_Report.csv"

    try:
        import geopandas as gpd  # type: ignore
    except Exception as exc:
        return _build_mock_manifest(scene_id, reason=f"geopandas_unavailable:{exc}")

    try:
        if not perimeters_path.exists():
            raise FileNotFoundError("Farsite_Perimeters.shp not found")

        perimeters_gdf = gpd.read_file(perimeters_path)
        time_field = detect_time_field(list(perimeters_gdf.columns))

        time_slices: dict[str, dict[str, Any]] = {}
        if time_field not in perimeters_gdf.columns:
            raise KeyError(f"Time field {time_field} not found in perimeters shapefile")

        for time_value in sorted(perimeters_gdf[time_field].dropna().unique()):
            slice_gdf = perimeters_gdf[perimeters_gdf[time_field] == time_value]
            geojson_obj = json.loads(slice_gdf.to_json())
            time_key = f"{int(float(time_value))}m" if str(time_value).replace(".", "", 1).isdigit() else f"{time_value}m"
            for feat in geojson_obj.get("features", []):
                feat.setdefault("properties", {})["time_key"] = time_key
                feat["properties"]["scene_id"] = scene_id
            time_slices[time_key] = {"type": "FeatureCollection", "features": geojson_obj.get("features", [])}

        fire_points: list[dict[str, Any]] = []
        if ignitions_path.exists():
            ignitions_gdf = gpd.read_file(ignitions_path)
            for _, point in ignitions_gdf.iterrows():
                geometry = getattr(point, "geometry", None)
                if geometry is None:
                    continue
                fire_points.append(
                    {
                        "type": "Feature",
                        "geometry": json.loads(gpd.GeoSeries([geometry]).to_json())["features"][0]["geometry"],
                        "properties": {"type": "ignition_point", "scene_id": scene_id},
                    }
                )

        time_series: list[dict[str, Any]] = []
        if csv_path.exists():
            try:
                import pandas as pd  # type: ignore

                report_df = pd.read_csv(csv_path)
                for _, row in report_df.iterrows():
                    time_series.append(
                        {
                            "time_minutes": row.get("Time", row.get("Elapsed_Min", row.get("ELAPSED", 0))),
                            "area_km2": row.get("Area", row.get("AREA", 0)),
                            "perimeter_km": row.get("Perimeter", row.get("PERIMETER", 0)),
                        }
                    )
            except Exception as exc:
                logger.warning("Failed to parse Fire_Growth_Report.csv for scene_id=%s: %s", scene_id, exc)

        return {
            "scene_id": scene_id,
            "fire_points": fire_points,
            "slices": time_slices,
            "time_series": time_series,
            "metadata": {
                "total_steps": len(time_slices),
                "time_field": time_field,
                "available_times": sorted(time_slices.keys(), key=lambda x: int("".join(ch for ch in x if ch.isdigit()) or "0")),
                "fallback": False,
            },
        }
    except Exception as exc:
        logger.warning("parse_farsite_output fallback for scene_id=%s error=%s", scene_id, exc)
        return _build_mock_manifest(scene_id, reason=str(exc))
