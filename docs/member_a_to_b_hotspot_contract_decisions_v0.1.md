# 火点候选契约问题确认 v0.1

以下规则用于乙同学开发视觉核验适配器。适配器现在即可使用样例 JSON 开发，不需要等待全部影像下载完成。

## 1. `status` 由谁设置、依据什么设置

### 状态流转

```text
candidate -> under_review -> confirmed
                         \-> rejected

candidate/under_review -> expired
```

| 状态 | 设置者 | 设置依据 |
|---|---|---|
| `candidate` | 甲的数据接入模块 | FIRMS 或其他遥感产品完成有效解析，坐标、时间和来源字段完整；这只表示候选火点，不表示已经确认着火 |
| `under_review` | 业务编排层 | 候选点已提交给乙的视觉核验适配器，等待 Qwen-VL 或人工审核 |
| `confirmed` | 乙返回视觉核验结果后，由业务编排层写入 | Qwen-VL 返回 `fire=true` 且置信度达到约定阈值，或人工审核明确确认；必须保留核验结果和证据引用 |
| `rejected` | 乙返回视觉核验结果后，由业务编排层写入 | Qwen-VL 判断无火、影像不可支持火情，或人工审核否定；必须保留原因 |
| `expired` | 实时监测编排层 | 在规定时间内没有新的观测或复核结果；历史回放数据通常不主动设置为该状态 |

甲模块不会仅凭 FIRMS 一个火点把状态设置为 `confirmed`。甲只负责产生 `candidate`，并根据工作流把候选点送入 `under_review`。乙返回的视觉核验结果必须包含 `fire`、`confidence`、`reason` 和证据引用，编排层再负责最终状态落库。

## 2. 实际交付形式

系统采用三种形式，各自用途不同：

### PostGIS

PostGIS 是事实数据的持久化存储，保存事件、原始 FIRMS 观测、筛选后的候选火点和影像引用。

### HTTP 批量接口

乙的适配器主要通过 HTTP 获取候选点，接口返回批量 JSON 包络，不直接返回裸数组：

```http
GET /api/data/events/dixie_fire_2021/hotspots?status=candidate&limit=100
```

约定返回结构：

```json
{
  "schema_version": "fire.hotspot.candidate.v0.1",
  "event_id": "dixie_fire_2021",
  "generated_at": "2021-07-13T09:30:05Z",
  "candidates": []
}
```

### MQTT 增量消息

实时监测或历史回放时，通过 MQTT 推送新增观测：

```text
fire/events/dixie_fire_2021/hotspots
```

消息也使用上面的批量 JSON 包络；单次可以有一个或多个 `candidates`。乙可以订阅 MQTT 触发适配器，再通过 HTTP 获取完整候选记录和影像引用。

### JSON 文件

JSON 文件只用于开发样例、离线测试和接口回归测试，不作为生产状态同步机制。乙现在可以直接使用：

```text
docs/member_a_to_b_hotspot_contract_v0.1.md
```

## 3. `candidate_id` 固定规则

为保证重复导入得到同一个编号，核心规则固定如下：

1. 坐标统一为 WGS84，即 `EPSG:4326`。
2. 纬度和经度都四舍五入到小数点后 6 位。
3. FIRMS 的 `acq_date` 与 `acq_time` 先组合，并解释为 UTC。
4. `acq_time` 左侧补零到 4 位，例如 `930` 变为 `0930`。
5. 使用固定的源产品标识 `firms-viirs_snpp`。
6. 拼接格式固定为：

```text
{event_id}-firms-viirs_snpp-{YYYYMMDD}T{HHMMSS}Z-{latitude_6}-{longitude_6}
```

示例：

```text
dixie_fire_2021-firms-viirs_snpp-20210713T093000Z-39.926410--120.057170
```

其中纬度和经度之间的第一个连字符是字段分隔符，第二个连字符是负经度的负号，不要删除。候选编号不使用 CSV 行号或数组下标。产品字段变化、影像补充和重复导入都不能改变 `candidate_id`。

## 4. 影像未到位时的处理

影像还没有准备好时，固定使用：

```json
{
  "imagery_status": "pending",
  "imagery_refs": []
}
```

乙的适配器需要能够读取并处理这种状态，不应因为影像为空而崩溃。影像到位后，只追加 `imagery_refs`，不修改候选点核心字段。
