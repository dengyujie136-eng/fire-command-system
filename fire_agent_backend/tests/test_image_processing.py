import asyncio
import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from PIL import Image
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.visual_verification.image_processing.errors import (
    DerivativeConflictError,
    SourceImageNotFoundError,
    UnsafeImagePathError,
)
from app.visual_verification.image_processing.persistence import persist_derivative
from app.visual_verification.image_processing.schemas import ImageCropRequest
from app.visual_verification.image_processing.service import ImageProcessingService
from app.visual_verification.models import (
    VisualImageDerivativeRecord,
    VisualVerificationCaseRecord,
)


class ImageProcessingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.data_root = Path(self.temporary.name) / "data"
        self.output_root = Path(self.temporary.name) / "visual-output"
        self.source_directory = self.data_root / "raw" / "imagery"
        self.source_directory.mkdir(parents=True)
        self.service = ImageProcessingService(self.data_root, self.output_root)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def request(self, **updates) -> ImageCropRequest:
        values = {
            "visual_case_id": "case-fire-001",
            "source_asset_id": "asset-fire-001",
            "source_uri": "data://raw/imagery/fire.png",
            "imagery_status": "available",
            "longitude": -121.38241,
            "latitude": 39.87194,
            "is_simulated": True,
        }
        values.update(updates)
        return ImageCropRequest(**values)

    def create_image(self, name: str = "fire.png", size=(2400, 1200)) -> Path:
        path = self.source_directory / name
        Image.new("RGBA", size, (220, 80, 30, 180)).save(path)
        return path

    def test_plain_image_is_rgb_bounded_and_has_preview(self) -> None:
        self.create_image()
        result = self.service.process(self.request())

        self.assertEqual(result.source_kind, "plain_image")
        self.assertEqual(result.source_size.model_dump(), {"width": 2400, "height": 1200})
        self.assertEqual(result.output_size.model_dump(), {"width": 1536, "height": 768})
        self.assertEqual(result.preview_size.model_dump(), {"width": 512, "height": 256})
        self.assertIsNone(result.crs)
        self.assertFalse(result.cache_hit)
        self.assertTrue(result.output_uri.startswith("visual-output://"))
        output = self.service.paths.resolve_output(result.output_uri)
        preview = self.service.paths.resolve_output(result.preview_uri)
        metadata = self.service.paths.resolve_output(result.metadata_uri)
        self.assertTrue(output.is_file())
        self.assertTrue(preview.is_file())
        self.assertTrue(metadata.is_file())
        with Image.open(output) as image:
            self.assertEqual(image.mode, "RGB")

    def test_identical_request_reuses_verified_derivative(self) -> None:
        self.create_image()
        request = self.request()
        first = self.service.process(request)
        second = self.service.process(request)

        self.assertEqual(first.derivative_id, second.derivative_id)
        self.assertFalse(first.cache_hit)
        self.assertTrue(second.cache_hit)

    def test_tampered_output_is_rejected(self) -> None:
        self.create_image()
        request = self.request()
        result = self.service.process(request)
        output = self.service.paths.resolve_output(result.output_uri)
        output.write_bytes(b"tampered")

        with self.assertRaises(DerivativeConflictError):
            self.service.process(request)

    def test_pending_imagery_cannot_enter_processing(self) -> None:
        with self.assertRaises(ValidationError):
            self.request(imagery_status="pending")

    def test_missing_source_has_stable_error(self) -> None:
        with self.assertRaises(SourceImageNotFoundError) as context:
            self.service.process(self.request())
        self.assertEqual(context.exception.code, "source_image_not_found")

    def test_path_traversal_is_rejected(self) -> None:
        outside = Path(self.temporary.name) / "outside.png"
        Image.new("RGB", (32, 32)).save(outside)
        with self.assertRaises(UnsafeImagePathError):
            self.service.process(self.request(source_uri=str(outside)))

    def test_source_and_derivative_roots_are_separate(self) -> None:
        source = self.create_image()
        source_hash = source.read_bytes()
        result = self.service.process(self.request())

        output = self.service.paths.resolve_output(result.output_uri)
        self.assertTrue(output.is_relative_to(self.output_root))
        self.assertFalse(output.is_relative_to(self.data_root))
        self.assertEqual(source.read_bytes(), source_hash)

    def test_output_uri_cannot_escape_derivative_root(self) -> None:
        with self.assertRaises(UnsafeImagePathError):
            self.service.paths.resolve_output("visual-output://../outside.jpg")

    @unittest.skipUnless(
        __import__("importlib").util.find_spec("rasterio") is not None,
        "rasterio is not installed in the host test environment",
    )
    def test_geotiff_candidate_crop_records_spatial_metadata(self) -> None:
        import rasterio
        from rasterio.transform import from_origin

        raster_path = self.source_directory / "test.tif"
        values = np.arange(3 * 200 * 200, dtype=np.float32).reshape(3, 200, 200)
        with rasterio.open(
            raster_path,
            "w",
            driver="GTiff",
            width=200,
            height=200,
            count=3,
            dtype="float32",
            crs="EPSG:32610",
            transform=from_origin(620000, 4420000, 30, 30),
        ) as dataset:
            dataset.write(values)

        result = self.service.process(self.request(
            source_uri="data://raw/imagery/test.tif",
            source_kind="geotiff",
            longitude=-121.577,
            latitude=39.887,
            crop_radius_m=600,
            processing_purpose="pipeline_test",
        ))
        self.assertEqual(result.source_kind, "geotiff")
        self.assertEqual(result.crs, "EPSG:32610")
        self.assertIsNotNone(result.pixel_window)
        self.assertIsNotNone(result.actual_extent_geojson)
        self.assertEqual(result.band_indexes, [1, 2, 3])
        self.assertIn(
            "pipeline_test output is not eligible as visual fire evidence",
            result.warnings,
        )


class ImageDerivativePersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        data_root = Path(self.temporary.name) / "data"
        image_path = data_root / "raw" / "imagery" / "fire.jpg"
        image_path.parent.mkdir(parents=True)
        Image.new("RGB", (640, 480), (200, 70, 20)).save(image_path)
        output_root = Path(self.temporary.name) / "visual-output"
        self.service = ImageProcessingService(data_root, output_root)
        self.result = self.service.process(ImageCropRequest(
            visual_case_id="case-fire-001",
            source_asset_id="asset-fire-001",
            source_uri="data://raw/imagery/fire.jpg",
            longitude=-121.38241,
            latitude=39.87194,
            is_simulated=True,
        ))
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with self.engine.begin() as connection:
            await connection.run_sync(
                lambda sync_connection: Base.metadata.create_all(
                    sync_connection,
                    tables=[
                        VisualVerificationCaseRecord.__table__,
                        VisualImageDerivativeRecord.__table__,
                    ],
                )
            )
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

    async def asyncTearDown(self) -> None:
        await self.engine.dispose()
        self.temporary.cleanup()

    async def test_derivative_persistence_is_idempotent(self) -> None:
        async with self.session_factory() as session:
            session.add(VisualVerificationCaseRecord(
                visual_case_id="case-fire-001",
                source_candidate_id="candidate-fire-001",
                upstream_schema_version="fire.hotspot.candidate.v0.1",
                upstream_status="candidate",
                event_id="dixie_fire_2021",
                event_name="Dixie Fire",
                observed_at=datetime(2021, 7, 14, 9, 11, tzinfo=UTC),
                longitude=-121.38241,
                latitude=39.87194,
                imagery_status="available",
                data_owner={"organization": "fixture"},
                replay_metadata={"is_replay": True},
                product_fields={},
                upstream_payload_hash="0" * 64,
                status="imagery_ready",
                version=1,
                is_simulated=True,
            ))
            await session.flush()
            first, created = await persist_derivative(session, self.result)
            second, created_again = await persist_derivative(session, self.result)

            self.assertTrue(created)
            self.assertFalse(created_again)
            self.assertEqual(first.id, second.id)
            self.assertEqual(
                first.processing_parameters["parameter_sha256"],
                self.result.parameter_sha256,
            )


if __name__ == "__main__":
    unittest.main()
