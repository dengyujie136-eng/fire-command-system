# 成员甲最终交接说明

## 1. 交接范围

成员甲负责全球火灾数据源、Dixie Fire 历史复盘、FIRMS 候选火点、气象与地形燃料数据、FIRMS 三个月演示、GOES-18 影像检测演示，以及供其他智能体调用的数据目录接口。

代码分支：`member/qingzhe_ivory`。

本交接不包含任何 `.env`、FIRMS MAP KEY、Cesium Token、LLM Key 或个人密码。

## 2. 交付物

Git 分支提供代码、接口、脚本和文档。大型数据通过 U 盘或共享存储传递：

```text
qingzhe_ivory_dixie_fire_2021_data_bundle.zip
dixie_fire_2021_database_seed.sql
member_a_realtime_demo_data_20260917.zip
member_a_realtime_database_seed_20260917.sql
SHA256SUMS_20260917.txt
```

其中：

- `qingzhe_ivory_dixie_fire_2021_data_bundle.zip`：Dixie Fire 核心数据。
- `dixie_fire_2021_database_seed.sql`：Dixie Fire 专用数据库种子。
- `member_a_realtime_demo_data_20260917.zip`：FIRMS 三个月和 GOES-18 演示数据。
- `member_a_realtime_database_seed_20260917.sql`：实时观测与实时火点数据。
- `SHA256SUMS_20260917.txt`：交付文件完整性校验值。

Sentinel-2 影像已单独交付给乙、丙，固定目录为：

```text
data/raw/sentinel2/dixie_fire_2021/gee/
```

## 3. 获取甲分支但不影响自己的分支

```powershell
git status --short --branch
git fetch origin member/qingzhe_ivory
git log origin/member/qingzhe_ivory --oneline -10
```

乙、丙、丁不要直接覆盖自己的分支。最终代码由汇总成员在集成分支合并并解决冲突，测试通过后才能进入 `main`。

## 4. 恢复数据文件

将两个 ZIP 解压到临时目录，再把其中的 `data` 目录合并到仓库根目录的 `data`。不得先清空现有 `data`，不得覆盖其他成员新生成的文件。

恢复后至少应存在：

```text
data/raw/firms/
data/raw/burned_area/
data/raw/weather/
data/raw/realtime_demo/
data/processed/dem/
data/processed/fuel/
data/processed/weather/
data/processed/realtime_demo/
data/processed/forefire_input/
```

## 5. 恢复 Docker PostGIS

先启动 Docker Desktop，然后在仓库根目录执行：

```powershell
docker compose up -d fire-agent-api
./scripts/restore-dixie-data-docker.ps1 -SeedPath '<交付目录>/dixie_fire_2021_database_seed.sql'
./scripts/restore-member-a-realtime-docker.ps1 -SeedPath '<交付目录>/member_a_realtime_database_seed_20260917.sql'
```

禁止执行 `docker compose down -v`，该命令会删除本机 Docker 数据卷。

## 6. 本机环境变量

每位成员使用自己的 `.env`。需要主动同步 FIRMS NRT 数据的电脑自行配置：

```env
FIRMS_MAP_KEY=个人申请的MAP_KEY
```

预下载演示数据和历史回放不依赖该密钥。不得复制或提交成员甲的 `.env`。

## 7. 启动和验证

```powershell
docker compose up -d --build
docker compose ps
python scripts/verify_member_a_data.py
```

接口检查：

```text
http://localhost:8200/health
http://localhost:8200/api/data-agent/catalog/dixie_fire_2021
http://localhost:8200/api/data-agent/realtime-catalog
http://localhost:8200/api/realtime-demo/manifest
http://localhost:8200/api/realtime-demo/firms-archive/manifest
http://localhost:5173/realtime-monitor
```

## 8. 智能体调用入口

- 历史数据目录：`GET /api/data-agent/catalog/dixie_fire_2021`
- 按需求解析：`POST /api/data-agent/resolve`
- 实时数据目录：`GET /api/data-agent/realtime-catalog`
- FIRMS NRT 同步：`POST /api/realtime/sync`
- GOES 演示清单：`GET /api/realtime-demo/manifest`
- FIRMS 三个月清单：`GET /api/realtime-demo/firms-archive/manifest`

数据智能体当前采用确定性目录与数据库检索，不需要语言模型。丁后续可让语言模型负责理解“推演 Dixie Fire”等自然语言任务，再调用上述接口判断数据是否齐全。

## 9. 交接基线

- FIRMS 三个月演示：2025-06-15 至 2025-09-15，共 27,816 条。
- 实时数据库导出：16 批观测，5,709 个候选火点。
- Dixie Fire 既有基线：FIRMS 原始 70,460 条、候选热点 60,013 条、10 分钟聚合 11,704 条、MTBS 边界 1 条、日气象 105 条、小时气象 2,520 条。
- 栅格计算产品：EPSG:32610；接口坐标：EPSG:4326。
