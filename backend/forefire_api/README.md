# ForeFire API Service

This service exposes the real ForeFire simulation API used by the Vue frontend.

## Current Windows Requirement

ForeFire is run through Docker on Windows. Install Docker Desktop first, then run:

```powershell
.\backend\forefire_api\start-forefire-api.ps1
```

The API will be available at:

```txt
http://localhost:5000
```

## Required Input Files

The project-level `environment` folder must contain:

- `final_input.nc`
- `ignition.txt`

`ignition.txt` contains:

```txt
101.269444 28.530278
```

## Health Check

```powershell
Invoke-RestMethod http://localhost:5000/health
```

Expected real mode fields:

```json
{
  "final_input_exists": true,
  "ignition_exists": true,
  "real_result_mode": true
}
```

## Start Simulation

```powershell
Invoke-RestMethod `
  -Uri http://localhost:5000/api/simulate `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"duration":6,"longitude":101.269444,"latitude":28.530278}'
```

In real mode the API does not return fallback geometry. If ForeFire is unavailable or fails, the API returns an error instead of fake fire fronts.

## Archive Current Demo Fire Event

The frontend archive button calls this endpoint. The service stores events in SQLite at `backend/forefire_api/data/fire_events.db` through the Docker volume `/app/data`.

```powershell
Invoke-RestMethod `
  -Uri http://localhost:5000/api/fire/archive `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"event_id":"muli-fire-demo","ignition_point":{"longitude":101.269444,"latitude":28.530278},"forefire_result":{},"agent_result":{},"derived_state":{}}'
```

List archived events:

```powershell
Invoke-RestMethod http://localhost:5000/api/fire/archive
```
