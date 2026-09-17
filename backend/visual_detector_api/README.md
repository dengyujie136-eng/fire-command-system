# Visual detector API

Independent CPU inference service for the member-B professional fire/smoke detector.
The evaluated third-party model is linked from its original upstream repository as
the `third_party/wildfire-detection` Git submodule. Initialize the submodule before
starting this service, then mount `third_party/wildfire-detection/weights/best.pt` at
`/models/best.pt`. Set `MODEL_PATH` only when a different container path is used.

```powershell
git submodule update --init --recursive
git -C third_party/wildfire-detection lfs pull
```

The expected checkpoint SHA-256 is
`fe2bdd32dc92c06ef2006e87718b6cbec9a4537a01cff79cf445737c83ee4fd7`.
The upstream project currently publishes no license file, so the submodule preserves
source attribution and avoids copying the third-party source or checkpoint into this
repository. Use it only under terms authorized by the upstream owner.

Public business clients must call the fire-agent endpoint rather than this internal
service directly:

`POST /api/visual-verification/candidates/{visual_case_id}/professional-detections`

The backend-only orchestration endpoint runs this detector, Qwen-VL, conservative
fusion and confirmation persistence in one request:

`POST /api/visual-verification/candidates/{visual_case_id}/review`

The conservative default confidence threshold is `0.40`. Callers may explicitly use
`0.25` for known UAV small-target imagery; the response always records the actual
threshold and the SHA-256 of the mounted model.
