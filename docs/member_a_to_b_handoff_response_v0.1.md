# 甲给乙的火点候选与影像联调交接说明 v0.1

乙，你提出的 6 项要求已核对，当前情况如下。

## 1. 真实批量接口

Dixie Fire 的真实接口已经可用：

```http
GET http://localhost:8200/api/data/events/dixie_fire_2021/hotspots?status=candidate&limit=3
```

注意：实际返回数组字段是 `items`，不是 `candidates`。

当前真实返回的关键结构如下：

```json
{
  "schema_version": "fire.hotspot.candidate.v0.1",
  "event_id": "dixie_fire_2021",
  "generated_at": "2026-09-09T08:12:38.862395Z",
  "aggregate": false,
  "total": 60013,
  "limit": 3,
  "offset": 0,
  "items": [
    {
      "candidate_id": "dixie_fire_2021-firms-viirs_snpp-20210714T091100Z-39.871940--121.382410",
      "event_id": "dixie_fire_2021",
      "observed_at": "2021-07-14T09:11:00Z",
      "status": "candidate",
      "data_owner": "NASA FIRMS",
      "source_product": "VIIRS_SNPP_SP",
      "imagery_status": "pending",
      "imagery_refs": [],
      "is_simulated": false,
      "confidence_raw": "n",
      "confidence_score": 0.5,
      "frp_mw": 5.61,
      "brightness_ti4": 349.87,
      "brightness_ti5": 293.96,
      "location": {
        "longitude": -121.38241,
        "latitude": 39.87194,
        "crs": "EPSG:4326"
      },
      "product_fields": {
        "firms": {
          "frp_mw": 5.61,
          "daynight": "N",
          "satellite": "N",
          "attributes": {
            "version": "2",
            "acq_time_utc": "0911",
            "source_confidence": "n"
          },
          "confidence": "n",
          "instrument": "VIIRS"
        }
      },
      "replay": {
        "is_replay": true
      }
    }
  ]
}
```

当前字段规则如下：

- `schema_version` 只出现在顶层。
- `event_id` 同时出现在顶层和每个候选点对象中。
- 时间统一为 UTC ISO 8601 格式。
- 坐标为 WGS84，即 `EPSG:4326`。
- `generated_at` 是接口生成时间。
- `observed_at` 是 FIRMS 实际观测时间。
- `product_fields` 用于保存 FIRMS 等数据源的专有字段。
- 当前已经入库的候选点数量为 60,013 条。

## 2. 两阶段影像状态

当前真实数据均为：

```json
{
  "imagery_status": "pending",
  "imagery_refs": []
}
```

目前还没有真实的 `imagery_status=available` 数据，因此暂时不能提供真实的 available 样例，也不会伪造影像 URI。

乙可以先使用以下结构开发适配器：

```json
{
  "candidate_id": "dixie_fire_2021-firms-viirs_snpp-20210714T091100Z-39.871940--121.382410",
  "event_id": "dixie_fire_2021",
  "observed_at": "2021-07-14T09:11:00Z",
  "location": {
    "longitude": -121.38241,
    "latitude": 39.87194,
    "crs": "EPSG:4326"
  },
  "status": "candidate",
  "imagery_status": "available",
  "imagery_refs": [
    {
      "asset_id": "待甲提供",
      "uri": "待甲提供",
      "source": "Sentinel-2",
      "mime_type": "image/tiff",
      "acquired_at": "待甲提供",
      "coverage_bbox": [
        -121.40,
        39.85,
        -121.36,
        39.90
      ]
    }
  ]
}
```

以上只是开发用结构，不代表真实影像已经入库。影像资产准备好后，除 `imagery_status`、`imagery_refs` 和允许扩展的 `product_fields` 外，候选点的 ID、坐标、事件和观测时间都不会改变。

## 3. 影像 URI 规则

当前约定如下：

- 仓库相对路径相对于仓库根目录 `E:\fire-command-system`。
- 例如：

```text
data/raw/sentinel2/dixie_fire/example.tif
```

- 在 `fire-agent-api` 容器中对应：

```text
/app/data/raw/sentinel2/dixie_fire/example.tif
```

- 本机对应：

```text
E:\fire-command-system\data\raw\sentinel2\dixie_fire\example.tif
```

乙的模块不要直接猜测或拼接本机路径。当前影像资产 API 还没有正式实现，因此真实影像到位后，需要通过共享数据目录或后端资产接口访问。

后续建议统一使用资产接口，例如：

```http
GET /api/data/assets/{asset_id}
```

该接口应返回原图或裁剪图的访问地址、文件大小、MIME 类型和空间范围。正式资产接口完成前，乙可以先按照上述 URI 规则开发本地适配器。

## 4. 影像资产信息

目前暂时没有真实的 Sentinel-2、Landsat 或无人机影像资产，因此以下字段尚待补充：

- `asset_id`
- `uri`
- `mime_type`
- `acquired_at`
- 文件大小
- 是否裁剪
- CRS
- 空间范围
- 分辨率
- 波段含义
- NoData 值
- 云掩膜状态

首个真实资产准备好后，会优先提供一个与上述候选点关联的小范围影像，用于乙完成裁剪和 Qwen-VL 适配器联调。

## 5. 影像空间覆盖范围

建议正式加入 `imagery_refs`：

```json
"coverage_bbox": [
  -121.40,
  39.85,
  -121.36,
  39.90
]
```

字段顺序固定为：

```text
[west, south, east, north]
```

坐标系固定为 WGS84/EPSG:4326。

乙可以先按可选字段支持，影像没有该字段时不要报错。

## 6. 乙的复核结果回写方式

最终采用以下原则：

- 乙不直接修改甲的数据表。
- 乙只负责输出视觉核验结果。
- 业务编排层负责最终状态流转和写库。

状态规则：

```text
candidate -> under_review -> confirmed
                         \\-> rejected
```

建议乙返回以下结果：

```json
{
  "candidate_id": "dixie_fire_2021-firms-viirs_snpp-20210714T091100Z-39.871940--121.382410",
  "verifier_version": "qwen-vl-adapter-v0.1",
  "imagery_asset_id": "asset-id",
  "fire": true,
  "smoke": true,
  "confidence": 0.92,
  "reason": "影像中存在明显火焰和烟羽特征",
  "evidence_refs": [
    "asset-id"
  ],
  "reviewed_at": "2026-09-09T08:30:00Z"
}
```

建议幂等键固定为：

```text
candidate_id + verifier_version + imagery_asset_id
```

状态处理规则：

- 没有影像：保持 `imagery_status=pending`，不进入最终确认。
- 影像不可访问：记录失败原因，保持 `under_review` 或标记 `imagery_status=unavailable`。
- 模型不确定：保持 `under_review`，不能直接设置为 `confirmed` 或 `rejected`。
- 模型明确判断有火：由业务编排层根据置信度和证据设置 `confirmed`。
- 模型明确判断无火：由业务编排层设置 `rejected`。
- 乙不直接操作 PostGIS。

目前候选点查询接口已经可以用于乙开发。真实影像资产、available 样例和结果回写接口仍在甲模块后续工作中补齐，补齐后不会修改现有核心字段和 `candidate_id` 规则。

## 兼容性说明

之前契约文档中使用了 `candidates` 字段作为占位示例，但当前实际接口已经统一使用 `items`，请以真实接口返回为准。
