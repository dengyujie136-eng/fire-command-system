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

## 10. 详细交接操作清单

以下步骤适用于乙、丙、丁各自的电脑。`<交接根目录>` 是接收文件的任意本地目录，例如桌面下的 `fire-command-handoff`；`<仓库根目录>` 是他们实际克隆仓库的位置，不要求在 E 盘。

### 10.1 甲需要发送的文件

请完整发送以下文件：

```text
qingzhe_ivory_dixie_fire_2021_data_bundle.zip
dixie_fire_2021_database_seed.sql
member_a_realtime_demo_data_20260917.zip
member_a_realtime_database_seed_20260917.sql
SHA256SUMS_20260917.txt
MEMBER_A_FINAL_HANDOFF.md
MEMBER_A_AI_INSTALL_INSTRUCTION.md
```

可选发送：

```text
restore-member-a-realtime-docker.ps1
```

该脚本也会从甲分支的 `scripts/` 目录取得。Sentinel-2 TIFF 已单独交给乙、丙，不要把它误认为本交接包中的必需文件。

### 10.2 组员建立交接目录

组员先在电脑上建立一个临时交接目录，目录位置可自行决定。例如：

```text
<任意位置>/fire-command-handoff/FINAL/
```

把上述全部文件直接放入 `FINAL`，不要把压缩包解压到这个 `FINAL` 目录中。此时结构应为：

```text
fire-command-handoff/
└── FINAL/
    ├── qingzhe_ivory_dixie_fire_2021_data_bundle.zip
    ├── dixie_fire_2021_database_seed.sql
    ├── member_a_realtime_demo_data_20260917.zip
    ├── member_a_realtime_database_seed_20260917.sql
    ├── SHA256SUMS_20260917.txt
    ├── MEMBER_A_FINAL_HANDOFF.md
    └── MEMBER_A_AI_INSTALL_INSTRUCTION.md
```

### 10.3 获取甲的代码

组员进入自己已经克隆好的仓库，记为 `<仓库根目录>`，执行：

```powershell
cd <仓库根目录>
git status --short --branch
git fetch origin member/qingzhe_ivory
git log origin/member/qingzhe_ivory --oneline -5
```

这三条命令只读取甲分支。不要执行 `git reset --hard`、`git checkout --`、`git clean -fd` 或 `docker compose down -v`。不要把甲分支强行覆盖到自己的成员分支。

如果汇总成员需要集成甲的代码，应在独立的 integration 分支中合并 `origin/member/qingzhe_ivory`；乙、丙、丁日常开发不需要合并甲分支。

### 10.4 校验交接文件

在交接目录的 `FINAL` 中执行：

```powershell
cd <交接根目录>\FINAL
Get-FileHash .\qingzhe_ivory_dixie_fire_2021_data_bundle.zip -Algorithm SHA256
Get-FileHash .\dixie_fire_2021_database_seed.sql -Algorithm SHA256
Get-FileHash .\member_a_realtime_demo_data_20260917.zip -Algorithm SHA256
Get-FileHash .\member_a_realtime_database_seed_20260917.sql -Algorithm SHA256
```

将输出的 Hash 与 `SHA256SUMS_20260917.txt` 逐行比较。四个文件都一致后才能继续；不一致时重新复制文件，不要解压损坏的压缩包。

### 10.5 合并数据文件

先在 `<仓库根目录>` 建立临时解压目录，再解压两个 ZIP：

```powershell
New-Item -ItemType Directory -Force .\handoff_temp | Out-Null
Expand-Archive -LiteralPath '<交接根目录>\FINAL\qingzhe_ivory_dixie_fire_2021_data_bundle.zip' -DestinationPath .\handoff_temp\core -Force
Expand-Archive -LiteralPath '<交接根目录>\FINAL\member_a_realtime_demo_data_20260917.zip' -DestinationPath .\handoff_temp\realtime -Force
```

确认解压目录中存在 `data` 后，将两个包里的 `data` 内容合并到 `<仓库根目录>\data`，不是把整个 `data` 文件夹嵌套成 `data\data`。如果系统提示同名文件，先暂停并报告，不要选择“全部覆盖”。不要删除现有 `data`，因为其中可能有组员自己的数据。

合并完成后应至少存在：

```text
<仓库根目录>\data\raw\firms\
<仓库根目录>\data\raw\burned_area\
<仓库根目录>\data\raw\weather\
<仓库根目录>\data\raw\realtime_demo\
<仓库根目录>\data\processed\dem\
<仓库根目录>\data\processed\fuel\
<仓库根目录>\data\processed\realtime_demo\
```

### 10.6 恢复每台电脑自己的 Docker 数据库

打开 Docker Desktop，在 `<仓库根目录>` 执行：

```powershell
docker compose up -d postgis fire-agent-api
docker compose ps
```

等待 `postgis` 和 `fire-agent-api` 为 `healthy` 或 `Up` 后执行：

```powershell
./scripts/restore-dixie-data-docker.ps1 -SeedPath '<交接根目录>\FINAL\dixie_fire_2021_database_seed.sql'
./scripts/restore-member-a-realtime-docker.ps1 -SeedPath '<交接根目录>\FINAL\member_a_realtime_database_seed_20260917.sql'
```

第一个脚本只恢复 `dixie_fire_2021`，第二个脚本只恢复甲模块的实时观测和实时火点表。每台电脑的 Docker 数据库独立存在，数据不会自动互相同步。

### 10.7 配置本机 `.env`

不要复制甲的 `.env`。在自己的仓库根目录创建或编辑本机 `.env`，只填写本机自己的配置；FIRMS NRT 联网同步需要个人申请的 key：

```env
FIRMS_MAP_KEY=本机用户自己的MAP_KEY
```

历史数据、三个月 FIRMS 演示和 GOES 演示不依赖该 key。任何 key 都不得写入 Git、压缩包、SQL 或交接文档。

### 10.8 最终验收

在 `<仓库根目录>` 执行：

```powershell
docker compose up -d --build
docker compose ps
python scripts/verify_member_a_data.py
Invoke-RestMethod http://localhost:8200/health
Invoke-RestMethod http://localhost:8200/api/data-agent/realtime-catalog
Invoke-RestMethod http://localhost:8200/api/realtime-demo/firms-archive/manifest
```

浏览器打开 `http://localhost:5173/realtime-monitor`，检查历史复盘、FIRMS 三个月时间轴和 GOES 演示。最后向甲报告：当前成员分支、数据包校验结果、数据库记录数、容器状态和接口状态。

### 10.9 清理临时文件

确认验收完成后，才可以删除 `<仓库根目录>\handoff_temp` 和外部交接目录中的临时副本。不要删除仓库的 `data`，不要删除 Docker volume，不要执行 `docker compose down -v`。
