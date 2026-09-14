class ImageProcessingError(RuntimeError):
    """Base error with a stable machine-readable code."""

    code = "image_processing_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class UnsafeImagePathError(ImageProcessingError):
    code = "unsafe_image_path"


class SourceImageNotFoundError(ImageProcessingError):
    code = "source_image_not_found"


class ImageryNotReadyError(ImageProcessingError):
    code = "imagery_not_ready"


class UnsupportedImageError(ImageProcessingError):
    code = "unsupported_image"


class RasterBackendUnavailableError(ImageProcessingError):
    code = "raster_backend_unavailable"


class MissingRasterCrsError(ImageProcessingError):
    code = "missing_raster_crs"


class UnsupportedRasterCrsError(ImageProcessingError):
    code = "unsupported_raster_crs"


class CandidateOutsideRasterError(ImageProcessingError):
    code = "candidate_outside_raster"


class InvalidRasterBandError(ImageProcessingError):
    code = "invalid_raster_band"


class EmptyRasterCropError(ImageProcessingError):
    code = "empty_raster_crop"


class DerivativeConflictError(ImageProcessingError):
    code = "derivative_conflict"


class VisualCaseNotFoundError(ImageProcessingError):
    code = "visual_case_not_found"


class VisualAssetNotFoundError(ImageProcessingError):
    code = "visual_asset_not_found"
