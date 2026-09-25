import unittest

from app.services.spatial_analysis_service import _offset, _point_in_ring, _risk_areas


class SpatialRiskAreaTests(unittest.TestCase):
    def test_high_fire_intensity_drives_high_risk_without_front_override(self):
        center = [-121.38241, 39.87194]
        ring = [
            _offset(center[0], center[1], -0.3, -0.3),
            _offset(center[0], center[1], 0.3, -0.3),
            _offset(center[0], center[1], 0.3, 0.3),
            _offset(center[0], center[1], -0.3, 0.3),
            _offset(center[0], center[1], -0.3, -0.3),
        ]
        feature = {
            "type": "Feature",
            "properties": {
                "elapsed_minutes": 60,
                "sector_radii_km": [0.42] * 72,
                "sector_fire_intensity_kw_m": [2200.0] * 72,
                "environment": {
                    "wind_speed_m_s": 1.0,
                    "wind_direction_deg": 0.0,
                },
                "landscape": {},
            },
            "geometry": {"type": "Polygon", "coordinates": [ring]},
        }
        empty_assets = {
            "settlements": [],
            "targets": [],
            "stations": [],
            "roads": [],
        }

        areas = _risk_areas(feature, None, center, empty_assets, 0.3)
        ignition_areas = [
            area
            for area in areas
            if _point_in_ring(center, area["geometry"]["coordinates"][0])
        ]

        self.assertTrue(ignition_areas)
        self.assertTrue(ignition_areas)
        self.assertTrue(
            any(area["properties"]["risk_level"] == "high" for area in ignition_areas)
        )
        self.assertTrue(
            all(area["properties"]["mean_fire_intensity_kw_m"] == 2200.0 for area in ignition_areas)
        )

    def test_low_fire_intensity_can_produce_low_interior_risk(self):
        center = [-121.38241, 39.87194]
        ring = [
            _offset(center[0], center[1], -0.8, -0.8),
            _offset(center[0], center[1], 0.8, -0.8),
            _offset(center[0], center[1], 0.8, 0.8),
            _offset(center[0], center[1], -0.8, 0.8),
            _offset(center[0], center[1], -0.8, -0.8),
        ]
        feature = {
            "type": "Feature",
            "properties": {
                "elapsed_minutes": 24 * 60,
                "sector_radii_km": [1.0] * 72,
                "sector_fire_intensity_kw_m": [50.0] * 72,
                "environment": {"wind_speed_m_s": 0.0, "wind_direction_deg": 0.0},
                "landscape": {},
            },
            "geometry": {"type": "Polygon", "coordinates": [ring]},
        }
        empty_assets = {"settlements": [], "targets": [], "stations": [], "roads": []}

        areas = _risk_areas(feature, None, center, empty_assets, 0.4)
        interior_areas = [
            area for area in areas
            if area["properties"]["inside_fire_cell_count"] > 0
        ]

        self.assertTrue(interior_areas)
        self.assertTrue(interior_areas)
        self.assertTrue(
            any(area["properties"]["risk_level"] == "low" for area in interior_areas)
        )

    def test_mixed_fire_behavior_produces_high_medium_and_low_zones(self):
        center = [-121.38241, 39.87194]
        ring = [
            _offset(center[0], center[1], -2.0, -2.0),
            _offset(center[0], center[1], 2.0, -2.0),
            _offset(center[0], center[1], 2.0, 2.0),
            _offset(center[0], center[1], -2.0, 2.0),
            _offset(center[0], center[1], -2.0, -2.0),
        ]
        previous = {
            "type": "Feature",
            "properties": {
                "elapsed_minutes": 120,
                "sector_radii_km": [1.1] * 72,
            },
            "geometry": {"type": "Polygon", "coordinates": [ring]},
        }
        feature = {
            "type": "Feature",
            "properties": {
                "elapsed_minutes": 240,
                "sector_radii_km": [2.2] * 72,
                "sector_fire_intensity_kw_m": (
                    [1400.0] * 24 + [500.0] * 24 + [60.0] * 24
                ),
                "environment": {"wind_speed_m_s": 4.0, "wind_direction_deg": 315.0},
                "landscape": {},
            },
            "geometry": {"type": "Polygon", "coordinates": [ring]},
        }
        empty_assets = {"settlements": [], "targets": [], "stations": [], "roads": []}

        areas = _risk_areas(feature, previous, center, empty_assets, 0.5)
        levels = {area["properties"]["risk_level"] for area in areas}

        self.assertEqual({"high", "medium", "low"}, levels)
        self.assertTrue(
            all("mean_estimated_arrival_minute" in area["properties"] for area in areas)
        )



if __name__ == "__main__":
    unittest.main()
