# [Frontend-Contract] B端→前端字段契约清单 v1.0

> 说明：本文档仅描述 B 端对前端暴露的行为，不改变 C 端契约。
> 默认返回结构均为：`{ code, message, data, meta }`。
> `?format=raw` 可切换为原始结构。

---

## 1. GET `/api/fire/stat?scene_id=xxx`

### 1.1 返回结构总览

| 字段路径 | 类型 | 必填 | 可能为空 | 示例值 | UI 映射建议 |
| --- | --- | --- | --- | --- | --- |
| `data._raw` | object | 是 | 否 | `{...}` | 调试/兜底数据，不直接用于组件渲染 |
| `data.risk_level` | `"low" \| "medium" \| "high"` | 是 | 否 | `"high"` | 风险标签、告警色块 |
| `data.chart_data` | object | 是 | 否 | 见下方 | ECharts 折线/面积图 |
| `data.summary_cards` | array | 是 | 否 | 见下方 | AntD Card / Statistic |
| `data.metrics` | object | 否 | 是 | `{ fire_area_km2: 0.85 }` | 统计卡补充指标 |
| `data.wind_params` | object | 否 | 是 | `{ wind_speed: 6.5, wind_dir: 45 }` | 风向/风速标签 |
| `data.agent_summary` | string | 否 | 是 | `"火势向东蔓延..."` | 指挥建议提示条 |
| `data.stats` | object | 否 | 是 | `{ current_step: 2 }` | 页面底部摘要 |

### 1.2 `data.chart_data`

| 字段路径 | 类型 | 必填 | 示例值 | 是否可能为空 | UI 映射建议 |
| --- | --- | --- | --- | --- | --- |
| `data.chart_data.xAxis` | string[] | 是 | `["T0","T1","T2"]` | 否 | ECharts X 轴标签 |
| `data.chart_data.series` | array | 是 | `[{ name: "面积(km²)", data: [0.1,0.45,0.85] }]` | 否 | ECharts series |

#### 说明

- `chart_data.xAxis` **默认固定**为 `[
  "T0",
  "T1",
  "T2"
]`，用于演示和 UI 初始渲染；
- 当后端接入真实时序后，可扩展为动态时间点，但当前 B 端 P0 接口保持三段式输出，便于前端统一布局；
- `series[].data` 建议与 `xAxis` 等长，长度不一致时前端应按最短长度截断。

### 1.3 `data.risk_level` 映射建议

| 枚举值 | 含义 | 建议颜色 | 建议文案 |
| --- | --- | --- | --- |
| `low` | 低风险 | `#52c41a` | 低风险 |
| `medium` | 中风险 | `#faad14` | 中风险 |
| `high` | 高风险 | `#ff4d4f` | 高风险 |

### 1.4 `data.summary_cards`

| 字段路径 | 类型 | 必填 | 是否可能为空 | 示例值 | UI 映射建议 |
| --- | --- | --- | --- | --- | --- |
| `data.summary_cards[].label` | string | 是 | 否 | `"过火面积"` | Card 标题 |
| `data.summary_cards[].value` | string \| number | 是 | 否 | `"0.85km²"` | 大号数字 / Statistic |
| `data.summary_cards[].color` | string | 是 | 否 | `"#ff4d4f"` | 文字/边框强调色 |
| `data.summary_cards[].trend` | string | 是 | 否 | `"+12%"` | 趋势箭头/标签 |

#### `trend` 解析建议

| 格式 | 解析结果 | 建议前端处理 |
| --- | --- | --- |
| `+12%` | 正向增长 | 显示上升箭头 + 红/橙色 |
| `-5%` | 负向下降 | 显示下降箭头 + 绿色 |
| `稳定` | 无明显变化 | 显示中性状态 |

> 建议解析规则：
> - 以 `+` 开头视为上升；
> - 以 `-` 开头视为下降；
> - 其他值视为稳定/未知。

### 1.5 `data._raw`

| 字段路径 | 类型 | 必填 | 可能为空 | 示例值 | UI 映射建议 |
| --- | --- | --- | --- | --- | --- |
| `data._raw.scene_id` | string | 是 | 否 | `"demo"` | 调试标识 |
| `data._raw.current_step` | number | 是 | 否 | `2` | 时间轴/步骤条 |
| `data._raw.fire_area` | number | 是 | 否 | `0.85` | 与 chart_data 对应 |
| `data._raw.spread_speed` | number | 是 | 否 | `1.2` | 指标补充 |
| `data._raw.wind_params` | object | 是 | 否 | `{ wind_speed: 6.5, wind_dir: 45 }` | 风况信息 |
| `data._raw.risk_level` | string | 是 | 否 | `"high"` | 风险标签 |
| `data._raw.agent_summary` | string | 是 | 否 | `"火势向东蔓延..."` | 指挥建议 |
| `data._raw.current_fire_geojson` | object | 是 | 否 | Feature | 地图原始 GeoJSON |
| `data._raw.stats` | object | 否 | 是 | `{...}` | 调试/兜底 |

### 1.6 前端对接示例

```ts
// A同学可直接使用：
// const res = await fetch('/api/fire/stat?scene_id=demo')
// const json = await res.json()
// const { chart_data, summary_cards, risk_level } = json.data
// echarts.setOption({ xAxis: { data: chart_data.xAxis }, series: chart_data.series })
```

```tsx
import { useEffect, useState } from 'react'

export function FireStatPanel({ sceneId }: { sceneId: string }) {
  const [data, setData] = useState<any>(null)

  useEffect(() => {
    fetch(`/api/fire/stat?scene_id=${sceneId}`)
      .then((r) => r.json())
      .then((json) => setData(json.data))
  }, [sceneId])

  return <div>{data?.summary_cards?.[0]?.value ?? '加载中'}</div>
}
```

---

## 2. GET `/api/resource/list?type=xxx`

### 2.1 返回结构总览

| 字段路径 | 类型 | 必填 | 可能为空 | 示例值 | UI 映射建议 |
| --- | --- | --- | --- | --- | --- |
| `data._raw` | object | 是 | 否 | `{...}` | 原始兜底数据 |
| `data.table_data` | object | 是 | 否 | 见下方 | AntD Table |
| `data.stats` | object | 是 | 否 | `{ fire_truck: 2 }` | 图表/统计卡 |
| `data.quick_actions` | array | 否 | 是 | 见下方 | 操作按钮栏 |
| `data.items` | array | 是 | 否 | 资源列表 | 列表/下拉选择器 |

### 2.2 `data.table_data`

| 字段路径 | 类型 | 必填 | 示例值 | 是否可能为空 | UI 映射建议 |
| --- | --- | --- | --- | --- | --- |
| `data.table_data.columns` | array | 是 | AntD Columns[] | 否 | `columns` 直接传给 Table |
| `data.table_data.rows` | array | 是 | 平铺数组 | 否 | `dataSource` 直接传给 Table |

#### AntD Table Columns 类型约束

```ts
import type { ColumnsType } from 'antd/es/table'

interface ResourceRow {
  id: number | string
  name: string
  type: string
  status: string
  location?: unknown
  scene_id?: string
  last_update?: string | null
}

const columns: ColumnsType<ResourceRow> = [
  { title: '名称', dataIndex: 'name', key: 'name' },
  { title: '类型', dataIndex: 'type', key: 'type' },
  { title: '状态', dataIndex: 'status', key: 'status' },
  { title: '位置', dataIndex: 'location', key: 'location' },
]
```

### 2.3 `data.stats`

| 字段路径 | 类型 | 必填 | 示例值 | 可能为空 | UI 映射建议 |
| --- | --- | --- | --- | --- | --- |
| `data.stats.<resource_type>` | number | 是 | `2` | 否 | 饼图、柱状图、分组徽章 |

#### 说明

- `stats` 的 key 为资源类型聚合值，例如：`fire_truck`、`water_pump`、`first_aid`；
- 前端可以直接 `Object.entries(stats)` 渲染图例或统计卡。

### 2.4 `data.quick_actions`

| 字段路径 | 类型 | 必填 | 示例值 | 可能为空 | UI 映射建议 |
| --- | --- | --- | --- | --- | --- |
| `data.quick_actions[].label` | string | 是 | `"一键派发消防车"` | 否 | Button 文案 |
| `data.quick_actions[].endpoint` | string | 是 | `"/decision/resource-dispatch"` | 否 | 点击跳转/请求地址 |
| `data.quick_actions[].params` | object | 是 | `{ type: 'fire_truck' }` | 否 | 透传给调度接口 |

#### `params` 透传说明

`quick_actions[].params` 会原样透传到 `/decision/resource-dispatch`，当前建议字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `type` | string | 资源类型，例如 `fire_truck` |
| `scene_id` | string | 可选，建议前端带上当前场景 |
| `count` | number | 可选，派发数量 |
| `priority` | string | 可选，派发优先级 |

### 2.5 前端对接示例

```ts
// A同学可直接使用：
// const res = await fetch('/api/resource/list?type=fire_truck')
// const json = await res.json()
// const { table_data, quick_actions, stats } = json.data
// <Table columns={table_data.columns} dataSource={table_data.rows} />
```

```tsx
import { Button, Table } from 'antd'

export function ResourcePanel() {
  const [payload, setPayload] = useState<any>(null)

  useEffect(() => {
    fetch('/api/resource/list?type=fire_truck')
      .then((r) => r.json())
      .then((json) => setPayload(json.data))
  }, [])

  return (
    <>
      <div>
        {payload?.quick_actions?.map((action: any) => (
          <Button key={action.label} onClick={() => console.log(action.endpoint, action.params)}>
            {action.label}
          </Button>
        ))}
      </div>
      <Table columns={payload?.table_data?.columns ?? []} dataSource={payload?.table_data?.rows ?? []} />
    </>
  )
}
```

---

## 3. GET `/api/fire/list?scene_id=xxx`

### 3.1 GeoJSON 结构要求

| 字段路径 | 类型 | 必填 | 可能为空 | 示例值 | UI 映射建议 |
| --- | --- | --- | --- | --- | --- |
| `data.type` | string | 是 | 否 | `"FeatureCollection"` | Mapbox Source |
| `data.features` | array | 是 | 否 | `[]` | Mapbox Layer |
| `data.coords` | array | 否 | 是 | `[[lng,lat], ...]` | 调试/备用坐标 |

### 3.2 `features[].properties.popup`

| 字段路径 | 类型 | 必填 | 可能为空 | 示例值 | UI 映射建议 |
| --- | --- | --- | --- | --- | --- |
| `popup.scene_id` | string | 是 | 否 | `"demo"` | 气泡标题/上下文 |
| `popup.type` | string | 是 | 否 | `"fire_line"` | 图层分类 |
| `popup.step` | number | 是 | 否 | `3` | 时间步/阶段 |
| `popup.risk_hint` | string | 是 | 否 | `"火势向东蔓延"` | 气泡提示文案 |

#### 是否可选说明

- `popup` **建议必填**，用于地图点击气泡展示；
- 当前 B 端 P0 接口中，`scene_id/type/step/risk_hint` 都会返回；
- 若未来接入更复杂 GeoJSON，可继续在 `popup` 下扩展字段，前端无需改数据主结构。

### 3.3 坐标格式强制说明

| 规则 | 说明 |
| --- | --- |
| 正确格式 | `[lng, lat]` |
| 错误格式 | `[lat, lng]` |
| 禁止形式 | 深层嵌套但不符合 GeoJSON 的坐标数组 |

#### 示例

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "LineString",
        "coordinates": [
          [114.30, 30.50],
          [114.31, 30.50],
          [114.32, 30.50]
        ]
      },
      "properties": {
        "popup": {
          "scene_id": "demo",
          "type": "fire_line",
          "step": 3,
          "risk_hint": "火势向东蔓延"
        }
      }
    }
  ]
}
```

### 3.4 前端对接示例

```ts
// A同学可直接使用：
// const res = await fetch('/api/fire/list?scene_id=demo')
// const json = await res.json()
// mapboxSource.setData(json.data)
```

```tsx
import { useEffect } from 'react'

export function FireMap({ sceneId }: { sceneId: string }) {
  useEffect(() => {
    fetch(`/api/fire/list?scene_id=${sceneId}`)
      .then((r) => r.json())
      .then((json) => {
        console.log(json.data)
      })
  }, [sceneId])

  return <div id="map" />
}
```

---

## 4. 聚合接口契约

### 4.1 GET `/api/command/overview?scene_id=xxx`

| 字段路径 | 类型 | 必填 | 可能为空 | 示例值 | UI 映射建议 |
| --- | --- | --- | --- | --- | --- |
| `data.fires.count` | number | 是 | 否 | `1` | 指挥中心火情卡 |
| `data.fires.risk_level` | `low/medium/high` | 是 | 否 | `"high"` | 风险标签 |
| `data.uavs.online` | number | 是 | 否 | `2` | UAV 在线统计 |
| `data.uavs.total` | number | 是 | 否 | `3` | UAV 总量 |
| `data.resources.available` | number | 是 | 否 | `2` | 资源可用数 |
| `data.resources.in_use` | number | 是 | 否 | `1` | 资源占用数 |
| `data.personnel.total` | number | 是 | 否 | `8` | 人员总数 |
| `data.personnel.active` | number | 是 | 否 | `6` | 在岗数 |
| `data.alerts` | number | 是 | 否 | `3` | 告警角标 |
| `data.timestamp` | string | 是 | 否 | ISO8601 | 更新时间 |

### 4.2 GET `/api/map/all?layers=fire,uav,resource&scene_id=xxx`

| 字段路径 | 类型 | 必填 | 可能为空 | 示例值 | UI 映射建议 |
| --- | --- | --- | --- | --- | --- |
| `data.layers.fire` | FeatureCollection | 条件必填 | 是 | GeoJSON | Mapbox 火线层 |
| `data.layers.uav` | array | 条件必填 | 是 | UAV 坐标数组 | 无人机散点层 |
| `data.layers.resource` | array | 条件必填 | 是 | 资源坐标数组 | 资源点位层 |
| `data.layers.personnel` | array | 条件必填 | 是 | 人员坐标数组 | 人员点位层 |
| `data.timestamp` | string | 是 | 否 | ISO8601 | 更新时间 |

### 4.3 GET `/api/fusion/result?scene_id=xxx`

| 字段路径 | 类型 | 必填 | 可能为空 | 示例值 | UI 映射建议 |
| --- | --- | --- | --- | --- | --- |
| `data.confidence` | number | 是 | 否 | `0.87` | 融合置信度仪表盘 |
| `data.sources` | string[] | 是 | 否 | `["satellite_stub"]` | 数据源标签 |
| `data.fire_estimation.area_km2` | number | 是 | 否 | `0.85` | 面积指标 |
| `data.fire_estimation.trend` | string | 是 | 否 | `"expanding"` | 趋势箭头 |
| `data.recommendation` | string | 是 | 否 | `"建议增派..."` | 建议卡片 |
| `data.updated_at` | string | 是 | 否 | ISO8601 | 更新时间 |

### 4.4 前端对接示例

```ts
// 指挥中心卡片
const overview = await get('/api/command/overview?scene_id=demo')
// 地图多图层
const layers = await get('/api/map/all?layers=fire,uav&scene_id=demo')
// 融合页面
const fusion = await get('/api/fusion/result?scene_id=demo')
```

## 5. 变更历史

| 时间 | 版本 | 变更内容 | 状态 |
| --- | --- | --- | --- |
| 2026-04-29 | v1.0 | 初版字段契约清单，覆盖 fire/stat、resource/list、fire/list | 生效 |
| 2026-04-29 | v1.0 | 明确 `?format=raw` 与 UI 直出双模式 | 生效 |
| 2026-04-29 | v1.0 | 补充 `summary_cards`、`table_data`、`popup` 结构 | 生效 |

---

## 5. 联调说明

- 推荐前端优先读取 UI 直出结构；
- 调试时可加 `?format=raw` 查看原始数据；
- 所有接口都建议传 `scene_id`，避免场景串用；
- 地图组件优先消费 `FeatureCollection`，表格组件优先消费 `table_data`。
