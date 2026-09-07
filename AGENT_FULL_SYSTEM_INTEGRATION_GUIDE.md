# Agent 全系统联动实现说明

本文档给后端 Agent 开发者使用，目标是把当前前端从“ForeFire 火势预测 + 简单 Agent 决策”升级为“完整火灾应急处置编排系统”。

## 1. 当前演示事件

本项目当前只需要服务一个演示火情，不要求先做通用平台。

```json
{
  "event_id": "muli-fire-demo-001",
  "event_name": "木里县森林火灾演示事件",
  "ignition_point": {
    "longitude": 101.269444,
    "latitude": 28.530278
  }
}
```

前端流程：

1. 实时火情监测页显示高危火点。
2. 用户在火灾蔓延预测页点击“开始模拟”。
3. 前端调用本地 ForeFire API，得到时序火线 GeoJSON。
4. 前端通过 WebSocket 把 ForeFire 结果和上下文发给 Agent。
5. Agent 返回完整结构化处置方案。
6. 前端把 Agent 返回结果同步到无人机、路线、物资、灾情评估、指挥中心、多源融合页面。

## 2. 服务地址

### 2.1 ForeFire 与资源数据库 API

本地资源 API 由当前项目后端提供：

```txt
http://localhost:5000
```

如果 Agent 在另一台电脑上，需要把 `localhost` 换成运行本项目后端电脑的 ZeroTier/IP 地址，例如：

```txt
http://10.62.223.95:5000
```

Agent 环境变量建议：

```env
RESOURCE_API_BASE_URL=http://10.62.223.95:5000
```

### 2.2 Agent HTTP 与 WebSocket

当前 Agent 地址：

```txt
HTTP Base URL: http://10.62.223.117:8000
WebSocket URL: ws://10.62.223.117:8000/ws/agent/forefire/decision
REST fallback: POST http://10.62.223.117:8000/api/agent/forefire/decision
```

## 3. SQLite 数据库与资源 API

前端项目后端已经建立 SQLite 数据库：

```txt
Windows 路径:
backend/forefire_api/data/fire_events.db

Docker 容器路径:
/app/data/fire_events.db
```

不建议 Agent 跨机器直接打开 SQLite 文件。推荐 Agent 通过 HTTP API 读取资源上下文。

### 3.1 一次性读取完整上下文

```http
GET /api/context/fire-demo
```

返回：

```json
{
  "event_id": "muli-fire-demo-001",
  "event_name": "木里县森林火灾演示事件",
  "ignition_point": {
    "longitude": 101.269444,
    "latitude": 28.530278
  },
  "resource_inventory": [],
  "personnel_units": [],
  "uav_assets": [],
  "vehicles": [],
  "water_sources": [],
  "shelters": [],
  "important_targets": [],
  "road_segments": []
}
```

Agent 推荐优先调用这个接口，把返回对象作为本次决策的资源上下文。

### 3.2 分模块读取 API

```http
GET /api/resources/inventory
GET /api/resources/personnel
GET /api/uav/assets
GET /api/routes/network
GET /api/tasks/dispatch?event_id=muli-fire-demo-001
POST /api/tasks/dispatch
```

### 3.3 新建调度任务

Agent 如果要把已生成任务写回资源 API，可以调用：

```http
POST /api/tasks/dispatch
Content-Type: application/json
```

请求：

```json
{
  "event_id": "muli-fire-demo-001",
  "owner": "北线森林消防一队",
  "action": "建立北侧隔离带并压制火头",
  "target": "北侧重点林缘",
  "priority": "critical",
  "status": "planned",
  "eta_minutes": 18,
  "lng": 101.273,
  "lat": 28.554,
  "reason": "ForeFire 显示火势向北扩张，北侧林缘为重点保护目标。"
}
```

返回：

```json
{
  "ok": true,
  "task_id": "task-xxx",
  "status": "planned"
}
```

## 4. 数据表说明

### 4.1 `resource_inventory`

物资库存。

字段：

```txt
resource_id, name, category, unit, total, available, reserved,
location_name, lng, lat, status, notes
```

Agent 用途：

- 判断物资是否足够。
- 为水源保障、灭火器、防护服、通信、医疗生成调度任务。
- 输出 `inventory_changes`。

### 4.2 `personnel_units`

救援队伍。

字段：

```txt
unit_id, name, unit_type, headcount, available_headcount,
skill_tags_json, location_name, lng, lat, status, contact
```

Agent 用途：

- 根据技能选择任务承担方。
- `fire_crew` 用于火线压制。
- `evacuation` 用于疏散和交通管制。
- `medical` 用于救护。
- `logistics` 用于物资保障。

### 4.3 `uav_assets`

无人机资产。

字段：

```txt
uav_id, name, model, payloads_json, battery_percent,
endurance_minutes, max_range_km, lng, lat, status, current_task_id
```

Agent 用途：

- 选择热成像、可见光、多光谱、通信中继任务。
- 电量低于任务时长要求时不能分配。
- 生成巡航路线、覆盖区和任务时长。

### 4.4 `vehicles`

车辆资源。

字段：

```txt
vehicle_id, name, vehicle_type, capacity, lng, lat, status, assigned_unit_id
```

Agent 用途：

- 水车、消防车、救护车、指挥车调度。
- 计算响应时间。

### 4.5 `water_sources`

水源点。

字段：

```txt
source_id, name, source_type, capacity_tons,
refill_rate_tons_per_hour, lng, lat, access_level
```

Agent 用途：

- 水车补给路径。
- 灭火水源保障。

### 4.6 `shelters`

避难点。

字段：

```txt
shelter_id, name, capacity_people, current_people,
lng, lat, status, notes
```

Agent 用途：

- 疏散路线终点。
- 判断容量是否足够。

### 4.7 `important_targets`

重点保护目标。

字段：

```txt
target_id, name, target_type, priority, population,
lng, lat, protection_note
```

Agent 用途：

- 根据 ForeFire 扩散方向判断优先保护对象。
- 生成保护任务。

### 4.8 `road_segments`

道路/路径数据。

字段：

```txt
segment_id, name, start_lng, start_lat, end_lng, end_lat,
distance_km, travel_time_minutes, risk_level, status, notes
```

Agent 用途：

- 生成疏散路线、救援路线、物资运输路线。
- 避开高风险或 restricted 路段。

## 5. 前端发给 Agent 的请求

WebSocket 请求格式：

```json
{
  "type": "forefire_decision_request",
  "payload": {
    "event_id": "muli-fire-demo-001",
    "ignition_point": {
      "longitude": 101.269444,
      "latitude": 28.530278
    },
    "forefire_json": {},
    "weather": {
      "temperature": 24,
      "humidity": 40,
      "wind_speed": 3.4,
      "wind_direction": "north"
    },
    "resources": {},
    "include_coordinates": true
  }
}
```

Agent 收到请求后，应主动调用：

```http
GET {RESOURCE_API_BASE_URL}/api/context/fire-demo
```

把资源上下文合并到决策输入。

## 6. Agent 总返回结构

Agent 最终返回：

```json
{
  "type": "result",
  "status": "decision_generated",
  "payload": {
    "task_id": "xxx",
    "event_id": "muli-fire-demo-001",
    "source": "forefire",
    "status": "decision_generated",
    "generated_at": "2026-06-03T12:00:00Z",
    "input_summary": {},
    "agent_outputs": {},
    "packages": {},
    "candidate_plans": [],
    "recommended_plan": {},
    "blocked_or_downgraded_plans": [],
    "warnings": []
  }
}
```

前端会优先读取 `payload`；REST 接口可以直接返回同样的 payload 对象。

## 7. 各 Agent 功能详细说明

### 7.1 ForeFireAdapterAgent

职责：把 ForeFire GeoJSON 转成后续 Agent 可用的结构化火势摘要。

输入：

```json
{
  "forefire_json": {
    "task_id": "xxx",
    "status": "done",
    "source": "forefire",
    "geojson": {
      "type": "FeatureCollection",
      "features": []
    }
  }
}
```

实现步骤：

1. 校验 `status == done`。
2. 按 `properties.elapsed_seconds` 或 `elapsed_minutes` 排序。
3. 对每个火线多边形计算：
   - `bbox`
   - `area_km2`
   - `centroid`
   - `point_count`
4. 计算相邻时间步面积增长：
   - `growth_km2`
   - `growth_rate_km2_per_hour`
5. 计算最终外包矩形扩张方向：
   - north/south/east/west 扩张量
6. 判断主扩散方向：
   - 比较最终 bbox 与初始 bbox 的扩张距离。
7. 判断风险等级：
   - final_area < 1: low
   - 1-4: moderate
   - 4-10: high
   - >10: extreme

输出：

```json
{
  "validated": true,
  "time_steps": [
    {
      "step": 1,
      "elapsed_minutes": 72,
      "bbox": [101.25, 28.52, 101.28, 28.55],
      "area_km2": 0.64,
      "centroid": [101.269, 28.531],
      "point_count": 120
    }
  ],
  "growth_metrics": {
    "area_growth_intervals": [],
    "latest_spread_intensity": "high",
    "accelerated_spread": true,
    "main_spread_direction": "north",
    "bbox_expansion_km": {
      "north": 2.1,
      "south": 0.4,
      "east": 0.8,
      "west": 0.6
    },
    "priority_protection_directions": ["north", "south"]
  }
}
```

### 7.2 EnvironmentAssessmentAgent

职责：结合火势、气象、地形/燃料缺失情况，给出环境风险解释。

输入数据：

- `ForeFireAdapterAgent.growth_metrics`
- `weather`
- `warnings`
- 可选 DEM/Fuel 数据摘要

实现方式：

1. 根据风速、湿度、扩散方向判断火势是否有加速风险。
2. 如果缺失 DEM/Fuel，应输出 warnings，不阻断流程。
3. 根据主扩散方向输出 `protection_focus`。
4. 生成自然语言摘要。

输出：

```json
{
  "current_fire_area_km2": 8.23,
  "area_growth_km2": 7.59,
  "avg_growth_km2_per_hour": 1.26,
  "latest_growth_km2_per_hour": 2.67,
  "spread_direction": "north",
  "fire_risk_level": "high",
  "environment_risk_summary": "Final burned area is 8.23 km2. Latest growth rate is 2.67 km2/h. Main spread direction is north.",
  "protection_focus": [
    {
      "direction": "north",
      "reason": "火势主要向北扩张",
      "priority": "critical"
    }
  ]
}
```

### 7.3 FireSpreadAnalysisAgent

职责：给前端火势蔓延预测页提供曲线、时段和趋势说明。

输入：

- `time_steps`
- `growth_metrics`

实现方式：

1. 用 `time_steps[].area_km2` 生成面积增长曲线。
2. 根据增长率找出高风险时段。
3. 判断是否加速蔓延。
4. 输出未来 6 小时摘要。

输出：

```json
{
  "future_6h_summary": "火势在 216-360 分钟阶段增长加快，最终面积约 8.23 km2。",
  "area_growth_curve": [
    { "elapsed_minutes": 72, "area_km2": 0.64 },
    { "elapsed_minutes": 144, "area_km2": 1.32 }
  ],
  "high_risk_periods": [
    {
      "start_minutes": 216,
      "end_minutes": 360,
      "reason": "增长率超过平均水平"
    }
  ],
  "accelerated_spread": true,
  "latest_spread_intensity": "high",
  "main_spread_direction": "north"
}
```

### 7.4 CommandDecisionAgent

职责：生成候选方案、评分和推荐方案。

输入：

- 火势风险
- 重点目标
- 人员、车辆、水源、物资、无人机资源

实现方式：

1. 至少生成 3 个候选方案：
   - PLAN-A：保护下风向/重点目标
   - PLAN-B：直接压制火头
   - PLAN-C：疏散优先
2. 对每个方案计算：
   - `safety_margin`
   - `response_efficiency`
   - `resource_match`
   - `expected_control_effect`
   - `execution_difficulty`
3. 评分公式：

```txt
score = 0.30 * safety_margin
      + 0.25 * response_efficiency
      + 0.20 * resource_match
      + 0.20 * expected_control_effect
      - 0.15 * execution_difficulty
```

4. 选择最高分且没有硬安全阻断的方案为推荐方案。

输出：

```json
{
  "candidate_plans": [
    {
      "plan_id": "PLAN-A",
      "name": "Protect downwind and priority targets",
      "strategy": "Build protection positions ahead of the fastest expansion sector.",
      "target_area": "north fire edge and south evacuation corridor",
      "risk_level": "high",
      "safety_margin": 72,
      "response_efficiency": 68,
      "resource_match": 80,
      "expected_control_effect": 70,
      "execution_difficulty": 52,
      "score": 67.1,
      "status": "recommended",
      "reasons": [
        "Matches the inferred spread direction.",
        "Includes key-target protection."
      ],
      "safety_rules": {
        "no_route_through_active_fire": true,
        "crew_has_escape_route": true
      }
    }
  ],
  "recommended_plan": {},
  "blocked_or_downgraded_plans": []
}
```

### 7.5 ResourceDispatchAgent

职责：生成物资、人员、车辆调度任务。

输入：

- `resource_inventory`
- `personnel_units`
- `vehicles`
- `water_sources`
- `recommended_plan`

实现方式：

1. 选择最近可用消防队伍负责压制/隔离带。
2. 选择 logistics 队伍负责物资和水源补给。
3. 根据 `resource_inventory.available` 判断调拨数量。
4. 根据 `road_segments.travel_time_minutes` 估算 ETA。
5. 生成 `dispatch_tasks`。
6. 生成 `inventory_changes`，前端用来显示库存变化。

输出：

```json
{
  "resource_inventory": {},
  "recommended_plan_id": "PLAN-A",
  "tasks": [
    {
      "task_id": "dispatch-crew-north",
      "owner": "北线森林消防一队",
      "action": "建立北侧隔离带并压制火头",
      "target": "北侧重点林缘",
      "priority": "critical",
      "eta_minutes": 18,
      "status": "planned",
      "lng": 101.273,
      "lat": 28.554,
      "reason": "火势主要向北扩张。"
    }
  ],
  "inventory_changes": [
    {
      "resource_id": "res-suit",
      "name": "森林消防防护服",
      "change": -80,
      "unit": "件",
      "reason": "北线消防队部署"
    }
  ],
  "personnel_assignments": [
    {
      "unit_id": "unit-fire-north",
      "assigned_headcount": 60,
      "task_id": "dispatch-crew-north"
    }
  ]
}
```

### 7.6 UAVDispatchAgent

职责：生成无人机任务、巡航路线和覆盖区。

输入：

- `uav_assets`
- 火势最终 bbox
- 主扩散方向
- 重点保护目标

实现方式：

1. 选择包含 `thermal` payload 的 UAV 执行热成像任务。
2. 选择 `visible` 或 `multispectral` UAV 执行飞火点巡查。
3. 选择 `relay` UAV 作为通信中继。
4. 生成巡航路线：
   - 热成像路线沿火线外缘。
   - 可见光路线覆盖扩散方向山脊。
   - 中继点靠近安全营地。
5. 生成覆盖区 Polygon，不是火线边界，而是无人机重点工作区域。

输出：

```json
{
  "uav_tasks": [
    {
      "task_id": "uav-thermal-north",
      "uav_ids": ["UAV-01", "UAV-02"],
      "owner": "UAV-01/UAV-02",
      "action": "执行北侧火线热成像巡航",
      "target": "北侧火线",
      "priority": "critical",
      "duration_minutes": 45,
      "status": "planned",
      "reason": "北侧扩散最快，需要连续热成像复核。"
    }
  ],
  "patrol_routes": [
    {
      "route_id": "uav-route-north",
      "uav_ids": ["UAV-01", "UAV-02"],
      "coordinates": [
        [101.263, 28.548],
        [101.269, 28.552],
        [101.281, 28.551]
      ],
      "color": "#a78bfa"
    }
  ],
  "coverage_areas": [
    {
      "area_id": "uav-coverage-main",
      "name": "无人机重点覆盖区",
      "type": "Polygon",
      "coordinates": [
        [101.257, 28.542],
        [101.286, 28.544],
        [101.284, 28.522],
        [101.256, 28.520]
      ]
    }
  ]
}
```

### 7.7 RoutePlanningAgent

职责：生成疏散路线、救援路线、风险路段。

输入：

- `road_segments`
- `shelters`
- `important_targets`
- 火势 bbox / 风险区

实现方式：

1. 从高危目标或村落入口选择起点。
2. 选择可用 shelter 作为终点。
3. 避开 `risk_level=high` 且 `status=restricted` 的道路，除非是消防专用路线。
4. 生成：
   - `evacuation_routes`
   - `rescue_routes`
   - `blocked_routes`
   - `risk_zones`

输出：

```json
{
  "evacuation_routes": [
    {
      "route_id": "route-safe-south",
      "name": "南向安全疏散路线",
      "start": "下风向村落入口",
      "end": "南侧安全营地",
      "distance_km": 12.3,
      "eta_minutes": 25,
      "risk_level": "low",
      "coordinates": [
        [101.269444, 28.530278],
        [101.263, 28.508]
      ],
      "reason": "避开北侧火线与高风险烟羽方向。"
    }
  ],
  "rescue_routes": [],
  "blocked_routes": [],
  "risk_zones": [
    {
      "zone_id": "risk-north-smoke",
      "name": "北侧烟羽影响区",
      "risk_level": "high",
      "type": "Polygon",
      "coordinates": []
    }
  ]
}
```

### 7.8 DamageAssessmentAgent

职责：生成灾情评估数据。

输入：

- final_area_km2
- important_targets
- shelters
- population

实现方式：

1. `burned_hectares = final_area_km2 * 100`
2. 根据目标和面积估算经济损失。
3. 根据村落人口和避难点容量估算影响人数。
4. 生成严重程度评分：
   - 面积、增长速度、受影响人口、重点目标综合加权。

输出：

```json
{
  "severity": "严重",
  "severity_score": 6.8,
  "final_area_km2": 8.23,
  "burned_hectares": 823,
  "economic_loss_million_cny": 32,
  "affected_people": 12500,
  "ecological_impact": 72,
  "recovery_months": "3-6",
  "loss_breakdown": [
    { "name": "林木资源", "value_million_cny": 13.4 },
    { "name": "灭火投入", "value_million_cny": 7.6 }
  ]
}
```

### 7.9 FusionDiagnosticsAgent

职责：给多源数据融合页提供数据质量和缺失诊断。

输入：

- ForeFire 结果是否存在
- Agent 是否完成
- weather/dem/fuel/resources 是否缺失

输出：

```json
{
  "confidence": 88,
  "data_sources": [
    { "name": "高危火点监测", "status": "ready" },
    { "name": "ForeFire 火线", "status": "ready" },
    { "name": "Agent 决策", "status": "ready" },
    { "name": "气象风场", "status": "ready" },
    { "name": "DEM/Fuel", "status": "partial" }
  ],
  "warnings": [
    "DEM 坡度约束不完整，建议补充高分辨率地形数据。"
  ]
}
```

### 7.10 CommandSummaryAgent

职责：给指挥中心输出统一态势摘要。

输入：

- 推荐方案
- 任务包
- UAV 任务
- 路线任务
- 评估结果

输出：

```json
{
  "kpis": {
    "fire_count": 1,
    "final_area_km2": 8.23,
    "uav_online": 6,
    "uav_mission": 3,
    "resource_points": 12,
    "personnel_total": 360,
    "personnel_deployed": 318,
    "vehicles_dispatched": 52,
    "evacuated_people": 1680
  },
  "active_tasks": [
    {
      "task_id": "dispatch-crew-north",
      "name": "建立北侧隔离带并压制火头",
      "status": "执行中",
      "progress": 32,
      "location": "北侧重点林缘"
    }
  ],
  "command_summary": "建议优先保护北侧林缘和南侧疏散通道，调度北线消防队、水车编队和无人机热成像巡航。",
  "communication_log": [
    {
      "time": "2026-06-03T12:00:00Z",
      "sender": "Agent",
      "message": "推荐方案 PLAN-A 已生成。",
      "level": "info"
    }
  ]
}
```

## 8. 最终 `packages` 结构

Agent 最终响应中必须尽量提供：

```json
{
  "packages": {
    "map_package": {
      "hotspot": {},
      "fire_front_geojson": {},
      "uav_routes": [],
      "resource_routes": [],
      "evacuation_routes": [],
      "coverage_areas": [],
      "risk_zones": []
    },
    "task_package": {
      "tasks": []
    },
    "uav_package": {
      "uav_tasks": [],
      "patrol_routes": [],
      "coverage_areas": []
    },
    "route_package": {
      "evacuation_routes": [],
      "rescue_routes": [],
      "blocked_routes": [],
      "risk_zones": []
    },
    "resource_package": {
      "dispatch_tasks": [],
      "inventory_changes": [],
      "personnel_assignments": []
    },
    "assessment_package": {},
    "command_package": {},
    "fusion_package": {}
  }
}
```

## 9. 前端当前兼容字段

当前前端已经能读取：

```txt
input_summary
recommended_plan
warnings
agent_outputs.environment_assessment
agent_outputs.fire_spread_analysis
agent_outputs.resource_dispatch.tasks
packages.task_package.tasks
```

后续前端会继续扩展读取：

```txt
packages.uav_package
packages.route_package
packages.resource_package
packages.assessment_package
packages.command_package
packages.fusion_package
```

## 10. 后端实现建议顺序

建议分三步实现，不要一次做太大。

第一步：数据上下文接入

1. Agent 启动时配置 `RESOURCE_API_BASE_URL`。
2. 收到前端请求后调用 `/api/context/fire-demo`。
3. 把返回资源上下文写入 Agent 输入。

第二步：结构化输出

1. 完成 ForeFireAdapterAgent。
2. 完成 EnvironmentAssessmentAgent。
3. 完成 CommandDecisionAgent。
4. 输出 `recommended_plan` 和 `packages.task_package.tasks`。

第三步：全页面功能包

1. UAVDispatchAgent 输出 `uav_package`。
2. RoutePlanningAgent 输出 `route_package`。
3. ResourceDispatchAgent 输出 `resource_package`。
4. DamageAssessmentAgent 输出 `assessment_package`。
5. CommandSummaryAgent 输出 `command_package`。
6. FusionDiagnosticsAgent 输出 `fusion_package`。

## 11. 调试命令

验证本地资源 API：

```powershell
Invoke-RestMethod http://localhost:5000/api/context/fire-demo
Invoke-RestMethod http://localhost:5000/api/resources/inventory
Invoke-RestMethod http://localhost:5000/api/uav/assets
Invoke-RestMethod http://localhost:5000/api/routes/network
```

Agent 机器上验证资源 API：

```powershell
Invoke-RestMethod http://10.62.223.95:5000/api/context/fire-demo
```

如果无法访问：

1. 检查本机后端是否监听 `0.0.0.0:5000`。
2. 检查 Windows 防火墙是否放行 5000。
3. 检查 ZeroTier 两端是否互通。
