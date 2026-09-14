# 甲模块实时数据接口

本接口属于甲模块的实时候选火点数据源，服务地址为 `http://localhost:8200`，前端通过 Nginx 使用同源 `/api` 路径访问。

## 数据定位

当前实现使用 NASA FIRMS NRT 的 VIIRS 候选火点产品作为实时数据入口。它不是历史 Dixie Fire 数据，也不是 GOES/Himawari 原始栅格影像；返回结果必须标记为 `realtime_candidate`，供监测页展示和后续视觉核验。GOES-18、Himawari-8/9 的区域入口目前表示对应卫星覆盖区，后续可替换为各自的原始卫星数据适配器。接口中的 `satellite` 字段当前明确为 `FIRMS NRT / VIIRS`，避免把候选产品误称为 GOES 或 Himawari 原始观测。

## 配置

在仓库根目录 `.env` 中填写本机密钥，不要提交或发送该文件：

```dotenv
FIRMS_MAP_KEY=你的NASA_FIRMS_MAP_KEY
```

修改后重新创建后端容器：

```text
docker compose up -d --build fire-agent-api
```

## 接口

### 查询可用区域

```http
GET /api/realtime/regions
```

### 同步一次实时候选火点

```http
POST /api/realtime/sync
Content-Type: application/json

{"region_id":"goes18_north_america_west"}
```

当前支持的区域 ID：

- `goes18_north_america_west`
- `himawari_asia_pacific`

接口每次请求会：

1. 从 FIRMS NRT 下载最近数据；
2. 保存原始 CSV 到 `data/raw/realtime/firms_nrt/{region_id}/`；
3. 解析经纬度、观测时间、置信度和 FRP；
4. 把观测批次和候选火点写入 PostgreSQL/PostGIS；
5. 保存处理 JSON 和清单到 `data/processed/realtime/`；
6. 默认仅保留最近 3 批文件，数据库记录不删除。

实时候选点在 PostgreSQL 中保存经纬度，并由 PostGIS 生成 `location_geom geometry(Point, 4326)` 及 GiST 空间索引，坐标基准为 WGS84。

下载或解析失败时，旧文件和旧数据库记录保留，接口返回 `ready: false`。

### 查询最新状态

```http
GET /api/realtime/status?region_id=goes18_north_america_west
```

### 查询最新候选点

```http
GET /api/realtime/hotspots?region_id=goes18_north_america_west
```

也可以指定某个观测批次：

```http
GET /api/realtime/hotspots?region_id=goes18_north_america_west&observation_id=...
```

### 查询观测批次

```http
GET /api/realtime/observations?region_id=goes18_north_america_west
```

## 数据智能体检索

查询所有实时区域及各区域最新本地观测：

```http
GET /api/data-agent/realtime-catalog
```

按任务解析实时候选火点：

```http
POST /api/data-agent/resolve
Content-Type: application/json

{
  "needs": ["realtime_hotspots"],
  "region_id": "goes18_north_america_west"
}
```

该解析接口返回候选点接口、状态接口、区域覆盖范围和最新观测批次。实时检索采用确定性目录，不要求语言大模型；语言大模型后续可以负责把自然语言任务转换为上述结构化请求。

## 返回字段约定

候选点至少包含：

- `detection_id`
- `region_id`
- `source`
- `observed_at`
- `detected_at`
- `longitude`、`latitude`，WGS84 经度纬度
- `confidence`
- `status: candidate`
- `source_asset_id`
- `algorithm`
- `attributes`

候选点只是甲模块生成的待核验结果，不等同于乙模块确认的真实火点。乙模块完成视觉或目标检测复核后，应通过双方约定的状态回写链路更新业务状态。
