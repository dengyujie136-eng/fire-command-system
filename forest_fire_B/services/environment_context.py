from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENVIRONMENT_DIR = PROJECT_ROOT / "data" / "environment"


def load_local_environment_context(
    environment_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Build a lightweight environment summary without requiring GIS packages."""
    base = _resolve_environment_dir(environment_dir)
    warnings: list[str] = []
    assets = _environment_assets(base)
    ignition_point = _read_ignition_point(base / "ignition.txt")
    final_input = _inspect_final_input(base / "final_input.nc")

    if not base.exists():
        warnings.append(f"本地环境数据目录不存在：{base}")
    if not assets["final_input_nc"]["exists"]:
        warnings.append("缺少融合后的 final_input.nc，ForeFire 环境输入不完整。")
    if not assets["dem"]["exists"]:
        warnings.append("缺少 DEM 栅格目录 clip_dem，地形坡度约束只能使用火线几何估算。")
    if not assets["fuel"]["exists"]:
        warnings.append("缺少 fuel 栅格目录，燃料类型约束只能使用默认规则。")
    if assets["final_input_nc"]["exists"] and not final_input["readable"]:
        warnings.append("已发现 final_input.nc，但当前运行环境无法解析 HDF5/NetCDF 栅格，路径规划将使用几何兜底代价面。")
    if (assets["dem"]["exists"] or assets["fuel"]["exists"]) and not final_input["readable"]:
        warnings.append("已发现 DEM/Fuel 栅格目录，但未能解析融合栅格，暂未计算坡度和燃料分区统计。")

    return {
        "source": "local_environment_folder",
        "environment_dir": str(base),
        "loaded_at": datetime.now(timezone.utc).isoformat(),
        "ignition_point": ignition_point,
        "assets": assets,
        "dem": {
            "source": str(base / "clip_dem"),
            "available": bool(assets["dem"]["exists"] or final_input["readable"]),
            "status": "ready" if final_input["readable"] else "file_ready_unparsed" if assets["dem"]["exists"] else "missing",
            "summary": "DEM 已通过 final_input.nc 参与 A* 路径搜索，可用于高程剖面和坡度通行代价。"
            if final_input["readable"]
            else "DEM 文件已接入，但当前未能解析栅格，只能使用火场几何兜底规则。",
            "bounds": final_input.get("bounds"),
        },
        "fuel": {
            "source": str(base / "fuel"),
            "available": bool(assets["fuel"]["exists"] or final_input["readable"]),
            "status": "ready" if final_input["readable"] else "file_ready_unparsed" if assets["fuel"]["exists"] else "missing",
            "summary": "燃料指数已通过 final_input.nc 参与 A* 路径搜索，用于提高高可燃区域通行代价。"
            if final_input["readable"]
            else "燃料栅格文件已接入，但当前未能解析栅格，只能使用默认燃料规则。",
            "bounds": final_input.get("bounds"),
        },
        "weather": {
            "source": str(base / "weather_data.nc"),
            "available": bool(assets["weather_data_nc"]["exists"] or final_input["readable"]),
            "status": "ready" if final_input["readable"] else "file_ready_unparsed" if assets["weather_data_nc"]["exists"] else "missing",
            "summary": "风场已通过 final_input.nc 参与路径搜索，用于计算下风向烟羽风险代价。"
            if final_input["readable"]
            else "气象 NetCDF 文件已接入，当前不直接提取风速风向；如请求体提供 weather，将优先使用请求体数值。",
        },
        "forefire_input": {
            "source": str(base / "final_input.nc"),
            "available": assets["final_input_nc"]["exists"],
            "status": "ready" if final_input["readable"] else "file_ready_unparsed" if assets["final_input_nc"]["exists"] else "missing",
            "summary": "final_input.nc 已可解析，包含 DEM、燃料和风场融合栅格。"
            if final_input["readable"]
            else "final_input.nc 是 DEM、燃料和风场融合后的 ForeFire 输入文件。",
            "parsed": final_input["readable"],
            "shape": final_input.get("shape"),
            "bounds": final_input.get("bounds"),
            "variables": final_input.get("variables", []),
        },
        "warnings": warnings,
    }


def build_environment_dem_input(
    request_dem: dict[str, Any] | None,
    environment_context: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if request_dem:
        merged = dict(request_dem)
        if environment_context:
            merged.setdefault("local_environment", environment_context)
        return merged
    if not environment_context:
        return None
    dem = dict(environment_context.get("dem") or {})
    dem["local_environment"] = environment_context
    return dem


def build_environment_weather_input(
    request_weather: dict[str, Any] | None,
    environment_context: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if request_weather:
        merged = dict(request_weather)
        if environment_context:
            merged.setdefault("local_environment_weather", environment_context.get("weather"))
        return merged
    if not environment_context:
        return None
    weather = dict(environment_context.get("weather") or {})
    if not weather.get("available"):
        return None
    return weather


def _resolve_environment_dir(environment_dir: str | Path | None) -> Path:
    if environment_dir is None:
        return DEFAULT_ENVIRONMENT_DIR.resolve()
    path = Path(environment_dir)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def _environment_assets(base: Path) -> dict[str, Any]:
    return {
        "final_input_nc": _file_info(base / "final_input.nc"),
        "weather_data_nc": _file_info(base / "weather_data.nc"),
        "ignition_txt": _file_info(base / "ignition.txt"),
        "dem": _directory_info(base / "clip_dem"),
        "fuel": _directory_info(base / "fuel"),
    }


def _file_info(path: Path) -> dict[str, Any]:
    exists = path.exists() and path.is_file()
    return {
        "path": str(path),
        "exists": exists,
        "size_bytes": path.stat().st_size if exists else 0,
        "updated_at": _mtime(path) if exists else None,
    }


def _directory_info(path: Path) -> dict[str, Any]:
    exists = path.exists() and path.is_dir()
    files = [p for p in path.rglob("*") if p.is_file()] if exists else []
    return {
        "path": str(path),
        "exists": exists,
        "file_count": len(files),
        "size_bytes": sum(p.stat().st_size for p in files),
        "updated_at": max((_mtime(p) for p in files), default=None),
    }


def _mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def _read_ignition_point(path: Path) -> dict[str, float] | None:
    if not path.exists():
        return None
    parts = path.read_text(encoding="utf-8-sig").replace(",", " ").split()
    if len(parts) < 2:
        return None
    try:
        return {"longitude": round(float(parts[0]), 6), "latitude": round(float(parts[1]), 6)}
    except ValueError:
        return None


def _inspect_final_input(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"readable": False}
    try:
        import h5py
        import numpy as np
    except ImportError:
        return {"readable": False}
    try:
        with h5py.File(path, "r") as f:
            required = {"lat", "lon", "topography_z", "fuel_idx", "windU", "windV"}
            if not required.issubset(set(f.keys())):
                return {"readable": False}
            lats = np.asarray(f["lat"][()], dtype=float)
            lons = np.asarray(f["lon"][()], dtype=float)
            return {
                "readable": True,
                "shape": [int(len(lats)), int(len(lons))],
                "bounds": {
                    "west": round(float(np.nanmin(lons)), 6),
                    "south": round(float(np.nanmin(lats)), 6),
                    "east": round(float(np.nanmax(lons)), 6),
                    "north": round(float(np.nanmax(lats)), 6),
                },
                "variables": sorted(required),
            }
    except Exception:
        return {"readable": False}
