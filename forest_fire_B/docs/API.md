# 森林火灾应急决策后端接口文档

> 版本：1.0  
> Base URL：`http://localhost:8100`  
> 内容说明：本文档根据当前 FastAPI 路由整理，适用于前后端联调。

## 1. 接口总览

| Method | Path | 说明 |
| --- | --- | --- |
| GET | `/` | 服务根路由 |
| GET | `/health` | 健康检查 |
| POST | `/auth/register` | 用户注册 |
| POST | `/auth/login` | 用户登录并返回 Token |
| POST | `/simulate/` | 启动火灾蔓延模拟任务 |
| GET | `/simulate/result/{task_id}` | 查询模拟结果 |
| POST | `/api/b/scene/create` | 创建场景 |
| POST | `/api/b/scene/{scene_id}/step` | 场景步进模拟 |
| GET | `/api/b/scene/{scene_id}/fire-line` | 获取当前火线 |
| GET | `/api/b/scene/{scene_id}/status` | 获取场景状态 |
| POST | `/api/b/decision/escape-route` | 逃生路径规划 |
| POST | `/api/b/decision/firefighter-route` | 消防员路径规划 |
| GET | `/api/b/decision/resource-dispatch/{scene_id}` | 资源调度建议 |
| POST | `/api/b/decision/uav/schedule` | 无人机巡检路径规划 |
| POST | `/agent/analyze` | 火情分析 |
| POST | `/agent/simulate` | 火灾推演报告 |
| POST | `/agent/drone-plan` | 无人机巡检规划 |
| POST | `/agent/loop/step` | 执行单轮闭环 |
| POST | `/agent/loop/start` | 启动持续闭环 |
| POST | `/agent/loop/stop/{scene_id}` | 停止闭环 |
| GET | `/agent/loop/status/{scene_id}` | 查看闭环状态 |
| GET | `/api/fire/list` | 获取火线 GeoJSON |
| GET | `/api/fire/stat` | 获取火情统计指标 |
| GET | `/api/uav/list` | 获取无人机列表 |
| GET | `/api/resource/list` | 获取资源列表与统计 |
| GET | `/api/personnel/list` | 获取人员列表 |
| GET | `/api/command/overview` | 指挥中心总览聚合 |
| GET | `/api/map/all` | 多图层地图聚合 |
| GET | `/api/fusion/result` | 多源融合结果 |
| WS | `/ws/alert` | 火灾警报广播 |
| WS | `/ws/uav` | 无人机位置模拟 |

---

## 2. 通用约定

### 2.1 请求格式

- `Content-Type: application/json`
- 路径参数使用 `{scene_id}`、`{task_id}` 形式传递
- 经纬度数组统一使用 `[lng, lat]`
- 除 WebSocket 外，接口基本都返回 JSON

### 2.2 响应格式

成功响应通常直接返回对象，不额外包统一 envelope。

失败时返回 FastAPI 标准错误格式：

```json
{
  "detail": "错误信息"
}
```

### 2.3 常见状态码

- `200` 成功
- `400` 参数错误或业务状态不合法
- `401` 认证失败
- `404` 资源不存在
- `500` 服务内部错误

### 2.4 认证方式

`/auth/login` 会返回 `access_token`，认证方式为 Bearer Token：

```http
Authorization: Bearer <access_token>
```

当前代码里部分接口尚未强制鉴权，但前端建议预留 Token 注入能力。

---

## 3. 基础接口

### 3.1 服务根路由

**GET** `/`

**说明**：返回服务运行状态。

**响应示例**

```json
{
  "message": "森林火灾应急决策后端服务运行中"
}
```

### 3.2 健康检查

**GET** `/health`

**说明**：用于探活。

**响应示例**

```json
{
  "status": "ok"
}
```

---

## 4. 认证接口

### 4.1 用户注册

**POST** `/auth/register`

**请求体**

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| username | string | 是 | 用户名 |
| password | string | 是 | 密码 |

**请求示例**

```json
{
  "username": "alice",
  "password": "123456"
}
```

**响应示例**

```json
{
  "msg": "注册成功",
  "username": "alice"
}
```

**可能错误**

- `400`：`Username already registered`
- `500`：数据库或内部异常

### 4.2 用户登录

**POST** `/auth/login`

**请求体**

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| username | string | 是 | 用户名 |
| password | string | 是 | 密码 |

**请求示例**

```json
{
  "username": "alice",
  "password": "123456"
}
```

**响应示例**

```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer"
}
```

**可能错误**

- `401`：`Incorrect username or password`
- `500`：内部异常

---

## 5. 模拟接口

### 5.1 启动火灾蔓延模拟任务

**POST** `/simulate/`

**说明**：异步启动模拟，立即返回 `task_id`，结果需轮询查询。

**请求体：SimulationRequest**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| fire_point | array[number] | 是 | - | 火点坐标 `[lng, lat]` |
| wind_speed | number | 是 | - | 风速 |
| wind_dir | number | 是 | - | 风向 |
| terrain | string | 是 | - | 地形类型 |
| steps | integer | 否 | 10 | 模拟步数 |

**请求示例**

```json
{
  "fire_point": [114.3, 30.5],
  "wind_speed": 6.5,
  "wind_dir": 45,
  "terrain": "mountain",
  "steps": 10
}
```

**响应示例**

```json
{
  "task_id": "8d6c7f8d-fce1-4f15-bf56-0d9db9f8c6f2",
  "status": "pending"
}
```

### 5.2 查询模拟结果

**GET** `/simulate/result/{task_id}`

**路径参数**

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| task_id | string | 是 | 模拟任务 ID |

**响应示例 - 处理中**

```json
{
  "task_id": "8d6c7f8d-fce1-4f15-bf56-0d9db9f8c6f2",
  "status": "pending"
}
```

**响应示例 - 成功**

```json
{
  "task_id": "8d6c7f8d-fce1-4f15-bf56-0d9db9f8c6f2",
  "status": "completed",
  "result": {
    "incident_id": "incident-xxx",
    "simulation_id": "simulation-xxx",
    "fire_lines": []
  }
}
```

**响应示例 - 失败**

```json
{
  "task_id": "8d6c7f8d-fce1-4f15-bf56-0d9db9f8c6f2",
  "status": "failed",
  "error": "xxx"
}
```

**可能错误**

- `404`：`Task not found`

---

## 6. 场景接口

### 6.1 创建场景

**POST** `/api/b/scene/create`

**说明**：创建场景后会生成 `scene_id`、`task_id`、`incident_id`，并写入初始火线。

**请求体：SceneCreateRequest**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| fire_point | array[number] | 否 | `[114.3, 30.5]` | 火点坐标 |
| wind_speed | number | 是 | - | 风速 |
| wind_dir | number | 是 | - | 风向 |
| terrain | string | 否 | `mountain` | 地形类型 |
| area_bbox | array[number] | 否 | null | 区域范围 `[minLng, minLat, maxLng, maxLat]` |
| source | string | 否 | `manual` | 场景来源 |

**请求示例**

```json
{
  "fire_point": [114.3, 30.5],
  "wind_speed": 5.0,
  "wind_dir": 45.0,
  "terrain": "mountain",
  "area_bbox": [114.1, 30.3, 114.5, 30.7],
  "source": "manual"
}
```

**响应示例**

```json
{
  "scene_id": "scene-uuid",
  "task_id": "task-uuid",
  "status": "created",
  "incident_id": "incident-uuid",
  "initial_fire_line": {
    "type": "Feature",
    "geometry": {
      "type": "LineString",
      "coordinates": []
    },
    "properties": {
      "timestamp": 0,
      "step": 0
    }
  }
}
```

**说明**

- `initial_fire_line` 是 GeoJSON Feature
- 前端可直接使用 `geometry.coordinates` 绘制火线

### 6.2 场景步进模拟

**POST** `/api/b/scene/{scene_id}/step`

**路径参数**

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| scene_id | string | 是 | 场景 ID |

**请求体：SceneStepRequest**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| wind_speed | number | 否 | null | 新风速 |
| wind_dir | number | 否 | null | 新风向 |

**请求示例**

```json
{
  "wind_speed": 6.0,
  "wind_dir": 60.0
}
```

**响应示例**

```json
{
  "scene_id": "scene-uuid",
  "step": 1,
  "simulation_id": "simulation-uuid",
  "fire_line": {
    "type": "Feature",
    "geometry": {
      "type": "LineString",
      "coordinates": []
    },
    "properties": {
      "timestamp": 123456,
      "time_index": 0,
      "simulation_id": "simulation-uuid"
    }
  }
}
```

**可能错误**

- `404`：`Scene not found`
- `400`：`No fire line found in scene` / `Scene missing incident_id, recreate scene`
- `500`：模拟服务调用失败

### 6.3 获取当前火线

**GET** `/api/b/scene/{scene_id}/fire-line`

**响应示例**

```json
{
  "scene_id": "scene-uuid",
  "fire_line": {
    "type": "Feature",
    "geometry": {
      "type": "LineString",
      "coordinates": []
    },
    "properties": {
      "timestamp": 123456,
      "step": 0
    }
  }
}
```

### 6.4 获取场景状态

**GET** `/api/b/scene/{scene_id}/status`

**响应示例**

```json
{
  "scene_id": "scene-uuid",
  "status": "running",
  "current_step": 1,
  "fire_area": 0.05,
  "spread_speed": 1.0,
  "last_update": "2026-04-29T08:00:00+00:00",
  "wind_params": {
    "wind_speed": 6.0,
    "wind_dir": 60.0
  }
}
```

---

## 7. 决策接口

### 7.1 逃生路径规划

**POST** `/api/b/decision/escape-route`

**请求体：EscapeRouteRequest**

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| start_lng | number | 是 | 起点经度 |
| start_lat | number | 是 | 起点纬度 |
| scene_id | string | 是 | 场景 ID |

**请求示例**

```json
{
  "start_lng": 114.3,
  "start_lat": 30.5,
  "scene_id": "scene-uuid"
}
```

**响应示例**

```json
{
  "route": [
    { "lng": 114.3, "lat": 30.5 },
    { "lng": 114.3, "lat": 30.55 }
  ],
  "distance": 5.0,
  "estimated_time": 1.0
}
```

### 7.2 消防员路径规划

**POST** `/api/b/decision/firefighter-route`

**请求体：FirefighterRouteRequest**

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| start_lng | number | 是 | 起点经度 |
| start_lat | number | 是 | 起点纬度 |
| scene_id | string | 是 | 场景 ID |

**请求示例**

```json
{
  "start_lng": 114.3,
  "start_lat": 30.5,
  "scene_id": "scene-uuid"
}
```

**响应示例**

```json
{
  "route": [
    { "lng": 114.3, "lat": 30.5 },
    { "lng": 114.31, "lat": 30.51 }
  ],
  "distance": 2.0,
  "estimated_time": 0.2
}
```

### 7.3 资源调度建议

**GET** `/api/b/decision/resource-dispatch/{scene_id}`

**响应示例**

```json
{
  "fire_trucks": 1,
  "uavs": 1,
  "firefighters": 3,
  "message": "根据火场面积 0.05 单位，建议调度 1 辆消防车，1 架无人机，3 名消防员"
}
```

### 7.4 无人机巡检路径规划

**POST** `/api/b/decision/uav/schedule`

**请求体：UAVScheduleRequest**

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| scene_id | string | 是 | 场景 ID |

**请求示例**

```json
{
  "scene_id": "scene-uuid"
}
```

**响应示例**

```json
{
  "waypoints": [
    { "lng": 114.302, "lat": 30.502, "alt": 100 },
    { "lng": 114.303, "lat": 30.503, "alt": 100 }
  ],
  "total_distance": 5.0,
  "estimated_time": 0.1
}
```

---

## 8. Agent 接口

### 8.1 火情分析

**POST** `/agent/analyze`

**请求体：AnalysisRequest**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| fire_point | array[number] | 是 | - | 火点坐标 `[lng, lat]` |
| wind_speed | number | 是 | - | 风速 |
| wind_dir | integer | 是 | - | 风向 |
| terrain | string | 否 | `local_dem` | 地形 |
| steps | integer | 否 | 12 | 推演步数 |
| sentinel_client_id | string/null | 否 | null | Sentinel 账号 ID |
| sentinel_client_secret | string/null | 否 | null | Sentinel 账号 Secret |

**请求示例**

```json
{
  "fire_point": [114.3, 30.5],
  "wind_speed": 8.0,
  "wind_dir": 90,
  "terrain": "local_dem",
  "steps": 12
}
```

**响应示例**

```json
{
  "analysis": "当前态势：中低速蔓延..."
}
```

### 8.2 火灾推演报告

**POST** `/agent/simulate`

**说明**：先走模拟链路，再生成推演报告。

**请求体**：同 `AnalysisRequest`

**响应示例**

```json
{
  "report": "火势推演报告：...",
  "incident_id": "incident-uuid",
  "simulation_id": "simulation-uuid",
  "fire_lines": []
}
```

### 8.3 无人机巡检规划

**POST** `/agent/drone-plan`

**请求体：DronePlanRequest**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| fire_point | array[number] | 是 | - | 火点坐标 `[lng, lat]` |
| area_range | number | 否 | 5.0 | 覆盖范围（km） |

**请求示例**

```json
{
  "fire_point": [114.3, 30.5],
  "area_range": 5.0
}
```

**响应示例**

```json
{
  "message": "已为火点 [114.3, 30.5] 生成勘察航线，共 5 个航点，覆盖范围 5.0km。",
  "route": [],
  "total_points": 5
}
```

### 8.4 执行单轮闭环

**POST** `/agent/loop/step`

**请求体：AgentCycleRequest**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| scene_id | string | 是 | - | 场景 ID |
| wind_speed | number | 否 | null | 覆盖风速 |
| wind_dir | number | 否 | null | 覆盖风向 |

**响应示例**

```json
{
  "message": "single cycle completed",
  "state": {
    "scene_id": "scene-uuid"
  }
}
```

### 8.5 启动持续闭环

**POST** `/agent/loop/start`

**请求体：AgentLoopStartRequest**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| scene_id | string | 是 | - | 场景 ID |
| interval_seconds | integer | 否 | 30 | 循环间隔（秒） |
| max_cycles | integer | 否 | 0 | 最大循环次数，0 表示不限 |

**请求示例**

```json
{
  "scene_id": "scene-uuid",
  "interval_seconds": 30,
  "max_cycles": 0
}
```

**响应示例**

```json
{
  "message": "loop started",
  "status": {
    "scene_id": "scene-uuid",
    "running": true
  }
}
```

### 8.6 停止闭环

**POST** `/agent/loop/stop/{scene_id}`

**响应示例**

```json
{
  "scene_id": "scene-uuid",
  "stopped": true
}
```

### 8.7 查看闭环状态

**GET** `/agent/loop/status/{scene_id}`

**响应示例**

```json
{
  "scene_id": "scene-uuid",
  "running": false,
  "cycles": 2
}
```

---

## 9. WebSocket 接口

### 9.1 火灾警报广播

**WS** `/ws/alert`

**说明**：连接后服务端每 5 秒广播一次警报。

**消息示例**

```json
{
  "type": "alert",
  "message": "火势扩大",
  "timestamp": 123456.0
}
```

### 9.2 无人机实时位置

**WS** `/ws/uav`

**说明**：连接后服务端会模拟无人机位置变化。

**消息示例**

```json
{
  "type": "uav_position",
  "lng": 114.31,
  "lat": 30.51,
  "alt": 120,
  "progress": 50.0
}
```

完成后会发送：

```json
{
  "type": "uav_status",
  "status": "completed",
  "message": "无人机已到达目标位置"
}
```

---

## 10. 前端数据接口速查

### 10.1 接口总览

| 接口 | 作用 | 前端主要用途 |
| --- | --- | --- |
| `GET /api/fire/list` | 火线 GeoJSON | 地图火线渲染 |
| `GET /api/fire/stat` | 火情统计 | 指挥中心 KPI/风险卡片 |
| `GET /api/uav/list` | 无人机列表 | 无人机态势与轨迹面板 |
| `GET /api/resource/list` | 资源列表与统计 | 资源调度与库存面板 |
| `GET /api/personnel/list` | 人员列表 | 人员调度与队伍管理 |

### 10.2 请求参数

| 接口 | 参数 | 类型 | 说明 |
| --- | --- | --- | --- |
| `/api/fire/list` | `scene_id` | string | 可选，按场景过滤 |
| `/api/fire/stat` | `scene_id` | string | 可选，按场景过滤 |
| `/api/uav/list` | `scene_id` | string | 可选，按场景过滤 |
| `/api/resource/list` | `type`, `scene_id` | string | 可选，按类型/场景过滤 |
| `/api/personnel/list` | `role`, `scene_id` | string | 可选，按角色/场景过滤 |

### 10.3 返回字段映射

| 后端字段 | 前端建议绑定 |
| --- | --- |
| `data.type` | GeoJSON 类型 |
| `data.features[]` | 地图图层数据 |
| `data.metrics.fire_area_km2` | 面积 KPI |
| `data.metrics.active_hotspots` | 热点数 |
| `data.risk_level` | 风险等级标签 |
| `data.items[]` | 列表渲染 |
| `data.stats` | 分组统计图表 |
| `ws_cache.lng/lat/alt` | 无人机实时坐标 |

### 10.4 前端使用建议

1. **实时监测页面优先接 `/api/fire/list` + `/api/uav/list`**，地图和无人机面板可以先渲染出基础态。
2. **指挥中心页面优先接 `/api/fire/stat` + `/api/resource/list`**，适合卡片、饼图、列表同时展示。
3. **所有接口都支持 `scene_id`**，建议切场景时统一重拉，避免跨场景数据串用。
4. **接口返回统一为 `{code, message, data, meta}`**，前端可复用同一层数据拦截器。

---

## 11. 错误排查

### 11.1 `400 Bad Request`

常见原因：

- `fire_point` 格式不正确
- 场景没有火线数据
- `scene_id` 对应的数据库记录不存在
- `incident_id` 缺失

### 11.2 `404 Not Found`

常见原因：

- `task_id` 不存在
- `scene_id` 不存在

### 11.3 `500 Internal Server Error`

常见原因：

- 外部模拟服务调用失败
- 数据库异常
- Agent 运行时依赖缺失

---

## 12. 建议的前端字段映射

| 页面/模块 | 主要字段 |
| --- | --- |
| 场景创建页 | `scene_id`, `task_id`, `incident_id`, `initial_fire_line` |
| 地图展示页 | `fire_line.geometry.coordinates`, `wind_params` |
| 模拟结果页 | `result.fire_lines`, `simulation_id` |
| 决策指挥页 | `route`, `distance`, `estimated_time`, `message` |
| 资源调度页 | `fire_trucks`, `uavs`, `firefighters` |
| 无人机态势页 | `waypoints`, `progress`, `status` |

---

如果你需要，我下一步可以继续帮你把这个 `API.md` 再拆成更适合前端直接对照的版本，比如：
- `接口总表`
- `请求参数表`
- `返回参数表`
- `前端字段映射表`

也可以直接帮你补一个 `README` 里能引用的简版目录。
