# Third-party wildfire detector

The member-B professional detector uses the upstream project
[`tarunnn12/wildfire-detection`](https://github.com/tarunnn12/wildfire-detection)
as a Git submodule at `third_party/wildfire-detection`.

## Pinned version

- Upstream commit: `c5b9bbc41e4806d521dd4f4d2f22b791914a7ab1`
- Runtime checkpoint: `weights/best.pt`
- Checkpoint size: approximately 148.30 MiB
- SHA-256: `fe2bdd32dc92c06ef2006e87718b6cbec9a4537a01cff79cf445737c83ee4fd7`
- Model classes: `smoke`, `fire`

## Installation

For a fresh clone:

```powershell
git clone --recurse-submodules https://github.com/dengyujie136-eng/fire-command-system.git
cd fire-command-system
git -C third_party/wildfire-detection lfs pull
```

For an existing clone:

```powershell
git pull origin main
git submodule update --init --recursive
git -C third_party/wildfire-detection lfs pull
```

Verify the downloaded checkpoint:

```powershell
Get-FileHash third_party/wildfire-detection/weights/best.pt -Algorithm SHA256
```

Run the detector compose example from the repository root:

```powershell
docker compose -f backend/visual_detector_api/compose.example.yaml up --build
```

To use another local checkpoint, set `WILDFIRE_MODEL_PATH` to its absolute path
before starting Docker Compose.

## Licensing and attribution

The upstream repository does not currently contain a license file. This repository
therefore records only a Git link to the original source and does not vendor or
redistribute its source code or checkpoint. Team members must obtain the model from
the upstream owner and use it only when authorized. Ultralytics and the source
datasets may have additional terms that also apply.
