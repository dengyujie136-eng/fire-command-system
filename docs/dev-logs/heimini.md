# heimini 开发日志

## 2026-09-24｜自动候选目标检测流程

- 分支：`member/heimini`
- 最新提交：未提交
- 任务目标：减少云影像干扰，取消逐个候选点选择，改为候选提取后自动目标检测。

### 已完成

- 核验页优先显示云量不超过 10% 的多波段灾中影像；无低云量影像时才回退到现有灾中影像。
- FIRMS 提取后自动按候选顺序裁剪并调用 YOLO，最多检测 20 个候选，找到首个火焰/烟雾支持证据即停止。
- 移除候选点下拉选择和逐点检测按钮；页面只展示自动选中的待确认火点和检测结果。
- Cesium 仍显示全部 FIRMS 候选位置，但不再要求用户逐点操作。
- 保留 Qwen-VL 和人工确认门；YOLO 结果不能绕过最终人工确认和推演前置条件。

### 接口变化

- 新增：`POST /api/visual-verification/imagery-catalog/{asset_id}/auto-detect`。
- 请求字段：`candidate_ids`、可选 `max_candidates`、`crop_radius_m`。
- 响应字段：`status`、`attempted_count`、`selected`、`attempts`；`selected` 包含局部影像 derivative 和 professional 检测结果。

### 验证结果

- 验证结果见本次交付说明。

### 合并提示

- 高冲突文件：`src/api/modules.ts`；新增自动检测客户端方法。
- 项目负责人需检查自动检测首个命中策略与人工确认门的演示要求。

## 2026-09-24｜候选点选择保持地图视角

- 分支：`member/heimini`
- 最新提交：未提交
- 任务目标：点击或切换候选火点时不自动缩放 Cesium 地图。

### 已完成

- 移除候选点重新渲染后的固定 `flyTo` 聚焦。
- 候选点没有局部裁剪影像时，恢复整幅影像叠加但不重新适配相机范围。
- 切换核验影像时仍保留影像范围适配，候选点点击只更新高亮和详情。

### 主要文件

- `src/views/VisualVerification.vue`：分离影像适配与候选选择行为。
- `docs/dev-logs/heimini.md`：记录本次修改。

### 接口、数据与配置变化

- 无。

### 验证结果

- `[通过]` `npm run build`。
- `[通过]` `git diff --check`。
- `[通过]` `docker compose up -d --build frontend`，前端及依赖服务健康启动。

### 对其他模块的影响

- 仅改变核验页 Cesium 相机交互，不影响候选、影像或检测数据。

### 合并提示

- 可随当前核验页面改动一并检查。

## 2026-09-24｜地图点选候选与高分辨率灾中影像

- 分支：`member/heimini`
- 最新提交：未提交
- 任务目标：允许直接点击 Cesium 候选点进行核验，并补充更适合识别烟羽和活跃燃烧的灾中影像。

### 已完成

- Cesium 演示点支持独立点击回调，核验页点击橙色候选点后会切换当前候选并加载其详情。
- 核验影像选择器同时接纳原有 `during` RGB 影像和数据 Agent 下载的 `primary` 灾中多波段产品。
- 多波段预览按 B04/B03/B02 生成自然色，避免 B02/B03/B04 顺序导致颜色颠倒。
- 候选提取接口允许对 `primary` 灾中产品查询同期 FIRMS 热异常。
- 启动火点范围内真实 Sentinel-2 L2A 下载，场景时间为 `2021-07-18T19:03:25.939Z`，云量约 `0.58%`，波段为 B02/B03/B04/B08/B12。

### 主要文件

- `src/components/CesiumMap.vue`：候选实体点击回调。
- `src/views/VisualVerification.vue`：地图点选与灾中多波段影像选择。
- `fire_agent_backend/app/visual_verification/router.py`：多波段自然色预览和 `primary` 产品候选提取。
- `docs/dev-logs/heimini.md`：记录本次修改。

### 接口、数据与配置变化

- 现有影像预览与候选提取接口行为扩展，无新增接口或环境变量。
- 新下载数据位于 `data/raw/imagery/dixie_fire_2021/`，处理产品位于 `data/processed/imagery/dixie_fire_2021/`，不应提交到 Git。

### 验证结果

- `[通过]` `npm run build` 与容器内 `python -m compileall -q app`。
- `[通过]` 三期 Sentinel-2 多波段任务全部完成：`2021-07-18`、`2021-07-23`、`2021-08-02`，每期均含 B02/B03/B04/B08/B12。
- `[通过]` 三期自然色预览均返回 HTTP 200；目视检查确认 7 月 18 日和 7 月 23 日存在明显烟羽，8 月 2 日可见烧灼区与局部烟柱。
- `[通过]` 7 月 18 日多波段产品执行 FIRMS 候选提取，2.20 秒内返回 247 条时间匹配观测并聚合为 61 个候选点。
- `[通过]` `docker compose up -d --build fire-agent-api frontend`，服务健康启动。

### 对其他模块的影响

- `CesiumMap.addDemoPoint` 新增可选 `onClick` 参数，不影响现有调用。
- `primary` 影像继续保持真实数据来源和独立波段元数据。

### 合并提示

- 项目负责人需检查核验页对 `primary` 与 `during` 两类灾中影像的统一展示。

## 2026-09-24｜压缩核验候选点列表

- 分支：`member/heimini`
- 最新提交：未提交
- 任务目标：候选点数量较多时不再逐条占满核验操作栏。

### 已完成

- 将候选点全量按钮列表替换为折叠下拉选择器。
- 操作栏仅展示当前候选点的坐标、观测时间、FIRMS 置信度和聚合观测数。
- 全部候选点继续显示在 Cesium 地图上，检测、复核和人工确认仍针对当前选择项执行。

### 主要文件

- `src/views/VisualVerification.vue`：压缩候选点选择界面。
- `docs/dev-logs/heimini.md`：记录本次修改。

### 接口、数据与配置变化

- 无。未改变候选点接口、数据库记录或环境变量。

### 验证结果

- `[通过]` `npm run build`。
- `[通过]` `git diff --check`。
- `[通过]` `docker compose up -d --build frontend`，前端及依赖服务健康启动。

### 对其他模块的影响

- 仅改变核验页候选点的展示方式，不改变 FIRMS 查询、影像裁剪和检测流程。

### 合并提示

- 可随当前核验页面改动一并检查。

## 2026-09-24｜Agent 选项执行反馈

- 分支：`member/heimini`
- 最新提交：未提交
- 任务目标：解决 Agent 选项点击后缺少可见反馈、当前页导航静默和工作流状态可能过期的问题。

### 已完成

- Agent 顶部新增“新建对话”，重置本轮消息、用户问题、模型建议、操作反馈和输入内容，但保留当前事件及工作流。
- 将原“清空”调整为“清空消息”，只清理可见消息，不丢失当前对话上下文和工作流建议。
- 为选项标记“打开页面、执行任务、执行并打开、继续询问”四种行为类型。
- 点击后立即显示正在处理状态，结束后显示成功或失败原因，并将结果写入任务对话。
- 导航目标与当前页面相同时，不再静默，明确提示用户需要在当前工作页完成操作。
- 未实现的动作类型返回明确错误，不再无提示结束。
- Agent 挂载时主动同步事件、数据就绪度、最新工作流和报告。
- 后台影像任务完成、无匹配或失败时更新可见状态并刷新工作流建议。

### 主要文件

- `src/components/AgentChat.vue`：选项分类、执行反馈、导航反馈、动作结果和初始状态同步。
- `docs/dev-logs/heimini.md`：记录本次修改。

### 接口、数据与配置变化

- 无。复用现有 Assistant、工作流、影像和报告接口；无数据库、环境变量或依赖变化。

### 验证结果

- `[通过]` `npm run build`。
- `[通过]` `docker compose config --quiet` 与 `git diff --check`。
- `[通过]` `docker compose up -d --build frontend`，前端容器已重建，依赖的 API、PostGIS 和检测服务保持健康。
- `[通过]` `GET /realtime-monitor` 与 `GET /health` 返回 HTTP 200；当前真实工作流仍正确停在 `fire_verification / WAITING_FOR_INPUT` 人工核验门。

### 对其他模块的影响

- Agent 会在挂载时主动读取当前事件状态，但不会自动执行具有副作用的选项或绕过人工确认门。

### 合并提示

- 完成构建和运行验证后可交给项目负责人检查。

## 2026-09-24｜状态驱动的完整应急工作流助手

- 分支：`member/heimini`
- 最新提交：未提交
- 任务目标：让智能体主动引导灾前准备、灾中处置、灾后评估和报告生成，并优化右侧对话窗口的可读性与操作效率。

### 已完成

- 新增独立的工作流引导决策层，根据九阶段运行状态生成当前阶段、进度、阻塞原因和下一步操作。
- 未启动时提供完整工作流、实时监测和历史事件入口；运行中自动推进到真实人工决策门。
- 火点核验、应急场景和指挥审批继续要求用户明确确认，不绕过人工决策门。
- 工作流完成后主动提供灾前灾后影像评估与综合报告生成，报告生成后进入 100% 完成状态并提供 PDF 下载。
- 重构智能体窗口：增加阶段条、进度条、推荐操作、运行编号和已完成阶段数；放大正文与按钮字号。
- 移除常驻的五页快捷按钮和大型推演输出卡，将页面入口改为上下文选项，将 GeoTIFF 导入收纳进数据工具。
- 右侧栏宽度调整为 `420-520px`，默认打开智能体标签，同时保留桌面收起和移动端抽屉能力。
- 修正初始引导：用户尚未提问时不展示任何操作选项；提问后才按实时监测、核验、推演、规划、评估、报告或完整流程意图生成相关选择。
- 将聊天接口返回的结构化 `action`、目标页面和地图参数作为下一步选择的首要来源，关键词分类只保留为无结构化结果时的降级逻辑。
- 有副作用的工作流启动、影像获取、火势推演、人工审批和报告生成不再随文字回答自动执行，必须由用户点击建议按钮确认；只读页面导航仍可直接展示。
- 核验页进入时自动打开右侧业务面板，确保候选点影像、Cesium 叠加、YOLO/Qwen-VL 结果和人工确认按钮可见；离开核验页恢复智能体对话。

### 主要文件

- `fire_agent_backend/app/services/assistant_guidance_service.py`：工作流阶段判断和下一步选项生成。
- `fire_agent_backend/app/routers/assistant.py`：新增下一步引导接口。
- `fire_agent_backend/tests/test_assistant_guidance.py`：工作流引导状态测试。
- `src/components/AgentChat.vue`：状态驱动交互、统一动作执行、报告下载和新版布局。
- `src/api/modules.ts`：新增智能体 API 封装。
- `src/App.vue`：右侧栏宽度和默认标签调整。

### 接口变化

- 新增：`POST /api/assistant/next-steps`。
- 请求字段：`page`；`context` 包含事件、工作流、阶段结果、人工确认和报告 ID。
- 响应字段：`phase`、`phase_label`、`title`、`message`、`progress`、`current_stage`、`waiting_for`、`completed_steps`、`choices`。
- 错误和状态变化：接口只根据已持久化/前端已知状态提供操作，不生成模型结论；真实动作失败会保留在对话中。

### 数据库与数据变化

- 表或字段：无。
- 坐标系或空间范围：无变化。
- 数据来源与处理脚本：复用现有 FIRMS、影像目录、工作流和报告数据。

### 配置与依赖变化

- 环境变量：无。
- Python/npm/Docker 依赖：无新增依赖。

### 验证结果

- `[通过]` `npm run build`。
- `[通过]` Docker Python 3.12 `python -m compileall -q app`。
- `[通过]` Assistant 引导、结构化操作确认、实时视角和工具 Agent 共 16 个单元测试。
- `[通过]` `docker compose config --quiet`、`git diff --check`。
- `[通过]` `docker compose up -d --build fire-agent-api frontend`，后端与前端健康启动。
- `[通过]` 1600x1000 无头浏览器界面检查；智能体区域无文字溢出或控件重叠。

### 对其他模块的影响

- 依赖的上游输出：`incidentContextStore` 的工作流状态、阶段列表和结果 ID。
- 提供给下游的输出：可直接执行的导航、影像获取、场景确认、指挥审批、评估和报告动作。
- 高冲突公共文件：`src/api/modules.ts`；新增 `assistantAPI`，未改变现有 API。

### 已知问题与下一步

- 灾后评估尚未纳入九阶段工作流表，当前由评估页的真实影像任务状态负责展示，报告 ID 用于标记最终闭环。
- 无头浏览器缺少 WebGL 时 Cesium 会显示硬件加速错误；正常启用 GPU 的桌面浏览器不受影响。

### 合并提示

- 可以合并；项目负责人需重点检查智能体选择动作与规划页现有人工确认按钮是否符合演示流程。

## 2026-09-23｜通用地点山火工具 Agent

- 分支：`member/heimini`
- 最新提交：未提交
- 任务目标：保留美国、加州等系统展示兜底，同时将其他地点山火分析改为 Qwen 工具调用和真实数据查询，不再为重庆等城市硬编码场景。

### 已完成

- 为 Qwen/OpenAI-compatible 模型增加结构化 `tools` 调用与工具结果续写能力。
- 新增通用 Agent 工具运行时，支持动态地理编码、按坐标选择实时区域、同步 FIRMS、按 AOI 筛选候选火点、查找附近事件、检查数据就绪度和读取工作流状态。
- 删除重庆坐标白名单；“重庆、雅安、大理”等普通地点统一通过 OpenStreetMap Nominatim 获取真实坐标和边界。
- 通用地点请求优先进入工具 Agent，不再回退到 `dixie_fire_2021`；没有独立事件、DEM、燃料、气象或资源时明确报告缺口。
- 保留全球、美国、加州和 Dixie 的确定性演示入口；新增“分析美国山火”的美国本土视角兜底。
- 工具 Agent 最多执行 12 次后端工具调用；FIRMS 仅标记为热异常候选点，不自动绕过遥感与人工确认门。
- 地理编码结果缓存一小时，并在进程内串行限速，避免并发对话重复请求公共服务。
- 对话来源显示为“Qwen 工具智能体 / 真实数据证据”；监测页会监听地点坐标和区域查询参数变化。

### 主要文件

- `fire_agent_backend/app/services/assistant_tool_service.py`：通用工具定义、执行、证据汇总和地图导航参数。
- `fire_agent_backend/app/llm/providers.py`：OpenAI-compatible tool calling 适配。
- `fire_agent_backend/app/routers/assistant.py`：通用地点路由与演示兜底边界。
- `fire_agent_backend/app/core/config.py`：地理编码服务地址和超时默认值。
- `src/components/AgentChat.vue`：工具 Agent 来源标识。
- `src/views/RealtimeMonitor.vue`：监听动态地点导航参数。
- `fire_agent_backend/tests/test_assistant_tool_service.py`：地点提取、区域选择和工具调用解析测试。
- `fire_agent_backend/tests/test_assistant_realtime_focus.py`：美国/全球兜底与通用 Agent 路由回归测试。

### 接口变化

- 修改：`POST /api/assistant/chat`。
- 请求字段：无变化；具体地点山火请求会使用现有 `message` 和精简 `context`。
- 响应字段：通用地点分析新增 `source_mode=tool_agent`、`provider`、`model`、`used_remote`、`tool_trace`、`evidence`，以及动态 `navigate_query.region/lng/lat/height`。
- 错误和状态变化：地理编码、FIRMS 或模型失败会作为真实工具错误返回，不再伪装成已完成分析；美国、加州等展示命令仍返回 `source_mode=structured`。

### 数据库与数据变化

- 表或字段：无。
- 坐标系或空间范围：地理编码和 FIRMS 候选点均使用 WGS84；默认 AOI 半径 75 km，模型可在 5-500 km 范围内选择。
- 数据来源与处理脚本：地点来自 OpenStreetMap Nominatim；候选热异常来自现有 NASA FIRMS NRT/VIIRS 同步服务；未新增模拟真值。

### 配置与依赖变化

- 环境变量：新增可选配置映射 `GEOCODER_BASE_URL`、`GEOCODER_TIMEOUT_SECONDS`，均有默认值，无需保存 API Key。
- Python/npm/Docker 依赖：无新增依赖，复用 `httpx`、SQLAlchemy 和现有 Qwen/FIRMS 配置。

### 验证结果

- `[通过]` 容器内真实 Nominatim 请求解析“雅安市, 四川省, 中国”，返回 WGS84 坐标和行政边界。
- `[通过]` 实际 `POST /api/assistant/chat` 请求“我想分析四川雅安山火”，Qwen `qwen-plus` 依次调用地理编码、区域选择、FIRMS 同步、AOI 查询和附近事件工具。
- `[通过]` 实际雅安请求使用 `himawari_asia_pacific`，读取当前 FIRMS 观测并返回候选点数量，没有套用 Dixie 数据。
- `[通过]` 实际“大理山火”请求返回 `source_mode=tool_agent`、`provider=qwen`，动态坐标 `100.2651597, 25.6074778`，并执行五项真实工具。
- `[通过]` 实际“分析美国山火”请求保留 `source_mode=structured` 和 `focus=usa` 展示兜底。
- `[通过]` `npm run build`。
- `[通过]` Docker Python 3.12 `python -m compileall -q app`。
- `[通过]` 8 个 Assistant/工具 Agent 单元测试。
- `[通过]` `docker compose config --quiet`、`git diff --check`。
- `[通过]` `docker compose up -d --build fire-agent-api frontend`；API、PostGIS 健康，前端可访问。

### 对其他模块的影响

- 依赖的上游输出：Qwen 文本模型、Nominatim、FIRMS NRT、实时观测表和现有事件/工作流表。
- 提供给下游的输出：带真实地点、区域、火点证据和数据缺口的导航与分析结果。
- 高冲突公共文件：`fire_agent_backend/app/routers/assistant.py`；修改原因是将对话路由从城市白名单升级为受控工具 Agent，集成时需检查其他成员新增的命令优先级。

### 已知问题与下一步

- 当前不会根据普通候选火点自动创建正式事件；必须先完成遥感和人工核验，再设计真实事件入库流程。
- 当前实时同步仍按既有大区域下载后在数据库中按 AOI 筛选，尚未改为每个地点单独请求 FIRMS 小范围接口。
- Nominatim 是外部公共服务，网络不可用时会要求用户补充坐标，不会猜测地点。

### 合并提示

- 完成最终构建和接口回归后可合并；重点检查 `assistant.py` 命令优先级、外部服务超时和工具证据字段大小。

## 2026-09-23｜移除侧边导航步骤编号

- 分支：`member/heimini`
- 最新提交：未提交
- 任务目标：移除左侧五个工作页面入口上方的 `01` 至 `05` 编号。

### 已完成

- 删除侧边导航步骤编号，仅保留图标和页面名称。
- 调整导航网格布局，使图标显示在上方、页面名称显示在下方，并保持整体居中。

### 主要文件

- `src/components/AppSidebar.vue`：删除编号渲染及相关样式。
- `docs/dev-logs/heimini.md`：记录本次界面调整。

### 接口变化

- 无。

### 数据库与数据变化

- 无。

### 配置与依赖变化

- 无。

### 验证结果

- 验证结果见本次交付说明。

### 对其他模块的影响

- 仅影响公共左侧导航的视觉布局，不改变路由和页面功能。

### 已知问题与下一步

- 无。

### 合并提示

- 可随当前前端改动一并检查和合并。

## 2026-09-23｜升级地点山火分析与 Qwen 开放问答

- 分支：`member/heimini`
- 最新提交：未提交
- 任务目标：让 Agent 能理解“分析重庆山火”等地点型任务，并用已配置的文本模型回答未命中固定命令的开放问题。

### 已完成

- 新增地点山火分析层：识别重庆后切换到 `himawari_asia_pacific` FIRMS 区域，地图定位重庆中心，并明确当前缺少独立事件、DEM/燃料和逐时气象。
- 地点任务不再返回通用页面模板，而是给出候选火点、影像核验、环境数据、推演和规划的执行顺序。
- 未命中可靠操作规则的开放问题调用已配置的 `qwen-plus`；系统提示词禁止编造实时火点、面积、坐标、风险、气象、道路和资源结果。
- Qwen 不可用时返回结构化分析步骤，不退回旧的“请到对应页面运行”空泛模板。
- 监测页支持通过查询参数选择实时区域和任意地点中心；从其他实时区域切换到重庆时会清空旧状态并同步亚太区域。
- 对话消息来源区分“地点识别 / 数据准备计划”和“Qwen 文本智能体 / qwen-plus”。

### 主要文件

- `fire_agent_backend/app/routers/assistant.py`：地点识别、重庆分析计划和开放问答模型兜底。
- `fire_agent_backend/app/llm/providers.py`：新增正确标记为 `qwen` 的 OpenAI-compatible DashScope 文本提供者。
- `src/views/RealtimeMonitor.vue`：区域、经纬度和相机高度导航及区域切换同步。
- `src/components/AgentChat.vue`：展示回答来源。
- `fire_agent_backend/tests/test_assistant_realtime_focus.py`：重庆地点计划回归测试。

### 接口变化

- 修改：`POST /api/assistant/chat`。
- 请求字段：无变化；开放问答会将 `message` 和现有精简 `context` 发送给配置的文本模型，不发送 API Key、`.env` 或数据库内容。
- 响应字段：地点任务可返回 `navigate_query.region/focus/location/lng/lat/height`；模型回答返回 `source_mode=llm`、`provider`、`model` 和 `used_remote`。
- 错误和状态变化：模型请求失败时自动降级为 `source_mode=structured_analysis`。

### 数据库与数据变化

- 表或字段：无。
- 坐标系或空间范围：重庆定位使用 WGS84 `106.5516, 29.563`，相机高度 850 km；实时候选点使用现有亚太 FIRMS 区域。
- 数据来源与处理脚本：无新增文件；不把亚太区域候选点直接当作已确认重庆火灾。

### 配置与依赖变化

- 环境变量：复用现有 `LLM_PROVIDER=qwen`、`LLM_MODEL=qwen-plus`、`LLM_API_KEY` 和 `LLM_BASE_URL`。
- Python/npm/Docker 依赖：无新增依赖。

### 验证结果

- `[通过]` `npm run build`。
- `[通过]` Docker Python 3.12 `python -m compileall -q app`。
- `[通过]` “我想分析重庆山火”返回 `structured_location_plan`、亚太区域、重庆坐标和 `focus=location`。
- `[通过]` 开放问题“山火分析时最应该先确认哪些证据？”实际调用 `qwen-plus`，返回 `source_mode=llm`、`provider=qwen`。
- `[通过]` `docker compose up -d --build fire-agent-api frontend`，API healthy，前端已启动。
- `[通过]` `git diff --check`。

### 对其他模块的影响

- 依赖的上游输出：现有亚太 FIRMS 实时区域、LLM 配置和精简事件上下文。
- 提供给下游的输出：更具体的导航参数和受约束的自然语言分析。
- 高冲突公共文件：无；但 `assistant.py` 是对话路由核心文件，需要集成时检查行为顺序。

### 已知问题与下一步

- 当前只为重庆配置了经过确认的地点坐标；其他未登记地点会要求补充市县或经纬度。
- 重庆尚无完整本地事件数据，不能直接运行 Dixie 的地形、燃料和历史气象推演。
- 地点型响应目前先进入监测与数据准备，不会绕过火点人工确认和场景确认门。

### 合并提示

- 可以合并：前后端构建、容器编译、地点计划和真实 Qwen 调用通过。
- 项目负责人需要重点检查：文本模型外发字段范围、重庆地点配置，以及未来地点目录的维护方式。

## 2026-09-23｜修正美国实时火点的地图视角

- 分支：`member/heimini`
- 最新提交：未提交
- 任务目标：避免 Agent 将“美国地区实时火点”错误解析成全球视角，并为美国本土提供合适的相机范围。

### 已完成

- Agent 将实时火点意图按全球、美国本土、加州和当前支持区域分级识别，具体地区优先于通用“实时火点”。
- 新增美国本土视角：中心约为 `-98.5, 38.5`，相机高度 4,000 km。
- 普通“查看实时火点”使用当前支持区域视角；只有明确包含“全球/全世界/世界范围”才使用 18,000 km 全球视角。
- 监测页增加“美国本土”快捷按钮，并将当前支持区域默认高度由 120 km 修正为 5,200 km。

### 主要文件

- `fire_agent_backend/app/routers/assistant.py`：地区意图分级和 `focus=usa` 导航结果。
- `src/views/RealtimeMonitor.vue`：美国视角类型、按钮和相机预设。
- `fire_agent_backend/tests/test_assistant_realtime_focus.py`：美国、当前区域和全球意图回归测试。
- `docs/dev-logs/heimini.md`：记录接口与验证结果。

### 接口变化

- 修改：`POST /api/assistant/chat` 的实时火点导航行为。
- 请求字段：无变化。
- 响应字段：`data.navigate_query.focus` 新增 `usa`；通用实时火点由 `global` 改为 `region`。
- 错误和状态变化：无。

### 数据库与数据变化

- 表或字段：无。
- 坐标系或空间范围：新增美国本土相机中心 `[-98.5, 38.5]`，仅用于地图导航。
- 数据来源与处理脚本：无；火点数据仍以页面所选 FIRMS 支持区域为准。

### 配置与依赖变化

- 环境变量：无。
- Python/npm/Docker 依赖：无。

### 验证结果

- `[通过]` `npm run build`。
- `[通过]` Docker Python 3.12 `python -m compileall -q app`。
- `[通过]` Docker 内联回归断言：美国原句返回 `usa`，普通实时火点返回 `region`，明确全球返回 `global`。
- `[通过]` 实际调用 `POST /api/assistant/chat`，原句“我想获得现在美国地区的实时火点”返回 `mode=realtime&focus=usa`。
- `[通过]` `docker compose up -d --build fire-agent-api frontend`，API healthy，前端已启动。
- `[未通过]` 本机 Python 3.7 编译和 unittest；该环境缺少 FastAPI，且不支持仓库已有 Python 3.8+ 海象运算符，已改用项目 Docker Python 3.12 完成验证。

### 对其他模块的影响

- 依赖的上游输出：现有 FIRMS 实时火点同步结果。
- 提供给下游的输出：Agent 导航新增 `focus=usa`。
- 高冲突公共文件：无；`assistant.py` 和 `RealtimeMonitor.vue` 为本次直接修改文件。

### 已知问题与下一步

- 美国本土视角不表示已经下载全美所有 FIRMS 数据，实际覆盖仍由当前支持区域决定。
- 当前支持区域为美国西部及北美西部；接入全美 FIRMS 分区后可按区域自动选择更精确的边界。

### 合并提示

- 可以合并：前后端构建、容器编译和 Agent 实际请求均通过。
- 项目负责人需要重点检查：依赖 `focus` 查询参数的其他入口是否接受新增的 `usa` 值。

## 2026-09-23｜放大并支持折叠右侧智能体栏

- 分支：`member/heimini`
- 最新提交：未提交
- 任务目标：提高右侧业务/对话栏的可读性，并允许桌面端收起后释放主工作区空间。

### 已完成

- 桌面右栏宽度由 280-330 px 提高到 360-440 px。
- 增大对话标题、消息正文、来源、任务进度、快捷入口、影像导入表单、输入框和推演输出字体与间距。
- 右栏顶部新增收起/展开按钮；收起后仅保留 42 px 控制条，主页面自动扩展。
- 移动端继续使用原有侧滑抽屉，桌面折叠状态不会改变移动端的两列布局。

### 主要文件

- `src/App.vue`：右栏宽度、折叠状态、桌面与移动端响应式布局。
- `src/components/AgentChat.vue`：对话内容、任务状态、表单和输入区字号与间距。
- `src/components/SimulationOutput.vue`：推演结果卡的字号与信息密度。
- `docs/dev-logs/heimini.md`：记录实现与验证。

### 接口变化

- 新增/修改/无：无。
- 请求字段：无。
- 响应字段：无。
- 错误和状态变化：无。

### 数据库与数据变化

- 表或字段：无。
- 坐标系或空间范围：无。
- 数据来源与处理脚本：无。

### 配置与依赖变化

- 环境变量：无。
- Python/npm/Docker 依赖：无。

### 验证结果

- `[通过]` `npm run build`。
- `[通过]` `git diff --check`。
- `[通过]` `docker compose up -d --build frontend`，前端容器启动，PostGIS 与 fire-agent-api healthy。

### 对其他模块的影响

- 依赖的上游输出：无。
- 提供给下游的输出：所有五个页面共享更宽且可折叠的右侧栏。
- 高冲突公共文件：`src/App.vue`。

### 已知问题与下一步

- 折叠状态当前不跨浏览器刷新持久化，刷新后默认展开。
- 本机无头浏览器截图链路不可用，未完成像素级截图验收。

### 合并提示

- 可以合并：前端构建和容器重建通过。
- 项目负责人需要重点检查：桌面 100% 缩放下主工作区与 360-440 px 右栏的空间平衡。

## 2026-09-23｜放大监测页风场并隔离稀疏气象降级

- 分支：`member/heimini`
- 最新提交：未提交
- 任务目标：放大监测页历史回放风场，并在空间气象采样不足时为各网格点生成稳定的随机局地风向，不改变推演页风场和传播计算。

### 已完成

- 监测页风场由 38 km 矩形采样改为 110 km 径向椭圆覆盖，当前视野内不再出现矩形截断边缘；箭头、位移和流动尾迹缩短到原来的约 72%。
- 当前日期的 NASA POWER 日气象记录继续提供基准风速和基准风向。
- 数据库只有起火区代表点、缺少逐网格气象观测时，各网格点在基准风向附近生成随机偏移；随机种子包含事件和日期，因此同一天刷新不会跳变，切换日期会更新局地风场。
- 推演页仍使用自己的气象输入和 `setManualWindField` 默认模式；监测页专用参数不会改变推演环境时间线或火势传播算法。

### 主要文件

- `src/views/RealtimeMonitor.vue`：启用监测页专用径向覆盖、短箭头和稀疏方向降级参数。
- `src/components/CesiumMap.vue`：增加可选的稳定随机方向、方向变化范围和实例级视觉倍率；默认值保持原有推演页行为。
- `docs/dev-logs/heimini.md`：记录实现边界和验证结果。

### 接口变化

- 新增/修改/无：无 HTTP API 变化；仅扩展前端地图组件方法的可选参数。
- 请求字段：无。
- 响应字段：无。
- 错误和状态变化：无。

### 数据库与数据变化

- 表或字段：无。
- 坐标系或空间范围：地图仍使用 EPSG:4326；监测页可视风场改为 110 km 径向椭圆覆盖。
- 数据来源与处理脚本：基准气象来自现有 `NASA_POWER_DAILY` 单点日记录；未新增或伪造数据库气象记录。

### 配置与依赖变化

- 环境变量：无。
- Python/npm/Docker 依赖：无。

### 验证结果

- `[通过]` `npm run build`。
- `[通过]` `git diff --check`。
- `[通过]` `docker compose up -d --build frontend`，前端容器已重建并启动，PostGIS 与 fire-agent-api healthy。
- `[通过]` `http://localhost:5173/realtime-monitor` 返回 HTTP 200。
- `[未执行]` 像素级截图验收；本机 Chrome/Edge 无头进程未输出截图，相关临时浏览器进程已结束。

### 对其他模块的影响

- 依赖的上游输出：历史事件日气象的 `wind_speed_m_s`、`wind_direction_deg` 和 `observed_on`。
- 提供给下游的输出：仅监测页 Cesium 风场可视化，无持久化输出。
- 高冲突公共文件：`src/components/CesiumMap.vue`；新增参数均为可选，默认行为不变。

### 已知问题与下一步

- 当前核心同源 `/api/weather/wind-field` 返回 404，尚未接入逐网格真实风场；监测页明确使用单点日气象加稳定随机局地偏移作为可视化降级。
- 接入真实逐网格 U/V 风场后，应优先使用真实矢量并关闭稀疏随机降级。

### 合并提示

- 可以合并：前端构建和容器重建通过。
- 项目负责人需要重点检查：`CesiumMap.vue` 可选参数兼容性，以及监测页随机降级不应被解释为真实逐点气象观测。

## 2026-09-18｜成员丁接入统一主线

- 分支：`member/heimini-main-integrated`
- 最新提交：本地集成提交完成后以 Git 历史为准
- 任务目标：以最新 `origin/main` 为基线，迁移成员丁 Agent、规划、资源与路径能力，并打通甲候选点、乙视觉确认、丙火势/空间分析到丁指挥决策的真实闭环。

### 已完成

- 保留 Situation、Spread、Risk、Resource、Route、Commander Agent 和 MultiAgentOrchestrator。
- 保留 Dijkstra、A*、risk-aware A*、资源分配、任务规划与执行算法。
- 新增 `IncidentContext`，Agent 仅消费 DTO，不接收跨模块 ORM 对象。
- 新增 `TrustedIgnitionAdapter`，只接受乙方当前有效且状态为 confirmed 的 `fire_confirmations`。
- 新增 `SpreadAdapter`，将可信火点和甲方小时气象转换为丙方 `SpreadRunRequest`，调用现有 raster/dynamic spread service。
- 新增 `SpatialRiskAdapter`，调用丙方现有 spatial analysis service。
- 新增统一 command workflow，持久化 candidate、visual case、confirmation、spread、spatial、decision、agent packet、recommendation 的 ID 关系。
- Resource/Route 在缺少真实输入时返回 `unavailable`，不使用 synthetic inventory 或 synthetic graph 冒充真实结果。
- 视觉复核页面的一键操作改为调用现有完整 review 接口，确保生成 confirmation。
- Command Center 改为统一工作流状态页，显示执行状态、真实 ID、指挥方案和 unavailable 原因。

### 主要文件

- `fire_agent_backend/app/integrations/`：跨成员 DTO 与可信火点、火势、空间风险适配层。
- `fire_agent_backend/app/services/command_workflow_service.py`：A→B→C→D 编排与持久化。
- `fire_agent_backend/app/routers/command_workflow.py`：统一工作流 HTTP API。
- `fire_agent_backend/app/agents/`：成员丁 Agent、编排、规划与算法兼容迁移。
- `fire_agent_backend/app/models/decision.py`：DecisionRun 增加可追溯上游 ID。
- `fire_agent_backend/app/db/spatial.py`：仅新增 nullable 字段与索引的兼容升级。
- `src/views/CommandCenter.vue`：统一工作流状态与结果页面。
- `src/views/VisualVerification.vue`：完整 review 调用。
- `src/api/modules.ts`：视觉 review 与 command workflow API 客户端。
- `fire_agent_backend/tests/test_command_workflow_integration.py`：跨成员闭环测试。

### 接口变化

- 新增：`POST /api/events/{event_id}/command-workflow`。
- 请求字段：`confirmation_id` 或 `candidate_id`、`horizon_minutes`、`threat_buffer_km`、可选 `force_provider`。
- 响应字段：workflow status、完整 identifiers、confirmed point、situation、spread、spatial risk、resource、route、command plan、recommendation、agent results、warnings。
- 新增：`GET /api/events/{event_id}/command-workflow/latest`。
- 复用：`POST /api/visual-verification/candidates/{visual_case_id}/review`。
- 错误行为：没有 confirmed fire confirmation 时拒绝进入 spread；缺资源/路网不会使整体工作流失败，而是明确返回 unavailable。

### 数据库与数据变化

- `decision_runs` 新增 nullable 字段：`source_candidate_id`、`visual_case_id`、`confirmation_id`、`spread_run_id`、`spatial_analysis_id`。
- 字段升级为 additive/backward-compatible，不删除、不清空任何现有表。
- 实际运行确认甲方数据保留：hotspots 60013、clusters 11704、daily weather 105、hourly weather 2520、realtime observations 17、realtime hotspots 6363。
- 本次端到端测试使用成员甲 GOES-18 本地演示影像并明确标记 `is_simulated=true`；真实 Qwen 调用成功，未伪造模型结果。

### 配置与依赖变化

- 未新增代码依赖，未修改 compose 配置。
- 本机 `.env` 配置 Qwen、Cesium 和 FIRMS；`.env` 保持 Git ignored，密钥未写入代码或日志。
- 本地 ignored 数据仅增量同步到独立 worktree，不纳入提交。

### 验证结果

- `[通过]` 最新 main 基线：127 passed，25 warnings（Python 3.12 Docker）。
- `[通过]` 集成后端：305 passed，25 warnings（Python 3.12 Docker）。
- `[通过]` `npm run build`。
- `[通过]` `python -m compileall fire_agent_backend/app backend/forefire_api/app`。
- `[通过]` `docker compose config --quiet`。
- `[通过]` fire-agent-api 与 frontend Docker build；ForeFire 单独构建因 USTC Docker 镜像源 EOF 未完成，但 Dixie 主链使用内置 raster tool，不依赖该服务。
- `[通过]` fire-agent-api、frontend、postgis 运行；postgis 与 fire-agent-api healthy。
- `[通过]` 甲乙丙丁关键 HTTP API；真实闭环生成并持久化完整 ID 链。
- `[部分通过]` 无头浏览器确认 realtime-monitor 与 command-center 非白屏，command-center 读取真实 ID；Windows CUA helper 故障，其余页面通过 HTTP/路由但未完成可靠截图验收。

### 对其他模块的影响

- 依赖甲：candidate、weather、realtime/catalog 和 Dixie 数据。
- 依赖乙：visual case、finding、fusion 和 confirmed fire confirmation。
- 依赖丙：spread service、raster tool、spatial analysis service。
- 提供下游：可追溯 DecisionRun、AgentPacket、RecommendationPackage 和 Command Center 状态。
- 高冲突公共文件：`src/api/modules.ts`、`fire_agent_backend/app/main.py`；修改仅注册新 API 和客户端方法。

### 已知问题与下一步

- 本机缺少清单引用的 Sentinel-2 GeoTIFF，保持 Missing；没有伪装为 Available。
- 缺少真实资源 inventory，因此 ResourceAgent 在真实主链返回 unavailable。
- 缺少有效 OSM road graph，因此 RouteAgent 在真实主链返回 unavailable。
- ForeFire 镜像构建受 Docker 镜像源 EOF 影响；Dixie raster spread 已实际运行成功。

### 合并提示

- 可以交给项目负责人审查；不得直接推送或合并 main。
- 重点检查 decision_runs 的 additive 字段、command workflow 路由、VisualVerification review 调用和 Command Center 的真实/不可用状态表达。

## 2026-09-18 - Unified wildfire command productization

- Branch: member/heimini-main-integrated. Scope: additive unified incident context, nine-stage async command workflow, deterministic scenario/resource/route planning, commander review, and three-entry product navigation.
- Main files: workflow ORM/schema/router/runtime service, scenario rule YAML files, incidentContextStore, command components, CommandCenter.vue, DisasterAssess.vue, CesiumMap.vue, AppHeader.vue, and workflowRuntime API methods.
- API: added workflow event/readiness, create/latest/detail, human verification, scenario generate/confirm, commander review, and resume endpoints under /api.
- Persistence: added workflow_runs, workflow_stage_runs, emergency_scenarios, scenario_locations, scenario_resources, scenario_resource_plans, and scenario_route_plans. Existing tables and data paths remain additive.
- Runtime validation: npm run build, Python compileall, docker compose config --quiet, API/frontend image builds, healthy PostGIS/API/frontend containers, same-origin proxy checks, legacy route checks, and Dixie end-to-end workflow.
- Dixie E2E result: data preparation 5/7 available, Sentinel/GOES explicitly Missing, human confirmation completed, spread/spatial/scenario/resource/route/commander completed, deterministic scenario rules scenario-rules-v0.2, final workflow status COMPLETED with no error.
- Scenario smoke test passed under Python 3.13 for deterministic safe locations and SCENARIO_ROUTE graph creation.
- Test limitation: pytest is not installed in the local Python environments or API image; full pytest suite was not claimable. The available unittest run passed dependency-light agent/resource/route tests but reported import errors for tests requiring uninstalled project dependencies.
- Browser visual validation limitation: the Windows CUA helper exited before a screenshot could be captured. HTTP route and bundle checks passed; no browser screenshot claim is made.
- No Git push, merge, reset, clean, volume deletion, or data deletion was performed. Local realtime demo data remains untracked and untouched.

## 2026-09-18 - Command center product semantics and Dixie Fire regression

- Branch: `member/heimini-main-integrated`
- Replaced the realtime-monitor display-only handoff sidebar with a two-column monitoring workspace so the Cesium map receives the released space.
- Reworked the command center into a compact map-centered workspace with a real fire-front timeline player. It reads the backend `fire_front_steps` only, supports pause/replay, 0.5x/1x/2x speed, and time-step selection.
- Introduced scenario rule v0.3 semantics: dynamic safe command/staging locations, deterministic exercise rescue teams, an operations approach outside the modeled fire edge, an explicitly exercise-only protected target, inventory-only resource display, and a team-to-approach scenario accessibility route.
- Normalized Commander planning input so the structured Chinese summary uses the calculated ETA and Chinese resource names rather than internal resource IDs.
- Validation: `npm run build`, `python -m compileall fire_agent_backend/app backend/forefire_api/app`, `docker compose config --quiet`, rebuilt `fire-agent-api` and `frontend`, container health checks, and a complete Dixie Fire historical workflow through the Commander review gate. Final run `wfr_70dc7bafdda74b7194` produced 7 real fire-front steps (0 to 360 minutes), completed all nine stages, and calculated the exercise team-1 to operations-approach route as 1.5917 km / 4.08 minutes / 0.2394 risk.
- Known validation limitation: browser UI automation could not start because the Windows sandbox helper returned `setup refresh had errors`; production bundle marker checks, HTTP checks, API workflow validation, and frontend logs were successful.
- No Git add, commit, or push. No volumes, data directories, compose files, or unrelated member pages were modified.

## 2026-09-18 - Command Center decision-product refinement

- Branch: member/heimini-main-integrated. Scope: product presentation and business transparency for the existing nine-stage Dixie Fire Command Center workflow.
- Main files: src/views/CommandCenter.vue, src/components/CesiumMap.vue, src/components/command/WorkflowStatusPanel.vue, and src/components/command/CommandSituationPanel.vue.
- Interaction: the left workflow state panel now distinguishes completed, executing, waiting-for-confirmation, and failed stages; stage selection still switches the lower work area without leaving the page. Fire-front playback reports the current T+ time back to the spread stage.
- Product semantics: the command page disables the map wind-vector canvas and displays current wind speed, direction, temperature, and humidity in the right-side situation panel. The page now explains real fire-front playback metrics, risk-grid weights, scenario candidate ranking, exercise inventory, route inputs/outputs, and Chinese commander advice sections.
- Data boundary: no route, inventory, target, or candidate score was reclassified as real. Candidate scores remain the existing 95 - rank x 7 internal rule (88/81/74); real OSM roads, verified inventory, surveyed slope, water reserve rate, and real target layers remain explicitly unavailable.
- API/database/config: no API request or response contract, database schema, compose file, data file, environment variable, or dependency was changed.
- Validation: npm run build; Python compileall; docker compose config --quiet; rebuilt frontend image; PostGIS and fire-agent-api healthy; command-center, realtime-monitor, and health HTTP routes returned 200; production frontend bundle contained the new T+ playback and wind-display text.
- Dixie regression: new run wfr_6ac7d5189f1e42569d completed data preparation, human fire verification, raster spread, spatial risk, scenario recommendation, resource dispatch, route planning, and commander recommendation gate. It produced 7 fire-front steps, 0.8815 km2 final area, 321.3 degree spread direction, high risk, no resource shortage, and a 1.5917 km / 4.08 minute / 0.2394-risk A* exercise route.
- Known limitation: Windows CUA browser automation remains unavailable because its helper reports setup refresh errors. HTTP, production bundle, Docker logs, and complete backend workflow checks passed; no screenshot claim is made.
- No Git add, commit, push, merge, reset, clean, database deletion, volume deletion, or data deletion was performed.

## 2026-09-18 - Command Center workflow spread rerun

- Branch: member/heimini-main-integrated. Scope: safely expose the existing member C raster fire-spread inputs inside the unified Command Center workflow.
- Added POST /api/workflow-runs/{workflow_run_id}/spread-reruns. It requires a current human-confirmed fire point and an existing workflow spread result; it never calls the public raw spread endpoint from the client.
- The rerun path uses SpreadAdapter, which still delegates to create_spread_run and the existing Dixie raster tool. It records Command Center what-if inputs as a source, clears active spatial/scenario/resource/route/decision identifiers, recalculates spatial risk and situation, and regenerates a scenario candidate.
- Old downstream results remain persisted for traceability but are detached from the active workflow and their stages are marked invalidated. A regenerated scenario must be confirmed again before the existing resource, route, and Commander stages can run.
- Updated files: app/integrations/spread.py, app/schemas/workflow.py, app/routers/workflow_runtime.py, app/services/workflow_runtime_service.py, src/api/modules.ts, src/stores/incidentContextStore.ts, and src/views/CommandCenter.vue.
- Frontend: the spread stage has environmental what-if controls, source and model-boundary labels, and continues to render only persisted fire_front_steps through the existing Cesium timeline player.
- Validation: npm run build; python -m compileall fire_agent_backend/app backend/forefire_api/app; docker compose config --quiet; rebuilt API/frontend images; healthy postgis/API/frontend; command-center and same-origin workflow API returned 200; no traceback, ERROR, or 500 in recent service logs.
- Dixie rerun validation: changed wind to 5.0 m/s at 203 degrees for workflow wfr_e593601e2dce40dd8b. New run spr_710b3f357afe4f1cbe produced seven real steps, 0.8815 km2 final area, 219.8 degree direction, a new spatial analysis spa_cd2cfc25bcdf439992, a new scenario scn_fcb2f90643694952a7, route rtp_35142a1742dd48ae8a, and Commander decision dec_9a7c4910b023428a86.
- No database schema, compose configuration, fire-spread model, raw spread API behavior, data file, Git index, commit, or remote branch was changed.


## 2026-09-22 - Five-page local redesign and 100% zoom layout

- Branch: member/heimini-main-integrated. Goal: implement monitoring, verification, simulation, planning and assessment in the local project actually serving port 5173, with a persistent right business/chat dock and compact 100% zoom layout.
- Completed: five-item header navigation; monitoring retains historical replay and real-time fire data while its satellite-image demo option moves to verification; verification combines GOES-18 target detection and candidate screening with the existing Qwen-VL review; simulation retains Command Center workflow; planning exposes route/resource tabs; assessment adds local before/after image review, manually marked impacts and evidence-linked reconstruction suggestions.
- Right dock: existing Command Center situation, BackendDrivenPage agent, Qwen verification evidence, satellite candidate detail, and assessment evidence panels switch with the persistent local conversation interface. Business state and map remain visible across the five workflows.
- Layout: reduced header, panels, typography, form controls and Command Center markers; changed Command Center grid rows to preserve a scrollable lower workspace at 100% browser zoom.
- Main files: src/App.vue, src/components/{AppHeader,AgentChat,BackendDrivenPage}.vue, src/components/command/{WorkflowStatusPanel,CommandSituationPanel}.vue, src/router/index.ts, src/views/{RealtimeMonitor,CommandCenter,VisualVerification,VerificationWorkspace,SatelliteVerification,Planning,DisasterAssess,AssessmentWorkspace}.vue, fire_agent_backend/app/{main.py,routers/assistant.py}.
- API: POST /api/assistant/chat accepts message (1-1000 characters), page and a compact client-side context (event ID/name, mode, workflow status/stage, confirmation and result IDs). Response is {ok:true,data:{message,source_mode,navigate_to?}}. Invalid request returns FastAPI 422. Endpoint does local status/navigation routing only; it does not call a third-party model or transmit event data outside the local backend.
- Database/data/config/dependencies: no changes. Existing untracked realtime demo data and other WIP preserved. No new environment variable is required.
- Validation: npm run build passed; python -m compileall -q fire_agent_backend/app passed; docker compose config --quiet passed; git diff --check passed. Local API and frontend images rebuilt; API healthy; frontend /command-center returned 200; /api/assistant/chat appears in local OpenAPI. Browser screenshot verification remains unvalidated because CUA helper exited and headless Chrome did not produce a screenshot.
- Pending: confirm visual spacing interactively at 100% in the user's browser; current assessment is an explicit manual image interpretation workflow and does not claim automatic change detection or computed loss area. The local conversation interface reports loaded state and routes to pages; open-ended model conversation is not connected.
- Integration attention: src/App.vue, src/components/AppHeader.vue, src/router/index.ts, src/views/CommandCenter.vue, and fire_agent_backend/app/main.py are high-conflict UI/backend entry points. New assistant route is local only. No Git sync, add, commit, push or upload.

## 2026-09-22 - Five workspaces separated in the local browser project

- Branch: member/heimini-main-integrated. Goal: apply the user's corrected page ownership and left navigation locally; no branch synchronization or upload.
- Completed: moved the five navigation items into a fixed left sidebar; / redirects to monitoring and legacy page routes redirect to the matching workspace. Monitoring owns historical replay, real-time hotspots and event preparation. Verification owns satellite candidate detection, professional object detection output, Qwen-VL visual result and human confirmation. Simulation uses the member/wydze style FirePredict workbench for fire spread with manual weather inputs. Planning owns scenario, resource, route and commander stages. Assessment is a single before/after image workspace.
- Main frontend files: src/App.vue, src/components/AppSidebar.vue, src/components/AppHeader.vue, src/router/index.ts, src/views/RealtimeMonitor.vue, src/views/VerificationWorkspace.vue, src/views/VisualVerification.vue, src/views/FirePredict.vue, src/views/Planning.vue, src/views/CommandCenter.vue and src/views/AssessmentWorkspace.vue.
- API: verification reuses existing /api/visual-verification/candidates/{visual_case_id}/review, which returns professional_run, professional, visual, confirmation and warnings. The local assistant /api/assistant/chat supplies navigation targets and time-window query fields; it does not call an external LLM. No new API contract was added in this final frontend pass.
- Data/database/config/dependencies: no changes in this pass. New affected-point and firefighter-position markers and water/food request fields are local UI state; they are not included in route or resource computations. Assessment imagery stays local to the browser; automatic Qwen assessment and damaged-area extraction await imagery and an API.
- Validation: npm run build, Python compileall, docker compose config --quiet and git diff --check passed. API/frontend containers rebuilt and started; API health returned 200, all five frontend routes returned 200, same-origin workflow events returned 200, and the served bundle contains left navigation and assistant labels.
- Unverified: 100% zoom visual screenshot. The Windows computer-use node kernel again failed with "setup refresh had errors"; no screenshot or pixel-level layout claim is made.
- Known gaps: automatic arbitrary-data download with a one-minute link, scheduled hourly/two-hour weather refresh, recomputation for newly clicked affected points and firefighter supplies, and Qwen disaster-area extraction are not yet implemented. UI labels describe these states explicitly rather than presenting fabricated results.
- Integration attention: shared router, App layout, CommandCenter, and visual verification workflow are high-conflict files. No Git sync, add, commit, push, or upload.

## 2026-09-22 - Monitoring wind, team routes, and timed spread output

- Branch: member/heimini-main-integrated. Goal: apply the user's six UI corrections locally in the project served at localhost:5173. No branch sync or upload.
- Frontend: monitoring now uses CesiumMap wind particles instead of diagonal CSS stripes and adds flowing trails at close zoom; navigation is 72 px wide without top/bottom captions; header title is 星火智援. Verification disables rerunning a confirmed/rejected visual case and explains HTTP 409. Planning was replaced by firefighter starts and task targets with map picking, generated teams, mismatch/reserve warnings, route cards and water/food request fields. Assistant chat has a persistent spread-output card with status, area, direction and fireline extent. Simulation has an independent 1-24 hour horizon selector.
- Backend: POST /api/planning/preview accepts event_id, teams[], targets[] and optional fire_center, each point with longitude and latitude. It returns source_mode=simulated, synthetic grid network label, A* plan routes, unassigned target indexes, reserve team indexes and limitations. This endpoint uses the existing routing calculation unit; it does not claim real roads. Assistant POST /api/assistant/chat may now return action={type:run_spread,horizon_minutes}; phrases such as four hours later and explicit start map to 240 minutes. Existing workflow rerun endpoint executes the model asynchronously.
- Resource rules: new exercise scenarios omit UAV from all size templates; RESOURCE_RULE_VERSION changed to v0.4. Existing persisted scenarios are unchanged; the planning UI also filters out old UAV inventory entries.
- Database/data/config/dependencies: no table, data-file, environment variable, dependency or Compose changes. The new preview endpoint does not persist plans. Selected points and supply requests are local UI state.
- Validation: npm run build, Python compileall, docker compose config --quiet, git diff --check passed. Python 3.12 container ran 27 routing/planning tests successfully. A simulated 2-team/3-target API request returned two calculated routes and unassigned target index 2. Local assistant parser returned a 240-minute action for both '开始推演Dixie Fire' and '帮我预测四个小时之后火势会蔓延到哪里'. The current Dixie visual candidate was confirmed by read-only API check, matching the reported 409. API/frontend containers were rebuilt and healthy; all five frontend paths responded 200.
- Limitation: hourly/two-hour weather checks are UI settings; the current spread rerun uses one weather input across the selected horizon. Automatic hour-by-hour weather replacement is not implemented. The preview route is an exercise grid, not verified road navigation; water and food entries are requests rather than calculated delivery. 100% zoom screenshot validation remains unavailable because the Windows UI automation helper exits with setup refresh errors.
- Integration attention: AppHeader, AppSidebar, RealtimeMonitor, FirePredict, CesiumMap, Planning, AgentChat, assistant router, main router registration and scenario resource rules. No Git add, commit, push, merge, reset, clean or upload.


## 2026-09-23 - Historical imagery data agent and real assistant orchestration

- Branch: `member/heimini-main-integrated`. Scope: local-only implementation in the project served at port 5173; no branch synchronization, commit, push, upload or Git cleanup.
- Fixed simulation rerun: the Dixie page can rerun the persisted historical raster pipeline when no human-confirmed workflow exists, while a confirmed workflow uses the existing what-if rerun endpoint and manual weather fields. The assistant now parses a 1-24 hour horizon plus wind speed, wind direction, temperature and humidity and transfers those values into the actual simulation request.
- Assistant orchestration: POST `/api/assistant/chat` now returns executable actions for a full workflow, imagery acquisition, verification, spread, planning and assessment. AgentChat starts/polls persisted workflows and imagery tasks, shows actual stage IDs/status/errors, routes pages, keeps the existing human verification and scenario gates, and resumes automatic verification/assessment when downloaded imagery becomes available.
- Historical database/data agent: added the persisted `imagery_acquisition_tasks` table and `/api/data-agent/imagery` routes for California event listing/registration, catalog lookup, trusted STAC search, local reuse, Sentinel-2/Landsat five-band download, checksum and GeoTIFF validation, aligned AOI product creation, local registration/upload and task status. After 60 seconds the task status includes the selected scene or official portal URL and the real manual import directory `data/raw/imagery/import`.
- Data integrity: primary verification searches are constrained to the event and a continuous 24-hour window; missing contemporaneous scenes are returned as `no_match` rather than substituted by another date. Band requirements are B02/B03/B04/B08/B12. Real products are marked `is_simulated=false`; the existing exercise grid planner remains labelled simulated.
- Verification/assessment: real five-band products are attached to real visual cases, the existing image derivative/professional detector/Qwen review chain is reused, and the assessment page runs the existing dNBR/dNDVI raster change endpoint before calling Qwen-VL for visible-impact and reconstruction text. The model is not asked to invent damage area or loss amounts.
- Planning: reads the latest persisted fire-front result, displays and maps that perimeter, recommends 2-6 targets from real area/intensity/radius properties independently of fire-team count, accepts manual targets, and sends the current fire radius into A* exercise-grid routing. UAV is excluded; water and food remain explicit operator requests.
- Main files: `fire_agent_backend/app/models/imagery.py`, `routers/{assistant,imagery_agent,planning_preview}.py`, `services/{imagery_products,workflow_runtime_service}.py`, visual image processing, `src/components/AgentChat.vue`, `src/stores/assistantTaskStore.ts`, and `src/views/{FirePredict,Planning,VisualVerification,AssessmentWorkspace}.vue`.
- Validation passed: backend compileall; `npm run build`; `docker compose config --quiet`; `git diff --check`; API/frontend rebuild; healthy PostGIS/API/frontend; all five frontend routes returned 200. A temporary container test built a 60x60 five-band product with descriptions B4/B3/B2/B8/B12.
- API validation: exact request “执行Dixie Fire的完整历史火灾推演” returns `start_workflow` with 240 minutes and imagery acquisition. A real workflow `wfr_e52ca34b2237422594` imported FIRMS candidate `dixie_fire_2021-firms-viirs_snpp-20210714T091100Z-39.871940--121.382410`, completed data preparation and correctly paused at fire verification. The initial SQL failure was fixed by using the actual `confidence_score` column.
- Spread/planning validation: real historical raster run `spr_defcac7afdd541bd85` completed with the Copernicus DEM + ESA WorldCover landscape (`is_simulated=false`), 3 steps, 0.1375 km2 area and 0.2698 km radius. A 4-team/3-target preview returned three calculated routes and no unassigned target.
- Exception validation: an intentionally impossible two-minute 1900 comparison window returned `no_match`, all five bands missing, the Copernicus official search URL and `data/raw/imagery/import`. It did not substitute a false date.
- Not fully exercised: downloading a full real five-band satellite scene was not run to completion because it can transfer hundreds of MB; no suitable two-date local products currently exist, so the actual Qwen post-fire assessment was not invoked. The UI reports these as data requirements instead of showing fabricated output. Pixel-level browser screenshot validation remains unavailable because the Windows CUA helper fails during setup.
- High-conflict integration files changed: `fire_agent_backend/app/main.py`, `fire_agent_backend/app/db/session.py`, `src/api/modules.ts`. Review their additive router/model/API registrations during integration.


## 2026-09-23 - member/heimini release handoff

- User authorized committing and pushing the complete local five-page version to `member/heimini`.
- Added `docs/MEMBER_HEIMINI_SETUP_PROMPT.md` with exact branch clone, local `.env` configuration, Docker startup, full Dixie data package import, verification, five-page usage, assistant examples and troubleshooting.
- README now links to the handoff prompt.
- Git includes source code, schemas, SQL, manifests, download/import scripts and the small realtime demo README files. Ignored local `.env`, secrets, PostGIS volumes, downloaded imagery and about 305 MB of local raw/processed GIS data remain excluded as required by repository policy.
- The full data prompt explicitly requires the separate `xinghuo-full-data-v1` handoff package or the documented official-source download/import scripts before claiming complete Dixie historical inference.

## 2026-09-23 - Cesium verification workflow and local imagery registration

- Branch: `member/heimini`. Goal: make the verification page follow one real pipeline: candidate hotspot selection, imagery matching, object detection/Qwen-VL review, and human confirmation, with Cesium retained as the central basemap.
- Frontend: removed the disconnected simulated/visual tabs. `VisualVerification.vue` now maps every candidate on Cesium, highlights the selected point, shows imagery role and quality, creates the derivative, calls professional detection independently, preserves its result if Qwen-VL fails, and passes the actual confirmation ID to the workflow gate.
- Data bootstrap: added `POST /api/visual-verification/events/{event_id}/bootstrap-local-data`. For Dixie it validates the repository-managed candidate manifest and the actual local Sentinel-2 GeoTIFF with Rasterio, reads footprint/CRS/resolution, calculates SHA-256, verifies candidate coverage, and registers the imagery without marking it simulated.
- Verified data state: four Dixie candidates are `imagery_ready`; one usable primary Sentinel-2 asset is registered at `data://raw/sentinel2/dixie_fire_2021/gee/dixie_fire_2021_s2_rgb_during_overview.tif`; JPEG derivative `img-ca9966f4480155690c76c8409a5201b5` was generated successfully.
- Detector deployment boundary: core `compose.yaml` builds `backend/visual_detector_api` as an isolated Docker service and mounts the repository checkpoint read-only. PyTorch and Ultralytics are installed only inside the Docker image, not into the Windows Python environment or repository. `PROFESSIONAL_DETECTOR_API_URL` can still override the container URL for an externally deployed detector; missing configuration never fabricates output.
- Detector validation: `visual-detector-api` is healthy on port 8300 and loaded `best.pt`. Run `yolo_216bb5fe305b4f4d812e5a6877385f45` completed in 2795 ms with model SHA-256 `fe2bdd32dc92c06ef2006e87718b6cbec9a4537a01cff79cf445737c83ee4fd7`. At confidence 0.40, the overview derivative produced zero fire/smoke boxes and the persisted professional result was `against_fire` with confidence 0.60; this is a real zero-detection result, not a simulated fallback.
- Qwen-VL boundary: the local `.env` has no `QWEN_VL_API_KEY`, so the Qwen-VL review was not executed and must not be reported as passed.
- Public/high-conflict files: `compose.yaml`, `.env.example`, and `src/api/modules.ts`. Compose adds the isolated detector service and API health dependency; the API module adds local bootstrap and professional-detection calls.
- Validation: frontend production build passed during Docker rebuild; `docker compose config --quiet` passed; PostGIS, visual-detector-api and fire-agent-api are healthy; `/visual-verification` returns 200; backend health returns 200; candidate, asset, derivative and real YOLO detection paths were exercised. Python 3.12 compileall passed inside the API and ForeFire containers; the host Python is too old to parse existing repository walrus operators.
- No Git add, commit, push, merge, reset, clean, data deletion, or volume deletion was performed. Existing unrelated working-tree changes were preserved.

## 2026-09-23 - Verification page candidate-first workflow refinement

- Branch: `member/heimini`. Goal: make the page visibly follow the operational order requested by the user: obtain candidate hotspots first, then use candidate-centred imagery object detection, while retaining Cesium as the primary basemap.
- Page structure: the left column now reads and selects database candidates, the center is a full-height Cesium scene with all candidates, and the right business dock contains imagery selection, candidate-centred crop controls, YOLO execution, detection boxes/results, and an optional Qwen-VL fusion step.
- Interaction: professional detection and Qwen-VL review are separate actions. A failed or unconfigured Qwen-VL call no longer hides a completed YOLO result. Human confirmation remains evidence-gated and cannot be bypassed by merely selecting a point.
- Image processing: the frontend explicitly sends `source_kind=geotiff` and `crop_radius_m`; the existing backend transforms the candidate WGS84 coordinate into the raster CRS and creates a deterministic local crop before inference.
- Data finding: the installed disaster-period Sentinel RGB files are 60 m resolution. A 500 m radius crop is only 18 x 18 source pixels; run `yolo_032eff6de50c44ce97f1dde523942a61` completed but returned zero boxes. The page now reports source crop pixels and estimated metres per pixel and warns that a low-resolution zero-detection result cannot exclude a fire.
- Visual verification: a 1600 x 1000 headless Edge screenshot confirmed that the candidate list, Cesium map, workflow state and right detection panel fit without overlap. Long unselected candidate labels were removed and the selected candidate uses a short map label.
- Cesium imagery overlay: after a derivative is created, its `actual_extent_geojson` is converted to a WGS84 rectangle and loaded through `SingleTileImageryProvider`. The verification JPEG is draped on the Cesium terrain, old overlays are removed when switching candidates, and the business panel exposes visibility and opacity controls. This layer is isolated from monitoring and spread-map imagery controls.
- Overlay validation: a 1600 x 1000 automated screenshot with `auto_review=1` showed the 1.5 km candidate crop rendered on the Cesium terrain under the hotspot markers. The displayed crop was 51 x 50 source pixels at an estimated 58.8 m/px, and the low-resolution evidence warning remained visible.
- Validation: `npm run build` passed, the frontend container was rebuilt, `/visual-verification` returned 200, PostGIS/API/detector services remained healthy, and the 500 m GeoTIFF crop plus real YOLO endpoint were exercised.
- No Git add, commit, push, merge, reset, clean, data deletion, or volume deletion was performed.

## 2026-09-24 - Move verification controls to the left panel

- Branch: `member/heimini`. Goal: keep the verification workflow on the left and reserve the right business dock for concise results.
- Frontend: moved imagery selection, Cesium overlay controls, YOLO detection, Qwen-VL review, evidence details and human confirmation into the left candidate panel. The right dock now contains read-only status, evidence conclusion and next-step summary cards.
- Interface: `VisualVerification.vue` emits `confirm` actions to `VerificationWorkspace.vue`; no backend API or database schema changed. The existing Cesium `setVerificationImageOverlay` path and professional detector workflow remain unchanged.
- Validation: `npm run build`, `docker compose up -d --build frontend`, `docker compose ps` and `git diff --check` passed. Frontend container is running on `http://localhost:5173`; PostGIS, API and visual detector services are healthy.
- Known limitation: browser screenshot/pixel validation was not rerun for this layout-only change. Existing unrelated working-tree changes remain uncommitted and untouched.

## 2026-09-24 - Image-first candidate extraction flow

- Branch: `member/heimini`. Goal: do not expose candidate hotspots before the operator selects imagery and explicitly starts candidate extraction; keep the right dock dedicated to the assistant.
- Frontend: the verification page now starts with the event imagery catalog. After an image is selected, the operator runs candidate extraction; only then are imagery-linked FIRMS/manifest candidates requested, filtered by the selected asset and rendered in Cesium. Selecting one candidate unlocks candidate-centred cropping, Docker YOLO detection, optional Qwen-VL review and the existing human decision gate.
- Right dock: `/visual-verification` forces the assistant tab and hides the business-tab option. All verification controls and evidence stay in the left workflow rail; Cesium remains the center workspace.
- API use: added the frontend client for existing `GET /api/visual-verification/events/{event_id}/imagery-catalog`. No backend API, database schema, environment variable or dependency changed.
- Data boundary: the first extraction step exposes only candidates linked to the selected registered image and preserves their FIRMS/manifest provenance. It does not claim that an RGB-only image independently proves fire. YOLO/Qwen-VL and human confirmation remain separate downstream evidence stages.
- Validation: `npm run build`, frontend Docker rebuild, imagery-catalog API request, frontend route HTTP 200, service health checks and `git diff --check` passed. Browser screenshot validation was not rerun.

## 2026-09-24 - Discover all installed Dixie imagery

- Branch: `member/heimini`. Goal: expose the many GeoTIFF files already installed under `data/raw/sentinel2/dixie_fire_2021` instead of showing only the single previously cataloged overview.
- Backend: added `POST /api/visual-verification/events/{event_id}/discover-local-imagery`. It scans event GeoTIFFs, reads CRS, WGS84 footprint, resolution and band descriptions with Rasterio, classifies pre/during/post imagery from the managed filenames, registers new catalog rows and links spatially covering assets to visual cases. Files remain in `data/`; no imagery is copied into Git or the database.
- Frontend: the verification selector invokes discovery before reading the catalog, shows total and during-fire counts, sorts during-fire imagery first, and allows fire verification only with the during-fire group. Pre/post imagery remains visible but disabled because it belongs to temporal comparison rather than contemporaneous fire confirmation.
- Data result: 31 installed Dixie GeoTIFFs were discovered and cataloged: 17 pre-fire, 7 during-fire and 7 post-fire. The scan added 30 missing catalog records and 28 spatial case links; the existing during overview was reused. The `r01c01` during tile correctly links to all four current candidates.
- Validation: frontend build passed; API/Frontend images rebuilt; Python 3.12 container compileall passed; discovery endpoint returned `discovered=31`, `registered=30`, `linked=28`; services are healthy; `git diff --check` passed. Host compileall still reports syntax errors in pre-existing walrus-expression files because the host `python` is older than the repository requirement.

## 2026-09-24 - Compact imagery selector

- Branch: `member/heimini`. Goal: prevent the full 31-item imagery catalog from occupying the top of the verification workflow.
- Frontend: replaced the expanded radio list with one compact select containing the seven during-fire verification images. The selected image shows a small metadata block, while pre/during/post inventory is summarized as three counts. Pre/post files remain cataloged for temporal assessment but are not expanded in the fire-confirmation control.
- API/database/config: no changes in this refinement.
- Validation: `npm run build`, frontend Docker rebuild and `git diff --check` passed.

## 2026-09-24 - Overlay selected catalog imagery on Cesium

- Branch: `member/heimini`. Goal: immediately display the image selected in the verification selector instead of waiting for a candidate-centred derivative.
- Backend: added `GET /api/visual-verification/imagery-catalog/{asset_id}/preview`. It resolves the catalog GeoTIFF inside the controlled data root, creates and caches a maximum-1600-pixel RGB JPEG with percentile stretching, and returns it as browser-renderable imagery.
- Frontend: selecting an image now loads that preview through the existing Cesium verification overlay with the catalog WGS84 footprint, opacity and automatic camera framing. Changing imagery clears candidates and evidence from the previous selection. After candidate detection, the candidate-centred derivative replaces the full-scene layer; the selected catalog asset is also preferred for the derivative and YOLO request.
- Data/API impact: one additive preview endpoint; no database, environment variable or dependency changes.
- Validation: frontend build, Python 3.12 container compileall, preview HTTP/image validation, Docker rebuild and `git diff --check` passed.

## 2026-09-24 - Remove fixed candidates from the verification entry path

- Branch: `member/heimini`. Goal: ensure the verification page never preloads FIRMS/manifest points and creates candidates only from the operator-selected GeoTIFF.
- Backend: `POST /api/visual-verification/imagery-catalog/{asset_id}/extract-candidates` runs the Docker YOLO detector on the selected full-scene preview, converts each detection-box center through the source raster transform to EPSG:4326, and persists IDs under the `scene-yolo` namespace. A zero-detection run returns an empty list without historical fallback.
- Frontend: removed the automatic `bootstrap-local-data` call and its client method. Page initialization now discovers and lists imagery only; candidate state remains empty until the operator explicitly runs extraction. Switching imagery clears all candidates and evidence from the previous run.
- Runtime validation: the Dixie during-fire overview returned one model detection and one calculated candidate at `-120.504774, 40.664560`; its source ID uses `dixie_fire_2021-scene-yolo-*`. No fixed candidate API is called by the verification page.
- Data/config: no schema, environment variable, dependency, secret or raw imagery changes. Historical candidate records may remain in PostGIS for other workflows, but this page neither reads nor displays them.

## 2026-09-24 - Remove verification page header strip

- Branch: `member/heimini`. Removed the verification title/workflow banner and the four-stage status strip so the image workflow and Cesium workspace begin at the top of the available page area.
- Scope: frontend layout only. Candidate extraction, detection, Qwen-VL review and human confirmation behavior are unchanged.

## 2026-09-24 - Use FIRMS Area API for verification candidates

- Branch: `member/heimini`. Goal: use FIRMS thermal anomalies as the first-stage candidates, then keep imagery target detection, Qwen-VL review and human confirmation as separate downstream evidence stages.
- Backend: added `fetch_firms_area_hotspots` to query the NASA FIRMS Area API by the selected GeoTIFF WGS84 footprint and date range. Historical imagery uses `VIIRS_SNPP_SP`; recent imagery uses `VIIRS_SNPP_NRT`. Requests are split into at most five-day chunks, retried on transient HTTP failures and never expose the configured MAP KEY.
- Candidate selection: `POST /api/visual-verification/imagery-catalog/{asset_id}/extract-candidates` now uses FIRMS instead of scene-level YOLO. It keeps only observations inside the actual footprint, selects the highest-confidence/FRP real observation per approximately 1 km grid cell and returns at most 100 operational candidates. Every candidate retains NASA FIRMS ownership, product, source record, observation time, confidence, FRP, satellite/instrument and selected-image linkage. Historical observations are marked as replay data, not simulated data.
- Frontend: the action is now labelled `从 FIRMS 获取候选火点`; the page states that FIRMS points are unconfirmed thermal-anomaly candidates and displays both the API observation count and representative candidate count. YOLO remains the next confirmation stage and no longer creates the initial candidates.
- Runtime validation: the selected Dixie during-fire overview queried `2021-07-13..2021-07-21`, received 5,208 FIRMS observations inside the footprint and returned 100 representative candidates. The first candidate ID followed the FIRMS convention and linked to the selected GeoTIFF. A 1.5 km crop was generated as `img-3fc40e5680de021d5eea74e24a82761d`, and Docker YOLO completed successfully with zero boxes and confidence 0.60; the zero result was preserved rather than promoted to a confirmed fire.
- Configuration/data: reuses the existing local-only `FIRMS_MAP_KEY`; no key, raw API payload, dependency or database schema was added to Git. FIRMS provenance remains explicit and is not presented as a proprietary image algorithm.

## 2026-09-24 - Match FIRMS candidates to imagery acquisition time

- Branch: `member/heimini`. Refined candidate acquisition so FIRMS is queried by the selected image acquisition date instead of the image catalog's broad search/composite interval.
- Local imagery discovery now records `metadata_json.acquired_at`; the installed Dixie during-fire imagery uses `2021-07-18T18:49:21Z`. If another asset has no explicit acquisition timestamp, the backend uses the midpoint of its catalog time interval and reports that resolved time.
- Candidate extraction queries only the acquisition date and retains FIRMS observations within plus/minus 12 hours of the image timestamp before spatial grouping. The API response and UI expose the image time, same-date observation count and time-matched count.
- Runtime validation: the overview resolved to `2021-07-18T18:49:21Z`; FIRMS was queried only for `2021-07-18`, returned 247 observations within the time/footprint filter and produced 61 representative candidates. The first ranked candidate was observed at `2021-07-18T20:59:00Z`.

## 2026-09-24 - Restore the historical monitor map context

- Branch: `member/heimini`. Goal: keep the Dixie historical wind field in the California research area after returning from realtime monitoring, and remove the misleading high-risk hotspot presentation from historical replay.
- Frontend: preserved a dedicated Dixie historical center and restore it whenever the user switches back from realtime monitoring. The historical camera and manually generated weather wind field therefore no longer inherit the previous realtime region center.
- FIRMS display: historical and realtime FIRMS points retain their existing red marker style. The monitor page suppresses the generic fixed `高危火点` text labels that were misleadingly attached to the currently displayed observations; other pages keep the shared renderer's default behavior.
- API/database/config: no changes.
- Validation: `npm run build`, `docker compose config --quiet`, `docker compose up -d --build frontend` and `git diff --check` passed. The rebuilt monitoring route and API health endpoint both returned HTTP 200; PostGIS, API and visual detector remained healthy.

## 2026-09-24 - Batch target-detection validation for FIRMS candidates

- Branch: `member/heimini`. Tested the first 20 ranked, acquisition-time-matched FIRMS candidates through the real candidate-centred GeoTIFF crop and Docker Ultralytics service.
- Detection settings: 3 km crop radius, 1280 model input and 0.25 confidence threshold. Every crop contained approximately `101 x 101` source pixels because the installed RGB imagery is about 60 m/px.
- Result: 20/20 detector calls succeeded; five candidates produced smoke boxes and 15 produced zero boxes. Positive coordinates/confidences were `(-121.33199, 39.92911) 0.560066`, `(-121.31885, 39.93119) 0.392349/0.256310`, `(-121.33850, 40.01313) 0.332642`, `(-121.32596, 39.92323) 0.286022`, and `(-121.34749, 39.99463) 0.284077`.
- Decision boundary: positive detections are stored as `supports_fire`, not human-confirmed fire. The low-resolution imagery, low-to-moderate confidence and edge-adjacent boxes require Qwen-VL and operator review. `QWEN_VL_API_KEY` is currently not configured, so that second review was not executed.
- Security: reduced `httpx`/`httpcore` logging to warning because FIRMS credentials are embedded in request URLs. API keys remain local-only and must not be emitted in service logs.

## 2026-09-24 - Require explicit fire-spread simulation start

- Branch: `member/heimini`. Goal: make the fire-spread page wait for an explicit operator command instead of appearing to run immediately on entry.
- Frontend: `FirePredict.vue` now opens with the fireline layer disabled and an input-review prompt. It no longer automatically consumes a queued assistant simulation task. The operator must click the primary start button; queued assistant parameters are applied only after that confirmation. Existing persisted firelines remain available through the explicit `火线` layer control.
- API/database/config: no changes. Existing spread-run and historical replay endpoints are unchanged.
- Validation: `npm run build`, Docker frontend rebuild and `git diff --check` passed. A 1600x1000 headless Chrome check confirmed the fireline control is inactive on entry, the explicit-start prompt and button render correctly, no spread/workflow POST request is sent on page load, and the map contains no pre-rendered fire perimeter.

## 2026-09-24 - Preserve imagery when object detection times out

- Branch: `member/heimini`. Goal: stop reporting successful GeoTIFF reads and candidate crops as imagery failures when the downstream CPU YOLO request exceeds the reverse-proxy timeout.
- Diagnosis: all 31 local GeoTIFFs are present; the imagery catalog, all seven during-fire previews, FIRMS extraction, candidate detail and derivative creation returned HTTP 200. The failing request was `POST /professional-detections`, which reached the Nginx 60-second upstream timeout and returned HTTP 504.
- Frontend: the derivative is now stored and overlaid immediately after a successful crop. A later detector failure reports that the imagery succeeded and only YOLO failed, preserves the local image, and allows a retry.
- Configuration: raised the professional detector timeout default to 180 seconds and the frontend reverse-proxy API read/send timeout to 210 seconds. Added `PROFESSIONAL_DETECTOR_TIMEOUT_SECONDS` to Compose and environment examples.
- API/database/data: no endpoint or schema changes; no imagery files changed.
- Validation: `npm run build`, `docker compose config --quiet` and `git diff --check` passed. Docker Desktop was restarted and `visual-detector-api`, `fire-agent-api` and `frontend` were rebuilt; all dependent services became healthy. The running API reports a 180-second detector timeout and Nginx reports 210-second proxy read/send timeouts. A real Dixie candidate completed derivative creation and `POST /professional-detections` through `http://localhost:5173` in 3.11 seconds with HTTP success and one detection, without the previous 504. Host Python import validation could not run because the installed Python 3.7 does not support the repository's `typing.Literal` usage.
- High-conflict files: `compose.yaml` and `.env.example`. The additive timeout setting keeps the existing detector URL and service topology unchanged.
## 2026-09-24 - Redesign the end-to-end incident workflow

- Branch: `member/heimini`. Goal: make the operational sequence explicit: select incident imagery, query time-matched FIRMS candidates, run target detection and Qwen-VL review, require human confirmation, control spread weather, plan from the latest fireline, assess pre/post imagery, then generate the full report.
- Workflow runtime: removed automatic candidate import from workflow startup. A new run now waits at `fire_verification.imagery_selection`; the verification page reports `imagery_selection`, `firms_candidates`, `target_detection`, `qwen_review`, and `human_confirmation` through the additive `POST /api/workflow-runs/{workflow_run_id}/verification-progress` endpoint.
- Human gates: confirming a fire point no longer launches every downstream stage immediately. The run pauses at spread configuration so the operator can inspect or change weather and duration. Existing scenario confirmation and commander approval gates remain unchanged.
- Spread control: the existing workflow spread-rerun endpoint now also accepts the first weather-controlled run after human confirmation. Later calls remain weather reruns. The existing rolling forecast path in `FirePredict.vue` continues from the latest final fireline and is not represented as a new ignition-point run.
- Agent guidance: next-step choices now reflect the verification substage, ask whether to start the initial spread after confirmation, and keep planning behind the generated fireline/scenario gate. A new `resume_workflow` frontend action starts the database-weather initial analysis when selected.
- Post-fire closure: successful change detection and Qwen-VL assessment publish an event-scoped assessment state containing the analysis ID, extracted area, method, and model. The Agent does not offer the full report before that state exists; after assessment it unlocks a report action. `report_service.py` now reads the latest successful real burned-area analysis and includes the extracted area, Qwen visible-impact summary, limitations, and reconstruction advice in a comprehensive incident report.
- API/config/data: one additive workflow API and request schema; no database migration, environment variable, secret, Docker dependency, or raw imagery change. Existing public workflow files were modified because they own orchestration state and frontend integration.
- Validation: `npm run build`, targeted Python `py_compile`, assistant guidance `unittest` suite, `docker compose config --quiet`, and `git diff --check` passed. Host-wide compileall still stops in pre-existing walrus-expression files because the installed host Python is 3.7. Docker compile/tests and image rebuild were not run because Docker Desktop was not running.
- Integration notes: review `workflow_runtime_service.py`, `workflow_runtime.py`, `src/api/modules.ts`, and `incidentContextStore.ts` as shared files. Existing unrelated uncommitted changes were preserved; no Git add, commit, push, merge, reset, clean, or volume deletion was performed.
## 2026-09-24 - Persist Agent conversation history

- Branch: `member/heimini`. Goal: keep old Agent conversations available after clicking “New conversation” instead of silently discarding the current message list.
- Frontend: `src/components/AgentChat.vue` now stores up to 30 conversations in browser `localStorage` under `xinghuo-agent-conversations-v1`. A new conversation saves the previous one first; page reload restores the latest conversation; the header exposes a collapsible history list with switching and deletion. Current incident/workflow state remains shared and is not reset when switching chat records.
- Data boundary: conversation text is local browser state only and is not sent to the backend or committed to Git. Existing “Clear messages” still clears only the active conversation and records that action.
- Validation: `npm run build`, `docker compose config --quiet`, and `git diff --check` passed. `docker compose up -d --build fire-agent-api frontend` completed; PostGIS, visual detector, fire-agent-api, and frontend were healthy/running. No database volume was removed.

## 2026-09-24 - Automatic detection endpoint validation

- Branch: `member/heimini`. Re-ran the selected low-cloud Dixie Sentinel-2 asset `img_f86ee18bb6b1f2cdd1bf47729add` through FIRMS extraction and the new automatic target-detection endpoint.
- `POST /api/visual-verification/imagery-catalog/{asset_id}/extract-candidates` returned 247 time/footprint-matched observations and 61 representative candidates.
- `POST /api/visual-verification/imagery-catalog/{asset_id}/auto-detect` returned HTTP 200 with `status=detected` and `attempted_count=1`. The first candidate produced one smoke detection, `supports_fire`, confidence `0.926375`; the crop and YOLO evidence were persisted.
- The result remains a professional detector signal only. Qwen-VL review and human confirmation are still required before fire-spread simulation.
- Validation completed: frontend build, Docker backend compileall, Docker services healthy, endpoint integration test, and `git diff --check`.

## 2026-09-24 - Disable automatic verification execution

- Branch: `member/heimini`. Removed route, mount, candidate-switch, and imagery-ready triggers that automatically called the visual review pipeline.
- The verification page now only loads candidates and available imagery on entry. Target detection/Qwen review starts only from the explicit operator button.
- Validation: `npm run build` and `git diff --check` passed.

## 2026-09-24 - Hide historical replay hotspot markers

- Branch: `member/heimini`. Removed the FIRMS daily aggregate point layer from the historical replay map and removed its red-dot legend entry.
- Historical FIRMS counts and timeline data remain available; the MTBS burned-area boundary, weather, imagery and wind layers are unchanged.
- Scope: `src/views/RealtimeMonitor.vue` only; no API, database or source-data changes.

## 2026-09-24 - Add per-dataset manual upload entries

- Branch: `member/heimini`. Added an upload control to every historical data-catalog row instead of one generic upload button.
- Added `POST /api/data-agent/events/{event_id}/datasets/{dataset_id}/upload?filename=...` for raw-body uploads. Supported formats: FIRMS CSV/JSON, MTBS GeoJSON/JSON/ZIP, NASA POWER CSV/JSON, Copernicus DEM GeoTIFF, and WorldCover GeoTIFF.
- Files are limited to 350 MB, SHA-256 checksummed, and stored under `data/raw/manual_uploads/{event_id}/{dataset_id}` with status `uploaded_pending_validation`; uploads do not overwrite active production datasets.
- High-conflict/API impact: additive endpoint in `fire_agent_backend/app/routers/data_agent.py`; no database schema or environment changes.

## 2026-09-24 - Reorder monitoring modes

- Branch: `member/heimini`. Moved `实时火情监测` before `历史火灾复盘` in the monitoring-mode selector.
- Follow-up: realtime monitoring is now also the default when no `mode` query parameter is supplied. `?mode=history` still opens historical replay explicitly, while the default realtime entry immediately loads data and starts the existing polling loop.

## 2026-09-24 - Restore pre-list visual verification workspace

- Branch: `member/heimini`. Restored the image-first verification workspace that existed before the accidental regression to the 100-candidate list.
- The page again uses the staged flow: select low-cloud imagery, extract FIRMS candidates without listing them, manually start YOLO, manually run Qwen-VL, then submit human confirmation.
- Restored full-scene and candidate-crop Cesium overlays, candidate reference markers, detector evidence, Qwen conclusion, and the parent confirmation event contract.
- Validation: `npm run build` and `git diff --check` passed.

## 2026-09-24 - Fix verification imagery preview selection

- Branch: `member/heimini`. Excluded single-band STAC download assets from the verification image selector; primary imagery now requires the registered multiband `analysis_composite`, while during-fire imagery requires at least three bands.
- This prevents single-band B02/B03/B04 assets from reaching the RGB preview endpoint and returning `当前影像不足三个可视化波段`.
- Preview loading errors are now reported separately from imagery-catalog errors, so a failed overlay cannot falsely report that the catalog itself failed.
- `CesiumMap.addDemoPoint` now respects an explicitly empty label. Candidate reference points therefore render without source IDs or names, while callers that omit `label` retain the existing name fallback.

## 2026-09-24 - Restore verification map and imagery basemap

- Branch: `member/heimini`
- Goal: keep the Cesium map visible before candidate selection and restore imagery tiles.
- Completed: `VisualVerification.vue` keeps `CesiumMap` mounted at the default project center; `CesiumMap.vue` enables ArcGIS World Imagery after viewer initialization; added a non-blocking map hint.
- Files: `src/components/CesiumMap.vue`, `src/views/VisualVerification.vue`.
- API/data/config: none.
- Verification: `npm run build` passed; `git diff --check` passed with existing line-ending warnings.
- Known issue: imagery tiles require browser network access; Cesium still renders the globe if ArcGIS is unavailable.

## 2026-09-24 - Move visual verification workflow to right panel

- Branch: `member/heimini`
- Goal: expose the complete ordered workflow in the right business panel.
- Completed: moved imagery selection, FIRMS extraction, YOLO detection, Qwen-VL review, and manual confirmation controls into ordered step cards; locked later actions until prerequisites complete; retained map and evidence results.
- Files: `src/views/VisualVerification.vue`.
- API/data/config: none.
- Verification: `npm run build` passed; `git diff --check` passed with existing line-ending warnings.

## 2026-09-24 - Keep Qwen and manual review in the verification workflow

- Branch: `member/heimini`. Goal: remove the unnecessary local-crop display controls and make the remaining review actions visible on the verification page.
- Frontend: removed the local-image checkbox, opacity slider, candidate-crop map overlay, image preview card, and hidden `business-panel` teleport from `VisualVerification.vue`.
- Workflow: target detection details, explicit Qwen-VL review, its conclusion, and final human confirmation now render as consecutive steps 3-5 in the left workflow panel. Qwen review remains manual and is never started automatically.
- Map: the selected full-scene imagery remains overlaid after target detection; all candidate markers now use empty labels.
- API/data/config: no changes.

## 2026-09-24 - Implement visual-verification manual actions

- Branch: `member/heimini`. Goal: make all three human-review buttons perform their stated operations instead of emitting no-op events.
- Confirm fire point: the verification page now creates a workflow when needed, submits the reviewed confirmation ID to the human-verification gate, verifies that the trusted point was written to workflow state, and then opens the fire-spread workspace. No spread calculation starts automatically.
- Supplement imagery: the button opens a GeoTIFF upload form inside `选择核验影像`. Successful uploads use the existing imagery-agent upload API, are registered in the imagery catalog, selected immediately, and remain available in the image selector. Uploaded multiband `local_geotiff` assets are now eligible verification imagery.
- Exclude candidate: added `DELETE /api/visual-verification/candidates/{visual_case_id}`. It marks the candidate rejected upstream, invalidates any current automatic confirmation, retains audit evidence, removes the point from the active UI, and filters it from later extraction results for the same image.
- Main files: `src/views/VisualVerification.vue`, `src/views/VerificationWorkspace.vue`, `src/api/modules.ts`, and `fire_agent_backend/app/visual_verification/router.py`.
- API/config/data: one additive DELETE endpoint; no database migration, environment variable, dependency, or Docker configuration change. `src/api/modules.ts` is a high-conflict shared file and needs integration review.
- Validation: `npm run build`, Python `py_compile`, scoped `git diff --check`, Docker rebuild, container health checks, OpenAPI route inspection, a non-mutating unknown-candidate DELETE check returning 404, and deployed frontend bundle inspection passed. A real human-confirm click and a large GeoTIFF upload were not executed automatically because both would change operator data/state.

## 2026-09-24 - Adjust verification imagery camera framing

- Branch: `member/heimini`. Replaced the fixed 30 km camera height used after selecting verification imagery with a footprint-based height.
- The camera now keeps at least 90 km altitude, scales with the larger footprint dimension, and caps at 500 km so the selected scene remains visible without excessive zoom.
- Scope: `src/views/VisualVerification.vue`; no API, data, or configuration changes.
- Follow-up: tuned the camera to a 150 km minimum height and 2.4 footprint multiplier after testing showed that 90 km was too close and 250 km was too far.
- Final framing: replaced manual height calculations with Cesium rectangle fitting. The map now frames the selected imagery footprint with 4% geographic padding based on the actual viewport.

## 2026-09-24 - Align monitoring data-directory count

- Branch: `member/heimini`. Changed the monitoring catalog heading from the seven backend manifest rows to the five visible upload categories.
- The backend still contains seven physical manifests: NASA POWER daily and hourly are separate, and the ForeFire input manifest is an additional internal product. The UI combines both weather manifests into one category and does not expose ForeFire as an upload row.
- Scope: `src/views/RealtimeMonitor.vue`; no API or data changes.

## 2026-09-24 - Version repeated visual-verification rounds

- Branch: `member/heimini`. Goal: allow the same persisted FIRMS candidate to be verified again without mutating or deleting its previous human-confirmed record.
- Backend: added `create_reverification_version` to clone the latest candidate identity and registered imagery into the next `visual-case-...-vN` record with a fresh `imagery_ready` state and parent-version metadata.
- Workflow behavior: a normal page refresh continues to expose the persisted latest version. When the operator explicitly clicks `使用目标检测` on a confirmed or rejected candidate, the auto-detection endpoint creates a new version before producing derivatives and YOLO evidence. Qwen therefore analyzes the new version instead of attempting the invalid `confirmed -> analyzing` transition.
- Audit/data: prior cases, Qwen evidence, confirmations, and human decisions remain unchanged. No database schema migration is required because the existing case version column and uniqueness constraint are reused.
- Tests: added a candidate-service test covering version increment, fresh state, parent metadata, and asset-copy behavior.
- Frontend follow-up: after auto-detection creates a new case version, the map candidate entry is replaced with that version and matched by stable source candidate ID. The detected point now changes from orange to red and grows from 10 px to 16 px; this also keeps later exclusion aligned with the new case ID.

## 2026-09-24 - Hide persisted spread results until explicit start

- Branch: `member/heimini`. Goal: make the fire-spread workspace open as an input-review screen instead of immediately displaying the latest persisted historical calibration and fireline timeline.
- Frontend: `FirePredict.vue` clears its local spread presentation on entry and no longer requests the latest spread run during mount or confirmation restoration.
- Display gate: historical comparison, calibration metrics, fireline timeline, playback, and mapped fire fronts remain hidden until the operator explicitly clicks the start command in the current page session. Workflow spread updates are ignored for presentation before that action.
- Explicit start: the first Dixie historical run is submitted only after the operator clicks the start button; fixed an early-return branch that previously prevented that click from starting the run.
- The verified ignition point remains available, so coordinates and the start button still use the confirmed point. No backend run or database result is deleted.
- API/data/config: no changes.
- Verification: `npm run build`, scoped `git diff --check`, frontend container rebuild, service health check, and `GET /fire-predict` HTTP 200 passed.

## 2026-09-24 - Add restart and fireline continuation modes

- Branch: `member/heimini`. Goal: after one completed spread run, let the operator choose whether new weather starts again from the confirmed high-risk fire point or continues from the previous final fireline.
- Frontend: the single run command becomes two explicit actions after results exist: `从确认火点重新推演` and `从最终火线继续推演`.
- Restart behavior: submits the edited weather and forecast duration without a parent run, so the backend initializes the new run from the persisted trusted ignition point.
- Continuation behavior: submits the current run ID as `continue_from_run_id`, so the backend uses its final Fire Front as the next initial boundary.
- Both paths use the current temperature, humidity, wind speed/direction, precipitation, fuel moisture, FWI, and prediction duration. Continuation is no longer incorrectly limited by the weather-check interval or blocked until playback finishes.
- API/data/config: no new endpoint, schema, migration, dependency, or environment variable. Reuses the existing spread creation API and `continue_from_run_id` contract.
- Verification: `npm run build` and scoped `git diff --check` passed.

## 2026-09-24 - Focus the spread map on the confirmed fire point

- Branch: `member/heimini`. Goal: open the fire-spread workspace at the operator-confirmed ignition location instead of the default regional camera position.
- Frontend: after the confirmed point is restored, the Cesium camera flies to its longitude and latitude at a 30 km viewing height. The same behavior runs when confirmation data arrives after the page has mounted.
- The map focus does not start a spread run or load persisted fireline results.
- API/data/config: no changes.
- Verification: `npm run build` and scoped `git diff --check` passed.

## 2026-09-24 - Restore local Dixie raster inputs

- Branch: `member/heimini`. Goal: resolve `historical_raster_spread_failed` caused by missing local DEM and land-cover GeoTIFFs.
- Root cause: the required rasters existed in the sibling `fire-command-system` checkout, while the running `fire-command-system-heimini` Docker stack bind-mounts only its own `./data` directory.
- Local data: copied the Copernicus DEM and ESA WorldCover rasters into `data/processed/dem/` and `data/processed/fuel/` in the active checkout. These large runtime files remain excluded from Git.
- Validation: both files open inside `fire-agent-api` with Rasterio as EPSG:32610, 30 m, 4740 x 4525, and matching bounds. A real one-hour historical raster run completed with `raster_agent_tool`, three fireline steps, and run ID `spr_cedcf0b8589146a4ab`.
- API/schema/config: no changes.

## 2026-09-24 - Preserve visual-verification results across navigation

- Branch: `member/heimini`. Goal: keep a completed verification visible when the operator leaves for spread prediction and later returns to the verification workspace.
- Frontend: stores the selected imagery, FIRMS extraction summary and candidates, selected YOLO case, detector result, Qwen result, errors, manual message, and human-confirmed state in session storage keyed by event.
- Restore behavior: opening the verification page restores the saved imagery and all workflow steps, redraws candidate markers, and reloads the same imagery overlay.
- Reset behavior: state is cleared only when the operator actually selects a different imagery asset or explicitly performs another destructive workflow action such as excluding the candidate.
- Human confirmation: the state is synchronously persisted before navigation to spread prediction; returning shows `已确认火点` and prevents duplicate confirmation or rejection.
- API/data/config: no changes. Existing database audit records remain unchanged.
- Verification: `npm run build` and scoped `git diff --check` passed.

## 2026-09-24 - Restore spread risk-area visualization

- Branch: `member/heimini`. Goal: restore the high/medium/low danger-zone effect after fireline prediction.
- Root cause: spatial analysis still produced `risk_area` polygons, but the spread page defaulted the impact layer off, removed its toolbar control, and rendered only affected point objects.
- Frontend: risk areas are enabled by default after an explicit run, Polygon and MultiPolygon features are drawn with red/orange/blue severity styling, and labels describe both risk level and zone relation.
- Controls: restored the `风险区` map-layer button and high/medium/low legend entries.
- Workflow integration: when an asynchronous workflow publishes a new `spatial_analysis_id`, the page loads the latest spatial result and redraws danger zones without restarting fireline playback.
- API/data/config: no changes. Verified the current backend result contains two risk polygons (high and medium).
- Verification: `npm run build` and scoped `git diff --check` passed.


## 2026-09-24 - Block spread replay before fire-point confirmation

- Branch: `member/heimini`.
- Root cause: the Dixie-specific historical fallback could start a raster replay without a confirmed visual fire point, and the page loaded the latest spread run unconditionally.
- Frontend: `FirePredict.vue` now blocks run actions, clears stale spread/spatial state, and only loads spread results after `confirmationId` and confirmed-point coordinates are present.
- Store: `fireEventStore.ts` adds `clearSpreadState()` for removing stale replay data from the current session.
- Backend: historical spread and calibration resolve `TrustedIgnitionAdapter` first and reject requests without a current confirmed visual fire point.
- Verification: `npm run build`, `python -m compileall fire_agent_backend/app/services/historical_spread_service.py fire_agent_backend/app/integrations/trusted_ignition.py`, and `git diff --check` passed.
- Known issue: the reported DEM error is a separate data availability issue; the expected GeoTIFF is absent from the configured data directory and must be downloaded/ mounted before a confirmed run can execute.

## 2026-09-25 - Fix team-to-target route generation

- Branch: `member/heimini`.
- Root cause: randomly generated teams used a fixed 4-7 km radius, so a large simulated fire radius could place teams inside the excluded fire grid and isolate their A* start nodes.
- Frontend: teams are now generated outside the current fire radius with a 2.5 km safety buffer; existing teams and targets inside the excluded area are identified with a clear message and route generation remains disabled until corrected.
- Backend: the synthetic planning grid now includes padding based on the fire radius so A* has enough space to route around the excluded area.
- Files: `src/views/Planning.vue`, `fire_agent_backend/app/routers/planning_preview.py`, `fire_agent_backend/tests/test_planning_preview.py`.
- API: request and response contracts for `POST /api/planning/preview` are unchanged.
- Verification: `npm run build` passed; backend compile passed; rebuilt `fire-agent-api` and `frontend`; live API returned two successful routes (1.2398 km and 3.1072 km). Host `pytest` was unavailable, so the added pytest file was not run through pytest.

## 2026-09-25 - Use the actual fire perimeter for route exclusion

- Branch: `member/heimini`.
- Correction: maximum spread radius is only an enclosing metric and was incorrectly used as the forbidden area, causing points outside an irregular fireline to be rejected.
- Frontend: point validation now uses point-in-polygon against the latest fireline, and the actual perimeter is sent to `POST /api/planning/preview`.
- Backend: `fire_perimeter` is an optional request field; grid edges and point connectors crossing the polygon are excluded. The radius remains a compatibility fallback only when no perimeter geometry is supplied.
- Verification: frontend build and backend compile passed; containers rebuilt; a target inside the 8 km enclosing radius but outside the supplied irregular perimeter produced a successful 4.1306 km route with six geometry points.

## 2026-09-25 - Remove unnecessary route detours

- Branch: `member/heimini`.
- Root cause: `risk_aware_astar` multiplied every edge cost by fire-proximity risk (`risk_weight=2.5`), so it could move far away from the fire and then return even when the direct segment did not cross the perimeter. The 13 x 13 grid amplified the detour.
- Backend: unobstructed team-target pairs receive a direct synthetic edge; obstructed pairs use a denser 21 x 21 grid with distance-based A* and actual fire-perimeter exclusion.
- Frontend: route output now labels the method as `火线避障 A*`.
- Verification: unobstructed case returned a two-point 3.3904 km route; a fire-blocked case returned a successful 17-point 8.2675 km detour. Frontend and backend containers were rebuilt.

## 2026-09-25 - Assign every available team

- Branch: `member/heimini`.
- Requirement: active fire planning must not leave teams idle when reachable targets exist.
- Backend: each target first receives one primary team where capacity permits; every remaining team is then assigned to its nearest target as reinforcement. `assignment_role` is returned as `primary` or `reinforcement`.
- Frontend: removed the standby-team wording and displays each route as `主责` or `协同增援`.
- API impact: additive `assignment_role` field in each `POST /api/planning/preview` plan item; existing fields are unchanged.
- Verification: 4 teams and 2 targets returned 4 successful plans, 2 primary assignments, 2 reinforcement assignments, and zero reserve teams. Frontend and backend containers were rebuilt.
## 2026-09-25｜Move spread timing configuration into the agent

- 分支：`member/heimini`
- 最新提交：未提交
- 任务目标：从火情推理主界面移除推演时长和气象更新间隔控件，改由右侧智能体读取真实气象目录并收集参数，且不得自动启动推演。

### 已完成

- 智能体进入火情推理页后读取当前事件逐时气象，显示可用记录数、实际记录间隔和覆盖时间。
- 智能体表单收集 1-24 小时推理时长和气象更新间隔，保存为待执行任务；用户仍需点击推理页的开始按钮。
- 推理主界面删除时长预设、自定义时长、气象间隔和提醒输入。
- 历史数据库气象和人工气象时间线均实际使用用户设置的更新间隔。
- 移除引导区“一键开始首次推演”，避免智能体绕过人工点击直接运行模型。

### 主要文件

- `src/components/AgentChat.vue`：新增气象可用性摘要和推演参数表单。
- `src/views/FirePredict.vue`：删除主界面时间控件并消费智能体保存的参数。
- `src/stores/assistantTaskStore.ts`：保存气象更新间隔。
- `src/api/modules.ts`：新增逐时气象目录查询封装。
- `fire_agent_backend/app/schemas/spread.py`、`fire_agent_backend/app/schemas/workflow.py`：增加 `weather_update_interval_minutes`。
- `fire_agent_backend/app/services/historical_spread_service.py`、`fire_agent_backend/app/integrations/spread.py`：按配置间隔生成气象时间线。
- `fire_agent_backend/app/services/assistant_guidance_service.py`：调整人工门引导，禁止自动开始首次推演。

### 接口变化

- 修改：历史推演请求和工作流重推请求新增可选字段 `weather_update_interval_minutes`，默认 60，范围 1-1440 分钟。
- 读取：复用 `GET /api/data/events/{event_id}/weather-hourly`，响应中的 `total`、`interval_minutes`、`items[].observed_at` 用于智能体摘要。
- 错误和状态变化：保存智能体参数只进入 `queued`，不会提交模型；推演仍由页面按钮显式启动。

### 数据库与数据变化

- 表或字段：无。
- 坐标系或空间范围：无。
- 数据来源与处理脚本：复用 `weather_hourly_observations` 真实记录。

### 配置与依赖变化

- 环境变量：无。
- Python/npm/Docker 依赖：无。

### 验证结果

- `[通过] npm run build`
- `[通过]` Docker Python `compileall app`、智能体引导断言和新增 Schema 字段校验。
- `[通过]` `docker compose up -d --build fire-agent-api frontend`，后端健康、前端已启动。
- `[通过]` `GET /api/data/events/dixie_fire_2021/weather-hourly` 返回 2520 条、60 分钟间隔；OpenAPI 已包含新增字段。
- `[通过]` 容器内调用历史气象时间线：6 小时、120 分钟间隔得到 `[0, 120, 240, 360]` 四帧。
- `[通过] docker compose config --quiet`
- `[说明]` 主机 Python 3.7 无法编译仓库现有的 Python 3.8+ 语法，后端验证改在项目容器中执行。

### 对其他模块的影响

- 依赖的上游输出：逐时气象查询接口与人工确认火点状态。
- 提供给下游的输出：推演请求新增气象更新时间间隔。
- 高冲突公共文件：`src/api/modules.ts`，新增只读 API 方法；公共 Schema 增加向后兼容的默认字段。

### 已知问题与下一步

- 气象目录读取失败时仍允许页面保留已有默认参数，但智能体会明确显示读取失败。

### 合并提示

- 可以合并：本次修改已完成前后端构建与容器接口验证。
- 项目负责人需要重点检查：历史气象默认 60 分钟时间线和工作流重推参数兼容性。
## 2026-09-25｜Reclassify spread risk areas by fire behavior

- 分支：`member/heimini`
- 最新提交：未提交
- 任务目标：修复风险区被合并为单一整块的问题，依据火强、到达时间及环境因素生成高、中、低三级空间分区。

### 已完成

- 将固定 24 x 24 网格改为约 300 m 目标分辨率的自适应网格，避免狭长或紧凑火场只剩少量单元。
- 单元评分综合 Byram 火线强度代理、场内相对火强、预计到达紧迫度、蔓延增长、风、坡度、燃料与暴露对象。
- 火强影响随离开活动火线而衰减；外围威胁缓冲按实际缓冲宽度衰减，不再沿用整个火场半径。
- 风险面输出平均/最大火强、平均预计到达分钟、主导因素和分类方法。
- 地图每个等级只标注最大主区域，其余斑块保留颜色和边界，避免标签拥挤。

### 主要文件

- `fire_agent_backend/app/services/spatial_analysis_service.py`：三级风险网格分类与矢量分区。
- `fire_agent_backend/tests/test_spatial_risk_areas.py`：增加混合火强必须产生高、中、低三级区域的测试。
- `src/views/FirePredict.vue`：优化分区标签显示。

### 接口变化

- 新增/修改：无新增接口；空间分析 GeoJSON 的 `risk_area` 属性增加 `mean_estimated_arrival_minute` 和 `classification_method`。
- 请求字段：无变化。
- 响应字段：风险区继续使用 `risk_level=high|medium|low`，新增上述解释字段。
- 错误和状态变化：无。

### 数据库与数据变化

- 表或字段：无迁移；已用当前最新火线生成新的空间分析记录 `spa_7f92d1c8ed054acabb`。
- 坐标系或空间范围：沿用 WGS84 GeoJSON；威胁缓冲 0.55 km。
- 数据来源与处理脚本：使用当前栅格传播输出的 72 扇区火强和相邻时步火线。

### 配置与依赖变化

- 环境变量：无。
- Python/npm/Docker 依赖：无。

### 验证结果

- `[通过]` 容器内 `test_spatial_risk_areas.py`：3 个测试全部通过。
- `[通过]` 当前 `8.362 km²` 火线实算得到 1 个高风险区、1 个中风险区、4 个低风险斑块。
- `[通过]` 后端容器重建并启动。
- `[通过] npm run build`
- `[通过]` 后端修改文件容器内 `compileall`。
- `[通过] docker compose config --quiet`
- `[通过]` 前后端容器重建和健康检查。
- `[通过] git diff --check`，仅有现存 CRLF 转换提示。

### 对其他模块的影响

- 依赖的上游输出：火线扇区半径、扇区火强、相邻时步和气象/地形燃料信息。
- 提供给下游的输出：更细的三级风险面供规划、资源和报告模块使用。
- 高冲突公共文件：无新增；`src/views/FirePredict.vue` 已有本成员前序改动。

### 已知问题与下一步

- 当前火强为未校准 Byram 代理，输出继续标记为 demonstration/simulated，不作为官方火险等级。

### 合并提示

- 可以合并：三级风险区已通过合成测试和当前真实运行结果验证。
- 项目负责人需要重点检查：三级阈值 55/35 与后续历史火灾标定结果。
## 2026-09-25｜Remove duplicate current-weather panel

- 分支：`member/heimini`
- 最新提交：未提交
- 任务目标：移除推理页截图中的“本轮有效气象/当前火场实况”重复面板。

### 已完成

- 删除重复的当前风速、风向、湿度、降水输入卡片。
- 保留上方统一的气象输入区域，推演请求和智能体参数流程不变。

### 主要文件

- `src/views/FirePredict.vue`：移除 `forecast-timeline` 模板块。

### 接口变化

- 无。

### 数据库与数据变化

- 无。

### 配置与依赖变化

- 无。

### 验证结果

- `[通过] npm run build`
- `[通过]` 页面源码中不再包含“本轮有效气象/火场实况”面板。

### 对其他模块的影响

- 无；上方统一气象输入仍继续绑定 `forecastFrames[0]`。

### 已知问题与下一步

- 无。

### 合并提示

- 可以合并。
## 2026-09-25｜Restore single inference duration input

- 分支：`member/heimini`
- 最新提交：未提交
- 任务目标：恢复推理页面的单次推理时长输入，同时不恢复已删除的时长预设和重复气象面板。

### 已完成

- 在统一气象输入区新增“单次推理时间（小时）”字段，范围 1-24 小时。
- 该字段继续绑定 `forecastHours`，首次推演、重新推演和火线续推都会使用它。
- 气象更新间隔仍由右侧智能体配置。

### 主要文件

- `src/views/FirePredict.vue`：新增单次推理时长输入及全宽布局样式。

### 接口变化

- 无。

### 数据库与数据变化

- 无。

### 配置与依赖变化

- 无。

### 验证结果

- `[通过] npm run build`
- `[通过] git diff --check`，仅有现存 CRLF 转换提示。
- `[通过]` 前端容器重建并返回 `/fire-predict` HTTP 200。

### 对其他模块的影响

- 无。

### 已知问题与下一步

- 无。

### 合并提示

- 完成构建检查后可以合并。
## 2026-09-25｜Hide map labels and lower high-risk threshold

- 分支：`member/heimini`
- 最新提交：未提交
- 任务目标：地图不显示风险区和火点文字，并降低高风险区判定门槛。

### 已完成

- 关闭确认火点标签、风险区标签和受影响目标标签，只保留点符号、填充色与边界。
- 高风险综合评分阈值从 55 下调至 48；高火强特殊阈值同步下调。

### 主要文件

- `src/views/FirePredict.vue`：关闭地图业务文字标注。
- `fire_agent_backend/app/services/spatial_analysis_service.py`：调整高风险分类阈值。

### 接口变化

- 无。

### 数据库与数据变化

- 无迁移；重新生成空间分析结果。

### 配置与依赖变化

- 无。

### 验证结果

- `[通过]` 前后端容器重建，前端 `npm run build` 通过。
- `[通过]` 当前火线重新分析得到 2 个高风险区、1 个中风险区、4 个低风险区。
- `[通过]` 风险区测试 3/3 通过、`docker compose config --quiet` 通过、页面 HTTP 200。

### 对其他模块的影响

- 无接口影响。

### 已知问题与下一步

- 当前风险强度仍是未校准 Byram 代理，继续标记为演示结果。

### 合并提示

- 可以合并：文字标注已关闭，风险阈值已调整并完成当前火线核验。
## 2026-09-25 - Add Qwen route detour explanations

- Branch: `member/heimini`.
- Goal: explain why each planned team route is direct or detours, using Qwen and computed spatial evidence instead of hardcoded claims.
- Backend: added `POST /api/planning/explain-route`; it computes direct distance, route distance, detour ratio, route point count, and whether the direct segment intersects the current fire perimeter before invoking the configured Qwen text provider.
- Frontend: each successful route now has a `调用千问解释绕行` action and displays the explanation, model, direct distance, and detour ratio. When the remote model is unavailable, the result is explicitly labeled `结构化降级说明`.
- API request: event/team/target identifiers, assignment role, team and target coordinates, route result, and fire perimeter. Response: `explanation`, `provider`, `model`, `used_remote`, `source_mode`, computed `evidence`, warnings, and optional provider error.
- Data/config/dependencies: no database, coordinate reference, environment variable, dependency, or Docker configuration changes.
- High-conflict file: `src/api/modules.ts` adds only the planning API wrapper; integration should preserve other module exports.
- Verification: `npm run build`, host/backend container compile, `docker compose config --quiet`, Docker rebuild, and `git diff --check` passed. The backend image does not include pytest, so pytest was not run; equivalent evidence assertions and a live endpoint call were used.
- Live Qwen result: an 8.9204 km, 19-point route around a blocking perimeter had a 6.8274 km direct distance and 1.307 detour ratio; `provider=qwen`, `model=qwen-plus`, `used_remote=true`, and `source_mode=qwen_remote`.
- Limitation: route planning still uses a simulated grid rather than verified roads; the prompt prohibits inventing road, terrain, closure, imagery, or traffic facts.

## 2026-09-25 - Submit and persist fireline before planning

- Branch: `member/heimini`.
- Goal: require an explicit fireline handoff from inference to planning, provide explicit fireline clearing, and preserve inference state when navigating back.
- Frontend: `FirePredict.vue` now exposes submit/clear actions. Submit stores the current final fireline and navigates to `/planning`; clear removes spread, risk and route state while retaining the confirmed point and weather inputs.
- Store: `fireEventStore.ts` persists spread, spatial analysis, and submitted fireline state in session storage. The inference page no longer clears spread state unconditionally on mount.
- Planning: `Planning.vue` uses only the explicitly submitted fireline GeoJSON/run id and blocks route generation when no submitted fireline exists.
- API/data/config: no backend API, database, CRS, dependency, or Docker changes.
- Verification: `npm run build` and `git diff --check` passed. Browser click-through and real backend planning execution were not run in this turn.
- Known limitation: session storage is scoped to the current browser tab; the explicit clear action intentionally removes the submitted fireline.

## 2026-09-25 - Add imagery upload and Qwen post-fire assessment UI

- Branch: `member/heimini`.
- Goal: let the assessment page compare existing pre/post imagery or register uploaded GeoTIFFs, then run change extraction and Qwen recovery assessment by explicit user action.
- Frontend: `AssessmentWorkspace.vue` now accepts uploaded pre/post GeoTIFFs with acquisition dates and bands, registers them through the existing imagery upload endpoint, includes the repository's `pre`/`post` RGB assets in catalog selection, and exposes extracted area GeoJSON/mask artifacts plus Qwen damage and reconstruction output.
- Backend: `imagery_agent.py` adds `POST /api/data-agent/imagery/visual-assess` for RGB catalog pairs; it creates bounded JPEG previews from local GeoTIFFs and asks Qwen for visible affected-region descriptions and reconstruction advice without inventing coordinates or exact area.
- API/data/config: reused existing upload and five-band analysis contracts; added the RGB visual-assess endpoint, with no database schema change.
- Verification: `npm run build`, backend `compileall`, Docker frontend/backend rebuild, OpenAPI route check, catalog pre/post count check, and `git diff --check` passed. Real Qwen request was not run in this turn.
- Known limitation: quantitative area/GeoJSON requires five-band GeoTIFFs with `B02,B03,B04,B08,B12`; RGB mode is qualitative and requires a configured `QWEN_VL_API_KEY`.
## 2026-09-25 - Replace greedy dispatch with global routed assignment

- Branch: `member/heimini`.
- Goal: prevent upper/lower teams from crossing toward farther targets because targets were processed sequentially.
- Root cause: the previous loop assigned each target in list order using straight-line distance and permanently removed the selected team; it did not minimize the combined routed travel cost.
- Backend: computes every reachable team-target A* route first using travel-time cost and a small fire-risk weight, then uses dynamic programming to maximize target coverage and minimize total dispatch cost. Pair swaps add a 12-minute penalty for crossing straight dispatch lines.
- Reinforcements: remaining teams compare actual routed cost, a small target-load penalty, and crossing penalties; unreachable teams remain explicitly reported in `reserve_team_indices`.
- API: `POST /api/planning/preview` adds `assignment_method=global_routed_eta_with_crossing_penalty` and per-plan `dispatch_cost_minutes`; existing fields remain compatible.
- Data/config/dependencies: no changes.
- Files: `fire_agent_backend/app/routers/planning_preview.py`, `fire_agent_backend/tests/test_planning_preview.py`, `docs/dev-logs/heimini.md`.
- Verification: backend compile, Docker rebuild, `npm run build`, `docker compose config --quiet`, `git diff --check`, and all 23 built-in routing unit tests passed. A regression scenario that the old target-order greedy loop assigned poorly now returns `team 2 -> target 1` and `team 1 -> target 2`, both with `travel_time` route cost. A live four-team/two-target request returned two primary plans, two reinforcement plans, and zero reserves. The backend image still does not include pytest, so `test_planning_preview.py` was validated through equivalent container assertions rather than pytest.
- Known limitation: the underlying network is still a simulated grid; the global assignment is operationally better but is not verified-road dispatch.
## 2026-09-25 - Use available DEM in route planning

- Branch: `member/heimini`.
- Goal: use previously prepared terrain data in planning and stop drawing unobstructed routes as direct straight lines.
- Data audit: `data/processed/dem/dixie_fire_2021_copernicus_dem_30m_utm10.tif` exists (EPSG:32610, 30 m, about 59 MB). The expected OSM roads GeoJSON does not exist; repository documentation records the prior Overpass download timeout, so no real road network is claimed.
- Backend: samples DEM elevation for all planning-grid, team, and target nodes; writes elevation gain to every edge; uses the fire-engine 18% maximum slope constraint and terrain-adjusted travel time; removes direct team-target edges whenever DEM data is available.
- Response: `POST /api/planning/preview` now returns `terrain` metadata and uses `source_mode=terrain_assisted_simulated` plus `network=dem_terrain_grid_no_verified_roads` when DEM sampling succeeds.
- Qwen explanation: evidence now includes `terrain_aware` and route elevation gain/loss and slope metrics, allowing terrain-constrained detours to be distinguished from fire avoidance and grid approximation.
- Frontend: planning results explicitly show whether Copernicus DEM participated and continue warning that verified roads are unavailable.
- Configuration/dependencies: no new dependency; existing `rasterio` and `pyproj` packages are used. No database change.
- Files: `fire_agent_backend/app/routers/planning_preview.py`, `src/views/Planning.vue`, `docs/dev-logs/heimini.md`.
- Verification: Python compile, `npm run build`, `docker compose config --quiet`, `git diff --check`, backend/frontend Docker rebuild, and live API checks passed. A Dixie route sampled all 443 requested points, returned 12 route points, 51.41 m ascent, 43.28 m descent, 14.95% maximum slope, and 2.60% average slope. A missing-DEM event explicitly returned `available=false` and retained the simulated direct fallback. Live Qwen returned `used_remote=true` with `reason_code=terrain_constrained_grid_route` and `terrain_aware=true`.
- Known limitation: terrain-aware grid routing is not road navigation. OSM roads must be downloaded and validated before road-following routes can be enabled.
## 2026-09-25 - Guarantee target coverage with dismounted access fallback

- Branch: `member/heimini`.
- Root cause: hard 18% fire-engine slope constraints could disconnect a target from every team. Global assignment then covered only reachable targets and sent remaining teams as reinforcements, leaving target 1 uncovered.
- Backend: each team-target candidate first uses the fire-engine profile. If DEM terrain makes it unreachable, the planner retries with a clearly labeled `dismounted_fire_crew` profile limited to 45% slope and low walking speed. Global assignment can therefore prioritize one primary team per target before allocating reinforcements.
- API: each plan adds `access_mode=vehicle|dismounted_approach`; route metadata retains `vehicle_type` and source so fallback routes are auditable.
- Frontend: dismounted routes display `车辆坡度不可达 · 已切换消防员徒步接近`.
- Data/config/dependencies: no changes.
- Files: `fire_agent_backend/app/routers/planning_preview.py`, `src/views/Planning.vue`, `fire_agent_backend/tests/test_planning_preview.py`, `docs/dev-logs/heimini.md`.
- Verification: Python compile, `npm run build`, `docker compose config --quiet`, `git diff --check`, and backend/frontend Docker rebuild passed. A synthetic 30% slope edge correctly rejected the fire engine and returned a successful `dismounted_fire_crew` route. A live four-team/two-target DEM request returned four successful plans, primary target indices `[0, 1]`, no unassigned targets, and no reserve teams.
- Limitation: the walking approach is still based on the DEM terrain grid, not a verified trail network.
## 2026-09-25 - Remove connector-induced triangular detours

- Branch: `member/heimini`.
- Root cause: each team and target was snapped to only one nearest terrain-grid node. A point snapped on the wrong side of a steep cell or valley forced A* to travel away from the destination before returning, producing long triangular loops.
- Backend: terrain-grid resolution is now adaptive with an approximately 450 m target cell size, capped at 41 x 41. Each endpoint connects to up to six nearby fire-safe terrain nodes instead of one.
- Route guard: when a successful fire-engine route exceeds 1.65 times the direct distance, it is treated as an operationally excessive terrain detour and compared with the dismounted approach route; a valid dismounted route is selected and labeled instead of retaining the vehicle loop.
- API/config/dependencies: no contract-breaking change and no new dependencies. Existing `access_mode` identifies the selected approach.
- Files: `fire_agent_backend/app/routers/planning_preview.py`, `fire_agent_backend/tests/test_planning_preview.py`, `docs/dev-logs/heimini.md`.
- Verification: Python compile, `npm run build`, `git diff --check`, `docker compose config --quiet`, backend rebuild, and all 23 routing tests passed. The excessive-detour regression selected the 1 km dismounted shortcut instead of the 5.4 km fire-engine loop. A live four-team/two-target request used a 41 x 41 grid (1,687 DEM samples), retained complete target/team coverage, and completed in about 5.2 seconds before the final directional-connector refinement.
- Limitation: this reduces grid artifacts but remains terrain-grid planning until a verified road/trail network is available.

## 2026-09-25 - Fix assessment previews and Qwen RGB response coercion

- Branch: `member/heimini`.
- Goal: show selected repository pre/post imagery in the assessment page and stop valid Qwen RGB comparisons from failing when list fields are returned as paragraphs.
- Frontend: `AssessmentWorkspace.vue` now derives preview URLs from the selected catalog asset (`/api/visual-verification/imagery-catalog/{asset_id}/preview`), while preserving local upload previews and updating the assessment evidence status.
- Backend: `imagery_agent.py` now normalizes Qwen's string/paragraph values for `affected_region`, `affected_features`, `reconstruction_advice`, and `limitations` into bounded string lists before schema validation. The RGB endpoint remains qualitative and does not fabricate area or coordinates.
- API/data/config: no contract or database schema change.
- Verification: `python -m compileall fire_agent_backend/app/routers/imagery_agent.py`, `npm run build` via Docker, backend/frontend Docker rebuild, preview endpoint returned `200 image/jpeg`, and a live Qwen RGB pair request returned HTTP 200 with `qwen3-vl-plus`.
- Known limitation: RGB comparison remains qualitative; exact area and GeoJSON still require valid five-band products.

## 2026-09-25 - Enforce spatial overlap for pre/post assessment imagery

- Branch: `member/heimini`.
- Goal: prevent false change results when selected disaster-before and disaster-after images cover different areas.
- Frontend: `AssessmentWorkspace.vue` computes footprint bounding-box overlap over the smaller image footprint, shows the percentage beside the image pair, and rejects comparison when overlap is unavailable or below 80%.
- Backend: `imagery_agent.py` repeats the same minimum-overlap check for the RGB Qwen endpoint and returns HTTP 422 with the measured reason before sending imagery to Qwen.
- API/data/config: no database schema or dependency changes; successful RGB responses now also include `overlap_ratio`.
- Verification: backend compile, `npm run build`, Docker rebuild/restart, and a deliberately mismatched pre/post pair returned HTTP 422 as expected. The existing same-area pair remains eligible.
- Known limitation: overlap is calculated from catalog footprint bounds in geographic coordinates; it is a conservative selection guard, not a pixel-perfect co-registration test.

## 2026-09-25 - Prefer panorama comparison and Chinese damage grading

- Branch: `member/heimini`.
- Goal: compare disaster-before and disaster-after panorama products by default, classify visible affected zones, and keep Qwen assessment readable in Chinese.
- Frontend: assessment selection now prefers catalog assets whose product name contains `overview`, falling back to available products only when no panorama exists.
- Backend: Qwen prompts for RGB and derived RGB assessment now require simplified Chinese JSON and explicit high-, medium-, and low-impact region descriptions. Dictionary-shaped region entries are normalized into readable list strings.
- API/data/config: no schema or database change.
- Verification: backend compile, `npm run build`, Docker rebuild/restart, and a live panorama pair request returned HTTP 200 with overlap ratio 1.0 and Chinese damage-zone content.
- Limitation: RGB region grading is qualitative and image-relative; precise geospatial boundaries still require multi-band change extraction.

## 2026-09-25 - Simplify assessment presentation

- Branch: `member/heimini`.
- Goal: remove redundant manual interpretation blocks and improve the visual presentation of the pre/post imagery comparison.
- Frontend: hid the overlap banner, preview disclaimer, manual impact checklist, and manual recovery suggestion section. The comparison now uses compact fixed-ratio image cards with solid borders, labels, and reduced empty space.
- Data/behavior: spatial-overlap validation remains active in the analysis path; only its redundant visible notice was removed.
- Verification: `npm run build` and `git diff --check` passed. Docker restart is required after this frontend-only presentation change.

## 2026-09-25 - Generate qualitative affected-area GeoJSON

- Branch: `member/heimini`.
- Goal: provide a vector delineation for affected zones from the selected pre/post panorama pair.
- Backend: `imagery_agent.py` computes aligned RGB pixel-change scores, thresholds the 60th/80th percentiles into medium/high change classes, removes tiny regions, polygonizes the result, transforms it to EPSG:4326, and returns a GeoJSON FeatureCollection with severity and source properties.
- Frontend: `AssessmentWorkspace.vue` creates a temporary GeoJSON download URL after RGB assessment and exposes a compact “受灾区域矢量” download action.
- API/data/config: RGB assessment response adds `affected_area_geojson`; no database schema change. The output is explicitly qualitative and image-derived.
- Verification: backend compile, frontend build, Docker rebuild/restart, and a live panorama assessment returned HTTP 200 after vectorization.
- Limitation: RGB change polygons are not a burned-area truth boundary; use the five-band analysis path for quantitative area and stronger spectral discrimination.

## 2026-09-25 - Simplify affected-area vector classification

- Branch: `member/heimini`.
- Goal: provide one approximate affected-area vector result without high/medium/low categories.
- Backend: RGB vectorization now uses a single 60th-percentile change mask, polygonizes all retained changed regions, and labels features only as `qualitative_change`.
- Qwen prompts: affected regions are requested as broad image-relative areas without severity ranking.
- Verification: backend compile, frontend build, and API container rebuild passed.
## 2026-09-25 - Render affected-area vectors over post-fire imagery

- Branch: `member/heimini`.
- Goal: make the affected-area GeoJSON visible directly over the selected post-fire panorama instead of exposing only a download link.
- Frontend: `AssessmentWorkspace.vue` now retains the returned GeoJSON, projects Polygon and MultiPolygon outer rings from the selected post-fire asset footprint into SVG image coordinates, and renders the largest 400 regions as a red translucent overlay. The complete GeoJSON remains available for download.
- Five-band path: the page also reads the existing `area_geojson` analysis artifact so both RGB Qwen comparison and five-band change analysis can populate the overlay.
- API/database/config/dependencies: no API contract, database, environment variable, Docker configuration, or dependency changes.
- Verification: `npm run build` and `git diff --check` passed. Frontend container rebuild and live page availability are checked separately below.
- Known limitation: the on-page overlay assumes the catalog preview and catalog footprint cover the same full image extent; uploaded local browser previews are intentionally not overlaid because they do not carry catalog georeferencing.
- Merge note: this change is limited to `src/views/AssessmentWorkspace.vue`; `docs/dev-logs/heimini.md` records the work.
## 2026-09-25 - Restore FIRMS points during historical replay

- Branch: `member/heimini`.
- Goal: show the current day's FIRMS hotspots on the historical fire replay map during initial load, slider changes, and automatic playback.
- Root cause: `renderReplayHotspots()` cleared the previous hotspot entities but never called `addHotspotGeoJson()` for the new frame; the initial `renderMap()` path also omitted the current frame.
- Frontend: `RealtimeMonitor.vue` now renders the active replay frame with labels disabled and adds a FIRMS daily-hotspot item to the history legend.
- API/database/config/dependencies: no changes.
- Verification: `npm run build` and `git diff --check` passed. Frontend Docker rebuild and live availability are checked separately.
- Known issues: none for the missing-layer defect; very dense days still intentionally use the existing 0.02-degree aggregation performed before rendering.
- Merge note: review the shared historical/realtime map rendering paths in `src/views/RealtimeMonitor.vue`.
## 2026-09-25 - Synchronize verified and trusted fire points

- Branch: `member/heimini`.
- Goal: ensure spread prediction starts from the current human-confirmed verification point and never restores a fireline generated from a different point.
- Backend: `TrustedIgnitionAdapter` now idempotently synchronizes each current visual confirmation into `trusted_fire_points`. Human verification performs this synchronization immediately, and the generic spread service automatically backfills legacy confirmed records before returning `trusted_point_required`.
- Workflow state: selecting a different confirmation invalidates the previous spread run and downstream spatial, scenario, resource, route, decision, and recommendation results.
- Frontend: `FirePredict.vue` compares restored spread ignition coordinates with the active workflow confirmation. Mismatched cached firelines are cleared; matching results remain available when navigating back. Manual restart requests explicitly include the confirmed ignition point.
- API/database/config/dependencies: no endpoint or schema change; existing confirmation and spread request fields are reused. One trusted-point row was synchronized for the active Dixie confirmation through the existing workflow verification API.
- Verification: Python compile inside the Python 3.12 backend container, `npm run build`, `docker compose config --quiet`, `git diff --check`, backend/frontend Docker rebuild, container health checks, and live workflow/trusted-point API checks passed. The host-wide compile command is incompatible with the machine's Python 3.7 because existing repository files use Python 3.8+ assignment expressions. The live confirmed and trusted coordinates both returned `-121.31709,39.94808`; the previously latest spread used the mismatched old coordinate `-121.38241,39.87194` and is now rejected by the frontend restore guard.
- Known limitation: no new spread was started automatically during verification; the user must click the inference action to generate a fireline from the synchronized point.
- Merge note: review the shared `spread_service.py` fallback and `workflow_runtime_service.py` invalidation behavior because both are public backend orchestration paths.
## 2026-09-25 - Remove noisy RGB affected-area fragments

- Branch: `member/heimini`.
- Goal: replace the unusable full-image RGB change outline with a small number of broad, continuous qualitative affected regions.
- Root cause: the previous algorithm classified every pixel above the 60th change percentile, intentionally selecting about 40% of valid pixels, and removed only components of a few dozen pixels. Seasonal color, shadows, water, bright surfaces, and image edges therefore produced thousands of polygons.
- Backend: `imagery_agent.py` now analyzes a bounded 520-pixel overview, uses joint two-date channel normalization plus chromaticity/intensity change, smooths local scores, uses an 88th-percentile/statistical threshold, removes borders, applies binary close/open cleanup, sieves components below 0.25% of the analysis image, and retains at most six regions that are at least 8% of the largest region.
- Output behavior: if no component passes the continuity and size requirements, the existing endpoint returns an empty FeatureCollection and the frontend displays no overlay. The output remains explicitly qualitative RGB change rather than an observed burned-area boundary.
- API/database/config/dependencies: response schema is unchanged; no database, environment variable, Docker configuration, or dependency changes.
- Verification: module syntax check, backend Docker build/restart, and a direct run against the Dixie pre/post overview pair passed. The same pair decreased from roughly 3,011 fragmented features to 4 continuous regions; a generated diagnostic overlay confirmed that the retained regions no longer cover the full image with small fragments.
- Merge note: review the RGB-only fallback in `fire_agent_backend/app/routers/imagery_agent.py`; quantitative five-band analysis is unchanged.
## 2026-09-25 - Revert inference-page confirmation guard

- Branch: `member/heimini`.
- Goal: restore the inference page behavior that existed before the latest confirmed-point cache guard because it hid the restart and continue workflows behind the historical action.
- Frontend: removed the newly added confirmation-key/coordinate matching guard, restored the original persisted-spread visibility logic and `hasConfirmedPoint` watcher, and removed the extra manual restart ignition field.
- Backend retained: visual confirmation continues to synchronize into `trusted_fire_points`, so the previously fixed `trusted_point_required` mismatch remains resolved.
- API/database/config/dependencies: no new changes in this revert.
- Verification: `npm run build` and `git diff --check` passed; the frontend container is rebuilt separately.
- Merge note: this is a targeted manual revert in `src/views/FirePredict.vue`; no unrelated recovered changes were overwritten.
