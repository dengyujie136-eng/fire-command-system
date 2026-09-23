# member/heimini 下载、配置与使用提示词

本文对应分支 `member/heimini`。该分支包含当前最新版五个页面、统一工作流、历史火灾数据库模型、遥感影像目录、数据智能体、火点核验、火势推演、规划与灾后评估代码。

> 安全说明：真实 `.env`、API Key、PostGIS 数据卷及大型原始 GIS/遥感文件不进入 Git。完整 Dixie Fire 演示需要按本文安装数据包或自行下载官方数据。

## 一、可直接复制给安装人员或 AI 编程助手的提示词

```text
请在一台已安装 Git、Docker Desktop 和 PowerShell 7 的 Windows 电脑上部署“星火智援”森林山火应急系统。

一、下载指定分支
1. 执行：
   git clone --branch member/heimini --single-branch https://github.com/dengyujie136-eng/fire-command-system.git
   cd fire-command-system
2. 不要切换到 main，不要合并其他分支。

二、配置
1. 复制配置模板：
   Copy-Item .env.example .env
2. 编辑仓库根目录 .env，只在本机填写：
   - VITE_CESIUM_ION_TOKEN：Cesium Ion Token，用于在线三维底图。
   - QWEN_VL_API_KEY：阿里云 DashScope Key，用于 Qwen-VL 火点复核和灾后影像理解。
   - FIRMS_MAP_KEY：NASA FIRMS MAP KEY，用于实时候选火点同步。
   - POSTGRES_DB、POSTGRES_USER、POSTGRES_PASSWORD：可保留开发默认值；共享部署时改为自己的密码。
   - LLM_PROVIDER=structured 可使用本地结构化调度；LLM_API_KEY 可留空。
3. 不得打印、提交或上传 .env 和任何 Key。

三、启动核心系统
1. 确保 Docker Desktop 已启动。
2. 执行：
   docker compose up -d --build postgis fire-agent-api frontend
3. 等待 fire-agent-api 显示 healthy：
   docker compose ps
4. 访问：
   - 网页：http://localhost:5173
   - 后端健康检查：http://localhost:8200/health
   - API 文档：http://localhost:8200/docs

四、安装完整 Dixie Fire 数据
Git 只包含数据库模型、SQL、清单、下载/导入脚本，不包含数百 MB 的真实 DEM、燃料、FIRMS、气象、MTBS 和 Sentinel 文件。

推荐方式：
1. 从项目数据负责人取得 xinghuo-full-data-v1 数据交接包。
2. 执行：
   powershell -ExecutionPolicy Bypass -File scripts\import-dixie-full-data-from-usb.ps1 -PackageRoot "<数据包目录>" -InstallLocalEnv
   powershell -ExecutionPolicy Bypass -File scripts\verify-dixie-full-data.ps1
   powershell -ExecutionPolicy Bypass -File scripts\restore-dixie-data-docker.ps1 -SeedPath "data\local\database\dixie_fire_2021_database_seed.sql"
3. 再次执行：
   docker compose up -d --build fire-agent-api frontend

没有交接包时：
- 使用 scripts\download-dixie-aoi-raster-data.ps1 下载并处理 Copernicus DEM 与 ESA WorldCover；该脚本需要 GDAL。
- 使用 scripts\import-dixie-weather.ps1、prepare-dixie-weather-hourly.ps1 和 import-dixie-weather-hourly.ps1 准备 NASA POWER 气象。
- FIRMS 历史 CSV 和 MTBS 边界需要从 NASA/USGS 官方来源获取后放入 data/README.md 规定的目录，再运行 scripts\import-dixie-fire-data.ps1。
- Sentinel/ Landsat 核验影像可在网页对话框中要求数据智能体获取；也可将带波段描述的 GeoTIFF 放入 data/raw/imagery/import 后手动登记。

五、验证
依次执行：
   npm ci
   npm run build
   python -m compileall fire_agent_backend/app backend/forefire_api/app
   docker compose config --quiet
   curl.exe http://localhost:8200/health

浏览器中检查五个页面：
1. 监测：历史火灾复盘、实时 FIRMS 候选火点、全局/加州视角和风场。
2. 核验：遥感候选火点、影像预处理、专业目标检测、Qwen-VL 复核与人工确认。
3. 推演：Dixie 历史栅格推演、1-24 小时预测、风速风向温湿度修改和火线时间轴。
4. 规划：保留最新推演火线，推荐/手选灭火目标，消防队起点、A* 演练路线以及水和食物需求。
5. 评估：灾前灾后多波段变化检测、受灾区域计算、Qwen-VL 可见影响解释和重建建议。

测试对话：
- “执行Dixie Fire的完整历史火灾推演”
- “帮我预测4小时之后的火势，风速改成8米每秒，风向270度”
- “获取Dixie Fire灾前灾后影像并进行灾后评估和重建建议”

完整工作流会依次执行数据准备、候选火点核验、火势推演、空间风险、场景、资源和路线规划。系统在火点人工确认和应急场景确认处暂停，这是正常的人工决策门，不应绕过。影像任务超过一分钟时，对话框会显示真实任务状态、官方检索链接和手动导入目录。

六、故障排查
- 页面未更新：Ctrl+F5；再检查 docker compose ps。
- 后端不健康：docker compose logs --tail=200 fire-agent-api。
- 核验 409：该候选点已完成核验，应选择新候选版本。
- 影像 no_match：不得用其他日期冒充同期影像；按返回的官方入口人工检索。
- 缺少 B02/B03/B04/B08/B12：补齐波段后再做核验或灾前灾后分析。
- 历史推演缺文件：运行 verify-dixie-full-data.ps1，根据 missing_required_files 安装数据。
- 停止服务：docker compose down。不要使用 docker compose down -v，除非明确要删除数据库。
```

## 二、当前网页实现内容

- **监测页**：Dixie Fire 历史复盘、实时火点监测、地图聚焦和动态风场。
- **核验页**：影像候选火点提取、专业检测算法、Qwen-VL 视觉复核和人工确认。
- **推演页**：真实数据库逐时气象与栅格传播工具、可调气象、1–24 小时预测和火线播放。
- **规划页**：读取最新火势结果，推荐或手选目标点，设置消防队起点，计算演练路线并登记水/食物需求。
- **评估页**：灾前灾后影像变化检测、受灾范围计算、Qwen-VL 解释和重建建议。
- **固定智能体面板**：自然语言调度页面和真实 API，展示任务阶段、参与功能、结果 ID、错误、下载状态及人工操作提示。
- **数据系统**：PostgreSQL/PostGIS 事件数据、影像目录、影像任务状态；数据智能体负责官方来源检索、去重、五波段校验、下载、登记和手动导入续跑。

## 三、数据边界

- 数据智能体当前只负责遥感影像，不负责下载气象、地形或应急资源。
- 路径预览使用明确标记为 `simulated` 的演练网格；接入真实道路图后才能作为行动导航。
- Qwen-VL 只解释真实输入影像中的可见证据，不生成虚构受灾面积。
- 未配置 Qwen、FIRMS 或 Cesium Key 时，相关功能会返回具体缺失配置，其余页面仍可启动。
