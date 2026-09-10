# 数据智能体说明

## 它负责什么

数据智能体是系统的数据检索和编排层，负责根据事件编号和任务需求找到正确的数据，并返回：

- 数据集名称、来源和许可
- 时间范围、空间范围和坐标系
- 原始文件或处理后栅格的路径
- 对应的业务 API
- 数据处理步骤和已知限制

它不负责识别火点、不负责火势数值推演，也不负责替代 ForeFire。它把这些专业模块需要的数据组织好，再交给对应模块。

## 当前实现

当前版本使用确定性检索，不依赖大模型：

```text
event_id + needs
        -> 数据需求白名单
        -> PostGIS fire_data_manifests
        -> 返回 API、GeoTIFF 路径和交接说明
```

接口：

```text
GET  /api/data-agent/catalog/dixie_fire_2021
POST /api/data-agent/resolve
```

示例请求：

```json
{
  "event_id": "dixie_fire_2021",
  "needs": ["hotspots", "weather", "terrain", "slope", "aspect", "fuel"]
}
```

## 是否需要大模型

不需要。基础数据检索必须保持可重复、可审计，因此使用 SQL、manifest 和需求白名单更可靠。

大模型可以作为可选的上层入口：

```text
用户自然语言问题
        -> Qwen 解析事件、时间和数据需求
        -> 调用确定性 data-agent/resolve
        -> 返回数据包
```

例如 Qwen 可以把“分析 Dixie Fire 的地形和燃料数据”转换为：

```json
{
  "event_id": "dixie_fire_2021",
  "needs": ["terrain", "slope", "aspect", "fuel"]
}
```

## API Key 说明

- 当前数据智能体：不需要 API Key。
- Qwen 云端语言模型：需要相应服务商的 API Key。
- Qwen-VL 云端视觉模型：需要相应服务商的 API Key，并且还需要图像可访问或可上传。
- 本地部署 Qwen、vLLM 或 Ollama：通常不需要云端 API Key，但需要本机模型文件、显存和推理服务。

当前项目不应因为没有 Qwen Key 而阻塞数据检索、数据库建设和 ForeFire 输入准备。Key 只在启用自然语言解析、视觉核验或报告生成时配置。

## 成员交接

- 乙：调用 `hotspots`，再把 `imagery_refs` 交给 Qwen-VL。
- 丙：调用 `forefire_input` 获取甲整理的 ForeFire 输入清单，再调用 `terrain`、`slope`、`aspect`、`fuel` 和 `weather_hourly` 准备 ForeFire 输入。
- 丁：调用 `burned_area`、`hotspots`、`weather` 和火势输出，做影响分析和应急决策。
- 小时气象：调用 `weather_hourly` 获取 NASA POWER 小时数据，供 ForeFire 输入准备；当前数据未插值，`is_interpolated=false`。

小时气象接口：

```text
GET /api/data/events/{event_id}/weather-hourly
```

日尺度和小时尺度是两个独立数据集。日尺度接口不会自动返回小时数据，小时接口也不会覆盖日尺度数据。

历史实时回放接口：

```text
GET /api/data/events/{event_id}/realtime-replay?start_at=2021-07-14T09:00:00Z&end_at=2021-07-14T12:00:00Z
```

该接口使用已经入库的 FIRMS 火点聚合单元，时间粒度为 10 分钟、空间网格为 0.02°，用于模拟卫星火情产品的定时更新；它是历史回放，不是实时卫星数据。
