# 成员甲阶段进度说明

## 分支范围

- 当前分支：`member/qingzhe_ivory`
- 本阶段只负责监测页面和数据源头相关内容。
- 不修改 `main`，不修改其他成员分支。
- 监测页面文件：`src/views/RealtimeMonitor.vue`

## 已完成内容

### Dixie Fire 数据源

- 已整理 Dixie Fire 的 FIRMS 历史火点数据，并完成数据库接入和回放接口使用。
- 已准备 MTBS 真实过火边界，用于最终过火范围展示和验证。
- 已准备 NASA POWER 日尺度气象数据，用于历史火点按日期匹配气象参数。
- 已准备 NASA POWER 小时尺度气象数据，供 ForeFire 火势推演成员使用；监测页面不依赖小时气象。
- 已准备 DEM、坡度、坡向和 WorldCover/燃料栅格数据。
- 已准备覆盖 Dixie Fire 研究区的 Sentinel-2 L2A 真实 GeoTIFF 影像，保留原始 TIFF 和空间参考信息。

### 监测页面

`src/views/RealtimeMonitor.vue` 当前已经实现：

- Dixie Fire 历史事件加载；
- FIRMS 火点和十分钟聚合数据加载；
- 按日期聚合的历史火情回放；
- 地图下方可拖动时间轴；
- 播放/暂停回放；
- 当前日期火点数量、聚合单元和最大 FRP 展示；
- MTBS 过火边界展示；
- NASA POWER 日气象随当前回放日期同步更新；
- 温度、湿度、风速、风向、日降水和日照辐射展示；
- 风、云、雨可选的日尺度模拟效果；
- 数据源和乙、丙、丁交接状态展示。

### 服务验证

- 前端 Docker 镜像已成功重新构建。
- TypeScript 检查和 Vite 生产构建已通过。
- Docker Compose 前端、Fire Agent API、ForeFire API 和 PostGIS 服务均正常运行。
- `http://localhost:5173/realtime-monitor` 可正常返回。
- Dixie Fire 历史回放接口和日气象接口可正常返回数据。

## 本次快照不包含的本地文件

以下内容按照仓库忽略规则保留在本地或通过 U 盘交接，不上传 Git：

- 原始 FIRMS CSV；
- 原始和处理后的 GeoTIFF 影像；
- 数据库种子 SQL；
- `data/raw`、`data/processed` 中的大型数据文件；
- `.env`、Cesium Token 和其他密钥；
- Python `__pycache__` 缓存。

## 下一阶段任务

在不改变已有数据目录和交接契约的前提下，监测页面将增加两个模式：

1. `历史火灾复盘`：保留当前 Dixie Fire 历史回放功能。
2. `实时火情监测`：增加全球实时监测区域选择、数据源状态、最新观测时间、实时火点展示和不支持区域提示。

实时模式将优先预留 GOES-18 ABI 和 Himawari-8/9 区域适配入口，并通过后端实时接口获取数据。页面不在浏览器端直接保存 API Key、下载原始卫星数据或执行检测算法。

## 交接说明

本文件对应本次 `member/qingzhe_ivory` 分支快照。其他成员需要使用本分支代码时，应在自己的分支执行 `git fetch origin`，再按团队约定选择性合并或拣选提交；不要直接修改或推送 `main`。
