import hashlib
import io
import os
import time
from functools import lru_cache
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

os.environ["YOLO_CONFIG_DIR"] = "/tmp"
from ultralytics import YOLO


MODEL_PATH = Path(os.getenv("MODEL_PATH", "/models/best.pt"))
MODEL_NAME = os.getenv("MODEL_NAME", "wildfire-detection-yolov8m")
MAX_IMAGE_BYTES = int(os.getenv("MAX_IMAGE_BYTES", str(10 * 1024 * 1024)))
_model = None
_model_lock = Lock()

app = FastAPI(title="Wildfire Professional Detector", version="0.1.0")


@lru_cache(maxsize=1)
def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                if not MODEL_PATH.is_file():
                    raise RuntimeError(f"Model file not found: {MODEL_PATH}")
                _model = YOLO(str(MODEL_PATH))
    return _model


@app.get("/health")
def health() -> dict:
    return {
        "ok": MODEL_PATH.is_file(),
        "model_name": MODEL_NAME,
        "model_path_configured": MODEL_PATH.is_file(),
    }


@app.post("/detect")
async def detect(
    images: list[UploadFile] = File(...),
    confidence_threshold: float = Form(0.40, ge=0.05, le=0.95),
    image_size: int = Form(640, ge=320, le=1280),
) -> dict:
    prepared = []
    for upload in images:
        content = await upload.read(MAX_IMAGE_BYTES + 1)
        if len(content) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail="Image exceeds configured byte limit")
        try:
            image = Image.open(io.BytesIO(content))
            image.load()
            prepared.append((upload.filename or "image", image.convert("RGB")))
        except (UnidentifiedImageError, OSError) as exc:
            raise HTTPException(status_code=422, detail="Unsupported or corrupt image") from exc

    started = time.perf_counter()
    try:
        predictions = _get_model().predict(
            source=[item[1] for item in prepared],
            conf=confidence_threshold,
            imgsz=image_size,
            device="cpu",
            verbose=False,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    detections = []
    for (image_id, _image), prediction in zip(prepared, predictions, strict=True):
        if prediction.boxes is None:
            continue
        for box in prediction.boxes:
            class_id = int(box.cls.item())
            class_name = str(prediction.names[class_id]).lower()
            if class_name not in {"fire", "smoke"}:
                continue
            detections.append({
                "image_id": image_id,
                "class_id": class_id,
                "class_name": class_name,
                "confidence": round(float(box.conf.item()), 6),
                "bbox_xyxy": [round(float(value), 2) for value in box.xyxy[0].tolist()],
            })
    return {
        "model_name": MODEL_NAME,
        "model_version": "ultralytics-8.4.39-yolov8m",
        "model_sha256": _sha256(MODEL_PATH),
        "confidence_threshold": confidence_threshold,
        "image_size": image_size,
        "detections": detections,
        "duration_ms": max(0, int((time.perf_counter() - started) * 1000)),
    }
