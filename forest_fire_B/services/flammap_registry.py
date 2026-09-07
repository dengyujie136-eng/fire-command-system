from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from services.farsite_parser import parse_farsite_output

logger = logging.getLogger(__name__)


def register_flammap_scene(scene_id: str, results_dir: str) -> dict[str, Any]:
    manifest = parse_farsite_output(scene_id=scene_id, results_dir=results_dir)

    cache_dir = Path("data") / "flammap_cache" / scene_id
    cache_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = cache_dir / "manifest.json"

    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    logger.info("Registered FlamMap scene scene_id=%s cache=%s", scene_id, manifest_path)
    return manifest
