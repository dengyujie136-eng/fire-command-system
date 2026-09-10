# 四人协作数据交付与自动配置指南

本文件交给乙、丙、丁及其 AI 助手执行。目标是让四台电脑拥有相同的代码基线、Dixie Fire `data/` 文件和 PostGIS 事件数据。

## 来源与边界

- 仓库：`https://github.com/dengyujie136-eng/fire-command-system.git`
- 甲侧分支：`member/qingzhe_ivory`
- 事件：`dixie_fire_2021`
- 栅格处理 CRS：`EPSG:32610`；接口交换 CRS：`EPSG:4326`
- 宿主机 `data/` 映射到容器 `/app/data:ro`

本交付不包含 `.env`、API Key、Cesium Token、LLM Key 或个人密码。每位成员自行配置密钥。

## AI 必须遵守

1. 先执行 `git status --short --branch`，确认在自己的 `member/<GitHub用户名>` 分支。
2. 不执行 `git reset --hard`、`git checkout --` 或 `docker compose down -v`。
3. 不修改或推送 `main`，不删除其他成员分支。
4. 有未提交修改时先停止并报告，不自动覆盖。
5. 不删除或覆盖 `data/raw/` 原始文件。
6. 恢复数据库时只处理 `event_id = 'dixie_fire_2021'`，不得删除其他事件。
7. OSM 当前没有有效数据，不能把 Overpass 错误响应当作地图数据。

## 1. 获取代码

```powershell
git clone https://github.com/dengyujie136-eng/fire-command-system.git
cd fire-command-system
git fetch origin member/qingzhe_ivory
git switch -c member/<你的GitHub用户名> --track origin/member/qingzhe_ivory
```

已有自己的分支时：

```powershell
git status --short --branch
git fetch origin member/qingzhe_ivory
git merge --no-ff origin/member/qingzhe_ivory
```

有冲突或本地修改时，交给 AI 先检查，不要强制覆盖。之后只推送自己的分支：

```powershell
git push -u origin member/<你的GitHub用户名>
```

## 2. 解压数据包

U 盘交付物：

```text
qingzhe_ivory_dixie_fire_2021_data_bundle.zip
dixie_fire_2021_database_seed.sql
SHA256SUMS.txt
```

将 zip 解压并合并到仓库根目录，确认存在：

```text
data/raw/firms/
data/raw/burned_area/
data/raw/weather/
data/processed/dem/
data/processed/fuel/
data/processed/weather/
data/processed/forefire_input/
data/manifests/
```

不要清空 `data/`。可检查数据体积：

```powershell
Get-ChildItem -Recurse -File data | Measure-Object Length -Sum
```

## 3. 配置环境

```powershell
Copy-Item .env.example .env -ErrorAction SilentlyContinue
```

确认 `.env` 中数据库值与 Compose 一致：

```text
POSTGRES_DB=xinghuo
POSTGRES_USER=xinghuo
POSTGRES_PASSWORD=xinghuo_dev
```

不要复制甲的 `.env`。

## 4. 恢复 Docker PostGIS

先启动 Docker Desktop，再执行：

```powershell
docker compose up -d postgis
docker compose ps
.\scripts\restore-dixie-data-docker.ps1 -SeedPath "E:\交接包\dixie_fire_2021_database_seed.sql"
```

恢复脚本只重建 Dixie 事件、热点、聚合热点、MTBS 边界、日/小时气象和数据清单；不会删除其他事件，也不需要复制 Docker named volume。

禁止执行 `docker compose down -v`，因为这会删除整台电脑的 PostGIS 数据卷。

## 5. 启动与验证

```powershell
docker compose up -d --build
docker compose ps
Invoke-RestMethod http://localhost:8200/health
Invoke-RestMethod "http://localhost:8200/api/data/events/dixie_fire_2021"
Invoke-RestMethod "http://localhost:8200/api/data/events/dixie_fire_2021/hotspots?status=candidate&limit=1"
Invoke-RestMethod "http://localhost:8200/api/data/events/dixie_fire_2021/weather-hourly?limit=1"
.\scripts\validate-dixie-data.ps1
```

甲侧基线：FIRMS 原始 70460 条、候选热点 60013 条、10 分钟聚合 11704 条、MTBS 边界 1 条、日气象 105 条、小时气象 2520 条。

## 6. Docker 数据原理

四台电脑的 Docker 和 `postgis-data` named volume 彼此独立。复制 `data/` 只同步文件，不会自动同步数据库；数据库必须用上面的 seed 脚本恢复。恢复后，后端从本机 PostGIS 读取数据，前端通过 `localhost:5173` 访问本机后端。

## 7. 成员使用范围

- 乙：热点 API、`imagery_status` 和影像引用。
- 丙：ForeFire 输入清单、小时气象、DEM、坡度、坡向、燃料栅格。
- 丁：过火边界、热点、气象和后续推演结果。
- 甲：数据源、数据清单、数据接口和一致性校验。

ForeFire 实际 case、推演结果和 OSM 有效图层尚未包含在本次甲侧交付中。
