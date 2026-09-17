import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import rasterio
from rasterio.transform import from_origin
from rasterio.warp import transform

from app.tools.raster_fire_spread import _advance_interval, run_raster_fire_spread
from app.tools.registry import list_agent_tool_schemas


def weather(minute: int, direction: float = 270) -> dict:
    return {
        "elapsed_minutes": minute,
        "temperature_c": 30,
        "humidity_percent": 18,
        "wind_speed_m_s": 6,
        "wind_direction_deg": direction,
        "fuel_moisture": 0.07,
        "fire_weather_index": 26,
        "precipitation_mm_h": 0,
        "source": "unit_test_meteorological_weather",
    }


class RasterFireSpreadToolTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temporary.name)
        self.longitude = -121.38241
        self.latitude = 39.87194
        center_x, center_y = transform(
            "EPSG:4326",
            "EPSG:32610",
            [self.longitude],
            [self.latitude],
        )
        self.transform = from_origin(center_x[0] - 5000, center_y[0] + 5000, 100, 100)
        rows, cols = np.indices((100, 100))
        elevation = 1000 + cols * 2.0
        self._write("dem.tif", elevation.astype("float32"))
        self._write("fuel.tif", np.full((100, 100), 10, dtype="uint8"))
        barrier = np.full((100, 100), 10, dtype="uint8")
        barrier[:, 55:58] = 80
        self._write("fuel_barrier.tif", barrier)

    def tearDown(self):
        self.temporary.cleanup()

    def _write(self, name: str, values: np.ndarray) -> None:
        with rasterio.open(
            self.data_dir / name,
            "w",
            driver="GTiff",
            width=values.shape[1],
            height=values.shape[0],
            count=1,
            dtype=values.dtype,
            crs="EPSG:32610",
            transform=self.transform,
        ) as dataset:
            dataset.write(values, 1)

    def _run(self, fuel_name: str, **parameters) -> dict:
        with patch(
            "app.tools.raster_fire_spread._safe_data_path",
            side_effect=lambda value: self.data_dir / value,
        ):
            return run_raster_fire_spread(
                ignition_longitude=self.longitude,
                ignition_latitude=self.latitude,
                environment_timeline=[weather(0), weather(180)],
                dem_path="dem.tif",
                landcover_path=fuel_name,
                raster_resolution_m=100,
                simulation_buffer_km=4.9,
                initial_radius_m=150,
                wind_direction_convention="meteorological_from",
                **parameters,
            )

    def test_meteorological_wind_is_converted_to_spread_direction(self):
        result = self._run("fuel.tif")
        frame = result["input"]["environment_timeline"][0]
        self.assertEqual(frame["source_wind_direction_deg"], 270)
        self.assertEqual(frame["wind_direction_deg"], 90)
        self.assertEqual(result["engine"], "raster_agent_tool")
        self.assertIn(result["steps"][-1]["fireline_geojson"]["geometry"]["type"], {"Polygon", "MultiPolygon"})
        properties = result["steps"][-1]["fireline_geojson"]["properties"]
        self.assertEqual(len(properties["sector_fire_intensity_kw_m"]), 72)
        self.assertGreater(properties["fire_intensity"]["max_kw_m"], 0)
        self.assertIsNone(result["steps"][0]["fireline_geojson"]["properties"]["propagation_interval"])
        self.assertEqual(properties["propagation_interval"]["from_minute"], 0)
        self.assertEqual(properties["propagation_interval"]["to_minute"], 180)
        self.assertEqual(
            properties["weather_used_for_previous_interval"]["elapsed_minutes"],
            0,
        )

    def test_non_burnable_worldcover_barrier_reduces_spread(self):
        open_fuel = self._run("fuel.tif")
        barrier = self._run("fuel_barrier.tif")
        self.assertLess(
            barrier["summary"]["final_area_km2"],
            open_fuel["summary"]["final_area_km2"],
        )
        self.assertTrue(barrier["summary"]["terrain_aware"])
        self.assertTrue(barrier["summary"]["landcover_aware"])

    def test_flat_no_wind_spreads_to_right_and_downhill_side(self):
        burned = np.zeros((15, 15), dtype=bool)
        burned[7, 7] = True
        grid = {
            "elevation": np.full((15, 15), 1000.0),
            "landcover": np.full((15, 15), 10, dtype="int16"),
            "resolution_m": 100.0,
        }
        result = _advance_interval(grid=grid, burned=burned, frame=weather(0, direction=0), duration_minutes=120, suppression_factor=0)
        self.assertTrue(result[7, 8], "east/right propagation should remain possible")
        self.assertTrue(result[8, 7], "south/down propagation should remain possible")

    def test_terrain_adjustment_is_bounded(self):
        burned = np.zeros((15, 15), dtype=bool)
        burned[7, 7] = True
        elevation = np.full((15, 15), 1000.0)
        elevation[:7, :] = 1500.0
        grid = {
            "elevation": elevation,
            "landcover": np.full((15, 15), 10, dtype="int16"),
            "resolution_m": 100.0,
        }
        result = _advance_interval(grid=grid, burned=burned, frame=weather(0, direction=0), duration_minutes=120, suppression_factor=0)
        self.assertTrue(result[7, 8])
        self.assertTrue(result[8, 7])

    def test_agent_registry_exposes_raster_tool(self):
        names = [item["function"]["name"] for item in list_agent_tool_schemas()]
        self.assertIn("run_raster_fire_spread", names)

    def test_explicit_calibration_parameters_change_spread_and_are_recorded(self):
        baseline = self._run("fuel.tif")
        faster = self._run(
            "fuel.tif",
            spread_rate_multiplier=1.2,
            wind_influence_multiplier=1.25,
            terrain_influence_multiplier=0.75,
        )
        self.assertGreater(faster["summary"]["final_area_km2"], baseline["summary"]["final_area_km2"])
        self.assertEqual(
            faster["input"]["model_parameters"],
            {
                "spread_rate_multiplier": 1.2,
                "wind_influence_multiplier": 1.25,
                "terrain_influence_multiplier": 0.75,
            },
        )
        self.assertTrue(
            faster["steps"][-1]["fireline_geojson"]["properties"]["fire_intensity"]["calibrated"]
        )

    def test_extra_checkpoint_does_not_change_weather_or_final_spread(self):
        baseline = self._run("fuel.tif")
        checkpointed = self._run("fuel.tif", checkpoint_minutes=[90])
        self.assertEqual(
            [step["elapsed_minutes"] for step in checkpointed["steps"]],
            [0, 90, 180],
        )
        self.assertEqual(
            checkpointed["summary"]["final_area_km2"],
            baseline["summary"]["final_area_km2"],
        )
        self.assertEqual(
            checkpointed["input"]["weather_update_minutes"],
            [0, 180],
        )



if __name__ == "__main__":
    unittest.main()
