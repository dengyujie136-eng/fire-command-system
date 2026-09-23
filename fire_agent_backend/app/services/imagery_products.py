from __future__ import annotations

from pathlib import Path

import rasterio
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT
from rasterio.warp import transform_bounds
from rasterio.windows import Window, from_bounds


ORDER = ("B04", "B03", "B02", "B08", "B12")
DESCRIPTIONS = ("B4", "B3", "B2", "B8", "B12")


def build_multiband_product(
    files: dict[str, str],
    output: Path,
    bbox_wgs84: list[float],
) -> tuple[Path, dict]:
    """Crop aligned real bands to the fire AOI for verification and change analysis."""
    missing = sorted(set(ORDER) - set(files))
    if missing:
        raise ValueError("缺少构建多波段产品所需波段：" + ", ".join(missing))
    output.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(files["B04"]) as reference:
        if reference.crs is None:
            raise ValueError("参考影像缺少 CRS")
        bounds = transform_bounds("EPSG:4326", reference.crs, *bbox_wgs84)
        window = from_bounds(*bounds, transform=reference.transform).round_offsets().round_lengths()
        try:
            window = window.intersection(Window(0, 0, reference.width, reference.height))
        except Exception as exc:
            raise ValueError("影像不覆盖目标火场范围") from exc
        width, height = int(window.width), int(window.height)
        if width < 16 or height < 16 or width * height > 30_000_000:
            raise ValueError("火场影像裁剪范围过小或超过 3000 万像素")
        transform = reference.window_transform(window)
        crs = reference.crs
        dtype = reference.dtypes[0]
    temporary = output.with_suffix(".part.tif")
    try:
        with rasterio.open(
            temporary, "w", driver="GTiff", width=width, height=height,
            count=len(ORDER), dtype=dtype, crs=crs, transform=transform,
            compress="deflate", tiled=True,
        ) as destination:
            for index, band in enumerate(ORDER, start=1):
                with rasterio.open(files[band]) as source:
                    if source.crs is None:
                        raise ValueError(band + " 缺少 CRS")
                    with WarpedVRT(
                        source, crs=crs, transform=transform, width=width,
                        height=height, resampling=Resampling.bilinear,
                    ) as aligned:
                        destination.write(aligned.read(1), index)
                destination.set_band_description(index, DESCRIPTIONS[index - 1])
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    return output, {"width": width, "height": height, "crs": str(crs),
                    "bands": list(DESCRIPTIONS), "bbox_wgs84": bbox_wgs84}
