<template>
  <main class="command-center">
    <header class="command-header">
      <div>
        <span class="eyebrow">应急场景 / 空间决策</span>
        <h1>路径规划与资源调度</h1>
      </div>
      <EventSelector />
      <div class="header-actions">
        <span class="planning-status">火势依据：{{ store.spreadRunId ? '已生成' : '待推演' }}</span>
        <router-link class="header-link" to="/command-center">查看火势推演</router-link>
      </div>
    </header>

    <p v-if="store.error || localError" class="error-banner" role="alert">{{ localError || store.error }}</p>

    <section class="command-grid">
      <WorkflowStatusPanel :stages="planningStages" :active-stage="activeStage" :details="stageDetails" @select="activeStage = $event" />
      <div class="map-workspace">
        <CesiumMap ref="mapRef" :longitude="mapCenter[0]" :latitude="mapCenter[1]" :height="130000" :show-wind-field="false" />
        <div class="layer-control" aria-label="地图图层">
          <label v-for="layer in layerOptions" :key="layer.key"><input v-model="layer.visible" type="checkbox" @change="renderMap" />{{ layer.label }}</label>
        </div>
        <div v-if="editingMode !== 'NORMAL'" class="edit-notice"><strong>地图编辑</strong><span>点击地图设置{{ editModeLabel }}；按取消退出。</span><button type="button" @click="cancelMapEdit">取消</button></div>
      </div>
      <Teleport defer to="#business-panel"><CommandSituationPanel /></Teleport>
    </section>

    <section class="stage-workspace">
      <div class="stage-heading">
        <div><span class="eyebrow">规划工作台</span><h2>{{ stageLabel(activeStage) }}</h2></div>
        <div class="stage-state" :data-status="activeStageData.status"><span v-if="activeStageData.status === 'RUNNING'" class="spinner"></span>{{ statusLabel(activeStageData.status) }} · {{ activeStageData.message }}</div>
      </div>
      <div v-if="activeStageData.status === 'RUNNING'" class="progress-track"><span :style="{ width: `${activeStageData.progress}%` }"></span></div>

      <div v-if="activeStage === 'data_preparation'" class="readiness-grid">
        <article v-for="item in store.readiness?.items || []" :key="item.name"><div><strong>{{ item.name }}</strong><p>{{ item.description }}</p></div><span :data-state="item.status">{{ item.status }}</span></article>
        <p v-if="!store.readiness" class="empty">选择事件后读取 Data Catalog。</p>
      </div>

      <div v-else-if="activeStage === 'fire_verification'" class="module-layout">
        <div class="module-main">
          <div class="result-line"><span>当前候选</span><strong>候选火点 #1</strong></div>
          <div class="result-line"><span>视觉状态</span><strong>{{ activeStageData.metadata_json?.visual_status || '等待' }}</strong></div>
          <div class="result-line"><span>影像状态</span><strong>{{ activeStageData.metadata_json?.imagery_status || '等待' }}</strong></div>
          <div class="result-line"><span>当前结论</span><strong>{{ activeStageData.metadata_json?.review_state || store.workflow?.human_confirmation_state || 'AI_SUGGESTED' }}</strong></div>
          <div class="action-row">
            <button class="confirm" type="button" :disabled="busy || !store.confirmationId" @click="run(() => store.verify('confirm'))">确认火点</button>
            <button type="button" :disabled="busy" @click="run(() => store.verify('uncertain'))">需要进一步核验</button>
            <button class="danger" type="button" :disabled="busy" @click="run(() => store.verify('reject'))">驳回</button>
          </div>
        </div>
        <aside class="module-aside"><strong>专业分析</strong><p>Qwen-VL、专业检测和 Evidence Fusion 继续由原核验链负责。</p><router-link :to="professionalLink('/visual-verification')">查看视觉详细分析</router-link></aside>
      </div>

      <div v-else-if="activeStage === 'situation'" class="summary-grid">
        <article><span>可信火点</span><strong>{{ situationSummary.confirmed_fire_point ? '已确认' : '等待' }}</strong></article>
        <article><span>当前天气</span><strong>{{ situationPacket.environment?.wind_speed_m_s ?? '--' }} m/s</strong></article>
        <article><span>传播方向</span><strong>{{ spreadMeta.direction_deg ?? '--' }}°</strong></article>
        <article><span>缺失数据</span><strong>{{ missingReadiness.join('、') || '无' }}</strong></article>
      </div>

      <div v-else-if="activeStage === 'spread'" class="spread-module">
        <div class="spread-console">
          <section class="spread-input-panel">
            <div class="panel-heading"><div><span class="eyebrow">环境参数</span><h3>真实模型 What-if 推演</h3></div><span class="truth-label">参数调整会使当前场景、路径和建议失效</span></div>
            <div class="parameter-grid">
              <label>风速 <output>{{ spreadParameters.wind_speed_m_s.toFixed(1) }} m/s</output><input v-model.number="spreadParameters.wind_speed_m_s" type="range" min="0" max="30" step="0.5" /></label>
              <label>风向 <input v-model.number="spreadParameters.wind_direction_deg" type="number" min="0" max="359" step="5" /> <output>°</output></label>
              <label>温度 <input v-model.number="spreadParameters.temperature_c" type="number" min="-30" max="65" step="1" /> <output>℃</output></label>
              <label>湿度 <input v-model.number="spreadParameters.humidity_percent" type="number" min="0" max="100" step="1" /> <output>%</output></label>
              <label>降水 <input v-model.number="spreadParameters.precipitation_mm_h" type="number" min="0" max="200" step="0.1" /> <output>mm/h</output></label>
              <label>燃料湿度 <input v-model.number="spreadParameters.fuel_moisture" type="number" min="0.01" max="0.8" step="0.01" /></label>
              <label>FWI <input v-model.number="spreadParameters.fire_weather_index" type="number" min="0" max="100" step="1" /></label>
              <label>预测时长 <select v-model.number="spreadParameters.horizon_minutes"><option :value="60">1 小时</option><option :value="120">2 小时</option><option :value="360">6 小时</option><option :value="720">12 小时</option><option :value="1440">24 小时</option></select></label>
            </div>
            <div class="source-strip"><span>气象：{{ environmentSourceLabel }}</span><span>地形：Copernicus DEM</span><span>燃料：ESA WorldCover</span></div>
            <div class="action-row"><button class="primary" type="button" :disabled="busy || !canRerunSpread" @click="runSpreadRerun">{{ store.spreadRunId ? '重新推演' : '开始推演' }}</button><span v-if="!store.spreadRunId" class="module-note">首次推演由已确认火点后的现有工作流自动启动，避免创建孤立结果。</span><span v-else class="module-note">将使用当前已确认火点和上述参数调用既有栅格传播服务。</span></div>
          </section>
          <aside class="spread-provenance"><strong>计算边界</strong><p>气象参数用于本次人工 What-if 情景，真实传播计算仍读取当前确认火点、Copernicus DEM 与 ESA WorldCover。新火线完成后，空间风险和场景候选会自动更新。</p><p>资源、路线与 Commander 必须在新场景人工确认后重新生成。</p></aside>
        </div>
        <div class="spread-steps">
          <span :class="{ done: Boolean(store.confirmationId) }">可信火点</span>
          <span :class="{ done: activeStageData.status !== 'PENDING' }">小时气象</span>
          <span :class="{ done: activeStageData.status !== 'PENDING' }">DEM 高程</span>
          <span :class="{ done: activeStageData.status !== 'PENDING' }">可燃物</span>
          <span :class="{ active: activeStageData.status === 'RUNNING', done: activeStageData.status === 'COMPLETED' }">火势传播计算</span>
          <span :class="{ active: activeStageData.status === 'RUNNING', done: fireFrameCount > 0 }">火线序列</span>
          <span :class="{ active: firePlaybackPlaying, done: fireFrameCount > 0 }">地图动态展示</span>
        </div>
        <div v-if="activeStageData.status === 'RUNNING'" class="calculation-state"><i class="spinner"></i><span>{{ activeStageData.message || '正在执行真实火势计算，完成后自动播放火线序列。' }}</span></div>
        <template v-else-if="fireFrameCount">
          <div class="summary-grid wide"><article><span>计算引擎</span><strong>{{ spreadMeta.engine || '--' }}</strong></article><article><span>预测影响面积</span><strong>{{ currentFrameArea }}</strong></article><article><span>当前时间</span><strong>{{ fireFrameLabel }}</strong></article><article><span>扩散方向</span><strong>{{ currentFrameDirection }}</strong></article><article><span>面积增长速度</span><strong>{{ currentFrameGrowth }}</strong></article><article><span>火线时间步</span><strong>{{ fireFrameIndex + 1 }} / {{ fireFrameCount }}</strong></article></div>
          <div class="fire-playback">
            <button type="button" @click="toggleFirePlayback">{{ firePlaybackPlaying ? '暂停' : '播放' }}</button>
            <button type="button" @click="restartFirePlayback">重新播放</button>
            <label>速度 <select v-model.number="firePlaybackSpeed" @change="updatePlaybackSpeed"><option :value="0.5">0.5×</option><option :value="1">1×</option><option :value="2">2×</option></select></label>
            <input v-model.number="fireFrameIndex" type="range" min="0" :max="Math.max(0, fireFrameCount - 1)" aria-label="火线时间步" @input="selectFireFrame" />
          </div>
          <div class="timeline-scale"><span>起火时刻</span><span>{{ fireFinalLabel }}</span></div>
        </template>
        <p v-else class="empty">尚未生成真实火线时间步，不会以伪造中间火线替代。</p>
        <router-link :to="professionalLink('/fire-predict')" class="detail-link">查看火势推演详情</router-link>
      </div>

      <div v-else-if="activeStage === 'spatial_risk'" class="module-layout">
        <div class="module-main">
          <p class="lead">风险区已经叠加到同一 Cesium 地图，评分由火线强度、传播、增长、风向、地形、燃料和目标暴露共同计算。</p>
          <div class="risk-facts">
            <div><span>当前等级</span><strong>{{ spatialRisk.level }}</strong></div>
            <div><span>高风险区</span><strong>{{ spatialRisk.highCount }}</strong></div>
            <div><span>中风险区</span><strong>{{ spatialRisk.mediumCount }}</strong></div>
            <div><span>受威胁目标</span><strong>{{ spatialRisk.threatenedTargets }}</strong></div>
          </div>
          <p class="module-note">权重：火线强度 45%，传播半径 12%，增长 12%，风向 8%，坡度 7%，燃料 7%，目标暴露 9%。</p>
        </div>
        <aside class="module-aside warning"><strong>数据边界</strong><p>风险计算使用当前火线、气象、DEM 和燃料输入；居民点、设施与站点资产目前仍是演练资产，须接入真实业务图层后重新评估。</p></aside>
      </div>

      <div v-else-if="activeStage === 'scenario'" class="scenario-module">
        <div class="segmented"><button v-for="mode in scenarioModes" :key="mode.value" type="button" :class="{ active: scenarioMode === mode.value }" @click="scenarioMode = mode.value">{{ mode.label }}</button></div>
        <div v-if="scenarioMode === 'MANUAL'" class="manual-tools">
          <button type="button" @click="startMapEdit('SELECT_COMMAND_POST')">设置指挥点</button><span>{{ formatPoint(manual.command_post) }}</span>
          <button type="button" @click="startMapEdit('SELECT_STAGING_AREA')">设置集结点</button><span>{{ formatPoint(manual.staging_area) }}</span>
          <button type="button" @click="startMapEdit('ADD_RESOURCE_POINT')">增加资源点</button><span>{{ manual.resource_points.length }} 个</span>
          <button type="button" @click="startMapEdit('ADD_AFFECTED_POINT')">增加受灾点</button><span>{{ manual.affected_points.length }} 个 · 待核实</span>
          <button type="button" @click="startMapEdit('ADD_FIREFIGHTER_POINT')">标记救火人员位置</button><span>{{ manual.firefighter_points.length }} 个 · 待核实补给</span>
        </div>
        <div class="action-row"><button type="button" :disabled="busy || !store.spreadRunId" @click="regenerateScenario">生成候选</button><span class="truth-label">内部演练规则 v0.3；候选位置与路线均须人工确认</span></div>
        <div v-if="scenario" class="scenario-content">
          <div class="candidate-columns">
            <div><h3>指挥点候选</h3><label v-for="item in commandCandidates" :key="item.location_id" class="candidate-row"><input v-model="selectedCommand" type="radio" :value="item.location_id" /><span><strong>候选 {{ item.rank }} · 推荐指数 {{ Math.round(item.score * 100) }}%</strong><small>{{ candidateScoreDetail(item) }}</small></span></label></div>
            <div><h3>资源集结区候选</h3><label v-for="item in stagingCandidates" :key="item.location_id" class="candidate-row"><input v-model="selectedStaging" type="radio" :value="item.location_id" /><span><strong>候选 {{ item.rank }} · 推荐指数 {{ Math.round(item.score * 100) }}%</strong><small>{{ candidateScoreDetail(item) }}</small></span></label></div>
            <div><h3>火场作业接近点</h3><p>{{ operationApproach?.reason?.[0] || '等待火势推演结果。' }}</p><small>供灭火队伍从安全侧接近火场边缘；不是进入燃烧火线。</small></div>
            <div><h3>重点保护目标</h3><p>{{ protectedTarget?.reason?.[0] || '场景生成后显示。' }}</p><small>明确标注为演练重点保护目标，不代表真实居民区或设施。</small></div>
          </div>
          <div class="action-row"><button class="confirm" type="button" :disabled="busy || scenario.confirmed" @click="confirmCurrentScenario">{{ scenario.confirmed ? '场景已确认' : '确认场景并运行资源/路线' }}</button><span class="truth-label">{{ scenarioModeLabel(scenario.mode) }} · {{ scenario.size_class }} · 内部演练场景</span></div>
        </div>
      </div>

      <div v-else-if="activeStage === 'resource_dispatch'" class="resource-module">
        <p class="truth-label">演练资源库存：总量来自场景引擎，调度结论来自资源调度智能体，不代表真实消防库存。</p>
        <div class="resource-highlights"><article v-for="item in resourceHighlights" :key="item.type"><span>{{ resourceName(item.type) }}</span><strong>{{ item.total }}</strong><small>已部署 {{ item.allocated }} · 剩余 {{ item.remaining }}</small></article></div>
        <div class="inventory-table">
          <div class="inventory-head"><span>资源类型</span><span>总量</span><span>已分配</span><span>执行中</span><span>剩余</span><span>状态</span></div>
          <div v-for="item in resourceInventory" :key="item.type" class="inventory-row"><strong>{{ resourceName(item.type) }}</strong><span>{{ item.total }}</span><span>{{ item.allocated }}</span><span>{{ item.executing }}</span><span>{{ item.remaining }}</span><b>{{ item.status }}</b></div>
        </div>
        <p v-if="resourceSummary.shortage_count" class="warning-text">当前存在 {{ resourceSummary.shortage_count }} 项资源缺口，需要人工复核。</p>
        <p v-else class="resource-ok">{{ resourceDispatchNotice }}</p>
        <p class="module-note">水源当前只记录演练供水保障单元数量，未接入真实储备率，页面不会生成虚构百分比。</p>
        <section class="supply-requests"><h3>救火人员水与食物补给</h3><p>在“应急场景”中先标记人员位置，再录入补给需求。录入量仅作为规划请求，尚未自动匹配真实库存。</p>
          <div v-for="(point,index) in manual.firefighter_points" :key="index" class="supply-row"><strong>人员位置 {{ index+1 }} · {{ formatPoint(point) }}</strong><label>人数<input v-model.number="supplyRequests[index].people" type="number" min="0"></label><label>饮用水 L<input v-model.number="supplyRequests[index].water_liters" type="number" min="0"></label><label>食品份<input v-model.number="supplyRequests[index].food_packs" type="number" min="0"></label></div>
          <p v-if="!manual.firefighter_points.length">尚未标记救火人员位置。</p>
          <div v-else class="supply-total">待调配请求：{{ supplyRequests.reduce((sum,item)=>sum+Number(item.water_liters||0),0) }} L 水 · {{ supplyRequests.reduce((sum,item)=>sum+Number(item.food_packs||0),0) }} 份食品</div>
        </section>
      </div>

      <div v-else-if="activeStage === 'route_planning'" class="route-module">
        <div class="route-brief"><span>出发队伍</span><strong>演练灭火队伍 1</strong><span>任务终点</span><strong>火场作业接近点</strong><span>路线性质</span><strong>演练可达性路线</strong></div>
        <div class="summary-grid wide"><article><span>预计距离</span><strong>{{ routeSummary.distance_km == null ? '--' : Number(routeSummary.distance_km).toFixed(2) + ' km' }}</strong></article><article><span>预计到达</span><strong>{{ routeSummary.estimated_eta_minutes == null ? '--' : Number(routeSummary.estimated_eta_minutes).toFixed(1) + ' 分钟' }}</strong></article><article><span>候选路线</span><strong>{{ routeSummary.candidate_count ?? '--' }}</strong></article><article><span>路线风险</span><strong>{{ routeSummary.max_risk_score == null ? '--' : Number(routeSummary.max_risk_score).toFixed(2) }}</strong></article></div>
        <div class="route-explanation"><div><span>任务</span><strong>灭火队伍 1 → 火场作业接近点</strong></div><div><span>算法</span><strong>{{ routeAlgorithm }}</strong></div><div><span>输入</span><strong>演练可达性图、火势预测半径派生风险、距离与预计通行时间</strong></div><div><span>输出</span><strong>路径长度、预计到达时间、路径风险值</strong></div></div>
        <p class="route-copy">选择依据：路线从演练队伍位置出发，经安全中继点接近火场边缘外侧。当前图网络的路段坡度为场景默认值，未接入真实 OSM 路网或 DEM 路段坡度，因此不代表真实道路导航。</p>
        <div class="route-targets"><strong>新增受灾点</strong><span>{{ manual.affected_points.length }} 个待核实点位</span><p>地图上新增的受灾点尚未进入现有路线算法；当前路线仍以已确认演练作业接近点为终点。</p></div>
      </div>

      <div v-else-if="activeStage === 'commander'" class="commander-module">
        <div class="decision-copy">
          <section class="decision-section"><span>当前态势</span><h3>{{ commanderSituation }}</h3></section>
          <section class="decision-section"><span>风险分析</span><p>{{ commanderRisk }}</p></section>
          <section class="decision-section"><span>处置建议</span><ol><li v-for="action in commanderDecision.actions || []" :key="action">{{ action }}</li></ol></section>
          <p v-if="commanderDecision.limitations?.length" class="module-note"><strong>限制：</strong>{{ commanderDecision.limitations.join('；') }}</p>
        </div>
        <div class="action-row"><button class="confirm" type="button" :disabled="busy || !store.decisionRunId" @click="run(() => store.reviewCommander('approve'))">接受辅助决策</button><button type="button" :disabled="busy" @click="run(() => store.reviewCommander('regenerate'))">调整后重新计算</button><button type="button" :disabled="busy" @click="run(() => store.reviewCommander('revise'))">返回场景配置</button></div>
        <p class="truth-label">人工确认仅表示接受辅助/演练方案，不表示已下达真实救援命令。</p>
      </div>

      <details class="provenance"><summary>数据来源与技术详情</summary><dl><template v-for="item in provenanceRows" :key="item.label"><dt>{{ item.label }}</dt><dd>{{ item.value || '--' }}</dd></template></dl></details>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import CesiumMap from '../components/CesiumMap.vue'
import EventSelector from '../components/command/EventSelector.vue'
import CommandSituationPanel from '../components/command/CommandSituationPanel.vue'
import WorkflowStatusPanel from '../components/command/WorkflowStatusPanel.vue'
import { useIncidentContextStore, type WorkflowStage } from '../stores/incidentContextStore'

const store = useIncidentContextStore()
const mapRef = ref<any>(null)
const activeStage = ref('scenario')
const horizonMinutes = ref(360)
const busy = ref(false)
const localError = ref('')
const fireFrameIndex = ref(0)
const fireFrameCount = ref(0)
const firePlaybackPlaying = ref(false)
const firePlaybackSpeed = ref(1)
const spreadParameters = reactive({
  wind_speed_m_s: 0,
  wind_direction_deg: 0,
  temperature_c: 0,
  humidity_percent: 0,
  precipitation_mm_h: 0,
  fuel_moisture: 0.1,
  fire_weather_index: 0,
  horizon_minutes: 360,
})
let spreadParametersRunId = ''
const scenarioMode = ref<'RECOMMENDED' | 'MANUAL' | 'EXERCISE'>('RECOMMENDED')
const selectedCommand = ref('')
const selectedStaging = ref('')
const editingMode = ref<'NORMAL' | 'SELECT_COMMAND_POST' | 'SELECT_STAGING_AREA' | 'ADD_RESOURCE_POINT' | 'ADD_AFFECTED_POINT' | 'ADD_FIREFIGHTER_POINT'>('NORMAL')
const manual = reactive<{ command_post: [number, number] | null; staging_area: [number, number] | null; resource_points: [number, number][]; affected_points: [number, number][]; firefighter_points: [number, number][] }>({ command_post: null, staging_area: null, resource_points: [], affected_points: [], firefighter_points: [] })
const supplyRequests = reactive<{people:number;water_liters:number;food_packs:number}[]>([])
const layerOptions = reactive([{ key: 'fire', label: '火点', visible: true }, { key: 'front', label: '火线', visible: true }, { key: 'risk', label: '风险区', visible: true }, { key: 'scenario', label: '救援场景', visible: true }, { key: 'route', label: '救援路线', visible: true }])
const stageNames = ['data_preparation', 'fire_verification', 'situation', 'spread', 'spatial_risk', 'scenario', 'resource_dispatch', 'route_planning', 'commander']
const labels: Record<string, string> = { data_preparation: '数据准备', fire_verification: '火点核验', situation: '态势评估', spread: '火势推演', spatial_risk: '空间风险', scenario: '应急场景', resource_dispatch: '资源调度', route_planning: '路径规划', commander: '指挥决策' }
const scenarioModes = [{ value: 'RECOMMENDED' as const, label: '系统推荐' }, { value: 'MANUAL' as const, label: '地图人工配置' }, { value: 'EXERCISE' as const, label: '自动演练场景' }]
const emptyStage = (name: string): WorkflowStage => ({ stage: name, status: 'PENDING', progress: 0, message: '等待创建工作流。', metadata_json: {} })
const displayStages = computed(() => store.stages.length ? store.stages : stageNames.map(emptyStage))
const planningStageNames = ['scenario', 'resource_dispatch', 'route_planning', 'commander']
const planningStages = computed(() => displayStages.value.filter((item) => planningStageNames.includes(item.stage)))
const activeStageData = computed(() => displayStages.value.find((item) => item.stage === activeStage.value) || emptyStage(activeStage.value))
const mapCenter = computed<[number, number]>(() => store.selectedEvent?.center || [-121.38, 39.87])
const scenario = computed(() => store.workflow?.scenario || null)
const commandCandidates = computed(() => scenario.value?.locations?.filter((item: any) => item.type === 'command_post') || [])
const stagingCandidates = computed(() => scenario.value?.locations?.filter((item: any) => item.type === 'staging_area') || [])
const operationApproach = computed(() => scenario.value?.locations?.find((item: any) => item.type === 'operations_approach') || null)
const protectedTarget = computed(() => scenario.value?.locations?.find((item: any) => item.type === 'protected_target') || null)
const rescueTeams = computed(() => scenario.value?.locations?.filter((item: any) => item.type === 'rescue_team') || [])
const spreadMeta = computed(() => displayStages.value.find((item) => item.stage === 'spread')?.metadata_json || {})
const spreadEnvironment = computed<any>(() => spreadMeta.value.environment || currentFireFrame.value?.properties?.environment || {})
const canRerunSpread = computed(() => Boolean(
  store.workflowRunId
  && store.spreadRunId
  && store.confirmationId
  && activeStageData.value.status !== 'RUNNING'
))
const environmentSourceLabel = computed(() => {
  if (spreadMeta.value.parameter_source === 'command_center_manual_what_if') {
    return '指挥工作台人工情景参数（基线为成员甲小时气象）'
  }
  return spreadMeta.value.weather_source || '成员甲小时气象'
})
const situationMeta = computed(() => displayStages.value.find((item) => item.stage === 'situation')?.metadata_json || {})
const situationPacket = computed(() => situationMeta.value.situation_packet || {})
const situationSummary = computed(() => situationMeta.value.situation_summary || {})
const missingReadiness = computed(() => (store.readiness?.items || []).filter((item: any) => item.status !== 'Available').map((item: any) => item.name))
const resourceSummary = computed(() => store.workflow?.artifacts?.resource_plan?.result?.resource_summary || {})
const spatialRisk = computed(() => {
  const summary = displayStages.value.find((item) => item.stage === 'spatial_risk')?.metadata_json?.summary || {}
  const areas = summary.risk_areas || {}
  const label = ({ low: '低', medium: '中', high: '高', extreme: '极高' } as Record<string, string>)[String(summary.risk_level || '')] || '等待计算'
  return {
    level: label,
    highCount: areas.high_count ?? '--',
    mediumCount: areas.medium_count ?? '--',
    threatenedTargets: summary.threatened_target_count ?? '--',
  }
})
const routeResult = computed(() => store.workflow?.artifacts?.route?.result || {})
const routeSummary = computed(() => {
  const result = routeResult.value
  const recommended = result.recommended_route || {}
  return {
    ...(result.route_summary || {}),
    distance_km: recommended.distance_km,
    estimated_eta_minutes: recommended.estimated_travel_time_minutes,
    max_risk_score: recommended.risk_score,
  }
})
const resourcePlanResult = computed(() => store.workflow?.artifacts?.resource_plan?.result || {})
const resourceInventory = computed(() => {
  const selected = resourcePlanResult.value?.selected_resources || []
  return (scenario.value?.resources || []).map((item: any) => {
    const total = Number(item.quantity || 0)
    const allocated = selected
      .filter((entry: any) => entry.resource_type === item.type)
      .reduce((sum: number, entry: any) => sum + Number(entry.quantity ?? entry.allocated_quantity ?? 1), 0)
    return { type: item.type, total, allocated: Math.min(total, allocated), executing: allocated ? Math.min(total, allocated) : 0, remaining: Math.max(0, total - allocated), status: allocated ? '已纳入调度' : '可用' }
  })
})
const resourceHighlights = computed(() => resourceInventory.value.filter((item: any) => ['fire_team', 'fire_engine', 'uav', 'water_supply'].includes(item.type)))
const resourceDispatchNotice = computed(() => resourceSummary.value?.selected_count != null ? '当前资源满足本次演练任务，可进入人工指挥复核。' : '等待资源调度计算。')
const routeAlgorithm = computed(() => {
  const algorithm = String(routeResult.value?.recommended_route?.algorithm || '')
  if (algorithm === 'risk_aware_astar') return '风险感知 A* 可达性路径规划'
  if (algorithm === 'astar') return 'A* 可达性路径规划'
  return '等待路线计算'
})
const commanderDecision = computed(() => displayStages.value.find((item) => item.stage === 'commander')?.metadata_json?.decision || {})
const fireFrames = computed<any[]>(() => {
  const frames = store.workflow?.artifacts?.fire_front?.features || []
  return [...frames].sort((left, right) => Number(left.properties?.elapsed_seconds || 0) - Number(right.properties?.elapsed_seconds || 0))
})
const currentFireFrame = computed(() => fireFrames.value[Math.min(fireFrameIndex.value, Math.max(0, fireFrames.value.length - 1))] || null)
const previousFireFrame = computed(() => fireFrames.value[Math.max(0, fireFrameIndex.value - 1)] || null)
const fireFrameLabel = computed(() => currentFireFrame.value ? '+ ' + String(currentFireFrame.value.properties?.elapsed_minutes ?? 0) + ' 分钟' : '等待火线序列')
const fireFinalLabel = computed(() => fireFrames.value.length ? '+ ' + String(fireFrames.value[fireFrames.value.length - 1]?.properties?.elapsed_minutes ?? 0) + ' 分钟' : '--')
const currentFrameArea = computed(() => currentFireFrame.value?.properties?.area_km2 != null ? Number(currentFireFrame.value.properties.area_km2).toFixed(2) + ' km²' : metric(spreadMeta.value.final_area_km2, 'km²'))
const currentFrameDirection = computed(() => {
  const direction = currentFireFrame.value?.properties?.spread_direction_deg ?? spreadMeta.value.direction_deg
  return direction == null ? '--' : Math.round(Number(direction)) + '°'
})
const currentFrameGrowth = computed(() => {
  const current = currentFireFrame.value?.properties || {}
  const previous = previousFireFrame.value?.properties || {}
  const areaDelta = Number(current.area_km2) - Number(previous.area_km2)
  const minuteDelta = Number(current.elapsed_minutes) - Number(previous.elapsed_minutes)
  if (!previousFireFrame.value || !Number.isFinite(areaDelta) || !Number.isFinite(minuteDelta) || minuteDelta <= 0) return '--'
  return (areaDelta / minuteDelta * 60).toFixed(3) + ' km²/小时'
})
const stageDetails = computed<Record<string, string>>(() => {
  if (fireFrameCount.value) return { spread: '火势推演 T' + fireFrameLabel.value }
  if (displayStages.value.find((item) => item.stage === 'spread')?.status === 'RUNNING') return { spread: '火势推演计算中' }
  return {}
})
const commanderSituation = computed(() => {
  const area = currentFrameArea.value === '--' ? metric(spreadMeta.value.final_area_km2, 'km²') : currentFrameArea.value
  return '当前火场预测影响面积 ' + area + '，主要扩散方向 ' + currentFrameDirection.value + '，空间风险为 ' + spatialRisk.value.level + '。'
})
const commanderRisk = computed(() => {
  const horizon = Number(store.workflow?.horizon_minutes || horizonMinutes.value) / 60
  return '未来 ' + horizon + ' 小时内，应重点关注模型传播方向及风险区边界。该结论综合当前火势预测、空间风险、小时气象与资源状态生成；目标资产为演练数据时需现场复核。'
})
const editModeLabel = computed(() => ({ SELECT_COMMAND_POST: '指挥点', SELECT_STAGING_AREA: '集结点', ADD_RESOURCE_POINT: '资源点', ADD_AFFECTED_POINT: '受灾点', ADD_FIREFIGHTER_POINT: '救火人员位置', NORMAL: '' }[editingMode.value]))
const provenanceRows = computed(() => [{ label: '事件标识', value: store.eventId }, { label: '候选火点标识', value: store.candidateId }, { label: '视觉核验标识', value: store.visualCaseId }, { label: '确认记录标识', value: store.confirmationId }, { label: '工作流标识', value: store.workflowRunId }, { label: '火势推演标识', value: store.spreadRunId }, { label: '空间分析标识', value: store.spatialAnalysisId }, { label: '演练场景标识', value: store.scenarioId }, { label: '资源计划标识', value: store.resourcePlanId }, { label: '路线计划标识', value: store.routePlanId }, { label: '决策标识', value: store.decisionRunId }, { label: '建议包标识', value: store.recommendationId }])

function stageLabel(stage: string) { return labels[stage] || stage }
function scenarioModeLabel(mode: string) { return ({ RECOMMENDED: '系统推荐', MANUAL: '人工配置', EXERCISE: '自动演练' } as Record<string, string>)[mode] || '内部演练' }
function statusLabel(status: string) { return ({ PENDING: '等待', READY: '就绪', RUNNING: '运行中', WAITING_FOR_INPUT: '等待人工输入', COMPLETED: '已完成', FAILED: '失败', UNAVAILABLE: '不可用', SKIPPED: '已跳过' } as Record<string, string>)[status] || status }
function metric(value: any, unit: string) { return value == null ? '--' : `${Number(value).toFixed(1)} ${unit}` }
function pretty(value: any) { return JSON.stringify(value, null, 2) }
function formatPoint(value: [number, number] | null) { return value ? `${value[0].toFixed(5)}, ${value[1].toFixed(5)}` : '未设置' }
function candidateScoreDetail(item: any) {
  const rank = Number(item.rank || 1)
  const score = Math.round(Number(item.score || 0) * 100)
  return '排序得分 ' + score + '%：95 分基础值减去第 ' + rank + ' 名候选的 ' + (rank * 7) + ' 分。准入条件为火场外安全边界、反传播方向或侧翼及动态安全距离；尚未纳入实测坡度、真实道路可达性或真实库存权重。'
}
function resourceName(value: string) { return ({ fire_team: '灭火队伍', fire_engine: '消防车辆', firefighter_unit: '消防单元', uav: '无人机', medical: '医疗保障', water_supply: '供水保障', evacuation_support: '疏散保障', ground_vehicle: '地面保障车辆' } as Record<string, string>)[value] || value }
function professionalLink(path: string) { return { path, query: { event: store.eventId, workflow: store.workflowRunId || undefined } } }
function layerVisible(key: string) { return layerOptions.find((item) => item.key === key)?.visible }
function toggleFirePlayback() { if (firePlaybackPlaying.value) mapRef.value?.pauseFireTimeline(); else mapRef.value?.playFireTimeline() }
function restartFirePlayback() { mapRef.value?.resetFireTimeline(); fireFrameIndex.value = 0; mapRef.value?.playFireTimeline() }
function updatePlaybackSpeed() { mapRef.value?.setFireTimelineDuration(6400 / firePlaybackSpeed.value) }
function selectFireFrame() {
  mapRef.value?.pauseFireTimeline()
  const maxIndex = Math.max(1, fireFrameCount.value - 1)
  mapRef.value?.setFireTimelineProgress((fireFrameIndex.value / maxIndex) * 100)
}

function parameterNumber(value: any, fallback: number) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}
function seedSpreadParameters() {
  if (!store.spreadRunId || spreadParametersRunId === store.spreadRunId) return
  const environment = spreadEnvironment.value
  spreadParameters.wind_speed_m_s = parameterNumber(environment.wind_speed_m_s, 0)
  spreadParameters.wind_direction_deg = parameterNumber(environment.wind_direction_deg, 0)
  spreadParameters.temperature_c = parameterNumber(environment.temperature_c, 0)
  spreadParameters.humidity_percent = parameterNumber(environment.humidity_percent, 0)
  spreadParameters.precipitation_mm_h = parameterNumber(environment.precipitation_mm_h, 0)
  spreadParameters.fuel_moisture = parameterNumber(environment.fuel_moisture, 0.1)
  spreadParameters.fire_weather_index = parameterNumber(environment.fire_weather_index, 0)
  spreadParameters.horizon_minutes = parameterNumber(store.workflow?.horizon_minutes, 360)
  horizonMinutes.value = spreadParameters.horizon_minutes
  spreadParametersRunId = store.spreadRunId
}
async function runSpreadRerun() {
  if (!canRerunSpread.value) return
  await run(async () => {
    await store.rerunSpread({ ...spreadParameters })
    activeStage.value = 'spread'
  })
}

async function run(action: () => Promise<any> | undefined) { busy.value = true; localError.value = ''; try { await action() } catch (cause: any) { localError.value = cause?.message || '操作失败。' } finally { busy.value = false } }
async function regenerateScenario() { await run(() => store.generateScenario({ mode: scenarioMode.value, command_post: manual.command_post, staging_area: manual.staging_area, resource_points: manual.resource_points })) }
async function confirmCurrentScenario() { await run(() => store.confirmScenario({ command_location_id: selectedCommand.value || undefined, staging_location_id: selectedStaging.value || undefined })) }

function startMapEdit(mode: 'SELECT_COMMAND_POST' | 'SELECT_STAGING_AREA' | 'ADD_RESOURCE_POINT' | 'ADD_AFFECTED_POINT' | 'ADD_FIREFIGHTER_POINT') {
  editingMode.value = mode
  mapRef.value?.beginMapPointSelection(mode === 'ADD_AFFECTED_POINT' || mode === 'ADD_FIREFIGHTER_POINT' ? 'ADD_RESOURCE_POINT' : mode, (point: any) => {
    const value: [number, number] = [point.longitude, point.latitude]
    if (mode === 'SELECT_COMMAND_POST') manual.command_post = value
    else if (mode === 'SELECT_STAGING_AREA') manual.staging_area = value
    else if (mode === 'ADD_AFFECTED_POINT') manual.affected_points.push(value)
    else if (mode === 'ADD_FIREFIGHTER_POINT') { manual.firefighter_points.push(value); supplyRequests.push({people:0,water_liters:0,food_packs:0}) }
    else manual.resource_points.push(value)
    const pointName = editModeLabel.value || '人工点位'
    editingMode.value = 'NORMAL'
    mapRef.value?.addDemoPoint({ name: pointName, position: value, color: mode === 'ADD_AFFECTED_POINT' ? '#fb7185' : mode === 'ADD_FIREFIGHTER_POINT' ? '#34d399' : '#f4d35e', size: 12 })
  })
}
function cancelMapEdit() { mapRef.value?.cancelMapPointSelection(); editingMode.value = 'NORMAL' }

function renderAreaGeometry(geometry: any, name: string, color: string) {
  if (!geometry) return
  if (geometry.type === 'Polygon') mapRef.value?.addDemoArea({ name, coordinates: geometry.coordinates, color })
  if (geometry.type === 'MultiPolygon') geometry.coordinates.forEach((polygon: any, index: number) => mapRef.value?.addDemoArea({ name: `${name}-${index + 1}`, coordinates: polygon, color }))
}
function renderMap(autoPlay = false) {
  if (!mapRef.value) return
  const artifacts = store.workflow?.artifacts || {}
  mapRef.value.clearHotspots(); mapRef.value.clearFireFronts(); mapRef.value.clearDemoEntities()
  if (layerVisible('fire') && artifacts.candidate_point) mapRef.value.addHotspotGeoJson({ type: 'FeatureCollection', features: [{ type: 'Feature', geometry: artifacts.candidate_point, properties: { name: '候选火点' } }] })
  if (layerVisible('fire') && artifacts.confirmed_point) mapRef.value.addDemoPoint({ name: '可信火点', position: artifacts.confirmed_point.coordinates, color: '#ff4d3d', label: '可信火点', size: 14 })
  if (layerVisible('front') && artifacts.fire_front?.features?.length) {
    fireFrameCount.value = fireFrames.value.length
    mapRef.value.addFireFrontTimeline(artifacts.fire_front, {
      autoPlay,
      durationMs: 6400 / firePlaybackSpeed.value,
      onFrame: (payload: any) => { fireFrameIndex.value = Math.min(payload.index, Math.max(0, fireFrames.value.length - 1)) },
      onPlaybackState: (playing: boolean) => { firePlaybackPlaying.value = playing },
      onComplete: () => { firePlaybackPlaying.value = false },
    })
  } else {
    fireFrameCount.value = 0
    fireFrameIndex.value = 0
  }
  if (layerVisible('risk')) (artifacts.risk?.features || []).forEach((feature: any, index: number) => renderAreaGeometry(feature.geometry, `风险区-${index + 1}`, feature.properties?.severity === 'high' ? '#e34234' : '#f2a93b'))
  if (layerVisible('scenario')) {
    const styles: Record<string, { color: string, label: string, symbol: any }> = {
      command_post: { color: '#5cbcff', label: '指挥点', symbol: 'command' },
      staging_area: { color: '#f7c948', label: '资源集结区', symbol: 'staging' },
      rescue_team: { color: '#55d38a', label: '演练灭火队伍', symbol: 'team' },
      operations_approach: { color: '#ff7b39', label: '火场作业接近点', symbol: 'approach' },
      protected_target: { color: '#e76f51', label: '演练重点保护目标', symbol: 'target' },
    }
    ;(artifacts.scenario_locations || []).forEach((item: any) => {
      const style = styles[item.type]
      if (!style) return
      const candidate = ['command_post', 'staging_area'].includes(item.type) && !item.selected
      mapRef.value.addDemoPoint({
        name: style.label,
        position: [item.longitude, item.latitude],
        color: candidate ? '#78909c' : style.color,
        label: candidate ? style.label + '候选 ' + String(item.rank) : style.label,
        size: item.type === 'rescue_team' ? 14 : 17,
        symbol: style.symbol,
      })
    })
  }
  manual.affected_points.forEach((point,index)=>mapRef.value.addDemoPoint({name:'待核实受灾点 '+(index+1),position:point,color:'#fb7185',size:12}))
  manual.firefighter_points.forEach((point,index)=>mapRef.value.addDemoPoint({name:'救火人员位置 '+(index+1),position:point,color:'#34d399',size:12}))
  const route = artifacts.route?.geometry
  if (layerVisible('route') && route?.type === 'LineString') mapRef.value.addDemoRoute({ name: '演练灭火作业路线', coordinates: route.coordinates, color: '#65bfff', width: 5, arrow: true })
  const point = artifacts.confirmed_point?.coordinates || scenario.value?.summary?.ignition && [scenario.value.summary.ignition.longitude, scenario.value.summary.ignition.latitude]
  if (point) mapRef.value.flyTo({ center: point, height: 90000 })
}

watch(() => store.workflow?.current_stage, (stage) => { if (stage && planningStageNames.includes(stage)) activeStage.value = stage })
watch(() => store.workflow?.scenario, (value) => { if (!value) return; selectedCommand.value = value.locations?.find((item: any) => item.type === 'command_post' && item.selected)?.location_id || value.locations?.find((item: any) => item.type === 'command_post')?.location_id || ''; selectedStaging.value = value.locations?.find((item: any) => item.type === 'staging_area' && item.selected)?.location_id || value.locations?.find((item: any) => item.type === 'staging_area')?.location_id || '' }, { deep: true })
watch(() => store.spreadRunId, () => {
  seedSpreadParameters()
  nextTick(() => { renderMap(true) })
})
watch(() => [store.confirmationId, store.spatialAnalysisId, store.scenarioId, store.resourcePlanId, store.routePlanId].join(':'), () => nextTick(renderMap))

onMounted(async () => { await store.loadEvents(); await Promise.all([store.loadReadiness(), store.loadLatestWorkflow()]); seedSpreadParameters(); if (store.workflow?.status === 'RUNNING') store.startPolling(); setTimeout(() => renderMap(Boolean(store.spreadRunId)), 900) })
onUnmounted(() => { store.stopPolling(); cancelMapEdit() })
</script>

<style scoped>
.command-center { height: 100%; min-height: 0; display: grid; grid-template-rows: auto minmax(390px, 1fr) minmax(24vh, 30vh); overflow: hidden; color: #e7edf0; background: #0b1821; --line: #29404d; }
.command-header { display: grid; grid-template-columns: minmax(260px, 1fr) auto minmax(350px, 1fr); gap: 22px; align-items: center; min-height: 92px; padding: 14px 24px; border-bottom: 1px solid var(--line); background: #0e1d27; }
.eyebrow { color: #77909d; font-size: 13px; font-weight: 800; }
h1 { margin: 3px 0 0; font-size: 28px; letter-spacing: 0; } h2 { margin: 4px 0 0; font-size: 21px; } h3 { margin: 0 0 12px; font-size: 18px; }
.header-actions { display: flex; align-items: end; justify-content: flex-end; gap: 10px; }.header-actions label { color: #9fb0b9; font-size: 13px; }.header-actions select { display: block; height: 40px; margin-top: 4px; padding: 0 10px; border: 1px solid #526878; border-radius: 4px; color: #fff; background: #142532; font-size: 15px; }
button { min-height: 40px; padding: 0 14px; border: 1px solid #526878; border-radius: 4px; color: #dce7eb; background: #1b303c; font-size: 15px; font-weight: 700; cursor: pointer; } button:hover { border-color: #74a9c5; background: #244252; } button:disabled { cursor: not-allowed; opacity: .45; }.primary, .confirm { border-color: #20845c; background: #176a4a; }.danger { border-color: #9b4742; background: #71332f; }
.error-banner { margin: 0; padding: 11px 24px; border-bottom: 1px solid #8d3f3b; color: #ffd0cc; background: #5f2926; font-size: 14px; }
.command-grid { display: grid; grid-template-columns: 210px minmax(540px, 1fr) 290px; min-height: 0; border-bottom: 1px solid var(--line); }.map-workspace { position: relative; min-width: 0; min-height: 0; overflow: hidden; }.map-workspace :deep(.cesium-map-shell) { height: 100%; }
.layer-control { position: absolute; z-index: 4; top: 12px; left: 12px; display: flex; flex-wrap: wrap; gap: 3px; max-width: calc(100% - 24px); padding: 5px; border: 1px solid #526878; background: rgba(10, 24, 33, .9); }.layer-control label { padding: 5px 8px; color: #dce5e9; font-size: 13px; white-space: nowrap; }.layer-control input { margin-right: 5px; }
.edit-notice { position: absolute; z-index: 5; right: 14px; bottom: 14px; display: grid; grid-template-columns: auto 1fr auto; gap: 10px; align-items: center; padding: 10px 12px; border: 1px solid #e6a93d; background: rgba(35, 31, 18, .94); font-size: 14px; }.edit-notice button { min-height: 34px; }
.stage-workspace { min-height: 0; max-height: 34vh; overflow: auto; padding: 10px 24px 14px; background: #0f202a; }.stage-heading { display: flex; justify-content: space-between; gap: 24px; align-items: center; padding-bottom: 8px; border-bottom: 1px solid var(--line); }.stage-state { display: flex; align-items: center; gap: 8px; max-width: 58%; color: #a9bac2; font-size: 14px; text-align: right; }.stage-state[data-status='FAILED'] { color: #ff8e86; }.spinner { width: 17px; height: 17px; flex: 0 0 17px; border: 2px solid #536a77; border-top-color: #67b8e8; border-radius: 50%; animation: spin .8s linear infinite; }@keyframes spin { to { transform: rotate(360deg); } }.progress-track { height: 4px; margin-bottom: 9px; background: #223641; }.progress-track span { display: block; height: 100%; background: #43a77b; transition: width .3s; }
.readiness-grid, .summary-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 1px; margin-top: 18px; background: var(--line); }.readiness-grid article, .summary-grid article { display: flex; justify-content: space-between; gap: 12px; min-height: 88px; padding: 15px; background: #152934; }.readiness-grid strong { font-size: 17px; }.readiness-grid p { margin: 6px 0 0; color: #8fa2ac; font-size: 14px; }.readiness-grid article > span { align-self: flex-start; color: #63d19b; font-size: 14px; font-weight: 800; }.readiness-grid article > span[data-state='Missing'] { color: #ef8b80; }.summary-grid article { display: block; }.summary-grid span, .summary-grid strong { display: block; }.summary-grid span { color: #91a5af; font-size: 14px; }.summary-grid strong { margin-top: 9px; color: #fff; font-size: 24px; overflow-wrap: anywhere; }
.module-layout { display: grid; grid-template-columns: minmax(0, 1fr) 320px; gap: 12px; margin-top: 10px; }.module-main, .module-aside, .decision-copy { padding: 12px; border: 1px solid var(--line); background: #142731; }.module-aside { font-size: 15px; line-height: 1.5; }.module-aside p { color: #a8b8c0; }.module-aside a, .detail-link { color: #66b8e9; }.module-aside.warning { border-left: 3px solid #d49a36; }.result-line { display: flex; justify-content: space-between; gap: 18px; padding: 7px 0; border-bottom: 1px solid var(--line); font-size: 15px; }.result-line span { color: #91a4ae; }.action-row { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-top: 10px; }.lead { font-size: 16px; line-height: 1.55; }.result-json { max-height: 120px; overflow: auto; padding: 10px; color: #c9d8df; background: #0a1820; font-size: 13px; }
.scenario-module, .commander-module { margin-top: 10px; }.segmented { display: inline-flex; border: 1px solid #526878; }.segmented button { border: 0; border-right: 1px solid #526878; border-radius: 0; background: #142731; }.segmented button:last-child { border-right: 0; }.segmented button.active { color: #fff; background: #2d647e; }.manual-tools { display: grid; grid-template-columns: 180px 1fr; gap: 8px 12px; align-items: center; margin-top: 10px; padding: 10px; border: 1px solid var(--line); }.manual-tools span { color: #aabac2; font-size: 14px; }.truth-label { color: #e9bd62; font-size: 14px; }.candidate-columns { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 1px; margin-top: 10px; background: var(--line); }.candidate-columns > div { min-width: 0; padding: 10px; background: #142731; }.candidate-columns > div p { margin: 7px 0 0; color: #9bb0ba; font-size: 13px; line-height: 1.45; }.candidate-columns > div > small { display: block; margin-top: 5px; color: #8da3ad; font-size: 11px; line-height: 1.35; }.candidate-row { display: grid; grid-template-columns: 20px 1fr; gap: 9px; align-items: start; padding: 7px 0; border-top: 1px solid var(--line); cursor: pointer; }.candidate-row strong, .candidate-row small { display: block; }.candidate-row strong { font-size: 13px; }.candidate-row small { margin-top: 3px; color: #91a5af; font-size: 11px; line-height: 1.35; }.decision-copy h3 { font-size: 18px; line-height: 1.5; }.decision-copy ol { padding-left: 22px; font-size: 15px; line-height: 1.7; }
.spread-module, .resource-module, .route-module { display: grid; gap: 9px; margin-top: 10px; }.spread-steps { display: flex; flex-wrap: wrap; gap: 6px; }.spread-steps span { padding: 5px 8px; border: 1px solid #405765; color: #8ea2ac; font-size: 13px; }.spread-steps span.done { border-color: #357f5f; color: #75d9a2; }.spread-steps span.active { border-color: #d6a446; color: #ffd36d; }.calculation-state { display: flex; align-items: center; gap: 8px; color: #d7e3e7; font-size: 14px; }.fire-playback { display: grid; grid-template-columns: auto auto auto minmax(160px, 1fr); gap: 9px; align-items: center; }.fire-playback label { display: flex; align-items: center; gap: 6px; color: #aabdc5; font-size: 13px; }.fire-playback select { min-height: 32px; border: 1px solid #526878; color: #fff; background: #142532; font: inherit; }.fire-playback input { width: 100%; accent-color: #ef7b35; }.timeline-scale { display: flex; justify-content: space-between; color: #91a6b0; font-size: 12px; }
.spread-console { display: grid; grid-template-columns: minmax(0, 1fr) 290px; gap: 12px; }.spread-input-panel, .spread-provenance { padding: 12px; border: 1px solid var(--line); background: #142731; }.panel-heading { display: flex; justify-content: space-between; gap: 16px; align-items: start; }.panel-heading h3 { margin-bottom: 0; }.parameter-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 9px; margin-top: 12px; }.parameter-grid label { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 5px 8px; align-items: center; color: #aebec6; font-size: 13px; }.parameter-grid input, .parameter-grid select { min-width: 0; min-height: 32px; border: 1px solid #526878; color: #f1f5f6; background: #10222d; font: inherit; }.parameter-grid input[type='number'] { width: 72px; padding: 0 6px; }.parameter-grid input[type='range'] { grid-column: 1 / -1; width: 100%; accent-color: #ef7b35; }.parameter-grid output { color: #f2f6f7; font-weight: 700; }.source-strip { display: flex; flex-wrap: wrap; gap: 6px 15px; margin-top: 12px; color: #a9bdc5; font-size: 13px; }.source-strip span { padding-left: 8px; border-left: 2px solid #3e768c; }.spread-provenance { color: #aebec6; font-size: 14px; line-height: 1.55; }.spread-provenance strong { color: #e8f0f3; }.spread-provenance p { margin: 8px 0 0; }
.resource-module .truth-label, .warning-text { margin: 0; color: #e9bd62; font-size: 13px; }.inventory-table { border: 1px solid var(--line); }.inventory-head, .inventory-row { display: grid; grid-template-columns: minmax(150px, 1fr) repeat(5, minmax(68px, .45fr)); gap: 8px; align-items: center; min-height: 34px; padding: 0 10px; border-bottom: 1px solid #243b48; font-size: 13px; }.inventory-head { color: #91a6b0; background: #0d1c25; }.inventory-row { background: #152934; }.inventory-row strong { font-size: 14px; }.inventory-row b { color: #77dba1; font-size: 13px; }.route-brief { display: grid; grid-template-columns: max-content minmax(130px, 1fr) max-content minmax(130px, 1fr) max-content minmax(130px, 1fr); gap: 6px 12px; align-items: center; }.route-brief span { color: #91a6b0; font-size: 13px; }.route-brief strong { font-size: 14px; }.route-copy { margin: 0; color: #a8bac2; font-size: 13px; line-height: 1.45; }
.risk-facts, .resource-highlights { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 1px; margin-top: 12px; background: var(--line); }.risk-facts div, .resource-highlights article { min-width: 0; padding: 11px; background: #10222d; }.risk-facts span, .resource-highlights span, .resource-highlights small { display: block; color: #8fa5b0; font-size: 12px; }.risk-facts strong, .resource-highlights strong { display: block; margin-top: 5px; color: #f2f6f7; font-size: 20px; }.resource-highlights small { margin-top: 5px; }.module-note { margin: 10px 0 0; color: #9bb0ba; font-size: 13px; line-height: 1.5; }.resource-ok { margin: 0; color: #70d8a0; font-size: 14px; font-weight: 700; }.route-explanation { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1px; border: 1px solid var(--line); }.route-explanation div { padding: 11px; background: #142731; }.route-explanation span, .route-explanation strong { display: block; }.route-explanation span { color: #91a6b0; font-size: 13px; }.route-explanation strong { margin-top: 5px; color: #e7eff2; font-size: 14px; line-height: 1.45; }.decision-section { padding: 12px 0; border-bottom: 1px solid var(--line); }.decision-section > span { color: #69b9e6; font-size: 13px; font-weight: 800; }.decision-section h3, .decision-section p { margin: 6px 0 0; }.decision-section p { color: #d6e1e5; font-size: 15px; line-height: 1.6; }
.provenance { margin-top: 20px; border-top: 1px solid var(--line); padding-top: 12px; }.provenance summary { color: #91a5af; font-size: 14px; cursor: pointer; }.provenance dl { display: grid; grid-template-columns: 150px minmax(0, 1fr); margin-top: 12px; }.provenance dt, .provenance dd { margin: 0; padding: 7px; border-bottom: 1px solid #243944; font-size: 13px; }.provenance dt { color: #8da0aa; }.provenance dd { color: #cedae0; font-family: Consolas, monospace; overflow-wrap: anywhere; }.empty { padding: 16px; color: #91a5af; }
@media (max-width: 1250px) { .command-header { grid-template-columns: 1fr 1fr; }.header-actions { grid-column: 1 / -1; justify-content: flex-start; }.command-grid { grid-template-columns: 190px minmax(500px, 1fr); height: 560px; }.command-grid :deep(.situation-panel) { display: none; } }
@media (max-width: 820px) { .command-center { display: block; height: auto; overflow: auto; }.command-header { grid-template-columns: 1fr; }.command-grid { display: block; height: auto; }.command-grid :deep(.workflow-progress) { display: grid; grid-template-columns: repeat(3, 1fr); border-right: 0; }.map-workspace { height: 430px; }.stage-workspace { max-height: none; overflow: visible; }.readiness-grid, .summary-grid, .candidate-columns, .module-layout { grid-template-columns: 1fr; }.stage-state { max-width: 100%; }.stage-heading { align-items: flex-start; flex-direction: column; }.fire-playback { grid-template-columns: auto auto 1fr; }.fire-playback input { grid-column: 1 / -1; }.route-brief { grid-template-columns: max-content 1fr; }.inventory-head, .inventory-row { grid-template-columns: minmax(100px, 1fr) repeat(5, minmax(56px, .5fr)); } }
@media (max-width: 820px) { .command-grid :deep(.workflow-status-panel) { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); border-right: 0; }.command-grid :deep(.workflow-status-panel .stage-button) { grid-template-columns: 20px minmax(0, 1fr); min-height: 58px; padding: 8px; }.command-grid :deep(.workflow-status-panel .stage-number) { display: none; }.risk-facts, .resource-highlights, .route-explanation { grid-template-columns: repeat(2, minmax(0, 1fr)); } }

/* Compact desktop layout: keep controls reachable at 100% browser zoom. */
.command-center { grid-template-rows: auto minmax(0, 1fr) minmax(220px, 36%); }
.command-header { min-height: 68px; padding: 8px 16px; gap: 12px; grid-template-columns: minmax(210px, 1fr) minmax(240px, 1.2fr) auto; }
.command-grid { grid-template-columns: 168px minmax(0, 1fr) 244px; min-height: 0; }
.stage-workspace { max-height: none; padding: 8px 16px 12px; }
.command-header h1 { font-size: 21px; }
.command-center h2 { font-size: 17px; }
.command-center h3 { font-size: 15px; }
.command-center button { min-height: 32px; padding: 0 10px; font-size: 12px; }
.command-center .header-actions select { height: 32px; font-size: 12px; }
.command-center .eyebrow, .command-center .stage-state, .command-center .layer-control label { font-size: 11px; }
.command-center .readiness-grid article, .command-center .summary-grid article { min-height: 60px; padding: 9px; }
.command-center .summary-grid strong { font-size: 18px; margin-top: 4px; }
.command-center .readiness-grid, .command-center .summary-grid { margin-top: 10px; }
.command-center .lead, .command-center .module-aside, .command-center .result-line, .command-center .decision-section p { font-size: 12px; }
.command-center .parameter-grid { margin-top: 7px; gap: 5px; }
.command-center .parameter-grid label, .command-center .manual-tools span { font-size: 11px; }
.command-center .module-layout { grid-template-columns: minmax(0, 1fr) 240px; }
.command-center .spread-console { grid-template-columns: minmax(0, 1fr) 230px; }
@media (max-width: 1250px) {
  .command-center { grid-template-rows: auto minmax(0, 1fr) minmax(220px, 38%); }
  .command-grid { height: auto; grid-template-columns: 158px minmax(0, 1fr); }
}
@media (max-width: 820px) {
  .command-center { display: block; overflow: auto; }
  .command-grid { display: block; height: auto; }
  .stage-workspace { max-height: none; }
}


.command-grid { grid-template-columns: 168px minmax(0, 1fr); }
@media (max-width: 1250px) { .command-grid { grid-template-columns: 158px minmax(0, 1fr); } }

.planning-status {color:#9fb5c0;font-size:11px}
.header-link {display:inline-flex;align-items:center;min-height:32px;padding:0 10px;border:1px solid #3d6674;border-radius:4px;color:#9ddcec;font-size:11px;text-decoration:none}

.supply-requests,.route-targets {margin-top:10px;padding:10px;border:1px solid #355262;background:#102633}
.supply-requests h3 {margin:0 0 5px}.supply-requests p,.route-targets p {color:#a9bec8;font-size:11px;line-height:1.45}
.supply-row {display:flex;align-items:center;flex-wrap:wrap;gap:7px;margin-top:8px;padding:7px;border:1px solid #2c4552}
.supply-row strong {font-size:11px;margin-right:auto}.supply-row label {display:flex;align-items:center;gap:5px;color:#a9bec8;font-size:10px}
.supply-row input {width:60px;min-height:26px;padding:0 5px;border:1px solid #526878;background:#0a1d28;color:#eaf4ff;font-size:11px}
.supply-total {margin-top:8px;color:#5eead4;font-size:11px;font-weight:700}.route-targets strong,.route-targets span {display:inline-block;margin-right:9px;font-size:11px}
</style>
