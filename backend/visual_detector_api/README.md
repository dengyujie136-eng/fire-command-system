# Visual detector API

Independent CPU inference service for the member-B professional fire/smoke detector.
The model weight is deliberately not stored in Git. Mount an evaluated checkpoint at
`/models/best.pt` and set `MODEL_PATH` if a different container path is used.

Public business clients must call the fire-agent endpoint rather than this internal
service directly:

`POST /api/visual-verification/candidates/{visual_case_id}/professional-detections`

The backend-only orchestration endpoint runs this detector, Qwen-VL, conservative
fusion and confirmation persistence in one request:

`POST /api/visual-verification/candidates/{visual_case_id}/review`

The conservative default confidence threshold is `0.40`. Callers may explicitly use
`0.25` for known UAV small-target imagery; the response always records the actual
threshold and the SHA-256 of the mounted model.
