import importlib.util
import tempfile
import unittest
from pathlib import Path

import numpy as np

from app.visual_verification.image_processing.errors import InvalidRasterBandError
from app.visual_verification.raster_change import RasterChangeAnalyzer
from app.visual_verification.schemas import RemoteSensingAnalysisType


RASTERIO_AVAILABLE = importlib.util.find_spec("rasterio") is not None


@unittest.skipUnless(RASTERIO_AVAILABLE, "rasterio is not installed")
class RasterChangeAnalyzerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.source_root = root / "data"
        self.output_root = root / "visual-output"
        self.source_root.mkdir()
        self.analyzer = RasterChangeAnalyzer(self.source_root, self.output_root)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_raster(
        self,
        name: str,
        *,
        include_b12: bool,
        changed: bool,
        omit_b8: bool = False,
    ) -> None:
        import rasterio
        from rasterio.transform import from_origin

        descriptions = ["B2", "B3", "B4"]
        if not omit_b8:
            descriptions.append("B8")
        if include_b12:
            descriptions.append("B12")
        values = np.zeros((len(descriptions), 30, 30), dtype=np.int16)
        constants = {"B2": 1000, "B3": 1500, "B4": 2000, "B8": 8000, "B12": 2000}
        for index, description in enumerate(descriptions):
            values[index] = constants[description]
        if changed:
            for description, replacement in (
                ("B4", 2500),
                ("B8", 3000),
                ("B12", 6000),
            ):
                if description in descriptions:
                    values[descriptions.index(description), 10:20, 10:20] = replacement

        with rasterio.open(
            self.source_root / name,
            "w",
            driver="GTiff",
            width=30,
            height=30,
            count=len(descriptions),
            dtype="int16",
            crs="EPSG:32610",
            transform=from_origin(600000, 4400000, 10, 10),
            nodata=0,
        ) as dataset:
            dataset.write(values)
            for index, description in enumerate(descriptions, start=1):
                dataset.set_band_description(index, description)

    def analyze(self, *, include_b12: bool, target_geometry=None):
        self.write_raster("before.tif", include_b12=include_b12, changed=False)
        self.write_raster("after.tif", include_b12=include_b12, changed=True)
        return self.analyzer.analyze(
            event_id="generic_fire_event",
            analysis_type=RemoteSensingAnalysisType.BURNED_AREA,
            before_asset_id="before-asset",
            before_uri="data://before.tif",
            after_asset_id="after-asset",
            after_uri="data://after.tif",
            threshold=0.2,
            minimum_region_pixels=4,
            is_simulated=True,
            target_geometry_wgs84=target_geometry,
        )

    def test_dndvi_fallback_outputs_geometry_area_and_artifacts(self) -> None:
        result = self.analyze(include_b12=False)

        self.assertEqual(result.method, "dndvi_threshold_v1")
        self.assertEqual(result.changed_pixel_count, 100)
        self.assertEqual(result.valid_pixel_count, 900)
        self.assertAlmostEqual(result.area_hectares, 1.0)
        self.assertEqual(result.area_geometry_wgs84["type"], "MultiPolygon")
        self.assertTrue(result.area_geometry_wgs84["coordinates"])
        self.assertIn("B12 is unavailable", result.warnings[0])
        self.assertEqual(
            set(result.output_uris),
            {
                "before_rgb",
                "after_rgb",
                "before_nir",
                "after_nir",
                "before_index",
                "after_index",
                "change_index",
                "changed_area_mask",
                "area_geojson",
            },
        )
        for uri in result.output_uris.values():
            self.assertTrue(self.analyzer.paths.resolve_output(uri).is_file())

    def test_b12_prefers_dnbr(self) -> None:
        result = self.analyze(include_b12=True)

        self.assertEqual(result.method, "dnbr_threshold_v1")
        self.assertEqual(result.changed_pixel_count, 100)
        self.assertEqual(result.warnings, [])

    def test_target_polygon_limits_change_statistics(self) -> None:
        from rasterio.warp import transform_geom

        projected_geometry = {
            "type": "Polygon",
            "coordinates": [[
                [600100, 4399900],
                [600150, 4399900],
                [600150, 4399800],
                [600100, 4399800],
                [600100, 4399900],
            ]],
        }
        target_geometry = transform_geom(
            "EPSG:32610",
            "EPSG:4326",
            projected_geometry,
        )

        result = self.analyze(
            include_b12=False,
            target_geometry=target_geometry,
        )

        self.assertEqual(result.changed_pixel_count, 50)
        self.assertAlmostEqual(result.area_hectares, 0.5)

    def test_missing_required_band_is_rejected(self) -> None:
        self.write_raster(
            "before.tif",
            include_b12=False,
            changed=False,
            omit_b8=True,
        )
        self.write_raster("after.tif", include_b12=False, changed=True)

        with self.assertRaisesRegex(InvalidRasterBandError, "B8"):
            self.analyzer.analyze(
                event_id="generic_fire_event",
                analysis_type=RemoteSensingAnalysisType.TEMPORAL_CHANGE,
                before_asset_id="before-asset",
                before_uri="data://before.tif",
                after_asset_id="after-asset",
                after_uri="data://after.tif",
                threshold=None,
                minimum_region_pixels=4,
                is_simulated=True,
            )


if __name__ == "__main__":
    unittest.main()
