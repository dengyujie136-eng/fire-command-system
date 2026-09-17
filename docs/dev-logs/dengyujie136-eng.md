## 2026-09-09｜视觉火情确认第一天内部基线

- 分支：`member/dengyujie136-eng`
- 最新提交：尚未提交
- 任务目标：在等待成员甲冻结候选点和影像接口期间，建立不依赖上游表结构的视觉核验内部模型、状态机、模拟提供者、保守确认规则和测试。

### 已完成

- 建立候选点视觉核验状态机和合法转换规则。
- 建立视觉任务、图片分析请求、结构化视觉结果、专业检测结果、确认决策和确认火点内部 Schema。
- 建立异步视觉模型提供者协议和明确标记为 fallback 的模拟提供者。
- 建立多模型一致才自动确认、低质量或冲突证据保持不确定的确认规则。
- 建立只有确认结果才能转换为下游火势模型输入的门禁。
- 增加覆盖状态、Schema、确认、排除、不确定和下游门禁的单元测试。

### 主要文件

- `fire_agent_backend/app/visual_verification/`：成员乙独立视觉核验领域模块。
- `fire_agent_backend/tests/test_visual_verification.py`：第一阶段单元测试。
- `docs/dev-logs/dengyujie136-eng.md`：成员乙开发日志。

### 接口变化

- 新增/修改/无：无公共 HTTP API 变化；尚未注册路由。
- 请求字段：仅定义内部 `ImageAnalysisRequest`。
- 响应字段：仅定义内部 `VisualAnalysisResult`、`ConfirmationDecision` 和 `ConfirmedFirePoint`。
- 错误和状态变化：模型失败、无效图像和证据冲突不能生成确认火点。

### 数据库与数据变化

- 表或字段：无；尚未创建数据库表或迁移。
- 坐标系或空间范围：内部确认点采用 GeoJSON 经度、纬度顺序；对外适配待甲丙接口确认。
- 数据来源与处理脚本：当前仅使用明确标记为 fallback 的确定性模拟提供者。

### 配置与依赖变化

- 环境变量：无。
- Python/npm/Docker 依赖：无新增依赖。

### 验证结果

- `[通过]` `python -m compileall app\\visual_verification tests\\test_visual_verification.py`
- `[通过]` `python -m unittest discover -s tests -p 'test_visual_verification.py' -v`：10 项测试全部通过。
- `[通过]` `git diff --check`
- `[未执行]` 公共 API、数据库、Qwen-VL 和端到端测试：本次未接入这些功能。

### 对其他模块的影响

- 依赖的上游输出：成员甲候选点、影像资产编号和影像检索接口尚未冻结。
- 提供给下游的输出：已定义内部 `ConfirmedFirePoint`，成员丙的正式 DTO 适配待确认。
- 高冲突公共文件：本次未修改 `app/main.py`、公共模型、公共 Schema、前端 Store、公共 API 或 `docs/API_CONTRACT.md`。

### 已知问题与下一步

- 尚未接入真实 Qwen-VL、专业检测模型、影像质量计算或数据库持久化。
- 成员甲交接后新增候选点与影像边界适配器，不直接改动内部领域模型。
- 单次复核版本已定义，持久化时需要为重新复核建立新版本记录。

### 合并提示

- 暂时不要合并：等待成员甲交接并完成第一轮边界适配后再评估。
- 项目负责人需要重点检查：确认门禁、状态所有权以及与现有 `observations`/`trusted_fire_points` 的迁移关系。

## 2026-09-09｜视觉火情确认第二天数据基线

- 分支：`member/dengyujie136-eng`
- 最新提交：尚未提交
- 任务目标：建立乙模块独立持久化模型、四类可追溯影像样例和固定 JSON 契约，使后续开发不依赖甲的真实数据交接。

### 已完成

- 建立 6 张乙模块自有 SQLAlchemy 表模型：复核案例、案例影像、派生影像、分析运行、视觉发现、火点确认。
- 使用外部业务标识连接甲的候选点，不建立跨成员数据库外键。
- 增加状态、坐标、置信度、版本唯一性和确认火点必需位置/时间约束。
- 固定 4 类开发样例：山火烟羽、假彩色火烧迹地、裸地非火灾、云覆盖低质量影像。
- 为全部图片记录官方来源页、用途说明和 SHA-256，避免被误当作 Cresta Dam 真实观测。
- 建立候选点输入、影像资产、确认/排除/不确定/失败结果和已确认火点交接 JSON。
- 增加契约校验、图片完整性、证据关联、数据库建表、读写、历史版本和约束测试。

### 主要文件

- `fire_agent_backend/app/visual_verification/models.py`：乙模块数据库模型。
- `fire_agent_backend/app/visual_verification/schemas.py`：候选输入、影像清单、失败结果等结构化契约。
- `fire_agent_backend/tests/fixtures/visual_verification/`：固定 JSON、图片和来源说明。
- `fire_agent_backend/tests/test_visual_fixtures.py`：固定契约与图片哈希测试。
- `fire_agent_backend/tests/test_visual_persistence.py`：SQLite 隔离持久化测试。

### 接口变化

- 新增/修改/无：无公共 HTTP API 变化；未注册路由。
- 甲到乙的候选输入暂用 `provisional-a-b-v0`，待甲交接后通过适配器替换。
- 乙内部影像清单使用 `visual-imagery-v1`。
- 乙到丙的 `ConfirmedFirePoint` 仍为内部稳定交接对象，未改公共接口文档。

### 数据库与数据变化

- 新增模型表：`visual_verification_cases`、`visual_case_assets`、`visual_image_derivatives`、`visual_analysis_runs`、`visual_findings`、`fire_confirmations`。
- 当前未加入公共 `init_db`，避免在接口和表归属未确认时修改高冲突公共文件。
- 样例来源：NASA Earth Observatory、USGS、NOAA/NESDIS/STAR；只用于可重复开发测试。
- 所有事件坐标和案例标识均为模拟数据，并显式设置 `is_simulated=true`。

### 配置与依赖变化

- 环境变量：无。
- Python/npm/Docker 依赖：无新增依赖。

### 验证结果

- `[通过]` `python -m unittest discover -s tests -v`：20 项测试全部通过。
- `[通过]` 固定图片文件 SHA-256 与清单一致。
- `[通过]` SQLite 内存库建立且仅建立 6 张乙模块表，完整证据链可读写。
- `[通过]` 重复版本和缺少位置/确认时间的确认记录被数据库拒绝。

### 对其他模块的影响

- 不修改甲的数据表；通过 `source_candidate_id`、`observation_id` 和 `source_asset_id` 保存外部引用。
- 不修改 `app/main.py`、`app/db/session.py`、公共模型、前端 Store 或 `docs/API_CONTRACT.md`。
- 甲交接后只需新增边界适配，不需要重写乙模块数据模型或固定测试。

### 已知问题与下一步

- NASA/NOAA 样例外部发布前仍需按最终展示形式复核媒体使用规则；USGS 来源页明确标注 Public Domain。
- 尚未生成数据库迁移，也未接入公共数据库初始化；待负责人确认表命名和集成窗口。
- 尚未接入真实 Qwen-VL、影像裁剪流水线或 HTTP API，这些不属于第二天固定基线范围。

### 合并提示

- 暂时不要合并或推送：等待用户确认并获得甲的交接信息。
- 合并前重点复核：临时甲到乙契约、图像再分发许可和 6 张表的命名归属。

## 2026-09-09｜甲方候选契约 v0.1 补正

- 分支：`member/dengyujie136-eng`
- 最新提交：尚未提交
- 任务目标：依据甲补充的状态所有权、HTTP/MQTT批量包络、候选编号规则和待影像规则，完成第一、二天成果的兼容修订。

### 已完成

- 用 `fire.hotspot.candidate.v0.1` 替换原 `provisional-a-b-v0` 候选输入。
- 建立候选位置、数据权属、影像引用、历史回放、产品专有字段和批量包络 Schema。
- 强制上游时间使用 UTC、坐标使用 EPSG:4326，并拒绝 Base64/data URI 影像。
- 按甲给出的 6 位坐标和 UTC 时间规则校验 FIRMS VIIRS-SNPP 候选编号，包括负经度产生的双连字符。
- 建立甲到乙适配器，完整保留甲的 `candidate_id`，同时生成定长乙内部案例编号。
- 隔离甲方工作流状态和乙方视觉状态；上游 `confirmed` 不能绕过视觉复核。
- 支持 HTTP 与 MQTT 共用批量包络，并校验批内编号唯一和事件一致。
- 支持 `imagery_status=pending` 且 `imagery_refs=[]`，不会因影像尚未到位而失败。
- 扩充数据库模型，保存上游版本、状态、事件名称、影像状态、权属、回放和开放产品字段。
- 新增乙返回编排层的结构化核验结果，包含 `fire`、`confidence`、`reason` 和证据引用；最终状态仍由编排层写入。
- 将固定候选 JSON 更新为甲的正式包络，并增加真实历史 FIRMS 回放样例。

### 接口与数据决策

- HTTP：约定批量包络可用于 `GET /api/data/events/{event_id}/hotspots` 的响应适配，但本次不注册公共路由。
- MQTT：同一包络可从 `fire/events/{event_id}/hotspots` 进入适配器，但本次不实现订阅连接。
- JSON 文件：只用于开发、离线测试和回归测试，不承担生产状态同步。
- `product_fields` 原样保存；FIRMS `confidence` 的 `n/l/h` 不强制转换为浮点数。
- 历史回放和模拟数据是两个独立维度，不能互相推断。

### 验证结果

- `[通过]` `python -m unittest discover -s tests -v`：32 项测试全部通过。
- `[通过]` 上游 `confirmed` 仍只生成乙内部 `received` 案例。
- `[通过]` 历史回放样例保持 `is_simulated=false`。
- `[通过]` 重复候选编号、跨事件候选、错误 FIRMS 编号、非 UTC 时间和 Base64 图片均被拒绝。
- `[通过]` 待影像候选可正常解析和适配。

### 未纳入本次补正

- 未连接甲的 PostGIS 表、HTTP 服务或 MQTT Broker。
- 未实现第三天的候选点持久化服务和影像匹配业务。
- 未修改 `app/main.py`、`app/db/session.py` 或其他公共高冲突文件。
- 未提交、未推送。

## 2026-09-09｜第三天候选接收与影像匹配

- 分支：`member/dengyujie136-eng`
- 最新提交：尚未提交
- 任务目标：使用甲方 v0.1 批量包络完成候选点幂等接收、查询、影像绑定、匹配和缺失降级，为第四天影像预处理提供稳定输入。

### 已完成

- 建立异步候选点接收服务，支持单条和批量包络。
- 使用规范化载荷 SHA-256 识别完全相同的重复提交，重复提交不增加数据库记录或影像关联。
- 只补充影像、产品字段或上游状态时建立新版本；旧版本和旧影像记录继续保留。
- 同一候选编号的事件、坐标、观测时间、模拟属性或回放属性发生改变时拒绝写入。
- 建立候选列表、当前版本筛选、历史版本、详情和影像查询能力。
- 默认候选列表只返回每个候选点的最新版本，可显式查询完整历史。
- 根据甲方 `imagery_refs` 自动绑定图片；首张作为主证据，后续图片作为上下文证据。
- 建立显式引用影像匹配计算，综合影像角色、时间差和质量评分。
- 区分 `matched`、`partially_matched`、`pending`、`unavailable` 和 `invalid_reference`。
- 远时相、低质量、未登记、无效或绑定到错误候选点的影像均产生明确告警。
- 建立未注册公共入口的候选导入、列表、详情和历史 HTTP Router，并验证 OpenAPI 可以生成。

### 接口变化

- 新增乙模块内部路由：`POST /visual-verification/candidates/import`。
- 新增乙模块内部路由：`GET /visual-verification/candidates`。
- 新增乙模块内部路由：`GET /visual-verification/candidates/{visual_case_id}`。
- 新增乙模块内部路由：`GET /visual-verification/candidates/source/{event_id}/{source_candidate_id}/history`。
- Router 尚未加入 `app/main.py`，因此不构成当前公共运行接口变化。

### 验证结果

- `[通过]` `python -m unittest discover -s tests -v`：当前累计 46 项测试全部通过。
- `[通过]` 固定批量包络创建 3 个候选案例和 4 条影像关联。
- `[通过]` 相同包络重复导入后仍为 3 个案例、4 条影像关联。
- `[通过]` 待影像候选补充影像后生成第 2 版，列表返回新版且历史保留两版。
- `[通过]` 核心身份冲突被拒绝。
- `[通过]` 主影像、上下文影像、远时相、低质量、缺失引用、错误候选点绑定和影像不可用分支。
- `[通过]` 候选 Router OpenAPI 构建。

### 当前集成限制

- 尚未获得甲方非空真实 HTTP 批量响应，未验证真实包络中候选子对象是否重复 `schema_version` 和 `event_id`。
- 尚未获得真实 `imagery_refs.uri` 的解析基准、共享目录或资产 API。
- 尚未连接 MQTT Broker，也未验证同一候选从 `pending` 更新到 `available` 的真实消息顺序。
- 尚未注册公共路由和数据库初始化，等待负责人安排公共文件集成窗口。
- 未提交、未推送。

## 2026-09-10｜甲乙联调暂停与第4天准备

- 当前决定：不连接甲的HTTP、PostGIS或MQTT，不调取真实候选点及真实影像。
- 已记录甲的实际接口使用`items`分页包络，且与早期v0.1占位Schema存在结构差异；适配修订留到后续实现批次。
- 当前真实候选均为`imagery_status=pending`，尚无可用真实影像或资产API。
- 本机访问`localhost:8200`被拒绝，未把文档中的返回样例标记为已完成运行验证。
- 第4天将使用固定公开图片和临时生成的小型测试栅格实现影像裁剪计算单元。
- 当前`fire-agent-api`没有共享数据卷挂载，业务后端依赖也未声明Rasterio；真实联调前需要单独协调公共配置。
- 详细个人方案保存在仓库外：`C:\Users\Daisy\Desktop\GIS综合实习\个人工作\成员乙-第4天影像裁剪开发方案.md`。

## 2026-09-10｜第4天候选点影像裁剪与标准化

- 分支：`member/dengyujie136-eng`
- 最新提交：本批次尚未提交
- 任务目标：完成候选点周边 GeoTIFF 窗口裁剪、普通图片模型输入标准化，并保存空间范围、处理参数和完整性哈希。

### 已完成

- 新建乙模块内部`image_processing`计算单元，未注册公共 HTTP 路由。
- 建立严格请求与结果 Schema，区分`model_input`与`pipeline_test`。
- 支持 JPEG、PNG、WebP 的 EXIF 方向校正、RGB 转换、等比例缩放和 JPEG/PNG 输出。
- 支持投影 GeoTIFF 的 WGS84 候选点坐标转换、米制半径窗口读取、栅格边界裁切、波段选择、百分位拉伸和 NoData 统计。
- 输出模型图、预览图和 JSON 侧车元数据，文件使用临时文件加原子替换。
- 基于源文件 SHA-256 与参数 SHA-256 生成确定性派生标识；重复执行直接复用，输出被篡改时拒绝继续。
- 输出记录可幂等写入既有`visual_image_derivatives`表，没有新增公共数据库表。
- 路径解析限制在`data`根目录，拒绝路径穿越、远程 URL 和内嵌 Base64。
- 补充 NumPy、Pillow、Rasterio 及 Docker 的`libexpat1`运行依赖，增加 pip 下载超时配置。

### 真实数据管线验证

- 使用甲交付的`dixie_fire_2021_copernicus_dem_30m_utm10.tif`验证空间裁剪。
- 测试候选坐标：`(-121.38241, 39.87194)`；半径：1500 m；源 CRS：`EPSG:32610`。
- 实际读取窗口：列偏移 905、行偏移 3923、宽 101、高 101；NoData 比例 0。
- 输出：101×101 RGB JPEG、预览 JPEG 和完整 JSON 元数据；第二次运行命中缓存且哈希一致。
- 该 DEM 只用于真实空间数据管线测试，结果强制携带`pipeline_test output is not eligible as visual fire evidence`告警，不用于 Qwen-VL 火情判断。

### 验证结果

- `[通过]` 宿主机`python -m unittest discover -s tests -v`：54 项共计，53 项通过，1 项因宿主机未安装 Rasterio 跳过。
- `[通过]` Docker 中`python -m unittest discover -s tests -v`：54 项全部通过，包含 GeoTIFF 空间裁剪。
- `[通过]` 甲交付的真实 DEM 裁剪、参数侧车文件、预览图和幂等缓存。
- `[通过]` `python -m compileall -q app tests`。

### 当前边界与后续所需

- 甲已交付可用的候选点、DEM、燃料及数据库数据，足以验证候选坐标到栅格窗口的空间处理链。
- 仍缺真实 Sentinel-2、Landsat、无人机、瞭望塔或现场 RGB/多光谱影像，不能完成真实视觉火情裁剪和波段组合验证。
- 甲的真实候选目前仍为`imagery_status=pending`，不能进入视觉证据处理；需等待`available`状态及可读的`imagery_refs.uri`。
- Compose 当前将`./data`以只读方式挂载到`fire-agent-api`；本次通过一次性可写挂载完成计算验证。在注册正式裁剪 API 前，需由负责人决定独立派生数据卷或可写子目录。
- 本次未修改`app/main.py`、公共数据库初始化或公共 API 文档，未推送远程仓库。

## 2026-09-10｜原始影像与派生影像存储隔离

- 分支：`member/dengyujie136-eng`
- 最新提交：本批次尚未提交
- 任务目标：保持甲交付的原始`data`只读，将乙生成的裁剪图、预览图和元数据改为独立可写持久卷。

### 已完成

- 新增`VISUAL_OUTPUT_DIR`配置和`resolved_visual_output_dir`默认路径。
- 将影像处理服务改为`source_root`和`output_root`双根目录，源文件只能从前者读取，派生文件只能写入后者。
- 将派生文件 URI 从源数据的`data://`命名空间分离为`visual-output://`。
- 新增派生 URI 安全解析，拒绝错误 scheme、目录穿越和输出根目录外的路径。
- 修改高冲突公共文件`compose.yaml`：显式配置`DATA_DIR=/app/data`、`VISUAL_OUTPUT_DIR=/app/visual-output`，新增`visual-derivatives`持久卷。
- 补充`.gitignore`的 Python `__pycache__`和`*.py[cod]`规则，防止本地编译产物进入仓库。
- 实际运行容器挂载验证：`/app/data`为`RW=false`的 bind mount，`/app/visual-output`为`RW=true`的 volume。
- 从只读 DEM 生成`visual-output://dixie-dual-root-test/...jpg`，第二次运行成功命中持久卷中的缓存。

### 接口、数据库与他人模块影响

- 未新增公共 HTTP API，甲到乙的候选 Schema、`imagery_refs.uri`和`data://...`源地址不变。
- 无数据库表或字段变化；新的派生记录会保存`visual-output://...`地址。
- 甲无需修改数据包或当前接口，但应知悉公共 Compose 新增了乙的输出卷。
- 项目负责人合并时需重点检查`compose.yaml`的`fire-agent-api.environment`、`fire-agent-api.volumes`和顶层`volumes`三处。

### 验证结果

- `[通过]` 宿主机全量 56 项：55 项通过，1 项因宿主机未安装 Rasterio 跳过。
- `[通过]` Docker 全量 56 项测试，包含 GeoTIFF 裁剪和双根目录隔离。
- `[通过]` `docker compose ... config --quiet`。
- `[通过]` `python -m compileall -q fire_agent_backend/app backend/forefire_api/app`。
- `[通过]` `npm run build`；仅有现有的大体积 chunk 提示。
- `[通过]` 重建并重启`fire-agent-api`，`http://127.0.0.1:8200/health`返回`ok=true`。

### 下一步

- 在负责人确认公共接口窗口后，新增裁剪触发接口和派生图片读取接口。
- 等待甲提供`imagery_status=available`的真实视觉影像，再执行真实火情影像裁剪验证。

## 2026-09-10｜影像派生内部接口与 Qwen-VL 输入准备

- 分支：`member/dengyujie136-eng`
- 最新提交：本批次尚未提交
- 任务目标：串联已入库候选案例、已绑定影像、裁剪计算与派生记录，为后续 Qwen-VL 调用提供可追溯的标准图片。

### 已完成

- 新增案例-资产派生工作流，候选坐标、模拟标记、资产 URI 和影像状态全部从数据库取得，不允许调用者伪造。
- 只允许`imagery_status=available`的案例进入处理；未绑定资产、案例缺失和不安全存量元数据有稳定错误码。
- 栅格和图片处理放入线程池，避免阻塞 FastAPI 异步事件循环。
- 裁剪成功后幂等写入`visual_image_derivatives`，保留完整源资产和参数追溯。
- 新增派生详情、模型图和预览图读取路由，读文件时再次执行`visual-output://`路径边界校验。
- 路由仍未注册到`app/main.py`，因此当前正式 8200 公共 API 不受影响。

### 内部 API 提案

- `POST /visual-verification/candidates/{visual_case_id}/assets/{source_asset_id}/derivatives`：传入裁剪半径、波段、输出尺寸等可控参数，返回`ImageProcessingResult`。
- `GET /visual-verification/derivatives/{derivative_id}`：返回派生记录和追溯参数。
- `GET /visual-verification/derivatives/{derivative_id}/image`：返回 Qwen-VL 可读的标准图。
- `GET /visual-verification/derivatives/{derivative_id}/preview`：返回前端预览图。
- 错误响应区分 404 资源缺失、409 派生冲突和 422 影像不可处理。

### 验证结果

- `[通过]` 宿主机全量 59 项：58 项通过，1 项因未安装 Rasterio 跳过。
- `[通过]` Docker 全量 59 项，包含 GeoTIFF、工作流落库、待影像拒绝、资产越权拒绝和 OpenAPI 路由生成。

### 当前边界和下一步

- 已具备 Qwen-VL 输入文件的生成、定位、读取和追溯能力。
- 正式对外开放前仍需负责人确认`app/main.py`的集成时机，并将乙的6张表纳入公共数据库初始化或迁移。
- 下一个开发批次应建立 Qwen-VL 提示词版本、图片传输适配器、严格结构化响应解析、超时/重试与不确定降级。

## 2026-09-10｜Qwen-VL视觉分析计算单元

- 分支：`member/dengyujie136-eng`
- 最新提交：本批次尚未提交
- 任务目标：在无 API Key 和无真实火情影像条件下，完成 Qwen-VL 请求、严格解析、异常分类、重试及证据落库主干。

### 已完成

- 冻结`qwen-fire-assessment-v1`中文提示词，要求模型只根据可见证据判断，禁止使用候选真值。
- 要求严格 JSON 输出火灾、火焰、烟雾、火烧迹地、火灾概率、图像质量、场景类型、干扰解释、决策与依据。
- 实现 Qwen OpenAI 兼容多模态请求：`image_url`使用 JPEG/PNG Base64 Data URL，同时请求`response_format=json_object`。
- 模型只能读取已登记的`visual-output://`派生图；校验图片大小、类型和路径边界。
- 实现可注入传输层和 Httpx 真实传输层，API Key 只放在 Authorization 请求头，不写入日志或数据库。
- 实现超时、HTTP 408/429/5xx 及传输失败的有界重试，最多3次；业务非法输出不重试。
- 严格拒绝非 JSON、多余字段、非法枚举、概率越界和“确认火灾但没有火/火焰/烟雾证据”的自相矛盾结果。
- 成功运行写入`visual_analysis_runs`原始响应，并向`visual_findings`写入 fire、flame、smoke、burn_scar 4类发现。
- 超时、非法输出和提供者错误保存为结构化失败运行，不会生成火点确认。
- 修正上游 URI 校验：允许本地`data://`资产引用，仍拒绝`data:image/...;base64`内嵌输入。

### 验证与限制

- `[通过]` 宿主机全量 67 项：66 项通过，1 项因宿主机未安装 Rasterio 跳过。
- `[通过]` Docker 全量 67 项，包含 GeoTIFF 和 Qwen-VL 提供者全分支。
- `[通过]` 构造官方兼容多模态请求、严格响应解析、可重试临时错误、非法输出不重试。
- `[通过]` 成功运行落库 1 条 run 和 4 条 finding；非法输出落库为`invalid_output`。
- `[未执行]` 真实 Qwen-VL 网络调用：未提供 API Key、工作空间 Base URL 和真实视觉影像。
- 实现依据阿里云 Model Studio 官方 OpenAI 兼容 Vision 和结构化输出文档，模型默认名为`qwen3-vl-plus`。

### 下一步

- 组装“派生图查询 → ImageAnalysisRequest → Qwen 运行 → 分析记录”的案例级编排服务。
- 将 Qwen 视觉结果与独立的专业目标检测结果交给已有保守确认规则。
- 真实调用前由用户通过环境变量提供 API Key 和工作空间 Base URL，不得写入仓库。

## 2026-09-10｜Qwen-VL运行时接线与分析触发接口

- 分支：`member/dengyujie136-eng`
- 最新提交：本批次尚未提交
- 任务目标：从独立环境变量安全创建 Qwen-VL 客户端，并将已登记派生影像接入真实分析与持久化流程。

### 已完成

- 新增独立的`QWEN_VL_*`配置：Key、Base URL、模型名、超时、重试次数和图片大小上限。
- API Key 使用`SecretStr`承载，配置对象输出不会显示明文；未配置 Key 或 Base URL 非 HTTPS 时拒绝创建客户端。
- 新增 Qwen 提供者工厂，将运行时配置、双根影像目录和 Httpx 传输层集中组装。
- 新增`POST /api/visual-verification/candidates/{visual_case_id}/analyses`分析接口。
- 对外请求只接受最多8个派生影像编号；影像 URI 必须由服务端从数据库读取，并校验全部影像属于目标案例。
- 分析成功或失败均通过既有服务写入运行记录；模型失败不会伪装为成功结果。
- 将视觉复核路由注册到唯一业务后端，并将视觉复核6张表纳入应用启动建表元数据。
- 修改高冲突公共文件`compose.yaml`和`app/main.py`，项目负责人合并时需要检查 Qwen 环境变量与路由注册位置。

### API 与配置影响

- 新增请求 Schema：`VisualAnalysisStartRequest { derivative_ids: string[] }`。
- 成功响应为`VisualAnalysisResult`；模型端失败响应为持久化的`VisualAnalysisFailure`；未配置运行时返回`503 qwen_not_configured`。
- `fire-agent-api`容器新增`QWEN_VL_API_KEY`、`QWEN_VL_BASE_URL`、`QWEN_VL_MODEL`、`QWEN_VL_TIMEOUT_SECONDS`、`QWEN_VL_MAX_ATTEMPTS`和`QWEN_VL_MAX_IMAGE_BYTES`。
- 本地凭证文件仍在仓库外，不纳入 Git。

### 验证结果与当前阻塞

- `[通过]` 宿主机全量70项：69项通过，1项因宿主机未安装 Rasterio 跳过。
- `[通过]` Python 全模块编译、`docker compose config --quiet`和`git diff --check`。
- `[通过]` 重建`fire-agent-api`镜像并在 Python 3.12 容器中运行全量70项测试，全部通过。
- `[通过]` 容器内生成 OpenAPI，确认分析接口已注册到`/api`。
- `[通过]` 新增配置工厂测试：缺少 Key、HTTPS 校验、模型选择与密钥隐藏。
- `[通过]` `npm run build`；仅保留现有的大体积 chunk 提示。
- `[待执行]` 真实 Qwen-VL 网络调用。现有 Key 因调试检索输出意外暴露，已停止使用；必须先在平台重置并更新仓库外配置文件。

## 2026-09-11｜Qwen-VL首次真实网络验证

- 分支：`member/dengyujie136-eng`
- 凭证：用户已在平台重置并更新仓库外`qwen.env`；日志与仓库均不记录明文。
- 实际模型：`qwen3-vl-flash`。

### 真实调用结果

- 山火烟羽样例：调用成功，`fire=true`、`smoke=true`、`flame=false`、火灾概率`0.95`、场景`forest_wildfire`、决策`confirmed`。
- 裸地干扰样例：调用成功，火焰/烟羽/火烧迹地均为`false`、火灾概率`0.0`、场景`bare_ground`、决策`rejected`。
- 裸地调用用量：输入294 tokens（其中图片77、文本217），输出183 tokens，总计477 tokens。
- 两次返回均满足`qwen-fire-assessment-v1`严格 Schema 和决策一致性校验，未触发重试或降级。

### 当前结论

- API Key、DashScope OpenAI兼容 Base URL、模型名、Base64图片传输和结构化输出链路均已真实验证。
- 已验证一个正样例和一个典型误报样例，证明当前主干具备“确认真实火情”和“排除非火灾热目标”两种基本能力。
- 本轮为计算单元网络验证，未向团队远程仓库推送；案例级 HTTP 接口及数据库持久化已由容器自动化测试覆盖，后续用甲的正式候选影像做端到端联调。

## 2026-09-11｜三态实测与案例级端到端联调

- 分支：`member/dengyujie136-eng`
- 任务目标：验证云雾/低质量场景，并通过公开HTTP接口串联候选导入、派生处理、Qwen分析和证据落库。

### 已完成

- 原始GOES云图真实调用识别为`cloud_or_fog`且`rejected`，没有把云层误报为火灾，总用量862 tokens。
- 发现低分辨率实测中`alternative_explanations`偶发返回字符串而非数组；严格Schema正确将其保存为`invalid_output`，未生成错误火情。
- 依据阿里云当前结构化输出说明，确认`qwen3-vl-flash`的`json_object`只保证合法JSON，不保证字段结构；继续保留本地严格校验。
- 将提示词升级为`qwen-fire-assessment-v2`：明确数组字段类型，并将图像质量定义为“是否足以复核候选点”，空间尺度不足时必须返回`poor/invalid + uncertain`。
- v2低分辨率云图实测成功：`image_quality=poor`、`scene_type=cloud_or_fog`、`decision=uncertain`，总用量543 tokens。
- v2山火烟羽复测成功：`fire=true`、`smoke=true`、概率0.95、`decision=confirmed`，总用量1040 tokens。
- 升级本地业务容器，确认5张视觉相关表自动建立；通过公开API导入3个模拟候选和4个资产。
- 通过公开API完成山火样例派生与真实分析，数据库保存1条派生、成功运行及4类发现；派生图和预览图均可HTTP读取，主图261622字节且哈希存在。
- 真实网络曾发生一次可重试传输异常，系统保存为`provider_error`；随后重试成功，证明失败不会冒充业务结论。

### 验证与边界

- `[通过]` 宿主机70项：69项通过，1项因本机缺少Rasterio跳过。
- `[通过]` Python 3.12 Docker全量70项测试。
- `[通过]` 正例、负例和低质量不确定三类真实Qwen结果。
- `[未满足]` 甲的正式交付目前只有热点、DEM、坡度、坡向、土地覆盖和燃料栅格，没有候选点对应的光学、无人机、瞭望塔或现场影像；因此本轮端到端使用明确标记`is_simulated=true`的固定RGB样例。
- `[待后续]` 自动确认仍需独立专业目标检测结果与Qwen结论一致；不能用模拟检测结果生成交给成员丙的“真实火点”。

## 2026-09-11｜候选火点复核页面原型

- 分支：`member/dengyujie136-eng`
- 任务目标：将候选案例、空间位置、影像派生与Qwen结构化结果形成可操作的成员乙前端页面。

### 已完成

- 新增`/visual-verification`路由和顶部“复核”入口。
- 左侧展示候选点列表、坐标、当前状态、模拟标记和本次页面会话的分析统计。
- 中间使用Cesium展示选中候选点位置，并随候选切换更新标注与相机。
- 右侧展示影像资产选择、模拟数据警告、标准化派生图片、Qwen结论、概率、火焰/烟羽/火烧迹地、图像质量、场景类型、模型与判断依据。
- 页面按钮实际串联派生接口和分析接口；错误、处理中和不可用状态均有明确反馈。
- 新增`visualVerificationAPI`封装，不允许前端提交任意影像URI，只传案例、资产和派生编号。

### 公共文件与验证

- 修改高冲突公共文件`src/api/modules.ts`，新增视觉复核API封装；集成人员需检查接口命名。
- 修改`src/router/index.ts`和`src/components/AppHeader.vue`，加入复核页面导航。
- `[通过]` 宿主机`npm run build`。
- `[通过]` Docker前端镜像构建，`/visual-verification`返回HTTP 200。
- `[通过]` 浏览器实际加载3个候选、空间位置、2项山火影像资产和可用分析按钮。
- `[已知环境提示]` 本机未配置Cesium在线地形能力，组件回退到椭球地形；不影响视觉复核业务链路。
## 2026-09-11｜预训练火焰/烟羽检测器验证与后端封装

- 分支：`member/dengyujie136-eng`
- 本批次未提交、未推送。
- 任务目标：补充清晰火焰和无人机小火点样例，验证预训练专业目标检测器，并在达到最低可用标准后接入乙模块后端。

### 样例与模型验证

- 从官方 D-Fire、FASDD、FLAME 和 FLAME 2 仓库下载展示资产，全部保存在仓库外的`个人工作/第三方模型`目录。
- 采用本地评估的`tarunnn12/wildfire-detection` YOLOv8m 权重；权重 SHA-256 为`fe2bdd32dc92c06ef2006e87718b6cbec9a4537a01cff79cf445737c83ee4fd7`，权重未加入 Git。
- 清晰火焰得到`fire=0.663054/0.771022`，FASDD 无人机小火点得到`fire=0.688766`。
- FLAME 更小目标在`conf=0.25`得到`fire=0.326596`或`smoke=0.328451`，在`conf=0.40`漏检；但云图在0.25出现`smoke=0.283800`误报。因此全局默认保持0.40，仅对已知无人机小目标显式使用0.25，并记录实际阈值。
- 热成像、近红外样例不计入普通RGB能力结论；FASDD展示拼图裁片仅作冒烟测试，不冒充独立精度评估。

### 后端实现

- 新增`backend/visual_detector_api`独立CPU推理服务，接受最多由业务层限制的标准派生图片，输出fire/smoke边界框、类别、置信度、模型版本和权重SHA-256。
- 权重通过只读卷挂载，未复制到镜像；业务后端通过内部HTTP调用检测服务，前端不直接访问8300端口。
- 新增`POST /api/visual-verification/candidates/{visual_case_id}/professional-detections`，请求字段为`derivative_ids`、可选`confidence_threshold`及`image_size`。
- 服务端只从数据库解析属于目标案例的`visual-output://`派生图，拒绝由客户端提交任意文件路径。
- 检测运行复用既有`visual_analysis_runs`，每个目标框写入`visual_findings`，没有新增数据库表。
- 无目标框只表示“在当前阈值下未发现”，结果和阈值一并保存；最终确认仍由Qwen-VL、专业检测和影像质量保守融合。
- 修改高冲突公共配置`fire_agent_backend/app/core/config.py`和公共Schema/路由；负责人合并时需检查新增`PROFESSIONAL_DETECTOR_*`配置与接口命名。
- 本机部署覆盖文件仍在仓库外`个人工作/compose.dixie-local.yaml`，包含本机权重路径；仓库内只提供不含权重的示例Compose。

### 验证结果

- `[通过]` 独立评估脚本三档阈值运行，输出9张样例的JSON和标注图。
- `[通过]` 检测服务镜像构建、健康检查及真实multipart请求；同批返回FASDD小火点0.688766、FLAME小火点0.326596。
- `[通过]` 业务8200接口端到端调用，现有山火派生图返回两处smoke（0.529986、0.444282），运行与发现记录均已写入PostGIS。
- `[通过]` 宿主机73项测试，72项通过，1项因宿主机无Rasterio跳过。
- `[通过]` Python 3.12 Docker全量73项测试。
- `[通过]` Python编译、Compose配置、`git diff --check`。

### 已知边界

- 上游模型仓库未发现清晰的整体许可证；当前仅用于本地课程原型验证，不能提交或向团队重新分发权重，正式发布前需确认授权或替换为许可明确的模型。
- 当前仅证明若干公开样例可以检测，不代表在Dixie Fire、卫星宽幅图或所有无人机场景上的统计精度。
- 尚未把专业检测结果展示到前端，也尚未增加自动调用Qwen+YOLO+确认规则的一键编排接口。

## 2026-09-11｜模拟多源影像与一键复核后端闭环

- 分支：`member/dengyujie136-eng`
- 本批次只实现后端，不修改前端，不提交、不推送。
- 模拟影像、来源清单和本机部署配置保存在仓库外`个人工作`目录；团队仓库不包含样例图片、模型权重或密钥。

### 后端实现

- 新增`POST /api/visual-verification/candidates/{visual_case_id}/review`，一次调用完成专业目标检测、Qwen-VL结构化分析、保守融合和最终确认记录写入。
- 新增案例状态写入流程：`imagery_ready -> analyzing -> confirmed/rejected/uncertain/failed`；已确认或已排除版本保持不可变，重新复核使用新的候选版本。
- 专业检测服务失败时降级为`unavailable`并保留警告；Qwen失败则写入`failed`，任何单模型结果都不能越过融合规则自动确认。
- 最终记录包含Qwen证据ID、目标框证据ID、规则版本、模型信息、实际阈值与`is_simulated`标记。
- 本机只读数据挂载改为`/app/data-sources`下的并列来源，解决在只读父目录中创建嵌套挂载点失败的问题；派生图继续写入独立Docker卷。

### 模拟影像数据

- 建立仓库外`个人工作/模拟影像数据/visual-demo-v1`：无人机火焰/烟羽、固定瞭望相机火灾前后、裸地干扰和云层低质量影像。
- `manifest.json`记录真实来源、许可提示、尺寸和SHA-256；`candidate_import.json`记录模拟候选关联，全部强制`is_simulated=true`。
- 原图来源真实，但候选坐标、采集时间、设备和事件对应关系均为模拟；这些确认结果不得作为成员丙的真实起火点输入。
- 初始低分辨率裸地与夜间瞭望图都被Qwen保守判为`poor + uncertain`，没有为了演示强行排除；随后补充一张CC0白天裸地样例用于验证明确误报分支。

### 实际端到端结果

- 模拟无人机双图：Qwen判定`forest_wildfire/confirmed`、概率0.95；YOLO在0.25阈值检出smoke 0.36469；融合结果`confirmed`、置信度0.6866。
- 清晰白天裸地：Qwen判定`bare_ground/rejected`、概率0；YOLO在0.40阈值无目标；融合结果`rejected`、置信度0.73。
- GOES大区域云图：Qwen判定`cloud_or_fog/poor/uncertain`、概率0；YOLO在0.40阈值无目标；融合结果`uncertain`，要求获取更合适影像。
- 三类结果均成功写入PostGIS，确认记录保持`is_simulated=true`；检测服务和业务服务健康检查通过。

### 验证与边界

- `[通过]` 新增融合与持久化单元测试；专业检测相关7项测试通过。
- `[通过]` 宿主机全量77项：76项通过，1项因宿主机无Rasterio跳过。
- `[通过]` Python 3.12临时测试容器全量77项通过；仅有3条Rasterio上游弃用提示。
- `[通过]` 模拟候选Schema校验：3个候选、7份资产，所有文件SHA-256与清单一致。
- `[通过]` 实际HTTP链路：候选导入、派生处理、YOLO、Qwen、融合、确认落库。
- `[边界]` YOLO权重来源仓库许可不清晰，当前只能本地课程原型使用，不能随代码分发；正式发布需换成许可明确权重或完成授权确认。
- `[待甲]` 甲提供候选点对应的可见光/假彩色卫星裁片及时间、范围、波段信息后，再以真实资产替换模拟关联进行联调。
## 2026-09-12｜通用遥感分析任务契约与统一入口

- 分支：`member/dengyujie136-eng`
- 最新提交：尚未提交
- 任务目标：将乙模块从写死候选点流程扩展为可由多智能体按`event_id`调用的通用遥感分析计算单元，不修改前端。

### 已完成

- 新增事件无关的遥感分析请求契约，支持`fire_confirmation`、`temporal_change`和`burned_area`三种分析类型。
- 明确单景确认必须提供UTC目标时间，多时相变化和过火范围必须提供前后时间范围及至少两项影像资产。
- 新增Agent能力发现接口，向丁提供`analyze_fire_imagery`和`analyze_temporal_change`两个稳定工具名称。
- 新增统一分析入口；单景火情确认可以复用现有Qwen-VL、专业检测和保守融合链路。
- 统一入口校验`event_id`、视觉案例、源影像资产和模型派生图之间的归属关系，未准备影像返回稳定错误码。
- 多时相变化和过火范围只冻结契约，真实栅格计算留到第2天；当前明确返回501，不使用虚假计算结果。

### 主要文件

- `fire_agent_backend/app/visual_verification/schemas.py`：新增通用遥感任务、时间范围、能力和结果Schema。
- `fire_agent_backend/app/visual_verification/router.py`：新增能力发现与统一运行入口，并复用现有完整复核服务。
- `fire_agent_backend/tests/test_remote_sensing_contract.py`：新增事件无关、任务约束、接口暴露和调度测试。
- `docs/dev-logs/dengyujie136-eng.md`：记录公共接口变化和后续边界。

### 接口变化

- 新增`GET /api/visual-verification/analyses/capabilities`。
- 新增`POST /api/visual-verification/analyses/run`。
- 请求字段：`event_id`、`analysis_type`、`target_time`或`time_range`、`target_geometry`、`asset_ids`、`hotspot_ids`、可选`visual_case_id`和`prepared_image_ids`。
- 响应字段：通用Schema版本、事件、分析类型、Agent工具名、源资产、热点及现有视觉复核结果。
- 错误和状态变化：未准备影像返回`imagery_not_prepared`；第2天计算尚未实现时返回`analysis_stage_not_available`；不产生伪结果。

### 数据库与数据变化

- 表或字段：无新增数据库表或字段，继续复用现有视觉案例、资产、派生图、运行、发现和确认记录。
- 坐标系或空间范围：请求空间范围使用GeoJSON Point、Polygon或MultiPolygon；时间统一要求UTC。
- 数据来源与处理脚本：本批次不新增数据文件。

### 配置与依赖变化

- 环境变量：无新增。
- Python/npm/Docker依赖：无新增。

### 验证结果

- `[通过]` 新增通用遥感契约测试：11项全部通过。
- `[通过]` 乙模块回归测试：86项通过，1项因环境条件跳过。
- `[通过]` `python -m compileall -q fire_agent_backend/app`。
- `[通过]` FastAPI接口级检查：能力接口HTTP 200，缺少模型派生图HTTP 409且错误码为`imagery_not_prepared`。
- `[通过]` `git diff --check`，仅出现既有Windows行尾提示。

### 对其他模块的影响

- 依赖的上游输出：甲的数据Agent后续提供事件编号、影像资产编号、时间和空间范围。
- 提供给下游的输出：丁可读取能力接口并调用通用运行入口；丙仍使用确认火点交接结果。
- 高冲突公共文件：`fire_agent_backend/app/visual_verification/schemas.py`和`router.py`，负责人合并时需检查命名。

### 已知问题与下一步

- 第2天完成真实GeoTIFF多时相处理、NBR/dNBR和过火区GeoJSON计算。
- 当前真实候选点仍缺少可读取遥感影像，无法完成真实数据端到端验收。

### 合并提示

- 暂时不要合并；本批次与此前未提交的专业检测和一键复核代码共处同一工作区，待第2天计算完成后整体检查。
- 项目负责人需要重点检查通用任务字段是否与丁的Agent工具注册方式一致。

## 2026-09-12｜通用遥感分析第二天栅格计算

- 分支：`member/dengyujie136-eng`
- 最新提交：尚未提交
- 任务目标：在不使用甲新交付真实影像的前提下，用可重复的合成GeoTIFF完成多时相变化和过火区域计算，并接入第1天冻结的统一分析入口。

### 已完成

- 新增灾前/灾后GeoTIFF配对分析，自动将后一时相重投影并对齐到前一时相网格。
- 必需波段为B2、B3、B4、B8；两景都有B12时计算dNBR，否则计算dNDVI并明确标记为植被变化代理，避免把当前无短波红外的结果冒充标准过火强度产品。
- 新增可调变化阈值与最小连通区域像素数，使用8邻域剔除零散噪声。
- 计算变化像素数、有效像素数和公顷面积，将变化区域矢量化并转换为WGS84 MultiPolygon。
- 生成灾前/灾后RGB、近红外合成预览图，预览最长边限制为2048像素；同时输出前后指数、变化指数、掩膜GeoTIFF和GeoJSON。
- 将`temporal_change`与`burned_area`由计划状态改为可用，并通过统一`POST /api/visual-verification/analyses/run`执行。
- 统一入口只读取已登记且属于同一事件视觉案例的两项资产，缺失资产返回稳定错误码`imagery_asset_not_found`。

### 主要文件

- `fire_agent_backend/app/visual_verification/raster_change.py`：GeoTIFF波段校验、对齐、指数、过滤、面积、矢量化和成果输出。
- `fire_agent_backend/app/visual_verification/schemas.py`：新增变化参数与结构化计算结果。
- `fire_agent_backend/app/visual_verification/router.py`：接入统一分析入口并发布可用能力。
- `fire_agent_backend/tests/test_raster_change.py`：合成栅格计算测试。
- `fire_agent_backend/tests/test_remote_sensing_contract.py`：统一接口变化任务调度测试。

### 接口变化

- `RemoteSensingAnalysisRequest`新增可选`change_threshold`和`minimum_region_pixels`。
- `temporal_change`及`burned_area`严格要求两个资产，顺序为before、after。
- 新增`RemoteSensingChangeResult`，返回方法、阈值、像素统计、面积、WGS84几何、源坐标系、分辨率、成果URI、警告及模拟标记。
- 能力发现接口中三类分析均为`available`。

### 数据库与数据变化

- 无新增表和数据库迁移；本日成果暂以结构化响应和文件URI返回。
- 所有输入仍必须通过已有视觉案例资产登记，不允许客户端直接提交任意本机路径。
- 本日只使用测试临时目录中的合成EPSG:32610、10米GeoTIFF；甲通过U盘交付的18幅真实影像未读取、未复制进仓库、未参与验收。

### 验证结果

- `[通过]` 宿主机目标测试：12项通过，3项因宿主机未安装Rasterio跳过。
- `[通过]` 宿主机乙模块完整回归：88项通过，4项因宿主机未安装Rasterio跳过。
- `[通过]` 现有Docker环境完整回归：92项全部通过；其中Rasterio真实执行覆盖dNBR、dNDVI降级、缺失波段拒绝与统一接口调度。
- `[通过]` `python -m compileall -q fire_agent_backend/app fire_agent_backend/tests`。
- `[通过]` `git diff --check`，仅出现既有Windows行尾转换提示。

### 已知边界与下一步

- 当前按完整已登记影像范围计算，尚未用请求中的`target_geometry`再次裁剪。
- 当前变化成果尚未单独持久化到数据库；第3天再统一分析历史与结果查询。
- dNDVI只能支持植被显著下降筛选；待甲补充B11/B12后才使用dNBR进行更可靠的火烧迹地分析。
- 真实18幅影像后续需要先完成资产登记和阶段配对，再执行真实数据验收。

## 2026-09-12｜通用遥感分析第三天运行闭环

- 分支：`member/dengyujie136-eng`
- 最新提交：尚未提交
- 任务目标：把火情确认、时相变化和过火范围任务统一纳入可追溯运行记录，允许多智能体按事件查询历史与成果，并补齐空间分析范围约束。

### 已完成

- 新增`remote_sensing_analyses`表，统一记录三类遥感任务的请求、状态、源资产、结果、错误、耗时和模拟标记。
- 每次合法运行先写入`running`；正常结束写入`succeeded`及完整结构化结果；栅格、模型或调用异常写入`failed`及稳定错误信息。
- 为火情确认结果补充统一`analysis_id`，使Qwen-VL/目标检测复核与多时相计算都能通过同一编号追踪。
- 新增按事件、视觉案例、分析类型和状态筛选的历史接口，以及按分析编号读取详情的接口。
- 新增受控成果下载接口；只允许下载数据库结果中登记的`output_uris`，继续限制在乙模块派生目录内。
- 多时相任务的`target_geometry`限制为Polygon或MultiPolygon；计算时转换到源影像投影并生成掩膜，面积和像素统计只覆盖指定区域。
- 完成结果一致性门禁：分析编号、事件、分析类型和资产顺序必须与运行记录一致，防止错误结果写入其他事件的历史。

### 主要文件

- `fire_agent_backend/app/visual_verification/models.py`：新增统一遥感分析运行表。
- `fire_agent_backend/app/visual_verification/remote_analysis_service.py`：运行创建、成功、失败、详情和历史查询。
- `fire_agent_backend/app/visual_verification/router.py`：运行留痕、历史、详情和成果下载接口。
- `fire_agent_backend/app/visual_verification/raster_change.py`：目标范围投影与掩膜计算。
- `fire_agent_backend/app/visual_verification/schemas.py`：运行详情Schema、统一分析编号与空间类型约束。
- `fire_agent_backend/tests/test_remote_analysis_persistence.py`：数据库与统一入口闭环测试。

### 接口变化

- 新增`GET /api/visual-verification/analyses`，支持`event_id`、`visual_case_id`、`analysis_type`、`run_status`和`limit`筛选。
- 新增`GET /api/visual-verification/analyses/{analysis_id}`。
- 新增`GET /api/visual-verification/analyses/{analysis_id}/artifacts/{artifact_name}`。
- `POST /api/visual-verification/analyses/run`的火情确认结果新增`analysis_id`；变化任务的现有`analysis_id`改为与数据库运行编号一致。
- 无对应运行或成果时分别返回`remote_analysis_not_found`和`remote_analysis_artifact_not_found`。

### 数据库与数据变化

- 乙模块自有表由6张增加为7张；应用现有`create_all`初始化会创建新表，不修改甲、丙、丁的表。
- `request_payload`和`result_payload`保留完整JSON快照，源影像仍只保存资产编号，不复制大型原始数据进数据库或仓库。
- 本日开发和自动验收继续使用合成栅格；甲通过U盘交付的18幅真实影像未写入仓库，也未被当作已完成真实事件结论。

### 验证结果

- `[通过]` 第三天目标测试：17项全部通过。
- `[通过]` 第二、三天组合目标测试：20项通过，4项因宿主机没有Rasterio跳过。
- `[通过]` 宿主机乙模块完整回归：93项通过，5项因宿主机没有Rasterio跳过。
- `[通过]` Docker完整回归：98项全部通过，包含Rasterio实际计算和目标Polygon范围限制。
- `[通过]` Python编译、Compose配置和`git diff --check`；只有既有Windows行尾转换提示。
- `[通过]` 重建业务后端后健康检查正常，PostGIS已实际创建`remote_sensing_analyses`表。
- `[通过]` 8200端口能力接口HTTP 200；空历史查询HTTP 200并返回`[]`；不存在详情HTTP 404并返回`remote_analysis_not_found`。
- `[通过]` 运行中OpenAPI包含运行、历史、详情和成果下载四个通用遥感分析路径。

### 已知边界与下一步

- 当前没有数据库迁移框架，项目启动时沿用SQLAlchemy`create_all`创建新增表。
- 运行接口仍要求影像先登记到视觉案例；甲的真实18幅影像需要建立正式资产清单与阶段配对后才能调用。
- 当前影像只有B2/B3/B4/B8，真实事件只能生成dNDVI变化代理；标准dNBR仍依赖后续B12。
- 本批次不包含前端、真实Dixie结论、代码提交或远程推送。

### 合并提示

- 高冲突公共文件为`models.py`、`schemas.py`和`router.py`，负责人应重点检查统一分析编号、结果查询路径及新表命名。
- 新表只引用乙模块的`visual_verification_cases`，不建立跨成员数据库外键。

## 2026-09-12｜Cresta Dam起火候选筛选与真实影像首次复核

- 分支：`member/dengyujie136-eng`
- 最新提交：尚未提交
- 任务目标：从甲的Dixie Fire数据中筛选Cresta Dam起火输入，接入U盘交付的Sentinel-2影像并尽快向丙提供不夸大状态的交接文件。

### 数据筛选结果

- PostGIS实际读取到`dixie_fire_2021`候选热点60,013条、10分钟聚类11,704条。
- `Cresta Dam`是研究区名称，数据库中的正式事件编号和名称为`dixie_fire_2021 / Dixie Fire`。
- 沿用甲方ForeFire输入清单选择的候选：`2021-07-14T09:11:00Z`、经度`-121.38241`、纬度`39.87194`、EPSG:4326。
- 该点为FIRMS VIIRS热异常：置信度原值`n`、标准化0.5、FRP 5.61 MW、亮温I4 349.87 K、I5 293.96 K。
- 同一最早观测时刻、参考点5公里内共有5个热点，其中2个高置信度；最大FRP 19.34 MW、平均置信度0.66。
- 支撑主聚类包含4个点，中心`(-121.383205, 39.8747475)`，距候选319米，平均置信度0.7，代表点为高置信度且FRP 19.34 MW。

### 真实影像接入与复核

- 本机覆盖配置新增只读挂载`../data-sources/real -> /app/data-sources/real`，没有把3.18 GB影像复制进仓库。
- 六幅灾中瓦片中仅`dixie_fire_2021_s2_10m_during_r01c01.tif`覆盖候选坐标；实际验证为EPSG:32610、10米、B2/B3/B4/B8、3952×5198、int16。
- 阶段镶嵌产品没有单一拍摄时间，因此将影像引用`acquired_at`改为可空，采集区间保存在`product_fields.imagery`，不伪造精确时刻。
- 真实案例`visual-case-404da7bb3322b8e9b0d67839-v1`及影像资产已写入乙库，`is_simulated=false`。
- 生成1.5公里RGB与B8/B4/B3近红外裁片，源文件SHA-256为`0563a4c9efdf64e0e685678a5b971e25251fba1d65c3fef37a365c33ab80f9b5`。
- 首轮RGB复核：Qwen判未发现火焰、烟雾或火烧迹地，YOLO无目标框；保守融合为`uncertain`、置信度0.27。
- 双图复核：Qwen输出未通过结构一致性规则，YOLO仍无目标框；本轮保存为`failed`。因此没有生成`ConfirmedFirePoint`，不能宣称视觉确认成功。

### 真实数据暴露并修复的问题

- Sentinel-2 int16掩膜数组原先不能直接以NaN填充，真实裁剪首次返回500。
- 已在`image_processing/service.py`中先转float64再填充NaN，并将GeoTIFF回归样例改为int16；修复后真实影像裁剪成功。

### 向丙交付

- 交接文件保存在仓库外`个人工作/成员乙-交付丙/`，未推送到团队仓库。
- JSON：`dixie_cresta_forefire_ignition_provisional_v0.1.json`，SHA-256 `9D07322B234505F26DACEBCC2A3145AEA2F6E35A17ABA972C98BF305FC0AEF4F`。
- CSV：`dixie_cresta_forefire_ignition_provisional_v0.1.csv`，SHA-256 `CF4D98B046CAA14986FDE25C49673C9358047DCA004548A09722B6F03EA15423`。
- 两个文件均明确标记`provisional_not_visually_confirmed`，可供丙启动ForeFire临时调试，但不得当作乙确认后的真实火点。

### 验证结果

- `[通过]` 真实影像只读挂载、覆盖范围、波段、CRS、分辨率与数据类型检查。
- `[通过]` 候选登记、RGB/近红外裁剪、Qwen-VL、YOLO和融合结果实际写入PostGIS。
- `[通过]` 相关宿主机测试33项通过、1项因宿主机无Rasterio跳过。
- `[通过]` Docker完整回归99项全部通过。
- `[通过]` 交接JSON语法、CSV读取和两个文件SHA-256检查。
- `[通过]` 业务后端、专业检测和ForeFire服务均处于运行状态。

### 仍需甲补充

- 当前灾中影像只有阶段区间，没有具体场景拍摄时间，无法证明影像与09:11 UTC热异常同步。
- 当前没有B11/B12或热红外波段，不能用dNBR或热信号补强该点确认。
- 若要形成可正式交丙的`ConfirmedFirePoint`，需提供更接近候选观测时刻且能看到火焰/烟羽的影像，或可追溯的无人机、瞭望塔、现场图片。

## 2026-09-14｜Qwen辅助的课程演示自动确认

- 分支：`member/dengyujie136-eng`
- 最新提交：尚未提交
- 任务目标：保留Qwen-VL真实分析效果，但不让单张阶段镶嵌影像的负面结果阻断课程演示全链路；系统默认将上游已筛选候选点自动确认并交给丙。

### 已完成

- `POST /api/visual-verification/candidates/{visual_case_id}/review`仍依次执行专业目标检测和Qwen-VL，完整保留火焰、烟雾、场景类型、置信度与判断依据。
- 新增默认开启的`visual_auto_confirm_screened_candidates`课程演示规则；Qwen和目标检测结果可提高确认置信度，但不再否决上游已筛选热异常点。
- 自动确认最低置信度为`0.70`，直接落库为`confirmed`，坐标和确认时间同时写入`fire_confirmations`。
- 自动规则使用独立标识`course_demo_qwen_assisted_v1`，与严格的`qwen_yolo_fusion_v1`区分，不伪造Qwen原始判断。
- 不新增前端人工确认页面或确认按钮。
- 更新仓库外向丙交接文件，增加Qwen分析摘要和证据编号，最终状态保持`confirmed`。

### 配置与接口影响

- 新增配置`VISUAL_AUTO_CONFIRM_SCREENED_CANDIDATES`，默认`true`。
- 新增配置`VISUAL_AUTO_CONFIRM_MIN_CONFIDENCE`，默认`0.70`。
- 现有复核接口的请求字段不变；返回中的`visual`为Qwen原始结构化结果，`confirmation`为课程演示自动确认结果。

### 验证

- `[pass]` Qwen不支持火灾时，其结果和证据仍被保留，候选点自动确认为`confirmed`。
- `[pass]` 课程自动确认使用独立的`confirmation_method`和`rule_version`。
- `[pass]` 视觉复核、专业检测和遥感合同相关测试32项全部通过。

## 2026-09-14｜全球历史火灾通用火点筛选与入库

- 分支：`member/dengyujie136-eng`
- 最新提交：尚未提交
- 任务目标：将Dixie Fire的实验流程封装为由`event_id`驱动的通用能力，支持全球历史火灾数据库中任意事件。

### 通用处理链路

1. 数据Agent根据用户问题解析并返回`event_id`。
2. 甲的通用`fire.hotspot.candidate.v0.1`候选点通过现有导入接口入库。
3. 乙的筛选服务按时间窗口和地理距离形成时空聚类，优先选择最早达到最小点数的稳定聚类；若事件只有单点，可降级为最早单点。
4. 一键接口自动选择主影像、裁剪候选点范围、调用Qwen-VL和专业目标检测，并根据课程演示规则自动确认。
5. 结果写入通用`fire_confirmations`表，通过事件关联查询返回给ForeFire或多智能体编排层。

### 新增接口

- `POST /api/visual-verification/events/{event_id}/select-fire-points`：仅执行可解释的通用时空候选点筛选。
- `POST /api/visual-verification/events/{event_id}/auto-confirm-fire-points`：一次完成筛选、影像处理、Qwen分析、目标检测、自动确认和入库。
- `GET /api/visual-verification/events/{event_id}/confirmed-fire-points`：返回任意事件已入库的标准真实火点，供丙和丁调用。

### 数据和算法边界

- 筛选算法不包含`dixie_fire_2021`、`Cresta Dam`或固定经纬度。
- 默认参数为10分钟时间窗、2公里空间半径、最少2个热点；调用方可按事件调整。
- 只查询指定`event_id`的最新候选版本，排除上游已驳回或已过期数据，不会把不同火灾的火点混合。
- 确认结果保留`event_id`、`source_candidate_id`、坐标、置信度、证据编号、Qwen分析方法和`is_simulated`。

### 验证

- `[pass]` 使用`event-alpha`与`event-beta`两个不同地区、不同坐标的事件验证独立筛选。
- `[pass]` 时间范围筛选、单点降级和事件隔离查询。
- `[pass]` 三个通用API已进入FastAPI OpenAPI路由。

### 提交安全处理

- 发现根目录`.env`早期已被Git跟踪，其中包含已配置的Cesium令牌。
- 本次将`.env`从Git跟踪中移除并加入`.gitignore`，本机文件和配置值保持不变。
- `.env.example`继续作为不含真实API Key的共享配置模板。
- 为丙的ForeFire开发新增仓库内小型交接件`data/processed/confirmed_fire_points/dixie_fire_2021_confirmed_fire_point.json`；该文件是实际项目输入，不是个人文档，不包含原始影像或密钥。

## 2026-09-15｜候选火点视觉证据链五项优化与真实验收

- 分支：`main`
- 核心功能提交：`0aab1d2 Optimize visual fire evidence pipeline`
- 本地结果忽略提交：`9781e89 Ignore local visual pipeline results`
- 任务目标：复用甲的聚类成果，完善候选点与影像的自动匹配、多证据融合、PostGIS空间能力，并使用Dixie Fire灾前/灾中/灾后三时相真实影像完成Qwen-VL在线验收。

### 1. 复用甲的上游聚类

- 候选点契约新增`source_cluster_id`、`cluster_point_count`、`cluster_mean_confidence`和`cluster_max_frp_mw`。
- 当甲提供`source_cluster_id`时，乙直接按该编号组织候选组，不再执行第二次时空聚类。
- 仅对没有上游聚类编号的旧数据保留本地聚类兼容路径。
- Dixie Fire四条候选记录均复用聚类`dixie_fire_2021-cluster-20210714T0910Z--6070-1993`，筛选方法为`upstream_cluster_v1`。

### 2. 影像目录和候选点自动匹配

- 本机正式目录`data/raw/sentinel2/dixie_fire_2021/gee/`已放置18幅真实GeoTIFF，灾前、灾中、灾后各6幅，总计约3.181 GB；大影像继续由Git忽略。
- 新增`imagery_catalog`影像目录表和`candidate_imagery_matches`候选—影像匹配表。
- 候选导入时自动登记其影像引用，并按空间覆盖、时间接近度、云量、有效像元比例和空间分辨率计算匹配分数。
- 实际选中案例`visual-case-404da7bb3322b8e9b0d67839-v2`已匹配灾前、灾中、灾后三项代表影像，得分分别为`0.8462`、`0.85`和`0.55`。
- 新增事件影像目录与候选匹配查询接口，供遥感Agent和后续页面读取。

### 3. 多证据评分融合与持久化

- 新增`evidence_fusion_runs`表，保存各分量得分、权重、最终得分、决策、规则版本和证据编号。
- 融合权重固定为：热异常30%、上游聚类20%、Qwen视觉20%、专业检测10%、时相变化10%、影像质量10%。
- 真实端到端运行生成融合记录`fusion_8c57ce6ac04a42e19a89d27a57151001`，最终分数`0.6877`，规则版本`multi-evidence-fusion-v1`。
- 课程演示自动确认规则与严格融合判断继续分开保存，不篡改Qwen原始结论或融合分数。

### 4. PostGIS空间字段

- 为`visual_verification_cases.location_geom`和`fire_confirmations.location_geom`增加`POINT, SRID 4326`生成列。
- 为`imagery_catalog.footprint_geom`、`visual_image_derivatives.extent_geom`和`visual_findings.finding_geom`增加`GEOMETRY, SRID 4326`生成列。
- 五个空间字段均建立GiST索引，并由启动时幂等空间Schema安装逻辑兼容既有数据库。
- PostGIS实测可将Dixie候选点正确回读为`POINT(-121.38241 39.87194)`。

### 5. 灾前、灾中、灾后三时相Qwen联合分析

- Qwen提示词升级为`qwen-fire-multitemporal-v3`，明确要求分别识别灾前背景、灾中火焰/烟羽/异常和灾后火烧迹地，再给出联合结论。
- 模型请求为三幅图片附加`pre`、`during`、`post`时相标签；自动复核接口最多选择三个不同时相的可信派生图。
- 三幅真实GeoTIFF均完成候选点周边1.5公里裁剪，结果为`301×296`、源CRS `EPSG:32610`、`is_simulated=false`。
- 使用`qwen3-vl-flash`完成真实在线分析，模型返回`confirmed`、`wildfire_likelihood=0.95`、`image_quality=good`，并识别灾后大范围连续火烧迹地。
- 最终课程演示确认火点为经度`-121.38241`、纬度`39.87194`，确认方法`course_demo_qwen_assisted_v1`，结果已写入数据库。

### 新增查询接口

- `GET /api/visual-verification/events/{event_id}/imagery-catalog`
- `GET /api/visual-verification/candidates/{visual_case_id}/imagery-matches`
- `GET /api/visual-verification/candidates/{visual_case_id}/fusion-runs`

### 验证结果

- `[通过]` 五项优化按“代码检查—自动测试—Docker运行态—PostGIS数据”顺序逐项验收。
- `[通过]` 真实Dixie三时相一键流程：导入4条候选，复用甲的聚类，裁剪3幅影像，调用Qwen，融合入库并输出1个确认火点。
- `[通过]` 宿主机完整回归：108项测试全部通过，5项因宿主机未安装Rasterio而按条件跳过；Docker中的真实Rasterio裁剪已单独通过。
- `[通过]` `fire-agent-api`、`forefire-api`和PostGIS容器健康，前端容器正常运行。
- 本地完整结果：`data/local/results/dixie_fire_2021_visual_confirmation_latest.json`；`data/local/`已加入Git忽略规则，不作为团队源码或个人文档提交。

### 当前边界与提交状态

- 当前Sentinel-2仍只有B2、B3、B4、B8，三时相视觉判断可用，但标准NBR/dNBR仍需甲补充B11或B12。
- 本次专业目标检测服务不可用，结果中明确记录`professional_detector_unavailable`；Qwen三时相分析和课程演示确认不受影响。
- Qwen配置继续保存在仓库外个人配置文件中，未把密钥写入日志或Git。
- 核心五项优化提交`0aab1d2`已经进入远程`main`；提交`9781e89`因GitHub网络连接失败暂留本地，待网络恢复后推送。
