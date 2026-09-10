# 前端全页面数据驱动契约

目标：前端所有可见业务内容都不再写死。后端未返回时，前端显示空白、0、空列表或“等待数据”的交互状态；只有后端、ForeFire 或 Agent 返回后才显示具体数值、文案、任务和图层。

## 总体规则

- UI 固定标签可以保留：页面标题、按钮名、表单标签、图层开关名、导航名。
- 业务值必须来自后端：状态栏胶囊数值、温度、湿度、风速、风险等级、面积、任务、库存、人员、无人机、路线、告警、图表、报告正文、Agent 建议。
- 默认值规则：
  - 数字：`0`
  - 文本：`""`
  - 列表：`[]`
  - 对象：`{}`
  - 地图：默认只显示基础 Cesium 地球和已确认的高危火点；火线、任务、路径、资源覆盖区必须等待对应后端结果。

## 全局事件状态

接口建议：

```http
GET /api/fire/current-event
```

返回：

```json
{
  "event_id": "muli-20260603-001",
  "status": "hotspot_detected",
  "ignition_point": {
    "longitude": 101.269444,
    "latitude": 28.530278
  },
  "detected_at": "2026-06-03T14:20:00+08:00",
  "updated_at": "2026-06-03T14:38:00+08:00"
}
```

`status` 流程建议：

- `idle`：无火情，所有业务页面为空状态。
- `hotspot_detected`：只显示高危火点。
- `forefire_completed`：显示 ForeFire 火线结果，可发送 Agent 分析。
- `agent_decision_generated`：显示 Agent 决策、任务、路线、资源、无人机、评估。
- `archived`：归档完成，页面回到 `idle`。

## 实时火情监测

接口：

```http
GET /api/fire/hotspots
GET /api/weather/current
GET /api/video/list
GET /api/resource/summary
GET /api/alert/realtime
```

核心字段：

```json
{
  "hotspots": [
    {
      "id": "F-FORE-001",
      "location": "木里县火点",
      "longitude": 101.269444,
      "latitude": 28.530278,
      "temperature_c": 687,
      "area_km2": 0.0048,
      "confidence": 95,
      "risk_level": "high",
      "first_detected_at": "2026-06-03T14:20:00+08:00",
      "last_updated_at": "2026-06-03T15:23:00+08:00"
    }
  ],
  "weather": {
    "temperature_c": 28,
    "feels_like_c": 26,
    "humidity_percent": 45,
    "wind_speed_ms": 3.4,
    "wind_direction": "NW",
    "pm25": 65,
    "visibility_km": 8.2,
    "pressure_hpa": 1013,
    "warning_text": ""
  },
  "resource_summary": {
    "fire_teams": 0,
    "helicopters": 0,
    "uavs": 0,
    "water_trucks": 0
  },
  "alerts": [],
  "cameras": []
}
```

## 火灾蔓延预测

接口：

```http
POST /api/simulate
GET /api/simulate/result/{task_id}
POST /api/agent/forefire/decision
WS /ws/agent/forefire/decision
```

ForeFire 返回必须包含：

```json
{
  "task_id": "forefire-001",
  "duration_minutes": 360,
  "step_minutes": 72,
  "ignition_point": [101.269444, 28.530278],
  "summary": {
    "final_area_km2": 0,
    "max_area_km2": 0,
    "spread_speed_m_min": 0,
    "dominant_direction": ""
  },
  "timeline": [
    {
      "elapsed_minutes": 0,
      "timestamp": "2026-06-03T14:20:00+08:00",
      "area_km2": 0,
      "geojson": {}
    }
  ]
}
```

Agent 请求：

```json
{
  "type": "forefire_decision_request",
  "payload": {
    "forefire_json": {},
    "weather": {},
    "resources": {},
    "uavs": [],
    "personnel": [],
    "include_coordinates": true
  }
}
```

Agent 返回：

```json
{
  "type": "result",
  "status": "decision_generated",
  "payload": {
    "task_id": "agent-001",
    "input_summary": {
      "final_area_km2": 0,
      "risk_level": ""
    },
    "agent_outputs": {
      "environment_assessment": {},
      "fire_spread_analysis": {},
      "resource_dispatch": {},
      "uav_dispatch": {},
      "route_planning": {},
      "damage_assessment": {},
      "command_plan": {}
    },
    "packages": {
      "task_package": {
        "tasks": []
      }
    },
    "candidate_plans": [],
    "recommended_plan": {},
    "warnings": []
  }
}
```

## 多源数据融合

接口：

```http
GET /api/fusion/result
GET /api/fusion/preview
GET /api/system/status
GET /api/sensor/list
```

返回：

```json
{
  "source_status": {
    "fire_active_count": 0,
    "uav_online_count": 0,
    "sensor_active_count": 0
  },
  "fusion": {
    "confidence": 0,
    "fire_estimation_km2": 0,
    "data_volume": "",
    "record_count": 0,
    "coverage_percent": 0,
    "process_step": 0,
    "process_progress": 0,
    "quality": {
      "completeness": 0,
      "accuracy": 0
    }
  },
  "correlations": [],
  "distribution": [],
  "previews": [],
  "resources": []
}
```

## 无人机集群调度

接口：

```http
GET /api/uav/list
GET /api/uav/mission/list
POST /api/uav/control
POST /api/b/decision/uav/schedule
```

返回：

```json
{
  "stats": {
    "online": 0,
    "mission": 0,
    "standby": 0,
    "offline": 0
  },
  "uavs": [
    {
      "id": "UAV-01",
      "name": "",
      "status": "standby",
      "battery": 0,
      "longitude": 0,
      "latitude": 0,
      "payload": "",
      "current_task_id": ""
    }
  ],
  "missions": [],
  "alerts": []
}
```

## 应急路径规划

接口：

```http
POST /api/b/decision/escape-route
POST /api/b/decision/firefighter-route
GET /api/map/elevation
POST /api/route/save
```

返回：

```json
{
  "start": {},
  "end": {},
  "routes": [
    {
      "id": "safe",
      "name": "",
      "distance_km": 0,
      "duration_minutes": 0,
      "risk_level": "",
      "risk_score": 0,
      "geojson": {},
      "elevation_profile": []
    }
  ],
  "weather_on_route": [],
  "facilities": [],
  "risk_factors": [],
  "recommendations": [],
  "radar": []
}
```

## 物资与人员调度

接口：

```http
GET /api/resource/stat
GET /api/resource/list
GET /api/personnel/list
GET /api/dispatch/list
POST /api/dispatch/create
```

返回：

```json
{
  "stats": {
    "total": 0,
    "available": 0,
    "in_transit": 0,
    "resource_points": 0,
    "route_length_km": 0,
    "personnel": 0
  },
  "inventory": [],
  "personnel": [],
  "tasks": [],
  "history": [],
  "alerts": [],
  "suggestions": []
}
```

## 灾情评估分析

接口：

```http
GET /api/disaster/assessment?event_id=...
```

返回：

```json
{
  "severity": "",
  "score": 0,
  "final_area_km2": 0,
  "burned_hectares": 0,
  "economic_loss_million_cny": 0,
  "affected_people": 0,
  "ecological_impact": 0,
  "recovery_months": "",
  "report_text": "",
  "burned_areas": [],
  "loss_categories": [],
  "eco_factors": [],
  "measures": [],
  "trend": []
}
```

## 指挥调度中心

接口：

```http
GET /api/command/overview
GET /api/video/list
GET /api/personnel/list
GET /api/dispatch/list
```

返回：

```json
{
  "capsules": {
    "active_fire_count": 0,
    "risk_level": "",
    "humidity_percent": 0,
    "wind_speed_ms": 0,
    "updated_at": ""
  },
  "overview": {
    "event_name": "",
    "recommended_plan": "",
    "dispatch_count": 0,
    "uav_count": 0,
    "route_count": 0
  },
  "tasks": [],
  "cameras": [],
  "personnel": [],
  "communications": [],
  "alerts": []
}

## 后端连接数据库建议

当前建议 SQLite + API。后端 Agent 不需要直接操作前端状态，只需要通过 HTTP API 查询资源库，并在 Agent 返回中引用资源 `id`。

建议表：

- `fire_events(event_id, status, ignition_lng, ignition_lat, detected_at, archived_at)`
- `resources(resource_id, name, category, total, available, unit, lng, lat, status)`
- `personnel(person_id, name, role, team, status, lng, lat)`
- `uavs(uav_id, name, status, battery, lng, lat, payload)`
- `dispatch_tasks(task_id, event_id, type, owner_id, action, target, status, progress)`
- `routes(route_id, event_id, name, risk_level, distance_km, duration_minutes, geojson)`
- `agent_decisions(task_id, event_id, raw_json, created_at)`

Agent 使用方式：

1. 接收 ForeFire JSON。
2. 调用资源 API 获取 `resources/personnel/uavs/routes/weather`。
3. 生成决策 JSON，所有任务都带资源 ID、坐标和可视化字段。
4. 前端按返回的 ID 与坐标渲染页面组件和地图图层。
