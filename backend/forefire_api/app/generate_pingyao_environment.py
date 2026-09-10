from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import netCDF4
import numpy as np
import requests


SCENE_ID = "pingyao_liujian_gou_early_replay"
IGNITION_LONGITUDE = 112.3136
IGNITION_LATITUDE = 37.0468
START_DATE = "2024-06-13"
END_DATE = "2024-06-18"
GRID_SIZE = 31
LON_SPAN = 0.18
LAT_SPAN = 0.16


def fetch_open_meteo() -> dict[str, Any]:
    response = requests.get(
        "https://archive-api.open-meteo.com/v1/archive",
        params={
            "latitude": IGNITION_LATITUDE,
            "longitude": IGNITION_LONGITUDE,
            "start_date": START_DATE,
            "end_date": END_DATE,
            "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m",
            "wind_speed_unit": "ms",
            "timezone": "Asia/Shanghai",
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def fetch_elevations(lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    grid = np.zeros((len(lats), len(lons)), dtype=np.float32)
    points = [(float(lat), float(lng), y, x) for y, lat in enumerate(lats) for x, lng in enumerate(lons)]
    for start in range(0, len(points), 90):
        chunk = points[start : start + 90]
        locations = "|".join(f"{lat:.6f},{lng:.6f}" for lat, lng, _, _ in chunk)
        response = requests.get(
            "https://api.opentopodata.org/v1/srtm30m",
            params={"locations": locations},
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        results = payload.get("results") or []
        if len(results) != len(chunk):
            raise RuntimeError(f"OpenTopoData returned {len(results)} results for {len(chunk)} locations")
        for item, (_, _, y, x) in zip(results, chunk):
            elevation = item.get("elevation")
            grid[y, x] = np.float32(elevation if elevation is not None else np.nan)
    if np.isnan(grid).any():
        mean_value = float(np.nanmean(grid)) if not np.isnan(grid).all() else 1200.0
        grid = np.nan_to_num(grid, nan=mean_value).astype(np.float32)
    return grid


def wind_components(speed: float, direction_deg: float) -> tuple[float, float]:
    radians = math.radians(direction_deg)
    return speed * math.sin(radians), speed * math.cos(radians)


def fuel_grid(lats: np.ndarray, lons: np.ndarray, elevation: np.ndarray) -> np.ndarray:
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    distance = np.hypot((lon_grid - IGNITION_LONGITUDE) / LON_SPAN, (lat_grid - IGNITION_LATITUDE) / LAT_SPAN)
    ridge = (elevation - np.min(elevation)) / max(1.0, float(np.max(elevation) - np.min(elevation)))
    fuel = np.where(distance < 0.28, 2, np.where(ridge > 0.55, 3, 1)).astype(np.int16)
    return fuel


def write_environment(output_dir: Path, weather: dict[str, Any], elevation: np.ndarray, lats: np.ndarray, lons: np.ndarray) -> None:
    hourly = weather["hourly"]
    times = hourly["time"]
    selected_indices = [index for index, text in enumerate(times) if text.endswith(("08:00", "12:00", "16:00", "20:00"))]
    if not selected_indices:
        selected_indices = list(range(0, min(len(times), 24), 6))
    selected_indices = selected_indices[:24]
    time_values = np.array(selected_indices, dtype=np.int64)

    wind_u = np.zeros((len(selected_indices), len(lats), len(lons)), dtype=np.float32)
    wind_v = np.zeros_like(wind_u)
    air_temperature = np.zeros_like(wind_u)
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    slope_factor = (elevation - np.mean(elevation)) / max(1.0, float(np.std(elevation)))
    spatial_variation = 1 + 0.08 * np.sin((lon_grid - IGNITION_LONGITUDE) * 45) + 0.06 * np.cos((lat_grid - IGNITION_LATITUDE) * 55)
    terrain_variation = 1 + 0.04 * np.clip(slope_factor, -2, 2)

    for out_index, weather_index in enumerate(selected_indices):
        speed = float(hourly["wind_speed_10m"][weather_index] or 0)
        direction = float(hourly["wind_direction_10m"][weather_index] or 0)
        u, v = wind_components(speed, direction)
        wind_u[out_index] = np.float32(u * spatial_variation * terrain_variation)
        wind_v[out_index] = np.float32(v * spatial_variation * terrain_variation)
        temp_c = float(hourly["temperature_2m"][weather_index] or 25.0)
        air_temperature[out_index] = np.float32(temp_c + 273.15 - 0.0065 * (elevation - np.mean(elevation)))

    output_dir.mkdir(parents=True, exist_ok=True)
    fuel = fuel_grid(lats, lons, elevation)

    with netCDF4.Dataset(output_dir / "final_input.nc", "w", format="NETCDF4") as dst:
        dst.createDimension("lat", len(lats))
        dst.createDimension("lon", len(lons))
        dst.createDimension("time", len(selected_indices))
        lat_var = dst.createVariable("lat", "f8", ("lat",))
        lon_var = dst.createVariable("lon", "f8", ("lon",))
        time_var = dst.createVariable("time", "i8", ("time",))
        topo_var = dst.createVariable("topography_z", "f4", ("lat", "lon"))
        fuel_var = dst.createVariable("fuel_idx", "i2", ("lat", "lon"))
        wind_u_var = dst.createVariable("windU", "f4", ("time", "lat", "lon"))
        wind_v_var = dst.createVariable("windV", "f4", ("time", "lat", "lon"))
        temp_var = dst.createVariable("air_temperature", "f4", ("time", "lat", "lon"))
        lat_var[:] = lats
        lon_var[:] = lons
        time_var[:] = time_values
        time_var.units = "hours since 2024-06-13 00:00:00"
        topo_var[:] = elevation
        topo_var.units = "m"
        fuel_var[:] = fuel
        fuel_var.units = "1"
        wind_u_var[:] = wind_u
        wind_u_var.units = "m s**-1"
        wind_v_var[:] = wind_v
        wind_v_var.units = "m s**-1"
        temp_var[:] = air_temperature
        temp_var.units = "K"
        dst.title = "Pingyao 2024-06-13 generated environment package"
        dst.source = "Open-Meteo historical weather + OpenTopoData SRTM30m + rule-based fuel layer"

    with netCDF4.Dataset(output_dir / "weather_wind_large.nc", "w", format="NETCDF4") as dst:
        dst.createDimension("valid_time", len(selected_indices))
        dst.createDimension("latitude", len(lats))
        dst.createDimension("longitude", len(lons))
        t = dst.createVariable("valid_time", "i8", ("valid_time",))
        lat = dst.createVariable("latitude", "f8", ("latitude",))
        lon = dst.createVariable("longitude", "f8", ("longitude",))
        u10 = dst.createVariable("u10", "f4", ("valid_time", "latitude", "longitude"))
        v10 = dst.createVariable("v10", "f4", ("valid_time", "latitude", "longitude"))
        t[:] = np.array([weather_index * 3600 for weather_index in selected_indices], dtype=np.int64)
        t.units = "seconds since 2024-06-13 00:00:00"
        lat[:] = lats
        lon[:] = lons
        lat.units = "degrees_north"
        lon.units = "degrees_east"
        u10[:] = wind_u
        v10[:] = wind_v
        u10.units = "m s**-1"
        v10.units = "m s**-1"

    (output_dir / "ignition.txt").write_text(f"{IGNITION_LONGITUDE:.6f} {IGNITION_LATITUDE:.6f}\n", encoding="utf-8")
    metadata = {
        "scene_id": SCENE_ID,
        "location_name": "Pingyao County Zhukeng Township Fengsheng Village Yanzhi Gou area",
        "ignition_longitude": IGNITION_LONGITUDE,
        "ignition_latitude": IGNITION_LATITUDE,
        "coordinate_precision": "approximate_geocoded",
        "weather_source": "Open-Meteo historical weather archive",
        "elevation_source": "OpenTopoData SRTM30m",
        "fuel_source": "rule_based_simulated_fuel_layer",
        "weather_time_range": [times[0], times[-1]],
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "notes": [
            "Weather and elevation are retrieved from public services.",
            "Fuel layer is simulated and replaceable when surveyed fuel data is available.",
            "Ignition coordinate is approximate until an official coordinate is verified.",
        ],
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    output_dir = root / "environment" / "pingyao_20240613"
    weather = fetch_open_meteo()
    lons = np.linspace(IGNITION_LONGITUDE - LON_SPAN / 2, IGNITION_LONGITUDE + LON_SPAN / 2, GRID_SIZE)
    lats = np.linspace(IGNITION_LATITUDE - LAT_SPAN / 2, IGNITION_LATITUDE + LAT_SPAN / 2, GRID_SIZE)
    elevation = fetch_elevations(lats, lons)
    write_environment(output_dir, weather, elevation, lats, lons)
    print(f"Generated {output_dir}")


if __name__ == "__main__":
    main()
