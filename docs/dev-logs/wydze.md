# wydze 开发日志

## 2026-09-09 - `member/wydze`

### 任务目标

将成员丙的火情推演从固定场景 ForeFire HTTP API 调用，改为可以由智能体直接调用、支持时间变化环境输入的动态推演工具，并保持已有影响分析和路线规划接口可继续使用。

### 已完成功能

- 新增 `run_dynamic_fire_spread` 智能体工具。
- 工具接收火点、推演时长、输出步长、环境时间序列、地形和燃料参数。
- 在内部按最多 5 分钟的积分步长插值温度、湿度、风速、风向、燃料含水率、火险指数和降水。
- 使用 72 个方向扇区逐步更新火线，支持风向转变、风速变化、坡向、燃料类型和扑救抑制因子。
- 每个火线 GeoJSON 均保存当时使用的环境帧，便于追溯。
- 新增统一 Agent Tool 注册表、JSON Schema 列表和异步调用入口。
- 推演业务服务不再调用 `forefire-api /api/simulate`，改为直接调用动态工具。
- 智能体未提供环境时间序列时，根据数据库最新环境快照和近期变化趋势生成明确标注的动态预测序列。
- 推演页面显示动态工具状态，并可查看选中火线时步对应的环境因素。

### 主要文件

- `fire_agent_backend/app/tools/dynamic_fire_spread.py`
- `fire_agent_backend/app/tools/registry.py`
- `fire_agent_backend/app/tools/__init__.py`
- `fire_agent_backend/app/schemas/spread.py`
- `fire_agent_backend/app/services/spread_service.py`
- `fire_agent_backend/tests/test_dynamic_fire_spread_tool.py`
- `src/views/FirePredict.vue`

### API 变化

`POST /api/events/{event_id}/spread-runs` 新增可选字段：

- `environment_timeline[]`
  - `elapsed_minutes`
  - `temperature_c`
  - `humidity_percent`
  - `wind_speed_m_s`
  - `wind_direction_deg`
  - `fuel_moisture`
  - `fire_weather_index`
  - `precipitation_mm_h`
  - `source`
- `terrain`
  - `mean_slope_deg`
  - `aspect_deg`
  - `upslope_direction_deg`
  - `fuel_model`
  - `fuel_load_kg_m2`
  - `canopy_cover_percent`
  - `suppression_factor`
- `initial_radius_m`

兼容字段 `prefer_forefire` 暂时保留，但不再触发外部 API 调用。响应中的 `engine` 为 `dynamic_agent_tool`，`result_summary` 增加 `dynamic_environment`、`environment_source` 和 `environment_frame_count`。

### Agent 工具调用

工具名称：

```text
run_dynamic_fire_spread
```

可通过以下入口获取 Schema 和执行：

```python
from app.tools import invoke_agent_tool, list_agent_tool_schemas
```

工具只负责计算并返回结构化结果，不访问数据库、不调用外部 HTTP API。业务服务负责读取环境、保存运行结果和广播进度。

### 数据库变化

没有新增表或字段。动态环境时间序列保存在 `simulation_runs.input_snapshot`，每个时步环境保存在 `fire_front_steps.fireline_geojson.properties.environment`。

### 配置和 Docker 变化

- 删除业务后端中的 `FOREFIRE_API_URL` 和 `FOREFIRE_TIMEOUT_SECONDS` 配置。
- `fire-agent-api` 不再依赖 `forefire-api` 健康状态。
- `forefire-api` 服务暂时保留，供旧功能或后续直接 ForeFire 研究使用，但当前动态推演链路不会调用它。

### 验证

- `py -3.12 -m unittest fire_agent_backend.tests.test_dynamic_fire_spread_tool -v`：3 项通过。
- `py -3.12 -m compileall fire_agent_backend/app backend/forefire_api/app`：通过。
- `npm run build`：通过。
- `docker compose config --quiet`：通过。
- `git diff --check`：通过。
- 外部 API 调用残留搜索：动态推演服务和工具中没有 `/api/simulate` 或 `_try_forefire`。

### 尚未解决

- 当前动态工具是可复现的方向扇区蔓延模型，不是 ForeFire 命令行引擎。
- 真实任务应由气象数据 Agent 提供 ERA5、站点观测或预报时间序列；数据库趋势投影只用于上游尚未交付时的模拟演示。
- Docker Desktop 在本次验证期间未运行，因此未完成容器内 HTTP 端到端测试。
- 仓库不存在 `docs/dev-logs/README.md` 模板，本日志按 `AGENTS.md` 要求手工建立。

### 合并检查重点

- `compose.yaml`：删除了 `fire-agent-api` 对 `forefire-api` 的环境变量和启动依赖。
- `fire_agent_backend/app/schemas/spread.py`：扩展了公共推演输入契约。
- `src/views/FirePredict.vue`：推演引擎和环境时步展示发生变化。
- 项目负责人需要决定是否在后续阶段移除旧 `forefire-api` 服务，或将 ForeFire 命令行能力作为第二种工具引擎重新接入。

## 2026-09-09 - 火线检查点滚动续推

### 任务目标

在第一次推演完成后，允许智能体或用户修改风向、风速等环境因素，并从父运行的最终火线继续推演，而不是回到原始火点重新开始。

### 已完成功能

- `run_dynamic_fire_spread` 工具新增 `initial_fireline_geojson`，可读取上一次输出的 72 方向半径或从 Polygon 重建火线状态。
- 推演输出保存 `sector_radii_km`，保证后续续推可以无损恢复检查点。
- `POST /api/events/{event_id}/spread-runs` 新增 `continue_from_run_id`、`run_mode`、`initial_fireline_geojson` 和 `initial_fireline_source`。
- 后端通过 `continue_from_run_id` 自动读取父运行最终火线和累计时刻，生成父子运行谱系。
- 谱系保存在 `simulation_runs.input_snapshot.lineage` 和 `result_summary`，未新增数据库字段或迁移。
- 推演页面新增动态环境表单和“从当前火线继续推演”操作；续推完成后自动重新执行影响分析与 A* 路线规划。
- 页面时间轴显示事件累计分钟，避免滚动推演误显示为从 `T+0` 重新点火。

### API 影响

- 初始推演继续使用 `ignition_point`，并可显式提交 `environment_timeline`。
- 滚动续推提交父运行 `continue_from_run_id`，可省略 `ignition_point`。
- `run_mode` 可取 `initial_forecast`、`rolling_forecast`、`observation_corrected`、`what_if`。
- 响应 `result_summary` 新增 `parent_run_id`、`root_run_id`、`run_mode`、`initial_fireline_source` 和 `continued_from_checkpoint_minute`。
- 火线 GeoJSON properties 新增运行谱系、检查点来源和 `sector_radii_km`。

### 数据库与配置

- 未新增数据库表或字段。
- 未新增环境变量或 Docker 服务。
- 火线检查点和运行谱系使用现有 JSON 字段保存。
- 容器 HTTP 测试发现 `SimulationRun` 与 `FireFrontStep` 同批 flush 时可能先插入子记录；现已在保存火线前显式 flush 父运行，避免 PostgreSQL 外键错误。

### 验证

- `PYTHONPATH=fire_agent_backend py -3.12 -m unittest fire_agent_backend.tests.test_dynamic_fire_spread_tool -v`：4 项通过。
- `py -3.12 -m compileall fire_agent_backend/app backend/forefire_api/app`：通过。
- `npm run build`：通过。
- `docker compose config --quiet`：通过。
- `git diff --check`：通过。
- `docker compose up -d --build`：PostGIS、fire-agent-api、forefire-api 和 frontend 均成功启动，fire-agent-api 健康检查通过。
- HTTP 端到端续推：父运行在 `T+120`、`1.4101 km²` 结束；子运行从 `T+120`、`1.4101 km²` 起步，改风后推演至 `T+210`、`4.8394 km²`。
- 子运行返回 `run_mode=rolling_forecast`、`initial_fireline_source=parent_run_final_fireline`。
- 续推后的空间分析使用子运行 ID，并生成 9 条影响记录和 3 条应急路线。
- Chrome/Edge 无头截图检查 `/fire-predict`：桌面与移动端均显示新增环境输入和续推操作，未发现控件文字重叠。

### 集成检查重点

- `fire_agent_backend/app/schemas/spread.py` 修改了公共请求 Schema。
- `src/views/FirePredict.vue` 直接提交环境时间序列并依赖新增续推字段。
- 下游空间分析仍自动读取事件最新一次推演，因此续推后会使用子运行最终火线。

## 2026-09-09 - DEM 与土地覆盖栅格驱动

### 任务目标

参考 ForeFire 对地形和燃料空间分布的处理方式，避免动态智能体工具仅使用平均坡度和单一燃料类型，使火线能够受到局部山脊、沟谷和土地覆盖类别影响。

### 已完成功能

- `run_dynamic_fire_spread` 升级到 `2.0.0`，新增可选 `landscape` 栅格输入。
- 景观栅格包含经纬度轴、DEM、土地覆盖/燃料编码、类别名称、来源和模拟标记。
- 每个积分步对 72 个火线方向采样前缘和前方高程，计算有符号坡度；上坡加速、下坡减速。
- 每个方向根据即将进入的土地覆盖类别调整传播速度，支持项目燃料编码和 ESA WorldCover 常用编码。
- 场景接口未显式提供景观时，后端自动从对应 `final_input.nc` 读取 `topography_z` 与 `fuel_idx`。
- 续推继续使用父运行最终火线，同时重新按最新位置采样 DEM 和土地覆盖。
- 每个火线时步记录前缘平均/最小/最大高程、最大上下坡、主导地类和地类扇区数量。
- 推演页面新增 DEM/土地覆盖状态块，并显示所选时步的地形与地类统计。

### API 与 Agent 工具变化

`POST /api/events/{event_id}/spread-runs` 新增可选 `landscape`：

- `longitudes[]`
- `latitudes[]`
- `elevation_m[][]`
- `landcover_codes[][]`
- `landcover_labels`
- `source`
- `scene_id`
- `is_simulated`

不提交时按 `scenario_id` 自动加载场景 NetCDF。工具响应 `summary` 和运行 `result_summary` 新增：

- `terrain_aware`
- `landcover_aware`
- `landscape`
- `landscape_source`
- `landscape_warning`

### 数据与依赖

- `fire-agent-api` 新增只读挂载 `./environment:/app/environment:ro`。
- 新增 `LANDSCAPE_DATA_DIR`，本地默认指向仓库 `environment` 目录。
- 新增 Python 依赖 `numpy` 与 `netCDF4`。
- 没有新增数据库表或字段，景观来源与摘要继续保存在现有 JSON 字段。
- 当前木里 `fuel_idx` 是规则生成的模拟燃料层，必须保持 `is_simulated=true`；后续可替换为真实 ESA WorldCover、Sentinel 分类或林业调查数据。

### 验证

- 6 项动态工具单元测试通过。
- 合成 DEM 测试验证上坡方向传播距离大于下坡方向。
- 合成地类测试验证草地传播距离大于建筑/不可燃地类。
- 木里场景成功加载 31×31 栅格，高程范围 1925–4891 米，地类编码为 1、2、3。
- 相同气象输入下，均一地形结果为 `1.3278 km² / 0.9748 km`，栅格驱动结果为 `1.6653 km² / 1.3930 km`，证明空间地形和地类已实际改变结果。
- 栅格驱动 2 小时火线西北方向约 `1.379 km`、东南方向约 `0.177 km`，不再是规则椭圆。
- HTTP 初始推演与改风续推通过：子运行从父运行 `T+120`、`1.6653 km²` 原位继续，并自动重算影响分析和 3 条路线。

### 集成检查重点

- `compose.yaml` 新增景观目录挂载。
- `fire_agent_backend/requirements.txt` 新增二进制科学计算依赖，首次 Docker 构建时间会增加。
- `fire_agent_backend/app/schemas/spread.py` 再次扩展公共推演请求契约。
- `fuel_idx` 当前不是实测土地覆盖，合并或答辩时不得描述为真实遥感分类成果。

## 2026-09-09 - 气象更新时间驱动与临时模拟燃料层

### 任务目标

取消固定推演时长和固定火线输出步长，使每轮预测延伸到下一次气象信息有效时刻；在 ESA WorldCover 尚未下载前，提供结构兼容、来源清晰的临时模拟土地覆盖燃料层。

### 已完成功能

- `run_dynamic_fire_spread` 升级到 `2.1.0`，`horizon_minutes` 和 `step_minutes` 改为可选兼容字段。
- 环境时间轴最后一个有效时刻自动决定本轮推演时长，火线只在环境帧有效时刻输出。
- 不规则时间轴（例如 0、17、43、90 分钟）可直接驱动火线输出，内部仍使用最多 5 分钟的数值积分步长。
- 未提供环境时间轴时，业务后端根据场景 `time_segments` 计算下一次气象更新时间；木里场景当前为 5 分钟，平遥场景在 120 分钟前为 5 分钟、之后为 15 分钟。
- 推演结果新增 `timing_mode`、`weather_update_minutes`、`forecast_valid_until_minute` 和 `representative_update_interval_minutes`。
- 推演页面新增“下一次气象更新时间（分钟后）”，初始推演和改风续推均使用该时间作为本轮结束时刻，不再硬编码 180/120 分钟。
- 当前 NetCDF 的 `fuel_idx` 来源包含 `rule-based fuel layer`，确认不是真实土地覆盖分类。
- 针对该规则层，运行时根据 DEM 高程、坡度、山脊位置和确定性空间纹理生成临时模拟燃料层。
- 临时类别使用 ESA WorldCover 兼容编码：10 森林、20 灌丛、30 草地、60 裸地/岩石。
- 模拟层明确标记 `source=cesium_visual_dem_proxy_simulated`、`is_simulated=true`，同时保存原始 NetCDF 来源和分类方法，后续可直接替换为 ESA WorldCover 栅格。

### API 与数据变化

- `POST /api/events/{event_id}/spread-runs`
  - `horizon_minutes`、`step_minutes` 现在可省略。
  - 显式 `environment_timeline` 的最后时刻决定预测有效期。
  - 未显式提交时间轴时，场景气象更新计划决定预测有效期。
- `landscape` 新增可选元数据：
  - `original_source`
  - `classification_method`
- 未新增数据库字段或迁移；`simulation_runs.horizon_minutes` 与 `step_minutes` 保存本轮实际有效期和代表性气象间隔。

### 验证

- `PYTHONPATH=fire_agent_backend py -3.12 -m unittest fire_agent_backend.tests.test_dynamic_fire_spread_tool -v`：8 项通过。
- 不规则气象时间测试：输入 0、17、43、90 分钟，输出火线时刻完全一致，自动推断时长为 90 分钟。
- 临时土地覆盖测试：生成类别只使用 10/20/30/60，且包含森林、裸岩和至少一种过渡植被类别。
- `py -3.12 -m compileall fire_agent_backend/app backend/forefire_api/app`：通过。
- `npm run build`：通过。
- `docker compose config --quiet`：通过。
- `git diff --check`：通过，仅出现仓库现有 Windows 行尾提示。
- Docker HTTP 显式时间轴：17 分钟更新产生 `T+0,T+17`，运行时长与数据库代表间隔均为 17 分钟。
- Docker HTTP 自动时间轴：木里场景产生 `T+0,T+5`，自动采用下一次气象更新时间。
- Docker HTTP 改风续推：父运行在 `T+17`、`0.1154 km²` 结束；子运行从相同面积继续到 `T+30`、`0.2883 km²`。
- 场景分段更新时间检查：`T+117/T+120/T+134` 到下一有效时刻分别为 3/15/1 分钟。
- 木里临时模拟层为 31×31，类别像元数量为森林 153、灌丛 523、草地 48、裸岩 237。
- 前端 `http://localhost:5173/fire-predict` 返回 HTTP 200，后端和 PostGIS 健康。

### 尚未解决与替换说明

- 当前土地覆盖是联调和演示用模拟燃料层，不是 ESA WorldCover，也没有进行真实影像监督分类。
- 后续下载 ESA WorldCover 后，应裁剪、重投影/重采样到 DEM 网格，保留 10/20/30/40/50/60/80 等原始类别编码，并将 `source` 改为实际产品版本、`is_simulated` 改为 `false`。
- 当前动态方向扇区模型仍不是 ForeFire 数值引擎，但已把气象、DEM 和空间燃料类别作为逐步变化输入。

### 集成检查重点

- `fire_agent_backend/app/schemas/spread.py` 修改了公共请求字段的可选性。
- `fire_agent_backend/app/services/spread_service.py` 现在依赖场景气象更新计划决定默认时长。
- `src/views/FirePredict.vue` 移除了固定时长提交，展示文字改为气象有效期。
- 合并时不得将 `cesium_visual_dem_proxy_simulated` 或 `is_simulated=true` 描述为 ESA WorldCover 实测成果。

## 2026-09-09 - 火线动画播放与续推检查点交互

### 任务目标

解决地图动画播放速度偏慢、计算接口返回后动画尚未结束却可以提前续推的问题，并区分“模型预测时间”和“地图播放时间”。

### 已完成功能

- 火线动画默认压缩为约 3.2 秒，提供快速、标准、慢速三档播放时长。
- 动画播放时长只影响前端展示，不改变气象有效期、火线坐标或推演计算结果。
- 新增播放/暂停、跳到最终火线和播放速度控件。
- 续推按钮改为只有“最终火线检查点已就绪”且动画已停止时才可点击。
- 动画播放完成后明确提示可以更新气象条件并从最终火线继续推演。
- 影响分析、路线重算或图层切换不会重复播放当前运行的火线动画。
- 修正时间轴手动选择进度单位，Cesium 组件使用 0–100 百分比时不再错误传入 0–1。

### 交互约定

- “本轮预测至下次气象更新（分钟）”表示模型预测窗口，决定本轮火线计算到哪个气象有效时刻。
- “快速/标准/慢速”表示动画播放时长，只服务于观察，不代表真实火灾时间。
- 用户可以暂停动画或跳到最终火线；跳到最终火线后才允许执行“从最终火线继续推演”。
- 续推仍然使用后端父运行最终火线，不会使用动画中间帧作为计算起点。

### 主要文件

- `src/components/CesiumMap.vue`
- `src/views/FirePredict.vue`

### 验证

- `npm run build`：通过。
- `docker compose up -d --build frontend`：前端容器成功重建并启动。
- `http://localhost:5173/fire-predict`：服务可访问。

### 尚未解决

- 当前环境无法稳定生成 Cesium 页面无头截图，已完成 TypeScript 构建和容器启动验证；需要在浏览器中手动确认播放控件的视觉效果。
## 2026-09-10 - 动态火势五模型校准

### 本次目标

修正火线过度贴合 DEM 等高线的问题，使传播模型、风场、燃料、地形和火线更新逻辑具有可解释的参数边界，同时保持智能体工具接口和滚动续推兼容。

### 已完成

- `fire_agent_backend/app/tools/dynamic_fire_spread.py` 升级为 `2.2.0`。
- 风场改为基于起火点焦点的头火、侧火、尾火椭圆传播模型，避免逐方向指数放大。
- 基准传播率改为 Rothermel 风格的表面火速代理：气象干燥度、燃料含水率、燃料负荷和冠层只影响基准速率，风场单独处理。
- DEM 坡度修正改为有符号且受限的指数修正，典型 20 度坡度约为 `0.72` 至 `1.39`，限制范围为 `0.62` 至 `1.65`。
- 火线更新改为仅扩散本次新增量，并保持每个扇区半径单调不减，减少局部 DEM 噪声造成的等高线状边界。
- 推演摘要新增五个模型的名称和风向约定，便于 Agent、前端和报告追溯。
- `fire_agent_backend/tests/test_dynamic_fire_spread_tool.py` 新增无风近圆形和火线不回缩回归测试。

### 验证

- `PYTHONPATH=fire_agent_backend py -3.12 -m unittest fire_agent_backend.tests.test_dynamic_fire_spread_tool -v`：10 项通过。

### 限制

- 当前仍是可解释的规则/物理启发式工具，不等同于完整 ForeFire 数值引擎；尚未建模飞火、冠层火、地形风场和火场对流。
- `wind_direction_deg` 继续沿用项目约定，表示火势被风推向的方向；若接入标准气象“风从哪里来”的数据，必须先加 180 度转换。
- 临时土地覆盖仍需后续替换为 ESA WorldCover 栅格并进行投影、重采样和参数标定。
## 2026-09-10 - 火线驱动风险评估计算单元

### 本次目标

将火线、遥感观测和地物资产统一纳入居民点、道路和资源影响评估，移除土地覆盖影响统计中的固定比例。

### 已完成

- `fire_agent_backend/app/services/spatial_analysis_service.py` 在空间分析时读取事件的卫星、无人机、瞭望塔和视频观测，汇总观测数量、来源类型和最大/平均置信度。
- 居民点、设施、道路、消防站、避难点和水源统一生成影响记录；资源站和避难点增加资源容量字段。
- 点目标风险分数由火线净距和威胁缓冲区计算，道路风险由火线相交或道路净距计算，并保存 `risk_basis` 解释字段。
- 影响 GeoJSON 和数据库属性增加 `risk_score`、`risk_basis`、`resource_capacity`。
- 土地覆盖影响面积改为读取火线前缘土地覆盖扇区采样结果，按扇区占比估算，不再硬编码土地类型比例，并标明 `fireline_sector_sampling`。
- 空间分析摘要增加遥感证据、受影响资源数量、受影响资源容量和风险计算方法；无遥感观测时显式生成告警。

### 接口影响

`POST /api/events/{event_id}/spatial-analysis` 请求字段不变。响应 `run.summary` 新增或更新：

- `affected_resource_count`
- `affected_resource_capacity`
- `remote_sensing`
- `risk_method`
- `landcover_impacts[].share`
- `landcover_impacts[].calculation`

影响记录 `attributes` 和 `impact_geojson.features[].properties` 新增：

- `risk_score`
- `risk_basis`
- `resource_capacity`

### 验证

- 动态推演单元测试：10 项通过。
- `py -3.12 -m compileall fire_agent_backend/app fire_agent_backend/tests`：通过。
- `docker compose build fire-agent-api`：通过。
- `fire-agent-api` 重建后状态为 `healthy`，`GET /health` 返回 `200`。

### 限制

- 当前演示地物资产仍由场景资产适配器提供，接入真实 PostGIS 居民点、道路、资源图层时保持字段契约即可替换。
- 当前土地覆盖面积是火线扇区采样估算，不是严格栅格 zonal statistics；后续接入 ESA WorldCover 后应改为火灾面与燃料栅格的投影坐标空间叠加统计。
- 遥感观测当前用于证据质量与可追溯性，不直接伪造遥感影像覆盖范围。
## 2026-09-10 - 风险评估页面替换路线规划与火场分区

### 本次目标

将推演页面的主结果从“影响分析与 A* 路线规划”调整为风险评估，展示火场内部火强分区及其土地覆盖类型。

### 已完成

- 动态推演工具在火线前缘记录每个扇区的土地覆盖标签和坡度因子。
- 空间分析服务根据最终火线的 72 个扇区生成 `fire_intensity_zone` GeoJSON。
- 每个分区输出 `large_fire`、`medium_fire` 或 `small_fire`、风险分数、传播半径和土地覆盖标签。
- 风险分区以火点为中心、相邻火线节点组成扇区，覆盖整个最终火场，前端使用红/黄/蓝半透明面叠加显示。
- 推演页面新增“火强分区 / 土地覆盖”图层和火场强度分区列表；旧路线区域隐藏，路线接口和数据库结构暂时保留兼容。
- 本轮空间分析请求关闭路线计算，风险评估仍保留居民点、道路、设施和资源影响统计。

### 接口影响

`run.impact_geojson.features` 除目标影响要素外新增 `object_type=fire_intensity_zone` 要素，属性包括：

- `intensity_level`
- `intensity_label`
- `risk_score`
- `landcover_label`
- `sector_index`
- `radius_km`

`run.summary.fire_intensity_zones` 新增分区数量统计和分类方法。

### 验证

- 动态推演单元测试：10 项通过。
- `py -3.12 -m compileall fire_agent_backend/app`：通过。
- `npm run build`：通过。
- `docker compose build fire-agent-api frontend`：通过。
- `fire-agent-api` 和 `frontend` 容器已重建启动；后端健康检查通过，前端端口为 `5173`。

### 限制

- 当前“大火/中火/小火”是基于各扇区相对传播半径的火强代理，不代表真实火焰温度或火焰高度。
- 当前土地覆盖类型来自模拟 DEM 燃料层；接入 ESA WorldCover 后，分区属性可沿用，但应使用严格栅格叠加统计。
- 旧 A* 路线 API 暂未删除，避免其他成员页面或 Agent 合并时产生接口断裂；推演页面已不再将路线作为主结果。
## 2026-09-10 - 移除推演页面火强分区与土地覆盖展示

### 本次目标

根据联调截图，删除页面中造成视觉噪声的 72 扇区火强分区和土地覆盖叠加展示。

### 已完成

- `src/views/FirePredict.vue` 移除火强分区/土地覆盖图层按钮和地图实体绘制。
- 移除右侧 72 条火强分区列表、土地覆盖面积列表和左侧土地覆盖状态卡片。
- 移除环境卡片中的前缘土地覆盖字段，保留 DEM 坡度指标用于模型可解释性。
- 右侧页面标题、指标和图例收敛为风险评估、居民点、人口、道路、资源和受威胁目标。
- 后端仍保留 DEM、燃料层和风险评估数据契约，未删除动态推演计算所需的景观数据。
- 兼容性路线接口仍保留，但推演页面不再展示路线主结果。

### 验证

- `npm run build`：通过。
- `docker compose build frontend`：通过。
- 前端容器已强制重建并启动，`GET http://localhost:5173/fire-predict` 返回 `200`。
## 2026-09-10 - 多因素空间风险区域评估

### 本次目标

解决风险评估过于简单和 72 个扇区标注拥挤的问题，根据火势、环境、地形、燃料和目标暴露对空间区域计算风险值，并合并连续区域。

### 已完成

- `fire_agent_backend/app/services/spatial_analysis_service.py` 新增多因素空间风险计算：火线扩展程度、最近时段增长、风向一致性、坡度因子、燃料可燃性和周边居民点/设施暴露共同计算 `risk_score`。
- 相邻且等级相同的火线方向自动合并为少量 `risk_area` Polygon，不再把 72 个方向作为 72 个独立展示对象。
- 风险区域等级按风险值划分为 `high`、`medium`、`low`，每个区域保存连续方向数量和主要风险因子。
- `src/views/FirePredict.vue` 新增空间风险区域摘要和无文字标签的半透明风险面，避免火点附近出现大量重叠文字。
- `src/components/CesiumMap.vue` 修正 `addDemoArea`：只有显式提供 `label` 才绘制文字，风险面默认不再添加标签。
- 页面继续隐藏火强分区和土地覆盖展示，土地覆盖仅作为后端燃料风险因子参与计算。

### 接口影响

`run.impact_geojson.features` 新增 `object_type=risk_area` 要素，属性包括：

- `risk_level`
- `risk_score`
- `sector_count`
- `dominant_factors`

`run.summary.risk_areas` 返回高、中、低风险区域数量及 `multi_factor_sector_grouping` 分类方法。

### 验证

- 动态推演单元测试：10 项通过。
- `py -3.12 -m compileall fire_agent_backend/app`：通过。
- `npm run build`：通过。
- `docker compose build fire-agent-api frontend`：通过。
- 两个容器重建启动成功，`fire-agent-api` 健康，前端页面返回 `200`。

### 限制

- 当前风险区域仍基于径向火线和模拟场景资产，后续接入真实 PostGIS 地物后应替换资产查询。
- 风险值是面向应急决策的综合代理分数，不等同于现场测得的火焰温度、热释放率或官方灾害等级。
-
## 2026-09-10 - 修复空间风险评估 500

### 本次目标

修复 `spatial-analysis` 接口在生成多因素风险区域时的服务端异常。

### 已完成

- 在 `spatial_analysis_service.py` 增加 `_clamp` 数值边界函数，修复 DEM 坡度风险分量计算中的 `NameError`。
- 保持风险区域、多因素评分和前端展示契约不变。

### 验证

- 已定位原始异常：`_risk_areas()` 调用未定义的 `_clamp` 导致 `POST /api/events/{event_id}/spatial-analysis` 返回 500。
- 待完成代码编译、单元测试及 Docker 接口联调。

### 影响与限制

- 本次仅修复服务端异常，不改变风险评分权重、阈值或土地覆盖仅作为后端因素参与计算的设计。
## 2026-09-10 - 修复风险区域地图不可见

### 本次目标

解决右侧风险区域列表已有数据，但 Cesium 地图上风险面不易观察的问题。

### 已完成

- 存在风险区域时将地图自动视角调整为 `zoom=14`，避免研究区总览高度导致几公里风险面缩小不可见。
- 将风险面填充透明度从 `0.16` 提高到 `0.28`，边界透明度提高到 `0.98`。
- 保持风险区域无文字标签的展示设计。

### 验证

- 已确认空间分析响应包含 `object_type=risk_area` 的 Polygon 坐标。
- 待执行前端构建和浏览器页面复核。
## 2026-09-10 - 风险区域改为网格连通区并增强叠加显示

### 本次目标

解决风险区域仍呈放射扇形、地图叠加不明显的问题。

### 已完成

- 后端风险区域由火线方向扇区改为局部规则网格风险计算。
- 相邻且风险等级相同的网格单元合并为闭合 Polygon，保留风险值、等级和主要因素字段。
- 前端风险面填充增强，并增加独立贴地高亮边界线，改善三维地形上的可读性。

### 验证

- 新接口返回 4 个闭合风险区域 Polygon，网格单元数分别为 89、11、46、2。
- 动态火势推演测试 10 项通过。
## 2026-09-10 - 限制风险区超出火线的范围

### 本次目标

解决风险分区外接网格范围明显大于当前火线的问题。

### 已完成

- 风险网格改为按每个方向的当前火线半径裁剪。
- 仅保留火线以内及其小范围边缘缓冲区，缓冲范围限制为 `0.08-0.25 km`。
- 每个风险区域增加 `threat_buffer_km` 属性，明确风险区相对火线的扩展范围。

### 设计说明

风险区允许略微超出火线，用于表达火线边缘的即时威胁，但不再使用不受方向约束的外接圆作为风险区。
## 2026-09-10 - 增加风险区域地图图例

### 本次目标

补充地图叠加层的颜色和业务含义说明。

### 已完成

- 地图图例新增当前火线、火场范围、高风险区、中风险区、低风险区和受威胁目标。
- 增加说明文字，明确风险区表示火线及其边缘缓冲内的综合风险评估结果。
- 图例颜色与 Cesium 风险面颜色保持一致。
## 2026-09-10 - 风险区使用可配置火线外缓冲

### 本次目标

允许风险区域合理大于当前火线，表达未来一段时间的潜在蔓延和邻近威胁。

### 已完成

- `_risk_areas` 接入空间分析请求的 `threat_buffer_km`。
- 当前推演页面使用 `0.55 km` 火线外风险缓冲。
- 风险网格仍按各方向实际火线裁剪，不使用最大半径外接圆。
- 后端将可配置缓冲限制在 `0.08-1.0 km`，避免异常输入造成范围失控。
## 2026-09-10 - 修复风险区空洞并声明模型可靠性

### 本次目标

修复风险区域中间未连接的问题，并明确当前风险评估模型的适用范围。

### 已完成

- 风险网格范围改为基于真实火线 Polygon 内部及其边界距离缓冲，不再使用径向半径近似。
- 对相邻网格风险分数进行邻域平滑，并保留单格连通区域，减少空洞和碎片。
- 接口新增 `model_reliability`，标记为 `demonstration_only`、未校准、未完成历史火灾验证。
- 推演页面增加“演示级综合风险指数”说明，避免将结果解释为官方灾害等级。

## 2026-09-11 - Dixie Fire 历史栅格推演与空间验证

### 本次目标

利用甲成员交付的 Dixie Fire 小时气象、Copernicus DEM、ESA WorldCover、FIRMS 和 MTBS 数据，建立可由智能体调用的动态栅格火势推演链路，并用同期观测代理量化空间吻合程度。

### 已完成

- 新增智能体工具 `run_raster_fire_spread`，在 `EPSG:32610` 投影网格中按气象更新时间逐段推进火线。
- 使用多源 Dijkstra 到达时间传播，综合时变风速风向、死燃料含水率、DEM 有符号坡度和 WorldCover 燃料/阻隔类型。
- 新增 `POST /api/events/{event_id}/spread-runs/historical`，从 PostGIS 读取历史小时气象并保存 26 个火线时步。
- 标准气象风向在工具入口由“风从哪里来”转换为“火势被推向哪里”；转换后的方向和原始方向均保存在环境快照中。
- 使用同期 FIRMS 热点凸包计算面积偏差、交集面积、IoU、模拟区命中率和热点区覆盖率；MTBS 仅作为最终事件面积参考。
- 修复栅格火线零增长时风险分析除零错误，并兼容 Polygon/MultiPolygon 火线。
- 推演页面新增 Dixie 历史回放、真实栅格元数据和历史对比指标；历史回放禁止切换到径向工具续推，避免模型语义变化。
- 修复移动端全局导航拥挤，窄屏只显示当前导航入口。

### API 与响应字段

- 请求字段：`horizon_hours`、`start_at`、`raster_resolution_m`、`simulation_buffer_km`、`initial_radius_m`、`suppression_factor`、`hotspot_comparison_radius_km`、`wind_direction_convention`。
- `result_summary.comparison` 新增：`intersection_with_hotspot_hull_km2`、`spatial_iou_percent`、`simulation_precision_percent`、`hotspot_hull_recall_percent`。
- `result_summary.model_validation_status=course_demo_unvalidated`；风险模型仍标记 `demonstration_only`。

### 数据、依赖与公共文件

- 栅格路径限制在配置的 `data/` 目录内；Docker 只读挂载 `./data:/app/data:ro`。
- Python 新增 `rasterio`，后端镜像新增 Rasterio 运行所需的 `libexpat1`。
- 修改高冲突公共文件：`compose.yaml`、`fire_agent_backend/app/main.py`、`src/api/modules.ts`、`src/stores/fireEventStore.ts`、`src/components/AppHeader.vue`。
- `data/` 与 `handoff/` 为共享原始/处理数据，不纳入本成员代码提交。

### 验证结果

- 24 小时运行：26 帧，最终面积 `4.0435 km²`，最大半径 `2.1376 km`，方向 `337.8°`。
- 同期 96 个 FIRMS 热点凸包面积 `9.8759 km²`；交集 `4.0230 km²`，IoU `40.64%`，模拟区命中率 `99.49%`，热点区覆盖率 `40.74%`。
- MTBS 最终面积 `3965.121 km²`，不是 24 小时时间匹配边界，不能直接用于参数校准。
- `POST /api/events/dixie_fire_2021/spatial-analysis` 返回 `completed`，生成 3 个风险连通区，不再出现 500。
- 前端桌面 `1440x900` 与移动端 `390x844` 自动交互截图通过：Cesium 画布非空、无横向溢出、浏览器无 console/page error。

### 限制与合并检查重点

- 当前传播速率是可解释代理模型，尚未使用历史火场样本进行独立标定；不应根据单个 24 小时 FIRMS 凸包直接硬调参数。
- NASA POWER 是再分析/格点气象，不能替代火场局地风场；尚未模拟飞火、冠层火和火场诱导风。
- FIRMS 凸包是活跃火点范围代理，不是严格过火边界；后续应接入同时间戳的实测火场边界并划分训练、验证事件。
- 集成人员需重点检查上述公共路由、Store、Compose 和移动端 Header 样式冲突。
# 2026-09-12 - Retain Dixie scenario and balance raster terrain spread

### Scope

Keep only the Dixie Fire 2021 scenario in runtime selectors and defaults. Preserve old database rows for referential integrity, but disable non-Dixie scenarios.

### Changes

- Updated the scenario registry, event defaults, map defaults, and landscape mappings to `dixie_fire_2021` at the shared FIRMS ignition point.
- Updated the legacy ForeFire scene directory map so the old Muli and Pingyao scenes are no longer runtime entries.
- Reduced the signed DEM neighbor correction from an unbounded-looking 0.62-1.65 range to a bounded 0.78-1.28 range. Wind and fuel remain the primary controls, while terrain still promotes uphill spread and limits downhill spread without blocking lateral propagation.
- Added regression tests for right/east and down/south propagation on burnable flat terrain and for propagation under a sharp elevation change.

### Verification

- `py -3.12 -m compileall -q fire_agent_backend/app backend/forefire_api/app`: passed.
- `npm run build`: passed.
- Raster unit tests require the Rasterio PROJ data directory when a PostgreSQL PROJ environment variable is globally configured; rerun with `PROJ_LIB=D:\Python\Python312\Lib\site-packages\rasterio\proj_data`.

## 2026-09-12 - Unify the prediction page on the Dixie raster engine

- Removed the prediction page entry point for the legacy radial dynamic model, whose smoothed 72-direction geometry appeared circular.
- The primary prediction command now runs the Dixie historical raster workflow using hourly weather, DEM, and WorldCover data.
- Removed duplicate controls that allowed users to accidentally select two different spread engines for the same Dixie scenario.
- `npm run build`: passed.

## 2026-09-12 - Protect the ignition and active fire front risk levels

- Added conservative minimum risk scores for the active fire-front band and the early-stage burned footprint.
- The ignition core is now guaranteed to remain high risk during the first six simulation hours; neighborhood smoothing and isolated-cell cleanup cannot downgrade constrained cells.
- Multi-factor scores continue to classify the surrounding threat buffer and preserve spatial variation outside the confirmed burning area.
- Added a regression test asserting that an early ignition point is contained by a high-risk polygon.
- Fixed risk component GeoJSON to preserve interior holes, preventing a surrounding low-risk component from geometrically covering the high-risk ignition core.
- Updated Cesium risk rendering to support Polygon holes and draw low, medium, then high risk layers.

## 2026-09-12 - Use modeled fireline intensity in spatial risk

- Raster fire-front cells now calculate an uncalibrated Byram `H * w * R` fireline intensity proxy in kW/m from local spread rate, WorldCover-derived fuel load, fuel moisture, and representative heat content.
- Every fireline frame exposes 72 directional intensity samples plus mean and maximum intensity diagnostics.
- Fire intensity is now the largest weighted component of the spatial risk score; each merged risk polygon reports mean/max intensity and an intensity class.
- The UI displays mean and maximum fireline intensity for every risk area.
- Fixed grid-to-sector attribution so each risk cell uses its own directional intensity instead of the final sector's value.

## 2026-09-12 - Restore weather-driven rolling fire spread

- Restored manual current and forecast weather inputs as the primary prediction workflow, including temperature, humidity, wind speed, wind direction, fuel moisture, FWI, and the next weather update interval.
- Standard Dixie spread runs now use the same DEM- and WorldCover-aware raster agent tool as historical validation runs.
- Rolling forecasts inherit the parent run's final Polygon/MultiPolygon fireline, continue from its final minute, and apply the newly entered weather instead of restarting from the ignition point.
- Moved the 6/12/24-hour historical replay into an optional collapsed validation section; historical comparison runs remain non-continuable.
- Verified a 60-minute eastward forecast followed by a 60-minute southward continuation: the second run linked to the first, advanced from minute 60 to 120, and increased area from `0.1456 km2` to `0.1941 km2`.

### 气象更新时间语义修正

- 推演区间采用离散的更新时间语义：`T_i` 的气象条件驱动 `T_i -> T_{i+1}`，不对起止时刻做中点平均。
- 页面将当前气象和“距下次气象更新”作为本轮唯一人工输入；更新风向或其他环境因素后，从上一轮最终火线开启下一轮续推。

### 真实小时气象入口

- 推演页面将历史入口明确为“使用真实小时气象推演”，不再把它仅描述为结果对照。
- 结果中显示数据库小时气象帧数和实际覆盖时间；每个小时的气象输入会驱动对应的下一小时栅格火线更新。

### 逐时传播追溯与 FIRMS 验证

- 每个非初始火线检查点保存 `weather_used_for_previous_interval`、`propagation_interval`、`weather_used_from` 和 `weather_used_to`，明确本段实际使用的气象。
- 每个模拟检查点使用从起火到当前时刻的累计 FIRMS 热点构造过火范围代理，当前时刻前后 30 分钟热点只用于火头方向验证；计算面积误差、IoU、命中率、覆盖率、Hausdorff 距离、蔓延方向误差和最大半径误差。
- 少于有效面积的热点集合不再被错误记为 `IoU=0`，而是返回 `null` 并从面积指标汇总中排除。
- 页面显示逐时有效样本数及平均 IoU、Hausdorff 距离、方向误差和半径误差。


## 2026-09-12 - Restore manual weather and rolling continuation

- Restored current and forecast weather inputs as the primary prediction workflow, including the weather update interval that determines each run horizon.
- Routed normal Dixie spread requests through the DEM and ESA WorldCover raster agent tool instead of the legacy radial model.
- Enabled rolling continuation only after playback reaches the final checkpoint; the parent run's final Polygon/MultiPolygon is used as the next run's initial fireline.
- Kept 6/12/24-hour historical replay in a collapsed optional validation section rather than making it the main prediction action.

## 2026-09-14 - Calibrate short-window spread against FIRMS hull

### Scope

- Abandoned the expensive full-incident replay and MTBS tuning path.
- Calibrated only a 6/12/24-hour simulated fireline against the time-matched cumulative FIRMS hotspot convex hull.

### Model and API changes

- Added explicit bounded run parameters: `spread_rate_multiplier` (`0.6-1.6`), `wind_influence_multiplier` (`0.5-1.5`), and `terrain_influence_multiplier` (`0.5-1.5`). The values affect grid travel time and Byram intensity consistently and are stored in run metadata.
- Retained continuous edge progress across hourly weather boundaries, with `T_i` weather driving `T_i -> T_{i+1}`.
- Added `POST /api/events/{event_id}/spread-runs/calibrate`. It performs a three-stage bounded coordinate search across exact 6/12/24-hour checkpoints and persists only the selected 24-hour run.
- Extra output checkpoints slice the continuous arrival-time grid without inserting weather frames or changing hourly weather validity.
- Per-window score: `0.75 * FIRMS hull IoU + 0.25 * exp(-abs(log(simulated area / hull area)))`. Selection score: `0.70 * mean window score + 0.30 * worst window score` to limit degradation at any one stage.
- Removed the unfinished full-event output interval, 7-day/full-event UI choices, and MTBS final-perimeter comparison from this workflow.

### Real-data result

- Baseline selection score `0.383253`, mean `0.409069`, worst-window score `0.323015`.
- Selected parameters: spread `0.80`, wind `1.25`, terrain `1.25`; selection score `0.403310`, mean `0.429079`, worst-window score `0.343183`.
- Selected 6h result: IoU `37.68%`, area `0.8815 km2`, FIRMS hull `0.4010 km2`.
- Selected 12h result: IoU `28.92%`, area `3.2833 km2`, FIRMS hull `6.4999 km2`.
- Selected 24h result: IoU `46.32%`, area `12.3247 km2`, FIRMS hull `9.8759 km2`.
- Status is explicitly `calibrated_to_dixie_6h_12h_24h_windows`. FIRMS convex hull is an active-fire observation proxy with satellite overpass gaps, not a measured burned perimeter, and this is not an independent general validation.

### Verification

- Raster spread unit tests: 7 passed with Rasterio `PROJ_LIB` configured, including proof that an extra output checkpoint does not change final spread.
- `py -3.12 -m compileall -q fire_agent_backend/app`: passed.
- `npm run build`: passed.
- Docker `fire-agent-api`, `frontend`, and `postgis`: running; backend and PostGIS healthy.

## 2026-09-14 - Keep the Dixie map visible with terrain enabled

- Fixed `setTerrainEnabled(true)` re-enabling Cesium astronomical globe lighting after component initialization.
- Three-dimensional terrain, depth testing, and elevation exaggeration remain enabled, while day/night shading stays disabled because Cesium's clock is not the fire simulation clock.

## 2026-09-14 - Prevent unsupported low-risk cells inside the fire extent

- The cumulative burned footprint now has a medium-risk floor because the spread model does not track cell burnout, residual heat, or cooling time and therefore cannot justify a low-risk interior.
- The active fireline band remains high risk. Low risk is limited to the external threat buffer.
- Protected all constrained fire cells from the isolated-cell smoothing pass, which could previously overwrite the numeric minimum with a lower categorical class.
- Added `zone_relation`, interior-cell count, and active-front-cell count to risk polygons; the frontend labels active fireline, burned footprint, and external threat-buffer regions separately.
- Verified against the running Dixie database: 11 risk zones, 0 low-risk zones intersecting the fire footprint; 5 external low-risk zones, 5 medium zones, and 1 high-risk active-front zone.

## 2026-09-14 - Add interactive local weather visualization

- Added an interactive wind-direction dial using the existing `spread_toward` convention. Dragging the dial snaps to 5-degree increments and updates the same value sent to the raster spread tool.
- Added compact temperature, humidity, and wind-speed gauges with range controls and retained numeric inputs for precise entry.
- Mounted the existing Cesium wind canvas and added a manual local vector-field source centered on the ignition point.
- The ignition-point vector exactly follows the user setting. Surrounding vectors use smooth direction perturbations and speed gradients, then inverse-distance interpolation provides continuous particle motion between grid samples.
- Reduced wind particles from 760-1500 to 180-360, lengthened trail persistence, reduced opacity, and used a restrained blue/green/yellow speed palette.
- Historical playback updates the map weather strip and local flow field from the selected hourly environment frame; manual runs remain synchronized with current form values.
- Narrowed the modeled fire-front line and glow so the wind field, risk surfaces, and perimeter remain distinguishable.
- `npm run build`: passed. The frontend Docker image was rebuilt successfully before Docker Desktop later became unavailable.
- NASA POWER is not called in this change. It remains a possible real gridded/time-series source, but the current visualization is deterministic and works offline from project weather inputs.

## 2026-09-15 - Make the local wind field observable

- Added a one-click `定位风场` control that centers Cesium on the confirmed fire point and enables the wind layer without changing the camera while the direction dial is dragged.
- Kept the simulated field sparse and continuous, while allowing its radius to use the configured 90 km local field extent.
- Increased the wind speed heat layer visibility and added low, medium, and high wind speed legend entries so the map encoding is understandable.
- `focusWindField` is exposed by `CesiumMap` for future agent or workflow-driven map focus actions.

## 2026-09-15 - Reflow weather gauges

- Changed the left weather console layout so the wind-speed gauge occupies its own row.
- Temperature and humidity gauges now share a separate two-column row, keeping the controls readable in the narrow left panel.

## 2026-09-15 - Add readable wind direction arrows

- Replaced direction-ambiguous particle strokes with short animated trails ending in arrowheads.
- Increased particle density moderately and strengthened contrast so the wind field remains visible at the local map scale without returning to a crowded arrow grid.
- Arrowheads use each particle's interpolated local vector, preserving spatially varying wind direction around the fire point.

## 2026-09-15 - Decouple arrow animation from wind speed

- Replaced persistent arrow trails with discrete fixed-length direction arrows, clearing their previous positions every frame.
- All arrows now drift at the same deliberately slow animation rate; wind speed no longer controls arrow movement or arrow size.
- Wind speed remains encoded by the separate blue/green/yellow background field, while arrows use one light neutral color and only communicate direction.
- Extended particle lifetime to reduce visual blinking and kept density bounded for a cleaner close-range view.

## 2026-09-15 - Align weather gauges in one row

- Kept the wind-direction dial in the left column and aligned wind speed, temperature, and humidity gauges in one three-column row on the right.
- Ordered the gauges as wind speed, temperature, and humidity while preserving their existing controls and values.

## 2026-09-15 - Separate wind direction and weather gauge rows

- Moved the wind-direction dial and its precise numeric input into a dedicated full-width first row.
- Kept wind speed, temperature, and humidity together in a separate three-column second row.

## 2026-09-15 - Enlarge the wind-direction dial

- Increased the wind-direction dial from 108 px to 124 px and adjusted its arrow and center labels proportionally.
- Preserved sufficient width for the precise direction input in the same row.

## 2026-09-15 - Keep wind direction arrows persistent

- Removed particle lifetime expiry, random respawning, and positional drift from the wind-direction arrows.
- Arrows now remain anchored to stable geographic sample positions and only communicate direction.
- Camera movement still reprojects the arrows, and changing the wind input immediately updates their orientation without visible blinking.

## 2026-09-15 - Animate flow inside anchored arrows

- Kept every wind arrow anchored and continuously visible.
- Added a slow bright segment that travels along each fixed arrow shaft toward its head, providing forward motion without moving or respawning the arrow itself.
- Randomized animation phase per arrow to avoid synchronized flashing across the map.

## 2026-09-15 - Move complete arrows along short local tracks

- Replaced the fixed-arrow internal highlight with complete arrow glyphs moving slowly along short 28 px local tracks.
- Each arrow fades out at the track end and fades back in at the beginning, then repeats without changing its geographic wind sample.
- Increased the bounded arrow density to 360-560 after viewport inspection so enough samples remain visible across the full research-area view.
- Increased the final random geographic-sample density from 520-800 to 1000-1600 arrows for a more continuous wind-direction field.

## 2026-09-17 - Synchronize member branch with origin/main

### Goal

Prepare the historical raster spread and spatial risk work for review on `member/wydze`, then merge the latest shared baseline without pushing to `main`.

### Merge resolution

- Merged `origin/main` after committing the member-owned feature changes.
- Resolved conflicts in `compose.yaml`, `fire_agent_backend/.env.example`, `fire_agent_backend/app/core/config.py`, `fire_agent_backend/app/db/spatial.py`, `fire_agent_backend/app/main.py`, and `fire_agent_backend/requirements.txt`.
- Preserved the historical spread landscape mount, spatial-analysis router, impact geometry columns, and raster dependencies.
- Preserved the incoming realtime monitoring, visual verification, ForeFire client, Qwen-VL configuration, generated geometry columns, and image-processing dependencies.
- Kept downloaded rasters, raw GIS data, database seed files, and the handoff archive outside Git.

### Verification

- `npm run build`: passed after the merge.
- `py -3.12 -m compileall fire_agent_backend/app backend/forefire_api/app`: passed.
- `docker compose config --quiet`: passed.
- `py -3.12 -m unittest tests.test_raster_fire_spread_tool`: 7 tests passed after pointing PROJ to Rasterio's packaged database.
- `tests.test_spatial_risk_areas`: not run successfully because the host Python 3.12 environment does not have SQLAlchemy installed.
- Container tests were not run because Docker Desktop was not running.

### Integration notes

- Review the shared Compose environment, backend router registration, PostGIS schema upgrades, and dependency constraints during merge review.
- The frontend production bundle still reports the existing warning for a JavaScript chunk larger than 500 kB.
