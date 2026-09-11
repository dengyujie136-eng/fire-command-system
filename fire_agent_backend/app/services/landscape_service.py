from __future__ import annotations

from pathlib import Path
from typing import Any


SCENE_ENVIRONMENT_SUBDIRS = {
    "muli_lier_village": "",
    "pingyao_liujian_gou_early_replay": "pingyao_20240613",
}

PROJECT_LANDCOVER_LABELS = {
    "0": "non_burnable",
    "1": "mixed_forest",
    "2": "shrub_grass",
    "3": "conifer_forest",
    "4": "agriculture",
}

# These codes intentionally match ESA WorldCover where possible, so the
# temporary layer can later be replaced without changing the spread contract.
SIMULATED_LANDCOVER_LABELS = {
    "10": "forest",
    "20": "shrubland",
    "30": "grassland",
    "60": "bare_rock",
}


def _environment_file(scene_id: str) -> Path | None:
    if scene_id not in SCENE_ENVIRONMENT_SUBDIRS:
        return None
    from app.core.config import get_settings

    root = get_settings().resolved_landscape_data_dir
    subdir = SCENE_ENVIRONMENT_SUBDIRS[scene_id]
    return root / subdir / "final_input.nc"


def _ascending_grid(
    longitude: list[float],
    latitude: list[float],
    elevation: list[list[float]],
    landcover: list[list[int]],
) -> tuple[list[float], list[float], list[list[float]], list[list[int]]]:
    if longitude and longitude[0] > longitude[-1]:
        longitude.reverse()
        elevation = [list(reversed(row)) for row in elevation]
        landcover = [list(reversed(row)) for row in landcover]
    if latitude and latitude[0] > latitude[-1]:
        latitude.reverse()
        elevation.reverse()
        landcover.reverse()
    return longitude, latitude, elevation, landcover


def _normalized(values: Any, np: Any) -> Any:
    low = float(np.nanpercentile(values, 5))
    high = float(np.nanpercentile(values, 95))
    if high - low < 1e-9:
        return np.zeros_like(values, dtype=np.float64)
    return np.clip((values - low) / (high - low), 0.0, 1.0)


def simulate_landcover_from_dem(
    longitude: list[float],
    latitude: list[float],
    elevation: list[list[float]],
    np: Any,
) -> list[list[int]]:
    """Create a deterministic temporary fuel layer from terrain morphology."""
    elevation_grid = np.asarray(elevation, dtype=np.float64)
    mean_latitude = float(np.mean(latitude))
    longitude_spacing_m = max(
        1.0,
        abs(float(longitude[1] - longitude[0]))
        * 111_000.0
        * float(np.cos(np.radians(mean_latitude))),
    )
    latitude_spacing_m = max(
        1.0,
        abs(float(latitude[1] - latitude[0])) * 111_000.0,
    )
    gradient_y, gradient_x = np.gradient(
        elevation_grid,
        latitude_spacing_m,
        longitude_spacing_m,
    )
    slope_ratio = np.hypot(gradient_x, gradient_y)
    padded = np.pad(elevation_grid, 1, mode="edge")
    local_mean = sum(
        padded[
            row_offset : row_offset + elevation_grid.shape[0],
            column_offset : column_offset + elevation_grid.shape[1],
        ]
        for row_offset in range(3)
        for column_offset in range(3)
    ) / 9.0
    ridge_position = elevation_grid - local_mean

    elevation_norm = _normalized(elevation_grid, np)
    slope_norm = _normalized(slope_ratio, np)
    ridge_norm = _normalized(ridge_position, np)
    longitude_grid, latitude_grid = np.meshgrid(
        np.asarray(longitude, dtype=np.float64),
        np.asarray(latitude, dtype=np.float64),
    )
    texture = (
        np.sin((longitude_grid - longitude_grid.min()) * 460.0)
        + np.cos((latitude_grid - latitude_grid.min()) * 520.0)
        + np.sin((longitude_grid + latitude_grid) * 170.0)
    ) / 3.0

    # The temporary interpretation mirrors visible Cesium characteristics:
    # forested lower slopes, shrub/grass transitions, and exposed high ridges.
    landcover = np.full(elevation_grid.shape, 10, dtype=np.int32)
    bare_rock = (
        (elevation_norm >= 0.82)
        | ((elevation_norm >= 0.62) & (slope_norm >= 0.76))
        | ((elevation_norm >= 0.70) & (ridge_norm >= 0.72))
    )
    shrubland = (~bare_rock) & (
        (elevation_norm >= 0.58)
        | (slope_norm >= 0.60)
        | ((ridge_norm >= 0.60) & (elevation_norm >= 0.42))
    )
    grassland = (~bare_rock) & (~shrubland) & (
        ((elevation_norm >= 0.36) & (texture >= 0.08))
        | ((slope_norm <= 0.30) & (texture >= 0.34))
    )
    landcover[grassland] = 30
    landcover[shrubland] = 20
    landcover[bare_rock] = 60
    return landcover.tolist()


def _uses_rule_based_fuel_layer(dataset_source: str) -> bool:
    normalized = dataset_source.strip().lower()
    return (
        "rule-based fuel layer" in normalized
        or "rule based fuel layer" in normalized
    )


def load_scenario_landscape(
    scene_id: str,
) -> tuple[dict[str, Any] | None, str | None]:
    path = _environment_file(scene_id)
    if path is None:
        return None, f"No landscape dataset is registered for scene {scene_id}"
    if not path.exists():
        return None, f"Landscape NetCDF is unavailable for scene {scene_id}: {path}"

    try:
        import netCDF4
        import numpy as np

        with netCDF4.Dataset(path) as dataset:
            required = {"lon", "lat", "topography_z", "fuel_idx"}
            missing = sorted(required.difference(dataset.variables))
            if missing:
                return None, (
                    "Landscape NetCDF is missing variables: "
                    f"{', '.join(missing)}"
                )

            longitude = np.asarray(
                dataset.variables["lon"][:],
                dtype=np.float64,
            ).tolist()
            latitude = np.asarray(
                dataset.variables["lat"][:],
                dtype=np.float64,
            ).tolist()
            elevation = np.asarray(
                dataset.variables["topography_z"][:],
                dtype=np.float64,
            ).tolist()
            landcover = np.asarray(
                dataset.variables["fuel_idx"][:],
                dtype=np.int32,
            ).tolist()
            dataset_source = str(
                getattr(dataset, "source", "scenario_final_input_netcdf")
            )
            dataset_is_simulated = bool(
                getattr(dataset, "is_simulated", False)
            )
    except Exception as exc:
        return None, f"Landscape NetCDF could not be read: {exc}"

    longitude, latitude, elevation, landcover = _ascending_grid(
        longitude,
        latitude,
        elevation,
        landcover,
    )
    if _uses_rule_based_fuel_layer(dataset_source):
        landcover = simulate_landcover_from_dem(
            longitude,
            latitude,
            elevation,
            np,
        )
        landcover_labels = SIMULATED_LANDCOVER_LABELS
        landscape_source = "cesium_visual_dem_proxy_simulated"
        classification_method = (
            "deterministic DEM elevation, slope, ridge-position and spatial-"
            "texture proxy based on visible Cesium forest, transition and "
            "exposed-ridge patterns"
        )
        is_simulated = True
    else:
        landcover_labels = PROJECT_LANDCOVER_LABELS
        landscape_source = dataset_source
        classification_method = "netcdf_fuel_or_landcover_codes"
        is_simulated = dataset_is_simulated

    return (
        {
            "longitudes": longitude,
            "latitudes": latitude,
            "elevation_m": elevation,
            "landcover_codes": landcover,
            "landcover_labels": landcover_labels,
            "source": landscape_source,
            "original_source": dataset_source,
            "classification_method": classification_method,
            "scene_id": scene_id,
            "is_simulated": is_simulated,
        },
        None,
    )
