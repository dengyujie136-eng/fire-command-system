# ForeFire 智能体、资源调度与实时通信接口文档

Base URL：`http://localhost:8000`

本文档面向前端联调，覆盖 ForeFire 火势决策、无人机任务分配、三类路径规划、人员/物资调度、库存更新记录和 WebSocket 实时推送。

所有面向页面展示的方案名称、任务动作、原因、摘要、告警与诊断文案均返回中文；`status`、`priority`、`type` 等字段仍保留英文枚举，方便前端做逻辑判断和样式映射。

## 1. 接口总览

| Method | Path | 作用 |
| --- | --- | --- |
| POST | `/api/agent/forefire/decision` | 根据 ForeFire 火线数据生成完整应急决策，并可默认实施调度方案、更新库存 |
| POST | `/api/agent/forefire/route-plan` | 根据起点/终点生成安全路径、中等路径、危险路径三条候选路径 |
| GET | `/api/agent/forefire/dispatch/state` | 查询当前无人机、人员、物资库存和已实施动作日志 |
| WS | `/ws/agent/forefire/decision` | 接收 ForeFire 决策请求，并实时返回 progress/result 消息 |
| WS | `/ws/forefire` | 兼容通用广播通道，可接收决策生成、路径生成、调度状态更新等广播消息 |

## 2. 生成完整应急决策

### 功能

`POST /api/agent/forefire/decision`

该接口会完成：

1. 读取 ForeFire JSON、GeoJSON 或输出目录。
2. 解析时间序列火线，计算面积、bbox、增长速度、扩散方向、风险等级。
3. 读取 `data/environment` 的 DEM、Fuel、NetCDF、点火点文件摘要，依赖缺失时自动降级为文件级摘要。
4. 按 `RESOURCE_API_BASE_URL/api/context/fire-demo` 尝试读取外部资源上下文，失败时使用本地默认库存兜底。
5. 生成候选处置方案、推荐方案、降级方案。
6. 生成完整页面业务包：地图、无人机、路线、资源、灾情评估、指挥中心、多源融合。
7. 生成旧兼容包：无人机任务、三类候选路径、人员调度、物资调度。
8. 默认认为方案已实施，自动扣减库存并写入动作日志。
9. 通过 WebSocket 广播 `forefire_decision_generated` 和 `dispatch_state_updated`。

### 请求体

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `file_path` | string / null | 二选一 | null | ForeFire 汇总 JSON、单个 GeoJSON 或输出目录路径 |
| `forefire_json` | object / null | 二选一 | null | 直接传入 ForeFire JSON 对象 |
| `event_id` | string / null | 否 | `muli-fire-demo-001` | 演示事件 ID |
| `event_name` | string / null | 否 | `木里县森林火灾演示事件` | 演示事件名称 |
| `ignition_point` | object / array / null | 否 | `data/environment/ignition.txt` 或默认点 | 点火点，支持 `{longitude, latitude}` 或 `[lng, lat]` |
| `scene_id` | string / null | 否 | `task_id` | 前端场景 ID，用于库存和动作日志隔离 |
| `weather` | object / null | 否 | null | 气象数据，如 `wind_speed`、`wind_dir` |
| `dem` | object / null | 否 | null | 地形数据，暂可不传 |
| `environment_dir` | string / null | 否 | `data/environment` | 本地环境数据目录 |
| `use_local_environment` | boolean | 否 | true | 是否读取本地 DEM/Fuel/NetCDF/ignition 文件摘要 |
| `resource_api_base_url` | string / null | 否 | `RESOURCE_API_BASE_URL` 或 `http://localhost:5000` | 外部资源 API 地址 |
| `fetch_resource_context` | boolean | 否 | true | 是否主动调用 `/api/context/fire-demo` |
| `resources` | object / null | 否 | null | 外部资源数据，暂可不传；后端会使用默认库存 |
| `targets` | array / null | 否 | null | 重点目标数据，暂可不传 |
| `include_coordinates` | boolean | 否 | false | 是否返回完整火线坐标；前端列表页建议保持 false |
| `auto_implement` | boolean | 否 | true | 是否默认实施方案并扣减库存、写日志 |
| `route_start` | array[number] / null | 否 | 自动估算 | 路径起点 `[lng, lat]`，后续可传物资点/安全营地 |
| `route_end` | array[number] / null | 否 | 自动估算 | 路径终点 `[lng, lat]` |

### 请求示例

```json
{
  "file_path": "data/forefire-output/forefire_prediction_result_20260603_135229.json",
  "event_id": "muli-fire-demo-001",
  "scene_id": "muli-fire-demo-001",
  "include_coordinates": false,
  "auto_implement": true
}
```

带起终点坐标：

```json
{
  "file_path": "data/forefire-output/forefire_prediction_result_20260603_135229.json",
  "scene_id": "muli-fire-demo-001",
  "environment_dir": "data/environment",
  "fetch_resource_context": true,
  "route_start": [101.24, 28.51],
  "route_end": [101.27, 28.53],
  "include_coordinates": false,
  "auto_implement": true
}
```

### 响应顶层字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `task_id` | string | ForeFire 任务 ID |
| `event_id` | string | 演示事件 ID，默认 `muli-fire-demo-001` |
| `event_name` | string | 演示事件名称 |
| `source` | string | 数据来源，正常为 `forefire` |
| `status` | string | 成功为 `decision_generated` |
| `generated_at` | string | 生成时间 |
| `input_summary` | object | 火势输入摘要 |
| `agent_outputs` | object | 智能体完整输出 |
| `packages` | object | 前端直接使用的业务包 |
| `candidate_plans` | array | 候选方案 |
| `recommended_plan` | object | 推荐方案 |
| `blocked_or_downgraded_plans` | array | 降级或阻断方案 |
| `warnings` | array[string] | 缺失气象、DEM、资源等提示 |

### `input_summary`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `duration_hours` | number | 模拟总时长 |
| `steps` | number | 时间步数量 |
| `interval_minutes` | number | 时间间隔 |
| `ignition_point` | array[number] | 点火点 |
| `initial_area_km2` | number | 初始过火面积 |
| `final_area_km2` | number | 最终过火面积 |
| `area_growth_km2` | number | 面积增长 |
| `avg_growth_km2_per_hour` | number | 平均增长速度 |
| `latest_growth_km2_per_hour` | number | 最近增长速度 |
| `final_bbox` | array[number] | 最终 bbox |
| `risk_level` | string | `low` / `moderate` / `high` / `extreme` |
| `time_steps` | array | 每个时间步的面积、bbox、点数 |

## 3. 前端重点使用的业务包

### 3.1 完整页面包总览

`packages` 中会同时提供新页面包和旧兼容包。前端新页面建议优先读取：

| 字段 | 作用 |
| --- | --- |
| `map_package` | 火点、ForeFire 火线、无人机路线、资源路线、疏散路线、覆盖区、风险区 |
| `uav_package` | 无人机任务、巡航路线、覆盖区 |
| `route_package` | 疏散路线、救援路线、管制路段、风险区 |
| `resource_package` | 调度任务、库存变化、人员分配、资源统计 |
| `assessment_package` | 灾情评估、损失估算、影响人数、生态影响 |
| `command_package` | 指挥中心 KPI、当前任务、指挥摘要、通信日志 |
| `fusion_package` | 多源融合置信度、数据源状态、中文诊断告警 |
| `environment_package` | 本地 DEM/Fuel/NetCDF/ignition 摘要和环境接入状态 |

旧前端兼容字段仍保留：

| 字段 | 作用 |
| --- | --- |
| `uav_task_package` | 旧无人机任务包 |
| `route_options_package` | 旧安全/中等/危险三路径候选包 |
| `personnel_dispatch_package` | 旧人员需求包 |
| `material_dispatch_package` | 旧物资需求包 |
| `implementation_package` | `auto_implement=true` 时的库存扣减与动作日志 |

### 3.2 `packages.map_package`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `hotspot` | object | 演示火点，包含经纬度、风险等级、中文原因 |
| `fire_front_geojson` | FeatureCollection | ForeFire 时序火线 |
| `uav_routes` | array | 无人机巡航路线 |
| `resource_routes` | array | 救援/资源通行路线 |
| `evacuation_routes` | array | 疏散路线 |
| `coverage_areas` | array | 无人机覆盖区 Polygon |
| `risk_zones` | array | 火场 bbox 和烟羽影响区 |

### 3.3 `packages.uav_package`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `uav_tasks` | array | 热成像、飞火点巡查、通信中继等任务 |
| `patrol_routes` | array | 无人机巡航坐标，坐标为 `[lng, lat]` |
| `coverage_areas` | array | 无人机重点覆盖 Polygon |

### 3.4 `packages.route_package`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `evacuation_routes` | array | 主疏散路线 |
| `rescue_routes` | array | 消防救援接近路线 |
| `blocked_routes` | array | 管制或高风险道路 |
| `risk_zones` | array | 火场和烟羽风险区 |

### 3.5 `packages.resource_package`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `dispatch_tasks` | array | 中文调度任务 |
| `inventory_changes` | array | 资源预占/扣减变化 |
| `personnel_assignments` | array | 队伍分配 |
| `resource_summary` | object | 资源上下文数量统计 |

### 3.6 `packages.assessment_package`

包含 `severity`、`severity_score`、`final_area_km2`、`burned_hectares`、`economic_loss_million_cny`、`affected_people`、`ecological_impact`、`recovery_months`、`loss_breakdown`。

### 3.7 `packages.command_package`

包含 `kpis`、`active_tasks`、`command_summary`、`communication_log`。`command_summary` 为中文指挥摘要。

### 3.8 `packages.fusion_package`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `confidence` | number | 融合置信度，0-100 |
| `data_sources` | array | 数据源状态，`status` 是英文枚举，`label` 是中文展示文案 |
| `warnings` | array[string] | 中文告警 |
| `recommendation` | string | 中文补数建议 |

`data_sources[].status` 可能为 `ready`、`partial`、`missing`、`mock`。

### 3.9 `packages.environment_package`

`data/environment` 当前包含：

| 文件/目录 | 用途 |
| --- | --- |
| `final_input.nc` | DEM、燃料和风场融合后的 ForeFire 输入 |
| `weather_data.nc` | 气象 NetCDF |
| `clip_dem/` | DEM 栅格目录 |
| `fuel/` | 燃料栅格目录 |
| `ignition.txt` | 点火点，当前为 `101.269444 28.530278` |

当前运行环境如果未安装 `xarray/netCDF4/rasterio`，后端会接入文件级摘要，并在 `warnings` 与 `fusion_package.data_sources` 中标记为“部分接入”。不会阻断决策生成。

### `packages.uav_task_package`

无人机当前以任务分配为主，不要求具体飞行路径。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `summary` | string | 无人机任务说明 |
| `tasks` | array | 无人机任务列表 |

`tasks[]` 字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `task_id` | string | 任务 ID |
| `mission_type` | string | `firefighting` / `monitoring` / `communication` / `reconnaissance` / `transport` |
| `mission_name` | string | 灭火、监测、通信、侦查、运输 |
| `required_uavs` | number | 需要无人机数量 |
| `target` | string | 任务目标区域 |
| `priority` | string | `critical` / `high` / `medium` |
| `status` | string | `planned` / `standby` |
| `reason` | string | 任务原因 |
| `route_planning` | string | 中文航线规划说明，当前为“当前不需要单独规划航线” |

### `packages.route_options_package`

旧兼容路径规划包，目前固定返回三类候选路径。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `summary` | string | 路径规划说明 |
| `route_options` | array | 三条路径 |

`route_options[]` 字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `route_id` | string | 路径 ID |
| `type` | string | `safe` / `medium` / `danger` |
| `name` | string | 安全路径 / 中等路径 / 危险路径 |
| `start` | array[number] | 起点 `[lng, lat]` |
| `end` | array[number] | 终点 `[lng, lat]` |
| `waypoints` | array | 简化路径点 |
| `estimated_length_km` | number | 预计路径长度 |
| `estimated_time_minutes` | number | 预计通行时间 |
| `risk_level` | string | `low` / `medium` / `high` |
| `status` | string | `planned` |
| `reason` | string | 路径说明 |

### `packages.personnel_dispatch_package`

人员调度包含消防员、医疗员，也补充了指挥员和后勤保障人员。默认两个消防站合计 30 名消防员，调度不会超过库存。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `requirements` | array | 人员需求 |
| `constraints` | object | 人员约束说明 |

`requirements[]` 字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `role` | string | `firefighter` / `medic` / `commander` / `logistics` |
| `name` | string | 人员名称 |
| `required_count` | number | 建议调度数量 |
| `priority` | string | 优先级 |
| `reason` | string | 调度原因 |

### `packages.material_dispatch_package`

物资调度会判断是否够用、是否需要补库存，并给出定期更换策略。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `requirements` | array | 物资需求 |
| `maintenance_policy` | object | 定期检查/更换策略 |

`requirements[]` 字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `item_type` | string | 物资类型 |
| `name` | string | 物资名称 |
| `required_quantity` | number | 需要数量 |
| `unit` | string | 单位 |
| `priority` | string | 优先级 |
| `reason` | string | 需求原因 |

默认物资包含：

| item_type | name |
| --- | --- |
| `fire_hose` | 消防水管 |
| `extinguisher` | 灭火器 |
| `protective_suit` | 防护服 |
| `first_aid_kit` | 急救包 |
| `drinking_water` | 饮用水 |
| `radio` | 对讲机 |
| `fire_axe` | 消防斧 |
| `portable_pump` | 便携水泵 |
| `fuel_can` | 油料桶 |
| `lighting_tower` | 移动照明设备 |

### `packages.implementation_package`

当 `auto_implement=true` 时返回。后端默认认为方案已经实施，会扣减库存并写动作日志。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `implemented` | boolean | 是否已默认实施 |
| `summary` | object | 本次实施内容 |
| `current_state` | object | 实施后的库存、人员、无人机和动作日志 |

`summary` 关键字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `uav_assignments` | array | 实际分配的无人机 |
| `personnel_assignments` | array | 实际分配的人员 |
| `material_assignments` | array | 实际分配的物资 |
| `stock_warnings` | array[string] | 库存不足或低于阈值提醒 |
| `personnel_warnings` | array[string] | 人员不足提醒 |
| `uav_warnings` | array[string] | 无人机不足提醒 |

## 4. 独立路径规划接口

### 功能

`POST /api/agent/forefire/route-plan`

前端后续拿到物资点、安全营地、消防站等坐标后，可以调用该接口生成三条路径。

### 请求体

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `start` | array[number] | 是 | 起点 `[lng, lat]` |
| `end` | array[number] | 是 | 终点 `[lng, lat]` |
| `bbox` | array[number] / null | 否 | 火场 bbox，用于辅助绕行 |

### 请求示例

```json
{
  "start": [101.24, 28.51],
  "end": [101.27, 28.53],
  "bbox": [101.25194, 28.5204, 101.28789, 28.55261]
}
```

### 响应示例

```json
{
  "status": "route_plan_generated",
  "route_options": [
    {
      "route_id": "ROUTE-SAFE",
      "type": "safe",
      "name": "安全路径",
      "estimated_length_km": 5.328,
      "estimated_time_minutes": 17.8,
      "risk_level": "low"
    },
    {
      "route_id": "ROUTE-MEDIUM",
      "type": "medium",
      "name": "中等路径",
      "estimated_length_km": 4.409,
      "estimated_time_minutes": 12.0,
      "risk_level": "medium"
    },
    {
      "route_id": "ROUTE-DANGER",
      "type": "danger",
      "name": "危险路径",
      "estimated_length_km": 3.674,
      "estimated_time_minutes": 7.3,
      "risk_level": "high"
    }
  ]
}
```

## 5. 查询调度状态接口

### 功能

`GET /api/agent/forefire/dispatch/state`

查询当前场景下：

- 无人机库存和状态。
- 人员库存和剩余数量。
- 物资库存、剩余数量、补库提醒。
- 已实施动作日志。

### 查询参数

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `scene_id` | string | 否 | 场景 ID；不传使用默认场景 |

### 请求示例

```http
GET /api/agent/forefire/dispatch/state?scene_id=forest-fire-demo-001
```

### 响应字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `status` | string | `ok` |
| `data.materials` | array | 物资库存 |
| `data.personnel` | array | 人员库存 |
| `data.uavs` | array | 无人机库存 |
| `data.actions` | array | 已实施动作日志 |

`materials[]` 关键字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `item_type` | string | 物资类型 |
| `name` | string | 名称 |
| `total_quantity` | number | 总库存 |
| `available_quantity` | number | 当前可用库存 |
| `reorder_threshold` | number | 补库阈值 |
| `need_restock` | boolean | 是否需要补库 |
| `replacement_cycle_hours` | number | 建议更换/检查周期 |

`personnel[]` 关键字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `station_name` | string | 消防站/医院/队伍名称 |
| `role` | string | 人员角色 |
| `total_count` | number | 总人数 |
| `available_count` | number | 剩余可调人数 |
| `assigned_count` | number | 已分配人数 |

`uavs[]` 关键字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `uav_id` | string | 无人机 ID |
| `name` | string | 名称 |
| `capability` | string | 任务能力 |
| `status` | string | `available` / `assigned` |
| `battery_percent` | number | 电量 |

`actions[]` 关键字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `action_type` | string | 动作类型 |
| `summary` | string | 我干了什么 |
| `payload` | object | 动作详情 |
| `created_at` | string | 记录时间 |

## 6. WebSocket 实时通道

### 连接地址

```text
ws://localhost:8000/ws/agent/forefire/decision
```

### 连接成功消息

```json
{
  "type": "progress",
  "status": "streaming",
  "message": "ForeFire 决策 WebSocket 已连接。",
  "payload": {}
}
```

### 客户端心跳

前端可发送：

```json
{
  "type": "ping"
}
```

服务端返回：

```json
{
  "type": "pong"
}
```

### 事件：决策已生成

触发时机：调用 `/api/agent/forefire/decision` 成功后。

```json
{
  "type": "forefire_decision_generated",
  "scene_id": "forest-fire-demo-001",
  "task_id": "13357085-ae9c-4acf-bd6e-730abf35c7f3",
  "status": "decision_generated",
  "risk_level": "high",
  "recommended_plan_id": "PLAN-A",
  "generated_at": "2026-06-03T07:30:00+00:00"
}
```

### 事件：调度状态已更新

触发时机：`auto_implement=true` 且库存/人员/无人机状态已更新。

```json
{
  "type": "dispatch_state_updated",
  "scene_id": "forest-fire-demo-001",
  "task_id": "13357085-ae9c-4acf-bd6e-730abf35c7f3",
  "implementation": {
    "implemented_at": "2026-06-03T07:30:00",
    "stock_warnings": ["消防水管低于补库阈值，建议补充库存。"],
    "personnel_warnings": [],
    "uav_warnings": []
  }
}
```

### 事件：路径已生成

触发时机：调用 `/api/agent/forefire/route-plan` 成功后。

```json
{
  "type": "route_plan_generated",
  "route_count": 3,
  "safe_route": {
    "route_id": "ROUTE-SAFE",
    "type": "safe",
    "name": "安全路径"
  }
}
```

## 7. 前端 Axios 示例

```ts
import axios from 'axios'

export async function generateForeFireDecision(sceneId: string) {
  const res = await axios.post('/api/agent/forefire/decision', {
    file_path: 'data/forefire-output/forefire_prediction_result_20260603_135229.json',
    scene_id: sceneId,
    include_coordinates: false,
    auto_implement: true,
  })

  return res.data
}

export async function createRoutePlan(start: [number, number], end: [number, number]) {
  const res = await axios.post('/api/agent/forefire/route-plan', {
    start,
    end,
  })

  return res.data
}

export async function getDispatchState(sceneId: string) {
  const res = await axios.get('/api/agent/forefire/dispatch/state', {
    params: { scene_id: sceneId },
  })

  return res.data
}
```

## 8. 前端 WebSocket 示例

```ts
const ws = new WebSocket('ws://localhost:8000/ws/agent/forefire/decision')

ws.onopen = () => {
  ws.send(JSON.stringify({ type: 'ping' }))
}

ws.onmessage = (event) => {
  const message = JSON.parse(event.data)

  if (message.type === 'forefire_decision_generated') {
    // 刷新方案、风险、无人机任务等模块
  }

  if (message.type === 'dispatch_state_updated') {
    // 刷新库存、人员、无人机状态、动作日志
  }

  if (message.type === 'route_plan_generated') {
    // 刷新路径规划面板
  }
}
```

## 9. 错误响应

统一使用 FastAPI 标准错误格式：

```json
{
  "detail": "error message"
}
```

| 状态码 | 场景 |
| --- | --- |
| `400` | 请求体缺少 `file_path` 和 `forefire_json` |
| `400` | ForeFire JSON 缺少必要字段 |
| `400` | 路径规划起点/终点格式错误 |
| `404` | `file_path` 不存在 |
| `500` | 数据库、库存实施或其它服务端错误 |

## 10. 调试命令

生成决策：

```powershell
python run_forefire_decision.py --file data\forefire-output\forefire_prediction_result_20260603_135229.json
```

验证核心 ForeFire 决策：

```powershell
python scripts\verify_forefire_decision.py
```

启动后端：

```powershell
uvicorn main:app --reload
```

## 11. 物资扩展依据

默认物资在用户确认的消防水管、灭火器、防护服、急救包、饮用水、对讲机、消防斧基础上，补充了便携水泵、油料桶、移动照明设备。补充依据来自公开应急物资与野外火灾处置常识：

- [Ready.gov Build A Kit](https://www.ready.gov/kit)：应急包建议包含水、急救用品、通信/收音设备、照明等。
- [NWCG](https://www.nwcg.gov/)：野外火灾处置训练和资源体系中包含水泵、水带等灭火支撑装备。
- [CDC/NIOSH Wildland Fire Fighting](https://www.cdc.gov/niosh/firefighters/wildland.html)：野外消防作业强调个人防护和安全保障。
