import asyncio
import unittest

import numpy as np

from app.services.landscape_service import simulate_landcover_from_dem
from app.tools.dynamic_fire_spread import run_dynamic_fire_spread
from app.tools.registry import invoke_agent_tool, list_agent_tool_schemas


def environment_frame(
    minute: int,
    *,
    wind_speed: float,
    wind_direction: float,
    humidity: float = 32,
    fuel_moisture: float = 0.15,
    fire_weather_index: float = 18,
) -> dict:
    return {
        "elapsed_minutes": minute,
        "temperature_c": 30,
        "humidity_percent": humidity,
        "wind_speed_m_s": wind_speed,
        "wind_direction_deg": wind_direction,
        "fuel_moisture": fuel_moisture,
        "fire_weather_index": fire_weather_index,
        "precipitation_mm_h": 0,
        "source": "unit_test",
    }


def landscape_grid(*, elevation_slope_north: float = 0, split_landcover: bool = False) -> dict:
    center_longitude = 101.269444
    center_latitude = 28.530278
    longitudes = [center_longitude + (index - 10) * 0.001 for index in range(21)]
    latitudes = [center_latitude + (index - 10) * 0.001 for index in range(21)]
    elevation = []
    landcover = []
    for latitude in latitudes:
        north_m = (latitude - center_latitude) * 111_000
        elevation.append(
            [2200 + north_m * elevation_slope_north for _ in longitudes]
        )
        landcover.append(
            [
                50 if split_landcover and longitude > center_longitude else 30
                for longitude in longitudes
            ]
        )
    return {
        "longitudes": longitudes,
        "latitudes": latitudes,
        "elevation_m": elevation,
        "landcover_codes": landcover,
        "source": "synthetic_test_landscape",
        "is_simulated": True,
    }


class DynamicFireSpreadToolTests(unittest.TestCase):
    def test_time_varying_environment_is_embedded_in_each_fireline(self):
        result = run_dynamic_fire_spread(
            ignition_longitude=101.269444,
            ignition_latitude=28.530278,
            horizon_minutes=120,
            step_minutes=30,
            environment_timeline=[
                environment_frame(0, wind_speed=2, wind_direction=0),
                environment_frame(60, wind_speed=5, wind_direction=45),
                environment_frame(120, wind_speed=8, wind_direction=100),
            ],
        )

        self.assertEqual(result["engine"], "dynamic_agent_tool")
        self.assertEqual(len(result["steps"]), 3)
        self.assertEqual(result["summary"]["environment_frame_count"], 3)
        self.assertEqual(
            result["summary"]["weather_update_minutes"],
            [0, 60, 120],
        )
        self.assertEqual(result["summary"]["timing_mode"], "weather_updates")
        self.assertEqual(
            result["summary"]["representative_update_interval_minutes"],
            60,
        )
        self.assertEqual(result["summary"]["legacy_step_minutes_requested"], 30)
        self.assertEqual(result["steps"][0]["environment"]["wind_direction_deg"], 0)
        self.assertEqual(result["steps"][-1]["environment"]["wind_direction_deg"], 100)
        self.assertTrue(
            all(step["fireline_geojson"]["properties"]["dynamic_environment"] for step in result["steps"])
        )

    def test_changed_forecast_changes_spread_result(self):
        calm = run_dynamic_fire_spread(
            ignition_longitude=101.269444,
            ignition_latitude=28.530278,
            horizon_minutes=180,
            step_minutes=30,
            environment_timeline=[
                environment_frame(0, wind_speed=1, wind_direction=0),
                environment_frame(180, wind_speed=1, wind_direction=0),
            ],
        )
        changing_wind = run_dynamic_fire_spread(
            ignition_longitude=101.269444,
            ignition_latitude=28.530278,
            horizon_minutes=180,
            step_minutes=30,
            environment_timeline=[
                environment_frame(0, wind_speed=1, wind_direction=0),
                environment_frame(90, wind_speed=7, wind_direction=90),
                environment_frame(180, wind_speed=11, wind_direction=135),
            ],
        )

        self.assertGreater(
            changing_wind["summary"]["final_area_km2"],
            calm["summary"]["final_area_km2"],
        )
        self.assertNotEqual(
            changing_wind["summary"]["spread_direction_deg"],
            calm["summary"]["spread_direction_deg"],
        )

    def test_weather_valid_times_define_outputs_and_infer_horizon(self):
        result = run_dynamic_fire_spread(
            ignition_longitude=101.269444,
            ignition_latitude=28.530278,
            environment_timeline=[
                environment_frame(0, wind_speed=2, wind_direction=315),
                environment_frame(17, wind_speed=3, wind_direction=320),
                environment_frame(43, wind_speed=5, wind_direction=335),
                environment_frame(90, wind_speed=8, wind_direction=10),
            ],
        )

        self.assertEqual(
            [step["elapsed_minutes"] for step in result["steps"]],
            [0, 17, 43, 90],
        )
        self.assertEqual(result["input"]["horizon_minutes"], 90)
        self.assertEqual(result["summary"]["forecast_valid_until_minute"], 90)
        self.assertEqual(
            result["summary"]["representative_update_interval_minutes"],
            17,
        )

    def test_tool_is_available_through_agent_registry(self):
        schemas = list_agent_tool_schemas()
        self.assertEqual(
            schemas[0]["function"]["name"],
            "run_dynamic_fire_spread",
        )
        self.assertIn(
            "initial_fireline_geojson",
            schemas[0]["function"]["parameters"]["properties"],
        )
        self.assertIn(
            "landscape",
            schemas[0]["function"]["parameters"]["properties"],
        )
        result = asyncio.run(
            invoke_agent_tool(
                "run_dynamic_fire_spread",
                {
                    "ignition_longitude": 101.269444,
                    "ignition_latitude": 28.530278,
                    "horizon_minutes": 60,
                    "step_minutes": 30,
                    "environment_timeline": [
                        environment_frame(
                            0,
                            wind_speed=2,
                            wind_direction=315,
                        ),
                        environment_frame(
                            60,
                            wind_speed=6,
                            wind_direction=20,
                        ),
                    ],
                },
            )
        )
        self.assertEqual(result["tool_name"], "run_dynamic_fire_spread")

    def test_changed_wind_continues_from_previous_final_fireline(self):
        initial = run_dynamic_fire_spread(
            ignition_longitude=101.269444,
            ignition_latitude=28.530278,
            horizon_minutes=120,
            step_minutes=30,
            environment_timeline=[
                environment_frame(0, wind_speed=5, wind_direction=0),
                environment_frame(120, wind_speed=7, wind_direction=20),
            ],
        )
        parent_final = initial["steps"][-1]

        continued = run_dynamic_fire_spread(
            ignition_longitude=101.269444,
            ignition_latitude=28.530278,
            horizon_minutes=120,
            step_minutes=30,
            environment_timeline=[
                environment_frame(0, wind_speed=9, wind_direction=90),
                environment_frame(120, wind_speed=12, wind_direction=120),
            ],
            initial_fireline_geojson=parent_final["fireline_geojson"],
        )

        self.assertEqual(continued["summary"]["initial_state"], "fireline")
        self.assertAlmostEqual(
            continued["steps"][0]["area_km2"],
            parent_final["area_km2"],
            places=4,
        )
        self.assertGreater(
            continued["summary"]["final_area_km2"],
            parent_final["area_km2"],
        )
        self.assertNotAlmostEqual(
            continued["summary"]["spread_direction_deg"],
            initial["summary"]["spread_direction_deg"],
            delta=5,
        )

    def test_dem_signed_slope_accelerates_uphill_front(self):
        result = run_dynamic_fire_spread(
            ignition_longitude=101.269444,
            ignition_latitude=28.530278,
            horizon_minutes=90,
            step_minutes=30,
            environment_timeline=[
                environment_frame(0, wind_speed=0, wind_direction=0),
                environment_frame(90, wind_speed=0, wind_direction=0),
            ],
            landscape=landscape_grid(elevation_slope_north=0.32),
        )

        radii = result["steps"][-1]["fireline_geojson"]["properties"]["sector_radii_km"]
        self.assertGreater(radii[0], radii[36])
        self.assertTrue(result["summary"]["terrain_aware"])
        self.assertIsNotNone(
            result["steps"][-1]["fireline_geojson"]["properties"]["landscape"]
        )

    def test_landcover_classes_change_local_spread_rate(self):
        result = run_dynamic_fire_spread(
            ignition_longitude=101.269444,
            ignition_latitude=28.530278,
            horizon_minutes=90,
            step_minutes=30,
            environment_timeline=[
                environment_frame(0, wind_speed=0, wind_direction=0),
                environment_frame(90, wind_speed=0, wind_direction=0),
            ],
            landscape=landscape_grid(split_landcover=True),
        )

        radii = result["steps"][-1]["fireline_geojson"]["properties"]["sector_radii_km"]
        east_radius = radii[18]
        west_radius = radii[54]
        self.assertGreater(west_radius, east_radius)
        self.assertTrue(result["summary"]["landcover_aware"])
        self.assertEqual(
            result["summary"]["landscape"]["source"],
            "synthetic_test_landscape",
        )

    def test_temporary_landcover_uses_worldcover_compatible_codes(self):
        longitudes = [101.20 + index * 0.002 for index in range(31)]
        latitudes = [28.47 + index * 0.002 for index in range(31)]
        elevation = []
        for row in range(31):
            row_values = []
            for column in range(31):
                ridge = 850 * np.exp(
                    -(((row - 23) / 4.5) ** 2 + ((column - 19) / 5.0) ** 2)
                )
                valley = -260 * np.exp(
                    -(((row - 8) / 5.5) ** 2 + ((column - 9) / 4.0) ** 2)
                )
                row_values.append(2100 + row * 42 + column * 11 + ridge + valley)
            elevation.append(row_values)

        landcover = simulate_landcover_from_dem(
            longitudes,
            latitudes,
            elevation,
            np,
        )
        codes = {value for row in landcover for value in row}

        self.assertTrue(codes.issubset({10, 20, 30, 60}))
        self.assertGreaterEqual(len(codes), 3)
        self.assertIn(10, codes)
        self.assertIn(60, codes)

    def test_calm_flat_fire_is_nearly_circular(self):
        result = run_dynamic_fire_spread(
            ignition_longitude=101.269444,
            ignition_latitude=28.530278,
            horizon_minutes=120,
            environment_timeline=[
                environment_frame(0, wind_speed=0, wind_direction=0),
                environment_frame(120, wind_speed=0, wind_direction=0),
            ],
            landscape=landscape_grid(elevation_slope_north=0),
        )
        radii = result["steps"][-1]["fireline_geojson"]["properties"]["sector_radii_km"]
        self.assertLess(max(radii) / min(radii), 1.12)
        self.assertEqual(
            result["summary"]["model"]["wind_model"],
            "focus_based_elliptical_head_flank_backing",
        )

    def test_front_update_never_recedes(self):
        result = run_dynamic_fire_spread(
            ignition_longitude=101.269444,
            ignition_latitude=28.530278,
            horizon_minutes=180,
            environment_timeline=[
                environment_frame(0, wind_speed=6, wind_direction=45),
                environment_frame(90, wind_speed=2, wind_direction=225),
                environment_frame(180, wind_speed=4, wind_direction=90),
            ],
            landscape=landscape_grid(elevation_slope_north=0.15),
        )
        fronts = [
            step["fireline_geojson"]["properties"]["sector_radii_km"]
            for step in result["steps"]
        ]
        for previous, current in zip(fronts, fronts[1:]):
            self.assertTrue(all(new >= old for old, new in zip(previous, current)))



if __name__ == "__main__":
    unittest.main()
