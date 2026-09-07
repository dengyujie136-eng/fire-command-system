# fire_agent_backend Implementation And Acceptance Plan

This plan supersedes the earlier full execution-closure plan. The system boundary is now:

```text
early fire detection, assessment, spread prediction, and command decision support
```

The system does not manage full firefighter suppression execution.

## 0. Global Principles

Each feature should be implemented as a real usable unit:

- Database model.
- Backend API.
- Business logic.
- Event/timeline state.
- WebSocket update where relevant.
- Frontend integration where relevant.
- Error handling.
- Acceptance verification.

Do not build temporary fake endpoints that only return hardcoded frontend display data.

## 1. Stage 1: Backend Foundation

Status: completed.

Delivered:

- `fire_agent_backend` directory.
- FastAPI app.
- SQLAlchemy async DB.
- SQLite default, PostgreSQL-ready config.
- Health endpoints.
- System WebSocket.
- Config, errors, logging.

Acceptance:

- `/health` works.
- `/api/system/status` works.
- Database initializes.
- `/ws/system` supports ping/pong.

## 2. Stage 2: Unified Fire Event System

Status: completed.

Delivered:

- `FireEvent`.
- `EventTimeline`.
- Event creation/current/detail/timeline/close APIs.
- `/ws/events/{event_id}`.
- Frontend store support for `event_id`, `event_status`, and timeline.

Acceptance:

- Simulated event can be created.
- Current event can be restored.
- Event detail and timeline can be queried.
- Event WebSocket works.

## 3. Stage 3: Replaceable Processed-Data Simulation Adapters

Status: completed as static time-stamped batch. To be upgraded later to dynamic time-driven simulation.

Delivered:

- `Observation`.
- `EvidenceChain`.
- `FusionResult`.
- `TrustedFirePoint`.
- Simulated satellite detection adapter.
- Simulated four-layer sensor network adapter.
- Simulated evidence fusion adapter.
- Observation/fusion/trusted-fire-point APIs.
- Frontend realtime monitor and multi-source fusion initial integration.

Current limitation:

```text
one call -> generate time-stamped observations -> fusion -> trusted fire point
```

Required upgrade:

```text
simulation clock -> time-ordered observations and changing environment
```

Acceptance already met for stage-three batch mode:

- Observations are stored in DB.
- Evidence chain is stored.
- Fusion result is stored.
- Trusted fire point is stored.
- All records contain backend trace fields.

## 4. Stage 4: Dynamic Scenario Clock And Multi-Location Simulation

Purpose:

Upgrade stage-three simulation from static batch to time-driven scenario playback.

Confirmed locations:

1. Muli, Sichuan:
   - longitude `101.269444`
   - latitude `28.530278`
   - near Li'er Village, Yalongjiang Town, Muli County.

2. Pingyao, Shanxi:
   - near Liujian Gou, southwest of Xigou, Fengsheng Village, Zhukeng Township, Pingyao County.
   - backend should select an approximate vegetation-covered coordinate in that named area.
   - internal `coordinate_precision = approximate`.

Backend deliverables:

- Scenario registry:
  - `muli_lier_village`
  - `pingyao_liujian_gou_early_replay`
- `SimulationClock`.
- `ScenarioDefinition`.
- `EnvironmentSnapshot`.
- time-indexed observation generation.
- automatic playback.
- pause/resume/reset.
- clock APIs:

```text
POST /api/events/{event_id}/clock/start
POST /api/events/{event_id}/clock/pause
POST /api/events/{event_id}/clock/resume
POST /api/events/{event_id}/clock/reset
POST /api/events/{event_id}/clock/step
GET  /api/events/{event_id}/clock
```

WebSocket event types:

```text
clock.started
clock.tick
clock.paused
clock.resumed
clock.reset
observation.created
fusion.updated
trusted_fire_point.confirmed
environment.updated
```

Default time strategy:

Muli:

```text
duration_minutes = 120
time_step_minutes = 5
tick_interval_seconds = 2
```

Pingyao early replay:

```text
window = early decision-support window after initial discovery
0-2 hours:   5 minutes per step
2-12 hours: 15 minutes per step
```

Frontend deliverables:

- Scenario selector with only the two confirmed locations.
- Start/pause/resume/reset controls.
- Timeline playback driven by backend clock.
- Realtime monitor updates over time.
- Multi-source fusion updates over time.

Acceptance:

- Data appears in time order.
- Environment changes over time.
- Fusion confidence changes as sources appear.
- Trusted point is confirmed only after enough evidence appears.
- Frontend does not display simulation labels.

## 5. Stage 5: Fire Spread Prediction

Purpose:

Predict early spread trend for command decision support.

Backend deliverables:

- `SimulationRun`.
- `FireFrontStep`.
- ForeFire tool wrapper.
- Simplified fallback spread model.
- Spread APIs:

```text
POST /api/events/{event_id}/spread-runs
GET  /api/events/{event_id}/spread-runs/latest
GET  /api/spread-runs/{run_id}/steps
```

Policy:

```text
ForeFire first; fallback model if ForeFire fails.
```

Frontend deliverables:

- Fire prediction page reads spread run and fireline steps.
- Show model status in technical diagnostics if needed.
- Do not label frontend data as simulated.

Acceptance:

- Spread can be generated from trusted fire point and environment snapshot.
- Multi-time-step fireline exists.
- Results are usable by Agent.

## 6. Stage 6: LLM Provider Layer And Multi-Agent Decision

Purpose:

Build the actual command decision-support Agent.

Default model during development:

```text
Zhipu GLM-4.6
```

Future switch:

```text
MiMo
```

Backend deliverables:

- `LLMProvider`.
- `ZhipuGLMProvider`.
- `MimoProvider`.
- Environment Assessment Agent.
- Fire Spread Agent.
- Command Decision Agent.
- Resource Recommendation Agent.
- `DecisionRun`.
- `AgentPacket`.

Packets:

```text
situation_packet
risk_packet
plan_packet
recommendation_packet
uav_recommendation_packet
route_recommendation_packet
resource_recommendation_packet
report_packet
```

APIs:

```text
POST /api/events/{event_id}/decision-runs
GET  /api/events/{event_id}/decision-runs/latest
GET  /api/decision-runs/{decision_run_id}/packets
```

Acceptance:

- GLM-4.6 can generate readable command recommendations.
- Critical numbers come from tools or structured data.
- Packets are stored and queryable.
- Provider can be switched by config.

## 7. Stage 7: Route, UAV, And Resource Recommendation Packages

Purpose:

Generate recommendation packages for command staff. This is not real task execution.

Backend deliverables:

- `RoutePlan`.
- `ResourceInventory`.
- `UavAsset`.
- `RecommendationPackage`.
- Route planning tool.
- Resource recommendation tool.
- UAV recommendation tool.

APIs:

```text
GET  /api/events/{event_id}/recommendations/latest
POST /api/events/{event_id}/recommendations/regenerate
```

Recommended package statuses:

```text
draft
recommended
issued_to_command
archived
```

Do not implement firefighter execution states in this stage.

Frontend deliverables:

- Emergency route page displays recommended main/backup/evacuation routes.
- UAV page displays recommended UAV reconnaissance tasks.
- Resource page displays recommended team/material allocations.
- Command center displays recommendation package summary.

Acceptance:

- Recommendations are stored.
- Refreshing frontend restores recommendations from backend.
- No frontend-only route/resource fabrication is used for core results.

## 8. Stage 8: Scenario Disturbance And Recalculation

Purpose:

Support command-side what-if recalculation, not firefighter field feedback.

Disturbance types:

```text
wind_shift
road_unavailable
uav_availability_reduced
protected_target_priority_changed
weather_risk_increased
```

Backend deliverables:

- `ScenarioDisturbance`.
- `RecalculationRun`.
- disturbance APIs:

```text
POST /api/events/{event_id}/disturbances
POST /api/events/{event_id}/recalculate
GET  /api/events/{event_id}/recalculations/latest
```

Flow:

```text
disturbance assumption
  -> updated situation packet
  -> updated spread/risk packet
  -> updated route/resource/UAV recommendations
  -> updated command report
```

Frontend deliverables:

- Controls for what-if assumptions.
- Before/after recommendation comparison.
- Command center recalculation timeline.

Acceptance:

- A wind shift or road-unavailable assumption changes recommendations.
- Results are stored and queryable.
- UI does not call this real field feedback.

Implementation status: completed.

Implemented backend files:

- `fire_agent_backend/app/models/recalculation.py`
  - `ScenarioDisturbance`
  - `RecalculationRun`
- `fire_agent_backend/app/schemas/recalculation.py`
- `fire_agent_backend/app/services/recalculation_service.py`
- `fire_agent_backend/app/routers/recalculations.py`

Implemented APIs:

```text
POST /api/events/{event_id}/disturbances
POST /api/events/{event_id}/recalculate
GET  /api/events/{event_id}/recalculations/latest
```

Implemented behavior:

- `disturbance_type` supports:
  - `wind_shift`
  - `road_unavailable`
  - `uav_availability_reduced`
  - `protected_target_priority_changed`
  - `weather_risk_increased`
- Recalculation reads the latest recommendation package as the before state.
- Recalculation writes a new recommendation package as the after state.
- Route, UAV, and resource child records are persisted for the recalculated package.
- `RecalculationRun` stores `before_snapshot`, `after_snapshot`, `base_package_id`, `new_package_id`, and `change_summary`.
- Event timeline records `disturbance.created` and `recalculation.completed`.
- WebSocket broadcasts disturbance and recalculation events.

Implemented frontend integration:

- `src/api/modules.ts`
  - `recalculationAPI.createDisturbance`
  - `recalculationAPI.recalculate`
  - `recalculationAPI.getLatest`
- `src/stores/fireEventStore.ts`
  - stores `latestRecalculation`
  - applies recalculated recommendation packages into the same backend-driven recommendation state used by route/UAV/resource pages.
- `src/views/CommandCenter.vue`
  - provides command-side what-if controls.
  - displays before/after recommendation summary.
  - does not present the feature as real firefighter field feedback.

Validation result:

- Backend compile passed with `python -m compileall app run.py`.
- Frontend build passed with `npm run build`.
- Runtime validation passed on a temporary backend port:
  - created a `road_unavailable` disturbance.
  - created a recalculation run.
  - changed the recommendation package from a base package to a new package.
  - marked the main evacuation route as blocked/unavailable.
  - restored the latest recalculation through `GET /api/events/{event_id}/recalculations/latest`.
- Database evidence after validation:
  - `scenario_disturbances=1`
  - `recalculation_runs=1`
  - `recommendation_packages=3`
  - `route_plans=9`
  - `uav_assets=6`
  - `resource_inventory=6`

## 9. Stage 9: Early Command Decision Report

Purpose:

Generate a downloadable early decision-support report.

This is not a full disaster suppression/post-disaster report.

Backend deliverables:

- `DecisionReport`.
- report generator.
- report APIs:

```text
POST /api/events/{event_id}/reports
GET  /api/events/{event_id}/reports/latest
GET  /api/reports/{report_id}
GET  /api/reports/{report_id}/download
```

Report sections:

- Event summary.
- Evidence chain.
- Trusted fire point.
- Environment assessment.
- Spread prediction.
- Candidate plans.
- Recommended plan.
- Route/UAV/resource recommendations.
- Scenario disturbance recalculation if any.
- Assumptions and limitations.

Frontend deliverables:

- Disaster/assessment page displays report.
- Command center can download report.

Acceptance:

- Report is generated from stored event data.
- Report can be downloaded.
- Report does not pretend to include actual firefighter execution completion.

Implementation status: completed.

Implemented backend files:

- `fire_agent_backend/app/models/report.py`
  - `DecisionReport`
- `fire_agent_backend/app/schemas/report.py`
- `fire_agent_backend/app/services/report_service.py`
- `fire_agent_backend/app/routers/reports.py`

Implemented APIs:

```text
POST /api/events/{event_id}/reports
GET  /api/events/{event_id}/reports/latest
GET  /api/reports/{report_id}
GET  /api/reports/{report_id}/download
```

Implemented behavior:

- Report generation reads stored backend state:
  - `FireEvent`
  - `Observation`
  - `EvidenceChain`
  - `FusionResult`
  - `TrustedFirePoint`
  - `EnvironmentSnapshot`
  - `SimulationRun`
  - `FireFrontStep`
  - `DecisionRun`
  - `AgentPacket`
  - `RecommendationPackage`
  - `RoutePlan`
  - `UavAsset`
  - `ResourceInventory`
  - latest `RecalculationRun` when present.
- Report content is persisted in `decision_reports`.
- Download endpoints return both Markdown and PDF report files. Frontend download uses PDF by default.
- Report explicitly states that it is an early command decision-support report and does not include actual firefighter execution completion, suppression outcome, or post-disaster official conclusions.

Implemented frontend integration:

- `src/api/modules.ts`
  - `reportAPI.create`
  - `reportAPI.getLatest`
  - `reportAPI.get`
  - `reportAPI.downloadUrl`
- `src/stores/fireEventStore.ts`
  - stores `latestReport`
  - can generate reports and produce a PDF download URL.
- `src/views/DisasterAssess.vue`
  - displays backend report content when available.
  - export button generates/downloads backend report.
- `src/views/CommandCenter.vue`
  - export button generates/downloads backend report.

Validation result:

- Backend compile passed with `python -m compileall app run.py`.
- Frontend build passed with `npm run build`.
- Runtime validation passed on a temporary backend port:
  - generated report `rpt_3450e3c43c5b4ae49d`.
  - report linked to decision run `dec_437485f62e3e4dae88`.
  - report linked to recommendation package `rec_3f9f160a051e436db7`.
  - report linked to recalculation run `rcl_f26f9134d82d4382b0`.
  - Markdown download endpoint returned HTTP 200 and Markdown content length 2122.
  - PDF download endpoint returned HTTP 200 with `Content-Type: application/pdf`.
  - PDF file `rpt_3450e3c43c5b4ae49d.pdf` was generated with 40319 bytes.
  - PDF parsing confirmed a valid `%PDF-` header, 1 page, report title, and the execution-boundary statement.
- Database evidence after validation:
  - `decision_reports=1`

PDF download update:

- Added `GET /api/reports/{report_id}/download.pdf`.
- Frontend report download now uses the PDF endpoint by default.
- `reportlab>=4.2.0` was added to backend requirements.

## 10. Stage 10: Frontend Cleanup And Full Backend Driving

Purpose:

Remove frontend-generated business facts and make pages consume backend state.

Clean up:

- Fixed fire point arrays for core data.
- Random fusion metrics.
- Mock export buttons.
- Frontend-only UAV state changes.
- Frontend-only resource deduction.
- Local task execution fakery.
- Hardcoded event IDs.
- LocalStorage as business source of truth.
- Chinese garbled text.

Acceptance:

- All core pages use the same `event_id`.
- Core business data is loaded from backend.
- Refresh restores backend state.
- Frontend does not display simulation labels.
- Frontend does not fake firefighter execution.

Implementation status: completed.

Implemented frontend cleanup:

- Added `src/components/BackendDrivenPage.vue`.
  - Preserves the Cesium map as the primary visual surface.
  - Loads and refreshes backend event state through `fireEventStore`.
  - Provides one backend-driven workflow for event creation, evidence clock, spread prediction, Agent decision, recommendations, recalculation, report generation, and PDF download.
- Replaced the following former large demo pages with thin wrappers around `BackendDrivenPage.vue`:
  - `src/views/RealtimeMonitor.vue`
  - `src/views/MultiSourceFusion.vue`
  - `src/views/FirePredict.vue`
  - `src/views/EmergencyRoute.vue`
  - `src/views/UAVDispatch.vue`
  - `src/views/ResourceDispatch.vue`
  - `src/views/DisasterAssess.vue`
  - `src/views/CommandCenter.vue`

Result:

- Core pages now share the same active backend `event_id` from `fireEventStore`.
- Core business facts come from backend APIs:
  - event detail and timeline.
  - clock/environment/observations/fusion/trusted fire point.
  - spread runs and fire-front steps.
  - decision runs and Agent packets.
  - recommendation packages and child route/UAV/resource records.
  - recalculation runs.
  - decision reports and PDF download.
- Old frontend-only demo panels, hardcoded route/task/UAV/resource lists, random fusion metrics, fake report export, local task execution, and resource deduction UI were removed from the core pages.
- Frontend labels do not expose simulation mode.
- The UI does not claim actual firefighter execution or extinguishment completion.

Validation result:

- `npm run build` passed.
- Build output confirms former large page chunks are now thin wrappers, with shared backend-driven logic in `BackendDrivenPage`.
- Search over `src/views`, `BackendDrivenPage.vue`, and `fireEventStore.ts` found no remaining `mock`, `Math.random`, old default route/task/mission lists, or fake export strings in the core page implementation.

## 11. Final Acceptance

The final system should:

1. Support the Muli and Pingyao fire locations.
2. Generate processed observations over time.
3. Fuse evidence into trusted fire points.
4. Predict early fire spread.
5. Produce multi-Agent decision-support packets.
6. Recommend routes, UAV actions, and resource preparation.
7. Support what-if recalculation.
8. Generate early command decision reports.
9. Avoid claiming actual firefighting execution or full extinguishment tracking.
10. Keep backend adapters replaceable for future real data.
