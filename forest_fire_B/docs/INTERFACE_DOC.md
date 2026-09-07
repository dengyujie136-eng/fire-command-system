# 森林火灾应急决策后端接口文档

> 本文档面向前端联调与接口对接，仅描述 B 端对外暴露行为。
> 默认返回结构为 `{ code, message, data, meta }`。
> C 端契约保持不变，B 端新增能力均为内部聚合与前端友好封装。

---

## 1. 通用说明

### 1.1 返回格式

所有新增前端友好接口统一返回：

```json
{
  "code": 200,
  "message": "ok",
  "data": {},
  "meta": {}
}
```

### 1.2 通用参数

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `scene_id` | string | 场景 ID，可选。传入后按场景过滤数据。 |
| `format` | string | 仅部分接口支持，`raw` 返回原始结构，默认 UI 直出。 |
| `layers` | string | 多图层接口参数，逗号分隔，如 `fire,uav`。 |
| `type` | string | 资源类型过滤。 |
| `role` | string | 人员角色过滤。 |

---

## 2. 接口总览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/fire/list` | 获取火线 GeoJSON |
| GET | `/api/fire/stat` | 获取火情统计与图表数据 |
| GET | `/api/uav/list` | 获取无人机列表 |
| GET | `/api/resource/list` | 获取资源列表与表格数据 |
| GET | `/api/personnel/list` | 获取人员列表 |
| GET | `/api/command/overview` | 指挥中心总览聚合 |
| GET | `/api/map/all` | 地图多图层聚合 |
| GET | `/api/fusion/result` | 多源融合结果 |
| WS | `/ws/alert` | 火灾警报广播 |
| WS | `/ws/uav` | 无人机实时位置 |

---

## 3. 前端友好接口

### 3.1 GET `/api/fire/list`

获取火线 GeoJSON，适合 Mapbox / 地图页面直接渲染。

#### 请求参数

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `scene_id` | string | 否 | 场景 ID |
| `format` | string | 否 | `raw` 返回原始结构，默认 UI 结构 |

#### 返回结构

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `data.type` | string | 固定为 `FeatureCollection` |
| `data.features` | array | GeoJSON 特征数组 |
| `data.coords` | array | 备用坐标数组 |

#### `features[].properties.popup`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `scene_id` | string | 场景 ID |
| `type` | string | 图层类型，通常为 `fire_line` |
| `step` | number | 步数/阶段 |
| `risk_hint` | string | 风险提示，如“火势向东蔓延” |

#### 示例响应

```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "type": "FeatureCollection",
    "features": [
      {
        "type": "Feature",
        "geometry": {
          "type": "LineString",
          "coordinates": [
            [114.3, 30.5],
            [114.31, 30.5],
            [114.32, 30.5]
          ]
        },
        "properties": {
          "scene_id": "seed-demo-001",
          "type": "fire_line",
          "step": 3,
          "popup": {
            "scene_id": "seed-demo-001",
            "type": "fire_line",
            "step": 3,
            "risk_hint": "火势向东蔓延"
          }
        }
      }
    ],
    "coords": [[114.3, 30.5], [114.31, 30.5], [114.32, 30.5]]
  },
  "meta": {
    "scene_id": "seed-demo-001",
    "format": "ui"
  }
}
```

#### 前端使用建议

- Mapbox 直接 `setData(data)`。
- 点击图层时读取 `properties.popup` 展示气泡。
- 坐标必须使用 `[lng, lat]`。

---

### 3.2 GET `/api/fire/stat`

返回火情统计、图表和摘要卡片，适合指挥中心 KPI 区域。

#### 请求参数

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `scene_id` | string | 否 | 场景 ID |
| `format` | string | 否 | `raw` 返回原始结构，默认 UI 结构 |

#### 返回结构

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `data._raw` | object | 原始数据，调试兜底 |
| `data.risk_level` | string | UI 枚举：`low/medium/high` |
| `data.chart_data` | object | ECharts 直出数据 |
| `data.summary_cards` | array | 指挥中心摘要卡 |
| `data.metrics` | object | 统计指标 |
| `data.wind_params` | object | 风速/风向 |
| `data.agent_summary` | string | 决策建议 |
| `data.stats` | object | 结构化辅助信息 |

#### `chart_data`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `xAxis` | string[] | 默认 `['T0','T1','T2']`，用于演示三段式趋势 |
| `series` | array | ECharts series |

#### `summary_cards`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `label` | string | 卡片标题 |
| `value` | string \| number | 卡片值 |
| `color` | string | 展示颜色 |
| `trend` | string | 趋势，格式如 `+12%` 或 `-5%` |

#### `risk_level` 映射建议

| 值 | 含义 | 建议颜色 |
| --- | --- | --- |
| `low` | 低风险 | `#52c41a` |
| `medium` | 中风险 | `#faad14` |
| `high` | 高风险 | `#ff4d4f` |

#### 示例响应

```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "_raw": {
      "scene_id": "seed-demo-001",
      "current_step": 2,
      "fire_area": 0.85,
      "spread_speed": 1.2,
      "wind_params": {
        "wind_speed": 6.5,
        "wind_dir": 45
      },
      "risk_level": "high",
      "agent_summary": "火势向东蔓延，建议优先疏散东侧村庄",
      "current_fire_geojson": {
        "type": "Feature",
        "geometry": {
          "type": "LineString",
          "coordinates": [[114.3, 30.5], [114.31, 30.5], [114.32, 30.5]]
        },
        "properties": {
          "scene_id": "seed-demo-001",
          "type": "fire_line",
          "step": 3,
          "popup": {
            "scene_id": "seed-demo-001",
            "type": "fire_line",
            "step": 3,
            "risk_hint": "火势向东蔓延"
          }
        }
      },
      "stats": {
        "current_step": 2,
        "fire_area": 0.85,
        "spread_speed": 1.2,
        "risk_level": "high"
      }
    },
    "risk_level": "high",
    "chart_data": {
      "xAxis": ["T0", "T1", "T2"],
      "series": [
        {
          "name": "面积(km²)",
          "data": [0.1, 0.45, 0.85]
        }
      ]
    },
    "summary_cards": [
      {
        "label": "过火面积",
        "value": "0.85km²",
        "color": "#ff4d4f",
        "trend": "+12%"
      },
      {
        "label": "风速",
        "value": "6.5m/s",
        "color": "#1677ff",
        "trend": "稳定"
      },
      {
        "label": "当前步数",
        "value": "2",
        "color": "#52c41a",
        "trend": "+1"
      }
    ],
    "metrics": {
      "fire_area": 0.85,
      "fire_area_km2": 0.85,
      "spread_speed": 1.2,
      "uav_online": 3,
      "resource_ready": 5,
      "personnel_ready": 8
    },
    "wind_params": {
      "wind_speed": 6.5,
      "wind_dir": 45
    },
    "agent_summary": "火势向东蔓延，建议优先疏散东侧村庄",
    "stats": {
      "current_step": 2,
      "fire_area": 0.85,
      "spread_speed": 1.2,
      "risk_level": "high"
    }
  },
  "meta": {
    "scene_id": "seed-demo-001",
    "format": "ui"
  }
}
```

#### 前端使用建议

- ECharts 直接消费 `chart_data`。
- 指挥中心卡片直接消费 `summary_cards`。
- 若要调试原始数据，加 `?format=raw`。

---

### 3.3 GET `/api/uav/list`

返回无人机列表，合并数据库注册与 WS 内存缓存位置。

#### 请求参数

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `scene_id` | string | 否 | 场景 ID |

#### 示例响应

```json
{
  "code": 200,
  "message": "ok",
  "data": [
    {
      "id": 1,
      "name": "侦察鹰-1",
      "type": "inspection",
      "status": "idle",
      "location": {
        "lng": 114.31,
        "lat": 30.51,
        "alt": 100
      },
      "scene_id": "seed-demo-001",
      "last_update": "2026-04-29T12:00:00+00:00",
      "ws_cache": {
        "type": "uav_position",
        "uav_id": "mock-uav-001",
        "lng": 114.31,
        "lat": 30.51,
        "alt": 100,
        "progress": 0.0
      }
    }
  ],
  "meta": {
    "scene_id": "seed-demo-001",
    "cached": true
  }
}
```

---

### 3.4 GET `/api/resource/list`

返回资源列表、AntD 表格结构和调度建议。

#### 请求参数

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `type` | string | 否 | 资源类型过滤 |
| `scene_id` | string | 否 | 场景 ID |

#### 返回结构

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `data._raw` | object | 原始资源数据 |
| `data.items` | array | 资源列表 |
| `data.stats` | object | 资源分组统计 |
| `data.table_data.columns` | array | AntD Columns 定义 |
| `data.table_data.rows` | array | AntD Table dataSource |
| `data.quick_actions` | array | 调度按钮 |

#### `quick_actions.params`

会透传给 `/decision/resource-dispatch`，常见字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `type` | string | 资源类型，如 `fire_truck` |
| `scene_id` | string | 当前场景 |
| `count` | number | 派发数量 |
| `priority` | string | 优先级 |

#### 示例响应

```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "_raw": {
      "items": [
        {
          "id": 1,
          "name": "重型水罐车",
          "type": "fire_truck",
          "status": "available",
          "location": {
            "lng": 114.29,
            "lat": 30.49
          },
          "scene_id": "seed-demo-001",
          "last_update": "2026-04-29T12:00:00+00:00"
        }
      ],
      "stats": {
        "fire_truck": 1
      },
      "table_data": {
        "columns": [
          { "title": "名称", "dataIndex": "name", "key": "name" },
          { "title": "类型", "dataIndex": "type", "key": "type" },
          { "title": "状态", "dataIndex": "status", "key": "status" },
          { "title": "位置", "dataIndex": "location", "key": "location" }
        ],
        "rows": [
          {
            "id": 1,
            "name": "重型水罐车",
            "type": "fire_truck",
            "status": "available",
            "location": { "lng": 114.29, "lat": 30.49 },
            "scene_id": "seed-demo-001",
            "last_update": "2026-04-29T12:00:00+00:00"
          }
        ]
      },
      "quick_actions": [
        {
          "label": "一键派发消防车",
          "endpoint": "/decision/resource-dispatch",
          "params": { "type": "fire_truck" }
        }
      ]
    },
    "items": [
      {
        "id": 1,
        "name": "重型水罐车",
        "type": "fire_truck",
        "status": "available",
        "location": { "lng": 114.29, "lat": 30.49 },
        "scene_id": "seed-demo-001",
        "last_update": "2026-04-29T12:00:00+00:00"
      }
    ],
    "stats": {
      "fire_truck": 1
    },
    "table_data": {
      "columns": [
        { "title": "名称", "dataIndex": "name", "key": "name" },
        { "title": "类型", "dataIndex": "type", "key": "type" },
        { "title": "状态", "dataIndex": "status", "key": "status" },
        { "title": "位置", "dataIndex": "location", "key": "location" }
      ],
      "rows": [
        {
          "id": 1,
          "name": "重型水罐车",
          "type": "fire_truck",
          "status": "available",
          "location": { "lng": 114.29, "lat": 30.49 },
          "scene_id": "seed-demo-001",
          "last_update": "2026-04-29T12:00:00+00:00"
        }
      ]
    },
    "quick_actions": [
      {
        "label": "一键派发消防车",
        "endpoint": "/decision/resource-dispatch",
        "params": { "type": "fire_truck" }
      }
    ]
  },
  "meta": {
    "scene_id": "seed-demo-001",
    "type": null
  }
}
```

---

### 3.5 GET `/api/personnel/list`

返回人员列表，支持按角色过滤。

#### 请求参数

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `role` | string | 否 | 人员角色过滤 |
| `scene_id` | string | 否 | 场景 ID |

#### 示例响应

```json
{
  "code": 200,
  "message": "ok",
  "data": [
    {
      "id": 1,
      "name": "张指挥",
      "type": "commander",
      "status": "on_duty",
      "location": null,
      "scene_id": "seed-demo-001",
      "last_update": "2026-04-29T12:00:00+00:00"
    }
  ],
  "meta": {
    "scene_id": "seed-demo-001",
    "role": null
  }
}
```

---

## 4. 聚合接口

### 4.1 GET `/api/command/overview`

指挥中心总览，聚合火情、无人机、资源、人员和告警。

#### 返回结构

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `fires.count` | number | 火情条数 |
| `fires.risk_level` | string | `high/medium/low` |
| `uavs.online` | number | 在线无人机数 |
| `uavs.total` | number | 无人机总数 |
| `resources.available` | number | 可用资源数 |
| `resources.in_use` | number | 使用中资源数 |
| `personnel.total` | number | 人员总数 |
| `personnel.active` | number | 活跃人数 |
| `alerts` | number | 近期告警数 |
| `timestamp` | string | ISO8601 更新时间 |

#### 示例响应

```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "fires": { "count": 1, "risk_level": "high" },
    "uavs": { "online": 1, "total": 3 },
    "resources": { "available": 1, "in_use": 0 },
    "personnel": { "total": 1, "active": 1 },
    "alerts": 1,
    "timestamp": "2026-04-29T12:00:00+00:00"
  },
  "meta": {
    "scene_id": "seed-demo-001"
  }
}
```

---

### 4.2 GET `/api/map/all`

地图多图层聚合，支持 `fire,uav,resource,personnel`。

#### 请求参数

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `layers` | string | 是 | 逗号分隔，如 `fire,uav` |
| `scene_id` | string | 否 | 场景 ID |

#### 返回结构

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `layers.fire` | FeatureCollection | 火线图层 |
| `layers.uav` | array | 无人机坐标点 |
| `layers.resource` | array | 资源坐标点 |
| `layers.personnel` | array | 人员坐标点 |
| `timestamp` | string | ISO8601 更新时间 |

#### 示例响应

```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "layers": {
      "fire": {
        "type": "FeatureCollection",
        "features": [
          {
            "type": "Feature",
            "geometry": {
              "type": "LineString",
              "coordinates": [[114.3, 30.5], [114.31, 30.5], [114.32, 30.5]]
            },
            "properties": {
              "scene_id": "seed-demo-001",
              "type": "fire_line",
              "step": 3,
              "popup": {
                "scene_id": "seed-demo-001",
                "type": "fire_line",
                "step": 3,
                "risk_hint": "火势向东蔓延"
              }
            }
          }
        ]
      },
      "uav": [
        {
          "id": 1,
          "lng": 114.31,
          "lat": 30.51,
          "status": "idle",
          "battery": 0
        }
      ]
    },
    "timestamp": "2026-04-29T12:00:00+00:00"
  },
  "meta": {
    "scene_id": "seed-demo-001",
    "layers": "fire,uav"
  }
}
```

---

### 4.3 GET `/api/fusion/result`

多源融合结果，适合融合页面直出。

#### 返回结构

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `confidence` | number | 置信度 0~1 |
| `sources` | string[] | 数据源列表 |
| `fire_estimation.area_km2` | number | 预测面积 |
| `fire_estimation.trend` | string | `expanding/stabilizing/declining` |
| `recommendation` | string | 融合建议 |
| `updated_at` | string | 更新时间 |

#### 示例响应

```json
{
  "code": 200,
  "message": "ok",
  "data": {
    "confidence": 0.87,
    "sources": ["satellite_stub", "uav_telemetry", "open_meteo"],
    "fire_estimation": {
      "area_km2": 0.85,
      "trend": "expanding"
    },
    "recommendation": "建议增派无人机加密侦察东侧区域",
    "updated_at": "2026-04-29T12:00:00+00:00"
  },
  "meta": {
    "scene_id": "seed-demo-001"
  }
}
```

---

## 5. WebSocket 接口

### 5.1 `/ws/alert`

火灾警报广播通道，连接后服务端会周期广播告警消息。

### 5.2 `/ws/uav`

无人机实时位置通道，服务端模拟位置变化并同步内存缓存。

---

## 6. 前端联调建议

1. 指挥中心页面优先使用 `/api/command/overview`。
2. 地图页面优先使用 `/api/map/all?layers=fire,uav,resource,personnel`。
3. 融合页面优先使用 `/api/fusion/result`。
4. 调试时可用 `?format=raw` 查看原始结构。
5. 所有页面建议传 `scene_id`，避免跨场景数据混用。

---

## 7. 常见错误

| 状态 | 场景 | 说明 |
| --- | --- | --- |
| 400 | `layers` 非法 | `map/all` 只允许 `fire,uav,resource,personnel` |
| 404 | 接口路径错误 | 检查前缀是否为 `/api` |
| 500 | 数据库异常 | 检查 SQLite 和依赖注入 |

---

## 8. 变更记录

| 时间 | 版本 | 说明 |
| --- | --- | --- |
| 2026-04-29 | v1.0 | 初版接口文档，覆盖前端友好接口、聚合接口与 WebSocket |
| 2026-04-29 | v1.1 | 增加指挥中心与多源融合聚合接口说明 |
| 2026-04-29 | v1.2 | 补充 UI 直出字段与前端建议 |
