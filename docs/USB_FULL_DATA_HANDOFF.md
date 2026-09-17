# Dixie Fire 完整数据 U 盘交接

本方案用于让每位成员的电脑运行同一套完整系统。Git 同步代码，U 盘同步大型真实数据；代码始终使用仓库内相对路径，不写某一台电脑的盘符。

## 固定目录

丙的仓库可以位于任意位置，例如 `D:\fire-command-system`。数据必须复制到该仓库内部：

```text
<repo>\data\raw\sentinel2\dixie_fire_2021\gee\  # 18 个 GeoTIFF
<repo>\data\raw\firms\                           # FIRMS 原始火点
<repo>\data\raw\burned_area\                     # MTBS 数据
<repo>\data\processed\dem\                       # DEM、坡度、坡向
<repo>\data\processed\fuel\                      # 燃料数据
<repo>\data\processed\weather\                   # 气象数据
<repo>\data\local\database\dixie_fire_2021_database_seed.sql
<repo>\.env                                        # 丙本机运行配置，不进入 Git
```

Docker Compose 会把 `<repo>\data` 挂载成容器内 `/app/data`。因此代码和数据库只保存 `data/...` 或 `/app/data/...`，不要保存 `E:\...`、`D:\...` 等机器专属路径。

## 乙制作 U 盘包

将 `U:\xinghuo-full-data-v1` 替换为实际 U 盘路径：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\export-dixie-full-data-to-usb.ps1 `
  -DestinationRoot "U:\xinghuo-full-data-v1" `
  -IncludeLocalEnv
```

脚本会复制仓库中的真实原始/处理数据、外部的 18 个 Sentinel-2 GeoTIFF、数据库种子和可选本地 `.env`，并生成 `handoff-manifest.json`。它不会修改 Git。

## 丙合并代码

丙先保存自己的工作，然后在自己的成员分支合并 `main`：

```powershell
git status
git add -A
git commit -m "Save member C work before integration"
git fetch origin
git merge origin/main
```

不要删除丙的分支，也不要用 `reset --hard`。如有冲突，应逐文件合并。

## 丙导入 U 盘包

在丙的仓库根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\import-dixie-full-data-from-usb.ps1 `
  -PackageRoot "U:\xinghuo-full-data-v1" `
  -InstallLocalEnv

powershell -ExecutionPolicy Bypass -File scripts\verify-dixie-full-data.ps1
```

导入只合并 `data/raw`、`data/processed`，并安装数据库种子和可选 `.env`。不会覆盖丙的代码、Git 分支或 `environment/`。

## 恢复数据库并启动

```powershell
docker compose up -d --build

powershell -ExecutionPolicy Bypass -File scripts\restore-dixie-data-docker.ps1 `
  -SeedPath "data\local\database\dixie_fire_2021_database_seed.sql"

powershell -ExecutionPolicy Bypass -File scripts\run-dixie-visual-confirmation.ps1
```

数据库恢复只替换 `dixie_fire_2021` 事件的数据，不删除其他火灾事件。最后一条命令登记甲的四个最早聚类候选与真实 Sentinel-2 影像，执行裁剪、Qwen/专业检测、课程演示自动确认和真实火点入库。结果同时写到 `data/local/results/dixie_fire_2021_visual_confirmation_latest.json`。

## 交接验收

交接完成至少满足：

1. `verify-dixie-full-data.ps1` 输出 `PASS`。
2. Docker 服务正常启动。
3. 数据库中可以查询 Dixie Fire 事件、FIRMS 原始观测、合并后候选点、聚类、气象和过火范围。
4. 乙的视觉复核服务能读取 `/app/data/raw/sentinel2/dixie_fire_2021/gee/` 下影像，并输出确认火点。
5. 丙使用确认火点作为 ForeFire 起火输入，且仍保留自己的成员分支开发历史。
