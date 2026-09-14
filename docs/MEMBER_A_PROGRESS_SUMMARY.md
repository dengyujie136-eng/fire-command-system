# 成员甲阶段性工作总结

## 一、成员甲的职责定位

成员甲负责森林山火系统中的“全球火灾数据库与星地多源感知系统”，核心任务是为其他成员提供可靠、可检索、可追溯的数据源和数据接口。

当前工作范围严格限定在：

- Git 分支：`member/qingzhe_ivory`
- 网站页面：`/realtime-monitor`
- 甲模块后端：实时数据同步、数据目录和数据接口

未修改 `main` 分支，也未修改乙、丙、丁负责的页面和模块。

## 二、总体实现目标

甲模块围绕两条业务主线建设：

```text
历史火灾复盘
    └── Dixie Fire 历史火点、过火边界、气象和遥感数据回放

实时火情监测
    └── FIRMS NRT 实时候选火点同步、入库、地图展示和接口交接
```

其中，历史火灾复盘使用真实的 Dixie Fire 数据；实时火情监测使用 NASA FIRMS NRT/VIIRS 数据生成当前区域的候选火点。候选火点仅表示遥感产品发现的异常，不直接等同于已经确认的真实火灾，后续由乙模块进行视觉或目标检测核验。

## 三、历史火灾数据库建设

### 1. Dixie Fire 事件数据

已围绕 Dixie Fire 2021 建立历史火灾数据基础，事件标识为：

```text
dixie_fire_2021
```

数据库中关联了历史火灾事件、火点、火点聚合结果、过火边界、气象数据和数据清单等内容。

### 2. FIRMS 历史火点

已经通过 NASA FIRMS 获取 Dixie Fire 不同时间段的 VIIRS 火点 CSV 数据，并保存到仓库的数据目录中。数据主要包含：

- 火点经纬度；
- 采集日期和 UTC 采集时间；
- 卫星和传感器信息；
- `bright_ti4`、`bright_ti5` 热红外亮温；
- FRP 火点辐射功率；
- 置信度；
- 白天/夜间标识；
- 扫描角和轨道角；
- 原始文件引用。

这些历史火点用于：

- 历史火灾时间轴回放；
- 日尺度火点数量统计；
- 火点空间分布展示；
- 生成仿葵花八号系统的历史观测效果；
- 为乙模块提供候选火点位置；
- 为丙模块提供历史起火点和火点时序参考。

### 3. MTBS 过火边界

已经获取并整理 Dixie Fire 的 MTBS 过火区域数据，作为历史事件的真实结果数据。该数据用于：

- 在历史复盘页面显示最终过火范围；
- 验证火点是否落在最终过火区域内；
- 为火势推演结果提供真实参考边界；
- 支持后续过火面积对比和系统效果评估。

### 4. 气象数据

已经准备 NASA POWER 气象数据，包括日尺度和小时尺度数据。

日尺度数据主要用于历史火灾复盘页面，随回放日期显示：

- 温度；
- 相对湿度；
- 风速；
- 风向；
- 降水；
- 太阳辐射等。

小时尺度数据主要提供给丙模块，用于 ForeFire 火势推演。即使后续进行了时间插值，也保留原始数据，并通过字段标识插值状态，避免把插值数据误认为原始观测。

### 5. DEM 和地形数据

已经准备 Dixie Fire 研究区的 DEM 数据，并按统一空间参考进行整理。DEM 可用于：

- 高程显示；
- 坡度和坡向计算；
- ForeFire 地形输入；
- 火势影响方向分析；
- 后续空间查询和地图叠加。

### 6. ESA WorldCover 燃料数据

已经准备 WorldCover 土地覆盖数据，并建立了面向火势推演的燃料分类数据。该数据用于：

- 表示森林、灌木、草地、裸地和其他地表类型；
- 为丙模块提供燃料类型输入；
- 支持火险区域分析；
- 为数据智能体提供土地覆盖数据检索结果。

WorldCover 派生的燃料类别属于课程实习中的近似燃料代理数据，能够支持系统演示和流程复现，但不等同于经过专业标定的 LANDFIRE 燃料模型。

### 7. Sentinel-2 遥感影像

已经通过 GEE 获取 Dixie Fire 灾前、灾中、灾后的真实 Sentinel-2 GeoTIFF 影像，并保存到：

```text
data/raw/sentinel2/dixie_fire_2021/gee/
```

影像包含真实空间参考和地理范围，用于乙模块进行：

- 候选火点视觉核验；
- 灾前、灾中、灾后多时相比较；
- 火烧区域和地表变化分析；
- Qwen-VL 或目标检测模型的输入。

甲模块不对这些 Sentinel-2 文件进行二次修改，保持原始交接数据不变。

## 四、数据目录和数据清单

当前仓库沿用既有 `data/raw`、`data/interim`、`data/processed` 和 `data/manifests` 结构，没有移动已有数据目录。

实时数据新增目录为：

```text
data/
├── raw/
│   └── realtime/
│       └── firms_nrt/
│           └── {region_id}/
├── processed/
│   └── realtime/
│       ├── hotspots/
│       │   └── {region_id}/
│       └── manifests/
```

实时数据同步后：

- 原始 FIRMS CSV 保存到 `data/raw/realtime/firms_nrt/{region_id}/`；
- 处理后的候选点 JSON 保存到 `data/processed/realtime/hotspots/{region_id}/`；
- 每批数据的来源、时间、哈希值和记录数量保存到 `data/processed/realtime/manifests/`；
- 默认仅保留最近 3 批实时文件；
- 数据库历史记录不会因文件清理而删除；
- 下载失败时保留上一批可用文件，不覆盖有效结果。

## 五、数据库和 PostGIS 工作

项目使用 Docker 中的 PostgreSQL/PostGIS 作为团队开发基线，连接信息由 Docker Compose 配置提供。

### 新增实时数据表

新增了以下 ORM 模型：

```text
realtime_observations
realtime_hotspots
```

`realtime_observations` 保存每次实时同步的观测批次，包括：

- 观测批次编号；
- 区域编号；
- 数据源和产品名；
- 最新观测时间；
- 获取时间；
- 原始文件路径；
- 数据行数和 SHA-256 哈希值。

`realtime_hotspots` 保存去重后的实时候选火点，包括：

- `detection_id`；
- `region_id`；
- `observation_id`；
- 原始记录编号；
- 观测时间和检测时间；
- 经度、纬度；
- 置信度；
- 候选状态；
- 原始产品属性。

### 空间字段

实时候选点在 PostgreSQL 中通过 PostGIS 自动生成：

```text
location_geom geometry(Point, 4326)
```

并建立 GiST 空间索引，坐标系为 WGS84。这样乙、丙、丁可以直接基于空间范围、距离和相交关系进行查询。

## 六、后端代码修改

### 1. 配置模块

在 `fire_agent_backend/app/core/config.py` 中增加了实时数据配置：

- `FIRMS_MAP_KEY`；
- FIRMS 查询时间范围；
- 实时文件保留批次数；
- 实时请求超时时间。

密钥只从本机 `.env` 读取，不提交到 GitHub。

### 2. 实时数据模型

新增：

```text
fire_agent_backend/app/models/realtime.py
```

用于定义实时观测批次和实时候选火点的数据表结构。

### 3. 实时数据模式

新增：

```text
fire_agent_backend/app/schemas/realtime.py
```

用于固定实时接口的请求和响应字段，保证前端、数据智能体和其他成员使用统一格式。

### 4. 实时数据服务

新增：

```text
fire_agent_backend/app/services/realtime_service.py
```

主要功能包括：

- 区域配置管理；
- FIRMS NRT 请求；
- CSV 解析；
- 日期和 UTC 时间解析；
- 经纬度和产品字段解析；
- 置信度转换；
- 候选火点去重；
- 生成稳定的检测编号；
- 保存原始和处理文件；
- 写入 PostgreSQL/PostGIS；
- 旧批次清理；
- 失败时保留上一批有效数据。

### 5. 实时路由

新增：

```text
fire_agent_backend/app/routers/realtime.py
```

当前接口如下：

```http
GET  /api/realtime/regions
POST /api/realtime/sync
GET  /api/realtime/status?region_id=...
GET  /api/realtime/hotspots?region_id=...
GET  /api/realtime/observations?region_id=...
```

接口职责：

| 接口 | 作用 |
|---|---|
| `/regions` | 返回支持的区域和覆盖范围 |
| `/sync` | 下载并处理一批最新候选火点 |
| `/status` | 查询区域最新同步状态 |
| `/hotspots` | 查询最新或指定批次候选点 |
| `/observations` | 查询历史实时观测批次 |

### 6. 数据库初始化

在数据库初始化流程中注册实时模型，使 Docker 启动后自动创建实时数据表，并调用 PostGIS 空间字段和空间索引安装逻辑。

### 7. Docker 配置

在 `compose.yaml` 中完成了两项调整：

- 将 `FIRMS_MAP_KEY` 传入 `fire-agent-api` 容器；
- 将 `data` 挂载从只读改为可写。

这是因为实时系统需要下载原始数据、写处理结果以及清理过期文件。

## 七、监测页面功能实现

修改文件：

```text
src/views/RealtimeMonitor.vue
```

页面仍然只属于监测模块，没有修改其他成员负责的页面。

### 1. 模式切换

监测页面增加两个模式：

- `历史火灾复盘`；
- `实时火情监测`。

历史模式保留 Dixie Fire 历史回放逻辑；实时模式不使用历史 Dixie Fire 火点冒充实时数据。

### 2. 历史火灾复盘

历史模式支持：

- 日尺度火点回放；
- 历史时间轴；
- NASA POWER 日气象显示；
- MTBS 过火边界显示；
- 历史候选火点统计；
- 真实历史数据状态提示。

### 3. 实时火情监测

实时模式支持：

- 实时区域选择；
- GOES-18覆盖区入口；
- Himawari-8/9覆盖区入口；
- Meteosat和FY-4后续适配入口；
- 当前数据源显示；
- 观测时间显示；
- 获取时间显示；
- 数据延迟显示；
- 候选火点数量显示；
- 候选点地图展示；
- 手动获取最新数据；
- 每 60 秒自动同步；
- 不支持区域提示；
- 后端不可用时的明确错误提示。

当前接口真实数据源显示为：

```text
FIRMS NRT / VIIRS
```

区域名称只是卫星覆盖区域入口，不把 FIRMS 产品误称为 GOES 或 Himawari 原始影像。

## 八、数据智能体接口基础

项目原有的数据智能体已经支持通过数据清单和确定性接口检索：

- FIRMS 历史火点；
- MTBS 过火边界；
- NASA POWER 日气象；
- NASA POWER 小时气象；
- DEM；
- 坡度；
- 坡向；
- WorldCover；
- ForeFire 输入清单；
- 历史实时回放数据。

甲模块新增的实时接口可以进一步接入数据智能体，使智能体能够根据区域和任务自动找到最新候选火点数据。

当前实时数据的定位是：

```text
结构化实时数据源
    ↓
数据智能体检索
    ↓
候选火点接口
    ↓
乙模块视觉核验
    ↓
丙模块火势推演
```

实时数据检索本身不强制依赖大语言模型，优先使用确定性接口保证结果稳定；大语言模型可以在后续负责理解自然语言任务并调用这些接口。

## 九、实际测试结果

### 1. 后端编译检查

已通过 Python 模块编译检查：

```text
python -m compileall -q fire_agent_backend/app
```

### 2. Docker 构建

已通过 Docker 构建：

```text
docker compose up -d --build fire-agent-api frontend
```

前端 Vite/TypeScript 构建通过，Docker 中的前端服务正常启动。

### 3. 服务状态

已验证以下服务正常运行：

- frontend；
- fire-agent-api；
- forefire-api；
- postgis。

### 4. 实时 FIRMS 同步

曾经成功调用：

```http
POST /api/realtime/sync
```

实际结果包括：

- 返回 `ready: true`；
- 获取真实 FIRMS NRT/VIIRS CSV；
- 原始响应约 1514 行；
- 去重后保存 1493 个候选火点；
- 最新一次观测时间为 `2026-09-11T21:45:00Z`；
- 数据库候选点数量与去重结果一致，为 1493；
- CSV 和处理 JSON 均成功落盘；
- PostGIS `location_geom` 字段存在；
- 空间索引创建成功。

### 5. 前端代理

已验证通过前端地址访问后端接口：

```text
http://localhost:5173/api/realtime/regions
http://localhost:5173/api/realtime/status?region_id=goes18_north_america_west
```

说明 Nginx 反向代理和前后端连接正常。

## 十、GitHub 分支和提交

### 分支约束

所有甲模块工作均在：

```text
member/qingzhe_ivory
```

完成了以下提交：

```text
13ea810  Checkpoint member A monitoring and data baseline
8351dea  Add historical and live monitoring modes
9587ac3  Add realtime FIRMS monitoring data API
```

最新提交 `9587ac3` 已成功推送到远程：

```text
origin/member/qingzhe_ivory
```

并已验证本地提交哈希与远程分支哈希一致。

### 未提交内容

以下内容明确没有提交：

- `.env` 文件；
- FIRMS MAP KEY；
- Cesium Token；
- Python `__pycache__` 缓存；
- 本地生成的敏感配置。

## 十一、当前工作边界和限制

当前已经完成的是“实时数据源和候选火点链路”，还不是完整的 GOES/Himawari 原始卫星影像自主检测系统。

准确表述应为：

```text
当前版本：FIRMS NRT/VIIRS 实时候选火点监测
后续版本：GOES ABI 或 Himawari 原始影像下载与热异常检测
```

当前候选点不能直接视为最终确认火点，也不能直接替代乙模块的视觉核验结果。

## 十二、下一步工作建议

### 第一优先级：页面验证

在浏览器打开：

```text
http://localhost:5173/realtime-monitor
```

选择“实时火情监测”，验证实时区域、候选点数量、观测时间和地图点位是否正确显示。

### 第二优先级：数据智能体接入

为数据智能体增加实时数据目录和 `realtime_hotspots` 需求解析，使丁模块或总控 Agent 能够通过任务自动找到实时数据。

### 第三优先级：乙模块交接

向乙模块提供：

- `/api/realtime/hotspots` 接口；
- 候选点字段说明；
- `status=candidate` 的业务含义；
- `source_asset_id` 和原始文件引用；
- 明确说明当前数据源为 FIRMS NRT/VIIRS；
- 明确说明候选点需要视觉核验。

### 第四优先级：实时卫星原始影像适配

在不破坏现有 FIRMS 链路的前提下，增加 GOES ABI 或 Himawari 原始数据适配器，并让其输出与当前实时接口兼容的观测和候选点结构。

## 十三、阶段性结论

截至目前，成员甲已经完成了从历史火灾数据整理、实时候选火点获取、文件留档、PostGIS 入库、后端接口、监测页面展示到 GitHub 分支交付的第一阶段闭环。

系统现在能够：

```text
获取真实 FIRMS NRT 数据
        ↓
解析并去重候选火点
        ↓
保存原始和处理数据
        ↓
写入 PostgreSQL/PostGIS
        ↓
通过后端 API 输出
        ↓
在监测页面地图显示
        ↓
交给乙模块进行进一步核验
```

这一阶段已经具备后续成员开展视觉核验、火势推演和多智能体协同开发所需的数据源基础。
