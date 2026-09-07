# Xinghuo Backend Realization Reference

This document records the confirmed backend scope for `fire_agent_backend`. It is the reference for later implementation and acceptance.

## 1. Correct System Boundary

The system is now formally scoped as:

```text
Early fire detection, situation assessment, spread prediction, and command decision support.
```

It is not a full firefighting execution system.

The Agent starts working after an initial fire point is detected. It should help the command side answer:

- Is this fire point credible?
- What is the current environmental situation?
- Where may the fire spread?
- Which protected targets are at risk?
- What response level and command strategy are recommended?
- Which UAV, route, resource, and team suggestions should be prepared?
- How would the plan change under assumed scenario disturbances?

The system does not claim to:

- Track firefighters through the full suppression process.
- Receive real field execution feedback from firefighters.
- Manage actual acceptance, execution, blocked, completed, or failed task states from field teams.
- Simulate the entire fire until extinguishment.
- Produce a full post-disaster official loss report based on actual suppression records.

## 2. What Still Uses Simulation

The following upstream capabilities are currently simulated because there is no real hardware or real data source:

- Four-layer sensing network:
  - UAV processed observations.
  - Watchtower processed observations.
  - Canopy-layer device processed observations.
  - Ground sensor processed observations.
- Multi-source probability cross-verification:
  - Evidence chain.
  - Source reliability.
  - Evidence weight.
  - Fusion confidence.
  - Trusted fire point.
- Three-stage multi-source satellite fire detection:
  - Wide-area screening.
  - Precision filtering.
  - Temporal verification.

Simulation adapters must output the same structured data that future real adapters will output. Future real adapters should replace simulation adapters without rewriting the Agent or main workflow.

The frontend must not display "simulation data" labels. The backend should still keep engineering fields such as:

```json
{
  "is_simulated": true,
  "data_source_mode": "simulation"
}
```

## 3. Confirmed Fire Locations

Current simulation should only use these two ignition locations.

### 3.1 Muli, Sichuan

Location:

```text
Near Li'er Village, Yalongjiang Town, Muli Tibetan Autonomous County, Liangshan Prefecture, Sichuan Province.
```

Coordinate:

```text
Longitude: 101.269444
Latitude:  28.530278
Original DMS: 101 deg 16 min 10 sec E, 28 deg 31 min 49 sec N
```

Purpose:

```text
Short early-response demonstration scenario.
```

### 3.2 Pingyao, Shanxi

Location:

```text
Near Liujian Gou, southwest of Xigou, Fengsheng Village, Zhukeng Township, Pingyao County, Jinzhong City, Shanxi Province.
```

Coordinate:

```text
To be selected by the system within the named vegetation-covered area.
```

Backend should mark coordinate precision internally as:

```text
coordinate_precision = approximate
```

The frontend should not display this as simulation or uncertainty unless the user asks for technical diagnostics.

Purpose:

```text
Historical early-response replay scenario based on the user's known fire timing.
```

Important boundary:

The Shanxi event may have lasted from June 13 to June 18, but this Agent should not replay the entire suppression process. It should replay the early decision-support window after initial discovery.

## 4. Dynamic Simulation Requirement

The current stage-three implementation is a static time-stamped batch:

```text
one call -> observations -> evidence chain -> fusion result -> trusted fire point
```

The final design must evolve into a dynamic time-driven simulation engine:

```text
scenario clock tick
  -> environment snapshot changes
  -> processed observations appear over time
  -> fusion confidence updates
  -> trusted fire point is confirmed
  -> spread prediction updates
  -> Agent produces decision packets
  -> command-side plan suggestions update
```

Simulation must support:

- Multiple location scenarios.
- Default automatic trusted fire point generation.
- Data appearing in time order.
- Automatic playback.
- Pause, resume, and reset.
- Different confidence strengths:
  - high-confidence direct confirmation.
  - low-confidence needs-review case.
  - false-alarm review case.
- Scenario disturbances:
  - wind shift.
  - road unavailable assumption.
  - reduced UAV availability.
  - protected target priority escalation.

Scenario disturbances are not firefighter field feedback. They are command-side what-if assumptions.

## 5. Time Window and Time Step Policy

The time step is the interval between two generated simulation snapshots.

It should be chosen based on:

- Fire change speed.
- Data source update frequency.
- Total replay duration.
- Demo playback readability.
- Backend and frontend processing cost.

### 5.1 Short Demo Scenario

For Muli:

```text
duration_minutes = 120
time_step_minutes = 5
tick_interval_seconds = 2
```

This gives:

```text
120 / 5 = 24 snapshots
24 * 2 seconds = about 48 seconds of playback
```

### 5.2 Historical Early-Response Replay

For Pingyao:

The full historical fire may have lasted multiple days, but the system should replay the early decision-support window, not the full extinguishment process.

Suggested initial replay window:

```text
0-12 hours after initial discovery
```

Suggested variable time steps:

```text
0-2 hours:   5 minutes per step
2-12 hours: 15 minutes per step
```

If the user later asks for a longer strategic replay, use multi-scale steps, but keep it clearly framed as decision-support replay, not full suppression execution.

## 6. Agent Definition

The Agent is:

```text
A tool-calling multi-agent decision support system based on structured processed data.
```

LLM role:

- Understand the command task.
- Orchestrate tools.
- Coordinate Agent outputs.
- Explain results.
- Generate command-side decision reports.

Tool role:

- GIS analysis.
- Environment assessment.
- Simplified spread prediction.
- ForeFire invocation where available.
- Route planning.
- Resource recommendation.
- Safety rule checking.
- Decision report generation.

Rule:

The LLM must not invent critical numeric facts. Key values must come from structured data or tool outputs.

## 7. Multi-Agent Responsibilities

### 7.1 Environment Assessment Agent

Inputs:

- Trusted fire point.
- Weather and wind.
- Terrain and DEM.
- Fuel and vegetation.
- Roads and water sources.
- Protected targets.

Outputs:

- Situation packet.
- Environmental constraints.
- Risk factors.
- Data quality notes.

### 7.2 Fire Spread Agent

Inputs:

- Situation packet.
- Current fire point or fireline.
- Wind speed and direction.
- Slope and fuel.
- ForeFire availability.

Outputs:

- Risk packet.
- Multi-time-step fireline.
- Spread direction.
- Impact area.
- High-risk areas.

Policy:

```text
ForeFire first.
Fallback simplified spread model if ForeFire is unavailable or fails.
```

### 7.3 Command Decision Agent

Inputs:

- Situation packet.
- Risk packet.
- Emergency rules.
- Protected targets.
- Resource context.

Outputs:

- Candidate command plans.
- Plan ranking.
- Recommended plan.
- Risk explanation.
- Command recommendation.

### 7.4 Resource Dispatch Agent

This Agent generates command-side recommendations, not real execution orders.

Inputs:

- Recommended command plan.
- Available teams.
- Equipment.
- Vehicles.
- UAVs.
- Roads.
- Water sources.
- Safety constraints.

Outputs:

- Task recommendation package.
- Suggested team allocation.
- Suggested material allocation.
- Main route.
- Backup route.
- Evacuation route.
- UAV recommendation.
- Priority explanation.

## 8. Task Package Boundary

The system should generate:

```text
recommended_tasks
dispatch_plan
uav_plan
route_plan
resource_plan
evacuation_plan
```

These are command-side suggestions.

Recommended statuses:

```text
draft
recommended
issued_to_command
archived
```

Do not implement or claim firefighter execution states such as:

```text
accepted
executing
blocked
completed
failed
```

unless a real execution-side system is later added.

## 9. Scenario Disturbance and Recalculation

The system may support what-if disturbances:

- Wind direction changes.
- Main road assumed unavailable.
- UAV availability reduced.
- Protected target priority raised.
- Weather risk increased.

These disturbances should trigger:

```text
new assumption packet
  -> updated environment assessment
  -> updated spread/risk assessment
  -> updated route/resource recommendation
  -> updated command-side decision report
```

Do not call this firefighter feedback. It is command-side scenario recalculation.

## 10. Report Boundary

The report should be:

```text
early command decision report
```

Not:

```text
full post-disaster official suppression report
```

The report should include:

- Event summary.
- Data sources and evidence chain.
- Trusted fire point confirmation.
- Environment assessment.
- Fire spread prediction.
- Candidate command plans.
- Recommended plan.
- Route/resource/UAV recommendations.
- Scenario disturbance recalculation if used.
- Assumptions and limitations.

## 11. Frontend Coverage

The new backend should support all current frontend modules:

- Realtime fire monitoring.
- Multi-source fusion.
- Fire spread prediction.
- Emergency route planning.
- UAV dispatch recommendation.
- Resource dispatch recommendation.
- Disaster/impact assessment for early decision support.
- Command center.
- Agent decision view.

Frontend should consume backend events, observations, fusion results, simulation outputs, Agent packets, recommendation packages, and reports.

Frontend should not present backend simulation labels.

## 12. Confirmed Q&A Summary

- Q: Should the backend be real while upstream hardware data is missing?
  - A: Yes. Use replaceable simulation adapters, not frontend fake data.
- Q: Does backend receive raw satellite/video/hardware data?
  - A: No. It receives processed structured results.
- Q: What is the Agent?
  - A: A tool-calling multi-agent decision-support system.
- Q: Should simulation support multiple scenarios?
  - A: Yes, multiple fire locations/scenarios.
- Q: Should fire points be generated automatically?
  - A: Yes, default automatic generation.
- Q: Should data appear over time?
  - A: Yes, in time order.
- Q: Should frontend label data as simulated?
  - A: No.
- Q: Should confidence strength and low-confidence/false-alarm cases exist?
  - A: Yes.
- Q: Does Agent participate in actual firefighting execution?
  - A: No.
- Q: Should we implement firefighter task execution and feedback?
  - A: No. Generate recommendation packages and support what-if recalculation only.

## 13. Acceptance Criteria

Later code should satisfy:

1. `fire_agent_backend` remains the formal backend.
2. Missing upstream data is provided by replaceable simulation adapters.
3. Simulation supports the Muli and Pingyao locations.
4. Simulation is time-driven, not only static batch data.
5. The frontend does not show simulation labels.
6. The backend keeps engineering trace fields such as `is_simulated`.
7. The Agent produces situation, risk, plan, recommendation, and report packets.
8. Task outputs are recommendation packages, not real firefighter execution records.
9. Scenario disturbance recalculation is supported without pretending to receive field feedback.
10. Reports are early command decision reports, not full suppression/post-disaster reports.

## 14. Stage 8 Backend Update: Command-Side Recalculation

Stage 8 is implemented as command-side what-if recalculation. It is not firefighter field feedback and does not create execution-state records for rescue teams.

New persisted tables:

- `scenario_disturbances`
  - stores the command-side assumption.
  - key fields: `disturbance_id`, `event_id`, `disturbance_type`, `assumption`, `parameters`, `created_by`, `status`.
- `recalculation_runs`
  - stores the recalculation result.
  - key fields: `recalculation_id`, `event_id`, `disturbance_id`, `base_package_id`, `new_package_id`, `before_snapshot`, `after_snapshot`, `change_summary`.

Supported disturbance types:

```text
wind_shift
road_unavailable
uav_availability_reduced
protected_target_priority_changed
weather_risk_increased
```

Implemented APIs:

```text
POST /api/events/{event_id}/disturbances
POST /api/events/{event_id}/recalculate
GET  /api/events/{event_id}/recalculations/latest
```

Runtime flow:

```text
command-side assumption
  -> ScenarioDisturbance
  -> latest RecommendationPackage as before state
  -> disturbance rule application
  -> new RecommendationPackage with RoutePlan/UavAsset/ResourceInventory child records
  -> RecalculationRun with before/after snapshots
  -> event timeline and WebSocket notification
```

Acceptance evidence:

- `road_unavailable` changes recommendations by marking the main evacuation route as blocked/unavailable and promoting backup logic.
- Results are stored in `scenario_disturbances`, `recalculation_runs`, and recalculated recommendation tables.
- `GET /api/events/{event_id}/recalculations/latest` restores the latest recalculation.
- Frontend command center exposes the function as "情景重算", not real field feedback.

## 15. Stage 9 Backend Update: Early Command Decision Report

Stage 9 is implemented as a persisted early command decision-support report. It is not a full disaster suppression report, not a post-disaster investigation report, and not a record of actual firefighter execution completion.

New persisted table:

- `decision_reports`
  - stores generated reports.
  - key fields: `report_id`, `event_id`, `decision_run_id`, `recommendation_package_id`, `recalculation_id`, `title`, `summary`, `sections`, `content_markdown`.

Implemented APIs:

```text
POST /api/events/{event_id}/reports
GET  /api/events/{event_id}/reports/latest
GET  /api/reports/{report_id}
GET  /api/reports/{report_id}/download
GET  /api/reports/{report_id}/download.pdf
```

Report data sources:

- event summary.
- observation and evidence chain.
- fusion result and trusted fire point.
- latest environment snapshot.
- latest spread prediction and fire-front steps.
- latest decision run and Agent packets.
- latest recommendation package with route/UAV/resource child records.
- latest command-side recalculation, when present.

Report boundary:

- The report includes assumptions and limitations.
- The report states that it does not include actual firefighter execution completion, suppression outcome, or post-disaster official conclusions.
- `GET /api/reports/{report_id}/download` returns Markdown content.
- `GET /api/reports/{report_id}/download.pdf` returns a generated PDF file.
- Frontend report download uses the PDF endpoint by default.
- PDF generation uses `reportlab`, listed in backend requirements.
