# 火点候选核心数据契约 v0.1

可以先开始开发，不需要等待所有真实数据下载完成。请先按照下面的临时核心契约开发适配器，后续只在 `product_fields` 中补充 FIRMS、Sentinel-2、无人机等产品字段，不修改核心字段。

## 临时核心字段

| 字段 | 约定 |
|---|---|
| `candidate_id` | 稳定唯一编号，不能使用数组下标 |
| `event_id` | 火灾事件编号，例如 `dixie_fire_2021` |
| `location.longitude` | 经度，单位 degree，EPSG:4326 |
| `location.latitude` | 纬度，单位 degree，EPSG:4326 |
| `observed_at` | 观测时间，统一 UTC，ISO 8601 格式 |
| `status` | `candidate`、`under_review`、`confirmed`、`rejected`、`expired` |
| `data_owner` | 数据来源和数据权属信息 |
| `imagery_refs` | 影像引用列表，不直接嵌入图片 |
| `imagery_status` | `pending`、`available`、`unavailable` |
| `is_simulated` | 是否为合成数据 |
| `replay.is_replay` | 是否为历史数据回放 |
| `product_fields` | 产品专有字段，后续可以扩展 |

## 临时 JSON

```json
{
  "schema_version": "fire.hotspot.candidate.v0.1",
  "candidate_id": "dixie_fire_2021-firms-viirs_snpp-20210713T093000Z-39.926410--120.057170",
  "event_id": "dixie_fire_2021",
  "event_name": "Dixie Fire",
  "location": {
    "longitude": -120.05717,
    "latitude": 39.92641,
    "crs": "EPSG:4326"
  },
  "observed_at": "2021-07-13T09:30:00Z",
  "status": "candidate",
  "data_owner": {
    "organization": "NASA FIRMS",
    "source_product": "VIIRS_SNPP_SP",
    "license": "NASA Earthdata/FIRMS",
    "attribution_required": true
  },
  "imagery_status": "pending",
  "imagery_refs": [],
  "is_simulated": false,
  "replay": {
    "is_replay": true,
    "replay_interval_minutes": 10,
    "replay_source": "historical_observation"
  },
  "product_fields": {
    "firms": {
      "satellite": "N",
      "instrument": "VIIRS",
      "confidence": "n",
      "brightness_ti4": 299.76,
      "brightness_ti5": 288.25,
      "frp_mw": 0.97,
      "daynight": "N",
      "source_file": "data/raw/firms/dixie_fire_2021_20210713.csv"
    }
  }
}
```

## 使用约定

1. `is_simulated=false` 表示这个火点来自真实历史 FIRMS 观测。
2. `replay.is_replay=true` 表示系统把历史数据按实时流程回放，不代表火点本身是假的。
3. `imagery_refs` 目前可以为空，视觉适配器需要支持 `imagery_status=pending`。
4. 影像不要直接放 Base64，使用 `asset_id`、相对文件路径或后端 API 地址引用。
5. FIRMS 的 `confidence` 原始值可能是 `n`、`l`、`h`，暂时保留原始值，不要强行转换。
6. 所有时间统一使用 UTC，FIRMS 的 `acq_time=930` 应转换为 `2021-07-13T09:30:00Z`。
7. `candidate_id` 应由事件、数据源、观测时间和坐标共同生成，保证同一火点重复导入时编号不变。

## 影像引用示例

真实影像到位后，只需填充 `imagery_refs`：

```json
"imagery_refs": [
  {
    "asset_id": "dixie-sentinel2-20210715",
    "uri": "data/raw/sentinel2/dixie_during.tif",
    "source": "Sentinel-2",
    "mime_type": "image/tiff",
    "acquired_at": "2021-07-15T18:20:00Z"
  }
]
```

乙同学可以先使用本文件中的 JSON 建立 Qwen-VL 适配器和测试用例。真实影像到位后，只补充 `imagery_refs` 和 `product_fields`，不修改核心字段。
