<template>
  <main class="ops-page" :data-mode="mode">
    <aside class="side-panel left-panel">
      <header class="panel-header">
        <span class="panel-kicker">{{ config.leftKicker }}</span>
        <h2>{{ config.leftTitle }}</h2>
      </header>

      <section class="control-block">
        <label class="select-label" for="scenario-select">事件场景</label>
        <div class="scenario-row">
          <select id="scenario-select" v-model="scenarioId">
            <option v-for="item in fireEvent.scenarios" :key="item.scenario_id" :value="item.scenario_id">
              {{ item.name || item.scenario_id }}
            </option>
          </select>
          <button class="primary-btn" type="button" @click="startEvent" :disabled="busy">创建</button>
        </div>
        <div class="flow-grid">
          <button type="button" @click="advanceEvidence" :disabled="busy || !fireEvent.eventId">推进证据</button>
          <button type="button" @click="runSpread" :disabled="busy || !fireEvent.trustedFirePoint">火势推演</button>
          <button type="button" @click="runDecision" :disabled="busy || !fireEvent.spreadRun">Agent 决策</button>
          <button type="button" @click="runRecommendations" :disabled="busy || !fireEvent.decisionRun">推荐包</button>
          <button type="button" @click="runReport" :disabled="busy || !fireEvent.eventId">生成报告</button>
          <button type="button" @click="downloadReport" :disabled="busy || !fireEvent.latestReport">下载 PDF</button>
        </div>
        <p class="status-message">{{ message }}</p>
      </section>

      <section class="metric-grid">
        <article v-for="metric in leftMetrics" :key="metric.label" class="metric-card">
          <span>{{ metric.label }}</span>
          <strong>{{ metric.value }}</strong>
          <small>{{ metric.hint }}</small>
        </article>
      </section>

      <section class="panel-section">
        <h3>{{ config.leftSectionTitle }}</h3>
        <div v-if="leftRows.length" class="data-list">
          <article v-for="row in leftRows" :key="row.id" class="data-row">
            <div>
              <strong>{{ row.title }}</strong>
              <span>{{ row.subtitle }}</span>
            </div>
            <b>{{ row.value }}</b>
          </article>
        </div>
        <p v-else class="empty-text">{{ config.emptyLeft }}</p>
      </section>
    </aside>

    <section class="map-stage">
      <CesiumMap ref="mapRef" class="map" :scene-id="scenarioId" />
      <div class="map-topbar">
        <div>
          <p>{{ subtitle }}</p>
          <h1>{{ title }}</h1>
        </div>
        <div class="event-pill">
          <span>{{ eventLabel }}</span>
          <strong>{{ fireEvent.eventStatus || '待创建' }}</strong>
        </div>
      </div>
      <div class="map-bottombar">
        <article v-for="item in mapStatus" :key="item.label">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </article>
      </div>
    </section>

    <aside class="side-panel right-panel">
      <header class="panel-header">
        <span class="panel-kicker">{{ config.agentKicker }}</span>
        <h2>{{ config.agentTitle }}</h2>
      </header>

      <section class="agent-hero">
        <div>
          <span>当前智能体</span>
          <strong>{{ config.agentName }}</strong>
        </div>
        <p>{{ agentNarrative }}</p>
      </section>

      <section class="agent-flow">
        <article v-for="step in agentFlow" :key="step.label" :class="{ done: step.done }">
          <span>{{ step.label }}</span>
          <strong>{{ step.value }}</strong>
        </article>
      </section>

      <section v-if="mode === 'command'" class="whatif-panel">
        <h3>情景重算</h3>
        <div class="scenario-row">
          <select v-model="disturbanceType">
            <option value="wind_shift">风向突变</option>
            <option value="road_unavailable">道路不可用</option>
            <option value="uav_availability_reduced">无人机可用性下降</option>
            <option value="protected_target_priority_changed">保护目标优先级变化</option>
            <option value="weather_risk_increased">天气风险升高</option>
          </select>
          <button class="primary-btn" type="button" @click="runRecalculation" :disabled="busy || !fireEvent.recommendationPackage">
            重算
          </button>
        </div>
        <p>{{ recalculationText }}</p>
      </section>

      <section class="panel-section agent-section">
        <h3>{{ config.agentSectionTitle }}</h3>
        <div v-if="agentCards.length" class="agent-card-list">
          <article v-for="card in agentCards" :key="card.id" class="agent-card">
            <div class="agent-card-head">
              <strong>{{ card.title }}</strong>
              <span>{{ card.badge }}</span>
            </div>
            <p>{{ card.body }}</p>
            <small>{{ card.meta }}</small>
          </article>
        </div>
        <p v-else class="empty-text">{{ config.emptyAgent }}</p>
      </section>

      <section class="panel-section compact-section">
        <h3>后端输出摘要</h3>
        <div class="summary-grid">
          <span>模型</span><b>{{ modelLabel }}</b>
          <span>推演</span><b>{{ spreadEngineLabel }}</b>
          <span>报告</span><b>{{ fireEvent.latestReport?.report_id || '待生成' }}</b>
        </div>
      </section>
    </aside>
  </main>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import CesiumMap from './CesiumMap.vue'
import { WIND_VIEW_ZOOM, useFireEventStore } from '../stores/fireEventStore'
import { syncActiveFireToMap } from '../composables/useFireEventMapSync'

type Mode = 'monitor' | 'fusion' | 'predict' | 'route' | 'uav' | 'resource' | 'assess' | 'command'
type Row = { id: string; title: string; subtitle: string; value: string }
type Card = { id: string; title: string; badge: string; body: string; meta: string }

const props = defineProps<{
  mode: Mode
  title: string
  subtitle: string
}>()

const fireEvent = useFireEventStore()
const mapRef = ref<InstanceType<typeof CesiumMap> | null>(null)
const scenarioId = ref(fireEvent.selectedScenarioId || 'muli_lier_village')
const busy = ref(false)
const message = ref('等待操作')
const disturbanceType = ref('road_unavailable')
let mapSync: ReturnType<typeof syncActiveFireToMap> | null = null

const mode = computed(() => props.mode)
const title = computed(() => props.title)
const subtitle = computed(() => props.subtitle)

const configs: Record<Mode, any> = {
  monitor: {
    leftKicker: 'Telemetry',
    leftTitle: '实时参数',
    leftSectionTitle: '时序观测',
    agentKicker: 'Environment Agent',
    agentTitle: '环境评估智能体',
    agentName: '环境评估 Agent',
    agentSectionTitle: '态势解读',
    emptyLeft: '等待后端观测数据。',
    emptyAgent: '推进证据后生成环境态势解读。',
  },
  fusion: {
    leftKicker: 'Evidence',
    leftTitle: '融合参数',
    leftSectionTitle: '证据链',
    agentKicker: 'Fusion Agent',
    agentTitle: '可信火点判断',
    agentName: '多源融合 Agent',
    agentSectionTitle: '交叉验证结论',
    emptyLeft: '等待证据链生成。',
    emptyAgent: '可信火点生成后展示融合解释。',
  },
  predict: {
    leftKicker: 'ForeFire',
    leftTitle: '推演参数',
    leftSectionTitle: '时间步火线',
    agentKicker: 'Spread Agent',
    agentTitle: '火势推演智能体',
    agentName: '火势推演 Agent',
    agentSectionTitle: '风险包',
    emptyLeft: '等待 ForeFire 推演结果。',
    emptyAgent: '运行 Agent 决策后展示风险解释。',
  },
  route: {
    leftKicker: 'Route',
    leftTitle: '道路与路径',
    leftSectionTitle: '路径候选',
    agentKicker: 'Route Agent',
    agentTitle: '路径规划智能体',
    agentName: '路径规划 Agent',
    agentSectionTitle: '路线建议',
    emptyLeft: '等待推荐包生成。',
    emptyAgent: '生成推荐包后展示路径解释。',
  },
  uav: {
    leftKicker: 'UAV',
    leftTitle: '空中资源',
    leftSectionTitle: '无人机任务',
    agentKicker: 'UAV Agent',
    agentTitle: '无人机调度智能体',
    agentName: '无人机调度 Agent',
    agentSectionTitle: '侦察任务包',
    emptyLeft: '等待无人机推荐任务。',
    emptyAgent: '生成推荐包后展示侦察建议。',
  },
  resource: {
    leftKicker: 'Resources',
    leftTitle: '队伍装备',
    leftSectionTitle: '资源任务',
    agentKicker: 'Dispatch Agent',
    agentTitle: '资源调度智能体',
    agentName: '资源调度 Agent',
    agentSectionTitle: '任务分配',
    emptyLeft: '等待资源调度建议。',
    emptyAgent: '生成推荐包后展示资源匹配理由。',
  },
  assess: {
    leftKicker: 'Assessment',
    leftTitle: '评估指标',
    leftSectionTitle: '报告要点',
    agentKicker: 'Report Agent',
    agentTitle: '灾情评估智能体',
    agentName: '报告生成 Agent',
    agentSectionTitle: '评估结论',
    emptyLeft: '等待报告生成。',
    emptyAgent: '生成报告后展示评估摘要。',
  },
  command: {
    leftKicker: 'Command',
    leftTitle: '总态势',
    leftSectionTitle: '指挥输入',
    agentKicker: 'Multi-Agent',
    agentTitle: '综合决策中枢',
    agentName: '多智能体指挥系统',
    agentSectionTitle: '候选方案与推荐',
    emptyLeft: '等待完整链路数据。',
    emptyAgent: '运行 Agent 决策后展示综合方案。',
  },
}

const config = computed(() => configs[props.mode])
const records = computed(() => fireEvent.agentResult?.recommendation_records || {})
const routes = computed(() => records.value.routes || fireEvent.routePackage?.route_options || [])
const uavs = computed(() => records.value.uavs || fireEvent.uavPackage?.uav_tasks || [])
const resources = computed(() => records.value.resources || fireEvent.resourcePackage?.dispatch_tasks || [])
const eventLabel = computed(() => fireEvent.eventDetail?.name || fireEvent.eventId || '当前没有后端事件')
const clockMinute = computed(() => fireEvent.clockState ? `${fireEvent.clockState.current_minute}/${fireEvent.clockState.duration_minutes} 分钟` : '待启动')
const trustedConfidence = computed(() => fireEvent.trustedFirePoint ? Number(fireEvent.trustedFirePoint.confidence || 0).toFixed(3) : '待确认')
const spreadEngineLabel = computed(() => fireEvent.spreadRun ? `${fireEvent.spreadRun.engine}${fireEvent.spreadRun.fallback_used ? ' / 兜底' : ''}` : '待推演')
const modelLabel = computed(() => fireEvent.decisionRun ? `${fireEvent.decisionRun.provider || ''} ${fireEvent.decisionRun.model || ''}`.trim() : '待调用')
const recalculationText = computed(() => fireEvent.latestRecalculation?.recalculation?.change_summary?.message || '选择假设条件后重新计算推荐结果。')

const mapStatus = computed(() => [
  { label: '时钟', value: clockMinute.value },
  { label: '可信火点', value: trustedConfidence.value },
  { label: '推演引擎', value: spreadEngineLabel.value },
  { label: '风险等级', value: fireEvent.spreadRun?.risk_level || fireEvent.riskLevel || '待生成' },
])

const leftMetrics = computed(() => {
  const env = fireEvent.environmentSnapshot || {}
  const spread = fireEvent.spreadRun || {}
  const base: Record<Mode, any[]> = {
    monitor: [
      ['温度', fmt(env.temperature_c, '℃'), '环境快照'],
      ['湿度', fmt(env.humidity_percent, '%'), '环境快照'],
      ['风速', fmt(env.wind_speed_m_s, 'm/s'), '环境快照'],
      ['观测', String(fireEvent.observations.length), '多源输入'],
    ],
    fusion: [
      ['观测源', String(fireEvent.observations.length), '参与融合'],
      ['证据链', String(fireEvent.evidenceChain.length), '交叉验证'],
      ['融合置信', trustedConfidence.value, '可信火点'],
      ['状态', fireEvent.backendFusionResult?.decision || '待判断', '融合输出'],
    ],
    predict: [
      ['引擎', spreadEngineLabel.value, '真实推演'],
      ['步长', spread.step_minutes ? `${spread.step_minutes} 分钟` : '待推演', '时间粒度'],
      ['面积', fmt(spread.final_area_km2, 'km²'), '最终火线'],
      ['半径', fmt(spread.max_radius_km, 'km'), '影响范围'],
    ],
    route: [
      ['路径数', String(routes.value.length), '候选方案'],
      ['主路径', firstText(routes.value[0]?.name), '推荐结果'],
      ['阻断', fireEvent.latestRecalculation ? '已重算' : '未触发', '情景假设'],
      ['水源/道路', '可查询', 'GIS 条件'],
    ],
    uav: [
      ['任务数', String(uavs.value.length), '侦察任务'],
      ['可用性', uavs.value.length ? '已匹配' : '待匹配', '资产状态'],
      ['优先级', firstText(uavs.value[0]?.priority || uavs.value[0]?.status), '任务包'],
      ['覆盖', '火线周边', '侦察范围'],
    ],
    resource: [
      ['任务数', String(resources.value.length), '调度任务'],
      ['队伍', String(resources.value.filter((item: any) => /team|队|crew/i.test(rowText(item))).length || resources.value.length), '资源匹配'],
      ['装备', '按需配置', '后端推荐'],
      ['状态', fireEvent.recommendationPackage ? '已生成' : '待生成', '推荐包'],
    ],
    assess: [
      ['报告', fireEvent.latestReport ? '已生成' : '待生成', 'PDF 可下载'],
      ['面积', fmt(spread.final_area_km2, 'km²'), '推演输入'],
      ['风险', spread.risk_level || '待生成', '评估等级'],
      ['方案', fireEvent.recommendedPlan?.name || '待生成', '决策依据'],
    ],
    command: [
      ['观测', String(fireEvent.observations.length), '态势输入'],
      ['火线', String(fireEvent.spreadSteps.length), '推演步'],
      ['路径', String(routes.value.length), '推荐包'],
      ['资源', String(resources.value.length), '调度包'],
    ],
  }
  return base[props.mode].map(([label, value, hint]) => ({ label, value, hint }))
})

const leftRows = computed<Row[]>(() => {
  if (props.mode === 'monitor') return fireEvent.observations.slice(-8).reverse().map((item: any) => ({
    id: item.observation_id,
    title: `${item.source_type} / ${item.source_name}`,
    subtitle: `阶段 ${item.stage || '-'}，坐标 ${fmt(item.longitude)}, ${fmt(item.latitude)}`,
    value: fmt(item.confidence),
  }))
  if (props.mode === 'fusion') return fireEvent.evidenceChain.slice(-8).reverse().map((item: any) => ({
    id: item.evidence_id,
    title: item.source_name || item.source_type || '证据',
    subtitle: item.explanation || `权重 ${fmt(item.weight)}`,
    value: fmt(item.confidence || item.weight),
  }))
  if (props.mode === 'predict') return fireEvent.spreadSteps.map((step: any) => ({
    id: step.step_id,
    title: `${step.time_minute} 分钟火线`,
    subtitle: `半径 ${fmt(step.radius_km, 'km')}，方向 ${fmt(step.spread_direction_deg, '°')}`,
    value: fmt(step.area_km2, 'km²'),
  }))
  if (props.mode === 'route') return routes.value.map((item: any, index: number) => ({
    id: item.route_id || item.name || String(index),
    title: item.name || `路线 ${index + 1}`,
    subtitle: item.summary || item.route_type || item.type || '路径候选',
    value: item.risk || item.status || '可用',
  }))
  if (props.mode === 'uav') return uavs.value.map((item: any, index: number) => ({
    id: item.asset_id || item.task_id || item.name || String(index),
    title: item.name || item.task?.name || `无人机任务 ${index + 1}`,
    subtitle: item.mission || item.target || item.task?.target || '侦察任务',
    value: item.priority || item.status || item.task?.priority || '待执行',
  }))
  if (props.mode === 'resource') return resources.value.map((item: any, index: number) => ({
    id: item.resource_id || item.task_id || item.name || String(index),
    title: item.name || item.owner || `资源 ${index + 1}`,
    subtitle: item.target || item.action || item.reason || '资源配置',
    value: [item.quantity, item.unit].filter(Boolean).join('') || item.status || '推荐',
  }))
  if (props.mode === 'assess') return reportLines.value.map((line, index) => ({
    id: `report-${index}`,
    title: line.title,
    subtitle: line.subtitle,
    value: line.value,
  }))
  return [
    { id: 'event', title: '事件状态', subtitle: eventLabel.value, value: fireEvent.eventStatus || '待创建' },
    { id: 'spread', title: '推演状态', subtitle: spreadEngineLabel.value, value: fireEvent.spreadRun?.risk_level || '待生成' },
    { id: 'decision', title: '决策状态', subtitle: modelLabel.value, value: fireEvent.decisionRun ? '已生成' : '待生成' },
    { id: 'report', title: '报告状态', subtitle: fireEvent.latestReport?.title || '早期指挥报告', value: fireEvent.latestReport ? '已生成' : '待生成' },
  ]
})

const reportLines = computed(() => {
  const sections = fireEvent.latestReport?.sections || {}
  const spread = sections.spread_prediction || {}
  const decision = sections.decision || {}
  return [
    { title: '推演结论', subtitle: `引擎 ${spread.engine || spreadEngineLabel.value}`, value: fmt(spread.final_area_km2 || fireEvent.spreadRun?.final_area_km2, 'km²') },
    { title: '推荐方案', subtitle: decision.recommended_plan?.strategy || fireEvent.recommendedPlan?.strategy || '等待 Agent 决策', value: decision.recommended_plan?.name || fireEvent.recommendedPlan?.name || '待生成' },
    { title: '报告编号', subtitle: fireEvent.latestReport?.title || '早期指挥报告', value: fireEvent.latestReport?.report_id || '待生成' },
  ]
})

const agentNarrative = computed(() => {
  const plan = fireEvent.recommendedPlan?.name || fireEvent.recommendedPlan?.plan_id
  const fallback = {
    monitor: `正在汇集 ${fireEvent.observations.length} 条时序观测，并结合环境快照形成态势输入。`,
    fusion: `已接入 ${fireEvent.evidenceChain.length} 条证据，可信火点置信度为 ${trustedConfidence.value}。`,
    predict: `当前推演引擎为 ${spreadEngineLabel.value}，共生成 ${fireEvent.spreadSteps.length} 个火线时间步。`,
    route: `路径规划基于火线、道路、水源与保护目标生成 ${routes.value.length} 条候选路径。`,
    uav: `无人机调度围绕火线边界、下风向和保护目标安排 ${uavs.value.length} 项侦察任务。`,
    resource: `资源调度根据风险等级、到达时间和任务优先级生成 ${resources.value.length} 项配置。`,
    assess: `报告智能体整合推演、方案和推荐包，形成可下载的早期指挥报告。`,
    command: plan ? `多智能体已形成推荐方案：${plan}。` : '等待环境、推演、路径与资源工具输出，形成综合指挥方案。',
  }
  return fallback[props.mode]
})

const agentFlow = computed(() => [
  { label: '环境评估', value: fireEvent.environmentSnapshot ? '完成' : '等待', done: Boolean(fireEvent.environmentSnapshot) },
  { label: '火点融合', value: fireEvent.trustedFirePoint ? '可信' : '等待', done: Boolean(fireEvent.trustedFirePoint) },
  { label: '火势推演', value: fireEvent.spreadRun ? fireEvent.spreadRun.engine : '等待', done: Boolean(fireEvent.spreadRun) },
  { label: '指挥决策', value: fireEvent.decisionRun ? '完成' : '等待', done: Boolean(fireEvent.decisionRun) },
])

const agentCards = computed<Card[]>(() => {
  if (props.mode === 'monitor') {
    return [
      card('env', '环境态势', fireEvent.environmentSnapshot ? '已更新' : '等待', envSummary.value, `时钟 ${clockMinute.value}`),
      card('obs', '观测完整性', `${fireEvent.observations.length} 条`, `当前已接收卫星、地面、无人机或瞭望类观测，用于生成可信火点。`, `证据链 ${fireEvent.evidenceChain.length} 条`),
    ]
  }
  if (props.mode === 'fusion') {
    return [
      card('trusted', '可信火点', trustedConfidence.value, trustedPointSummary.value, fireEvent.backendFusionResult?.decision || '等待融合'),
      ...fireEvent.evidenceChain.slice(-3).map((item: any, index: number) => card(`ev-${index}`, item.source_name || '融合证据', fmt(item.confidence || item.weight), item.explanation || '参与交叉验证。', item.source_type || 'evidence')),
    ]
  }
  if (props.mode === 'predict') {
    return [
      card('spread', '推演结果', spreadEngineLabel.value, `后端生成 ${fireEvent.spreadSteps.length} 个火线时间步，最终面积 ${fmt(fireEvent.spreadRun?.final_area_km2, 'km²')}。`, fireEvent.spreadRun?.fallback_used ? '使用兜底模型' : 'ForeFire 真实推演'),
      card('risk', '风险解释', fireEvent.spreadRun?.risk_level || '待生成', `结合风向、坡度、可燃物和火线增长结果，输出早期风险包供指挥 Agent 排序。`, `最大半径 ${fmt(fireEvent.spreadRun?.max_radius_km, 'km')}`),
    ]
  }
  if (props.mode === 'route') return routes.value.map((item: any, index: number) => card(`route-${index}`, item.name || `路线 ${index + 1}`, item.risk || item.status || '推荐', item.summary || item.reason || '结合道路可达性、避险方向和保护目标生成。', item.route_type || item.type || 'route'))
  if (props.mode === 'uav') return uavs.value.map((item: any, index: number) => card(`uav-${index}`, item.name || item.task?.name || `侦察任务 ${index + 1}`, item.priority || item.status || '推荐', item.mission || item.target || item.task?.target || '对火线边界和下风向进行复核侦察。', item.asset_id || item.task_id || 'uav'))
  if (props.mode === 'resource') return resources.value.map((item: any, index: number) => card(`res-${index}`, item.name || item.owner || `资源任务 ${index + 1}`, item.status || '推荐', item.reason || item.action || item.target || '根据风险包、道路和到达时间匹配资源。', [item.quantity, item.unit].filter(Boolean).join('') || 'dispatch'))
  if (props.mode === 'assess') {
    return [
      card('report', '报告输出', fireEvent.latestReport ? '已生成' : '待生成', fireEvent.latestReport?.summary || '报告将整合推演、决策、路径、资源和重算结果。', fireEvent.latestReport?.report_id || 'report'),
      card('decision', '评估依据', fireEvent.decisionRun ? 'Agent 已完成' : '等待', fireEvent.recommendedPlan?.strategy || '等待综合决策后形成评估依据。', modelLabel.value),
    ]
  }
  const candidates = fireEvent.agentResult?.packages?.plan_packet?.candidate_plans || fireEvent.agentResult?.candidate_plans || []
  const cards = candidates.length
    ? candidates.map((item: any, index: number) => card(`plan-${index}`, item.name || item.plan_id || `候选方案 ${index + 1}`, String(item.score || item.rank || '候选'), item.strategy || item.reason || '由多智能体工具链生成并排序。', item.plan_id || 'plan'))
    : []
  return [
    card('recommended', '最终推荐', fireEvent.recommendedPlan?.name || '待生成', fireEvent.recommendedPlan?.strategy || '等待 Agent 决策输出。', modelLabel.value),
    ...cards,
  ]
})

const envSummary = computed(() => {
  const env = fireEvent.environmentSnapshot
  if (!env) return '等待环境快照。'
  return `温度 ${fmt(env.temperature_c, '℃')}，湿度 ${fmt(env.humidity_percent, '%')}，风速 ${fmt(env.wind_speed_m_s, 'm/s')}，火险指数 ${fmt(env.fire_weather_index)}。`
})

const trustedPointSummary = computed(() => {
  const point = fireEvent.trustedFirePoint
  if (!point) return '等待多源融合生成可信火点。'
  return `可信坐标 ${fmt(point.longitude)}, ${fmt(point.latitude)}，置信度 ${fmt(point.confidence)}，等级 ${point.level || 'confirmed'}。`
})

function fmt(value: any, unit = '') {
  const num = Number(value)
  if (!Number.isFinite(num)) return value === 0 ? `0${unit}` : `待生成`
  const rounded = Math.abs(num) >= 100 ? num.toFixed(0) : num.toFixed(3).replace(/\.?0+$/, '')
  return `${rounded}${unit}`
}

function firstText(value: any) {
  return value ? String(value) : '待生成'
}

function rowText(item: any) {
  return JSON.stringify(item || {})
}

function card(id: string, title: string, badge: string, body: string, meta: string): Card {
  return { id, title, badge, body, meta }
}

async function runStep(label: string, action: () => Promise<any>) {
  busy.value = true
  message.value = `${label}中...`
  try {
    const result = await action()
    message.value = `${label}完成`
    return result
  } catch (error: any) {
    message.value = error?.message || `${label}失败`
    throw error
  } finally {
    busy.value = false
  }
}

async function startEvent() {
  await runStep('创建后端事件', async () => {
    await fireEvent.startSimulatedEvent({ scenario_id: scenarioId.value })
    await refreshAll()
  })
}

async function advanceEvidence() {
  await runStep('推进时序证据', async () => {
    if (!fireEvent.eventId) throw new Error('没有后端事件。')
    await fireEvent.startClock({ tick_interval_seconds: 30, reset: true })
    await fireEvent.pauseClock()
    for (const minutes of [5, 5, 5, 5, 5, 5]) {
      await fireEvent.stepClock(minutes)
    }
    await refreshAll()
  })
}

async function runSpread() {
  await runStep('生成火势推演', async () => {
    await fireEvent.createSpreadRun({ horizon_minutes: 120, step_minutes: 30, prefer_forefire: true })
  })
}

async function runDecision() {
  await runStep('生成 Agent 决策', async () => {
    await fireEvent.createDecisionRun({ include_report: true })
  })
}

async function runRecommendations() {
  await runStep('生成推荐包', async () => {
    await fireEvent.regenerateRecommendations({ status: 'recommended' })
  })
}

async function runReport() {
  await runStep('生成报告', async () => {
    await fireEvent.generateReport({ include_recalculation: true, format: 'markdown' })
  })
}

function disturbancePayload() {
  const type = disturbanceType.value
  const parameters: Record<string, any> = type === 'wind_shift'
    ? { wind_direction_deg: 75, shift_degrees: 45 }
    : type === 'uav_availability_reduced'
      ? { available_uavs: 1 }
      : type === 'protected_target_priority_changed'
        ? { target: 'downwind village boundary' }
        : type === 'weather_risk_increased'
          ? { risk_level: 'high' }
          : { route_type: 'evacuation' }
  return { disturbance_type: type, assumption: `Command-side ${type} assumption.`, parameters, created_by: 'frontend-command' }
}

async function runRecalculation() {
  await runStep('执行情景重算', async () => {
    await fireEvent.recalculateWithDisturbance({ disturbance: disturbancePayload(), status: 'recommended' })
  })
}

async function downloadReport() {
  const report = fireEvent.latestReport || await fireEvent.generateReport({ include_recalculation: true, format: 'markdown' })
  const url = fireEvent.reportDownloadUrl(report?.report_id)
  if (url) window.open(url, '_blank')
}

async function refreshAll() {
  if (!fireEvent.eventId) return
  await Promise.allSettled([
    fireEvent.loadEventDetail(),
    fireEvent.loadEventTimeline(),
    fireEvent.loadClockState(),
    fireEvent.loadObservationState(),
    fireEvent.loadLatestSpreadRun(),
    fireEvent.loadLatestDecisionRun(),
    fireEvent.loadLatestRecommendations(),
    fireEvent.loadLatestRecalculation(),
    fireEvent.loadLatestReport(),
  ])
  await nextTick()
}

onMounted(async () => {
  await fireEvent.loadScenarios()
  mapSync = syncActiveFireToMap(() => mapRef.value, {
    zoom: WIND_VIEW_ZOOM,
    mode: props.mode,
    showHotspotBeforePrediction: true,
  })
})

watch(() => fireEvent.selectedScenarioId, (value) => {
  if (value) scenarioId.value = value
})

onUnmounted(() => {
  mapSync?.stop?.()
})
</script>

<style scoped>
.ops-page {
  width: 100%;
  height: 100%;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(270px, 19vw) minmax(480px, 1fr) minmax(360px, 26vw);
  background: #07111b;
  color: #edf6ff;
  overflow: hidden;
}

.side-panel {
  min-width: 0;
  min-height: 0;
  overflow: auto;
  padding: 16px;
  border-color: rgba(115, 139, 173, 0.24);
  background:
    linear-gradient(180deg, rgba(14, 29, 45, 0.96), rgba(7, 17, 27, 0.98)),
    #081421;
}

.left-panel {
  border-right: 1px solid rgba(115, 139, 173, 0.22);
}

.right-panel {
  border-left: 1px solid rgba(115, 139, 173, 0.22);
  background:
    linear-gradient(180deg, rgba(10, 34, 43, 0.96), rgba(7, 17, 27, 0.98)),
    #081421;
}

.panel-header {
  display: grid;
  gap: 5px;
  margin-bottom: 14px;
}

.panel-kicker {
  color: #7dd3fc;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

h1,
h2,
h3,
p {
  margin: 0;
  letter-spacing: 0;
}

h2 {
  font-size: 20px;
}

h3 {
  font-size: 14px;
  color: #dbeafe;
}

.control-block,
.panel-section,
.agent-hero,
.whatif-panel,
.compact-section {
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 8px;
  background: rgba(8, 19, 31, 0.72);
  padding: 12px;
}

.control-block {
  display: grid;
  gap: 10px;
}

.select-label {
  color: #94a3b8;
  font-size: 12px;
}

.scenario-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
}

select,
button {
  min-width: 0;
  min-height: 34px;
  border-radius: 6px;
  border: 1px solid rgba(148, 163, 184, 0.28);
  background: #0e1a2a;
  color: #e5f0ff;
  padding: 0 10px;
  font: inherit;
}

button {
  cursor: pointer;
  background: #164e63;
  border-color: rgba(34, 211, 238, 0.42);
  font-weight: 700;
}

.primary-btn {
  background: #0f766e;
  border-color: #14b8a6;
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.46;
}

.flow-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.status-message,
.empty-text {
  color: #93c5fd;
  font-size: 12px;
  line-height: 1.5;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin: 12px 0;
}

.metric-card {
  min-height: 82px;
  display: grid;
  align-content: center;
  gap: 4px;
  padding: 10px;
  border-radius: 8px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(15, 35, 53, 0.82);
}

.metric-card span,
.metric-card small,
.data-row span,
.agent-card small,
.summary-grid span,
.agent-flow span,
.agent-hero span,
.event-pill span,
.map-bottombar span {
  color: #9fb0c7;
  font-size: 12px;
}

.metric-card strong {
  color: #f8fafc;
  font-size: 20px;
  line-height: 1.1;
  word-break: break-word;
}

.panel-section {
  display: grid;
  gap: 10px;
}

.data-list,
.agent-card-list {
  display: grid;
  gap: 8px;
}

.data-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
  padding: 10px;
  border-radius: 7px;
  background: rgba(13, 28, 44, 0.78);
  border: 1px solid rgba(148, 163, 184, 0.14);
}

.data-row div {
  min-width: 0;
  display: grid;
  gap: 3px;
}

.data-row strong,
.agent-card strong {
  color: #f8fafc;
  font-size: 13px;
}

.data-row span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.data-row b {
  color: #67e8f9;
  font-size: 13px;
}

.map-stage {
  position: relative;
  min-width: 0;
  min-height: 0;
  background: #020712;
  overflow: hidden;
}

.map {
  position: absolute;
  inset: 0;
}

.map-topbar,
.map-bottombar {
  display: none !important;
  position: absolute;
  z-index: 5;
  left: 18px;
  right: 18px;
  pointer-events: none;
}

.map-topbar {
  top: 16px;
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: 16px;
}

.map-topbar > div:first-child {
  max-width: min(620px, 58%);
}

.map-topbar p {
  color: #bfdbfe;
  font-size: 13px;
  margin-bottom: 5px;
  text-shadow: 0 2px 12px rgba(0, 0, 0, 0.8);
}

.map-topbar h1 {
  font-size: 30px;
  line-height: 1.08;
  text-shadow: 0 2px 18px rgba(0, 0, 0, 0.85);
}

.event-pill {
  max-width: 340px;
  display: grid;
  gap: 4px;
  padding: 10px 12px;
  border: 1px solid rgba(191, 219, 254, 0.24);
  border-radius: 8px;
  background: rgba(2, 8, 23, 0.72);
}

.event-pill strong {
  color: #5eead4;
  font-size: 13px;
}

.map-bottombar {
  bottom: 16px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}

.map-bottombar article {
  min-height: 58px;
  display: grid;
  align-content: center;
  gap: 4px;
  padding: 10px;
  border-radius: 8px;
  border: 1px solid rgba(191, 219, 254, 0.2);
  background: rgba(2, 8, 23, 0.72);
}

.map-bottombar strong {
  color: #f8fafc;
  font-size: 15px;
}

.agent-hero {
  display: grid;
  gap: 10px;
  margin-bottom: 12px;
  border-color: rgba(45, 212, 191, 0.3);
  background: linear-gradient(135deg, rgba(13, 78, 75, 0.58), rgba(8, 24, 38, 0.88));
}

.agent-hero strong {
  display: block;
  margin-top: 4px;
  font-size: 22px;
  color: #ccfbf1;
}

.agent-hero p,
.whatif-panel p,
.agent-card p {
  color: #d6e8f8;
  font-size: 13px;
  line-height: 1.55;
}

.agent-flow {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 12px;
}

.agent-flow article {
  padding: 10px;
  border-radius: 8px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: rgba(13, 28, 44, 0.72);
}

.agent-flow article.done {
  border-color: rgba(45, 212, 191, 0.32);
  background: rgba(13, 78, 75, 0.35);
}

.agent-flow strong {
  display: block;
  margin-top: 5px;
  color: #f8fafc;
  font-size: 13px;
}

.whatif-panel {
  display: grid;
  gap: 10px;
  margin-bottom: 12px;
}

.agent-section {
  border-color: rgba(45, 212, 191, 0.22);
}

.agent-card {
  padding: 12px;
  border-radius: 8px;
  border: 1px solid rgba(45, 212, 191, 0.18);
  background: rgba(8, 29, 39, 0.82);
}

.agent-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 7px;
}

.agent-card-head span {
  flex: 0 0 auto;
  max-width: 45%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding: 3px 7px;
  border-radius: 999px;
  color: #99f6e4;
  background: rgba(20, 184, 166, 0.13);
  border: 1px solid rgba(45, 212, 191, 0.22);
  font-size: 11px;
}

.agent-card small {
  display: block;
  margin-top: 8px;
}

.compact-section {
  margin-top: 12px;
}

.summary-grid {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 8px 12px;
  margin-top: 10px;
  font-size: 13px;
}

.summary-grid b {
  min-width: 0;
  color: #f8fafc;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 1280px) {
  .ops-page {
    grid-template-columns: minmax(250px, 22vw) minmax(420px, 1fr) minmax(320px, 30vw);
  }

  .map-bottombar {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 980px) {
  .ops-page {
    height: auto;
    overflow: auto;
    grid-template-columns: 1fr;
  }

  .map-stage {
    height: 58vh;
    min-height: 420px;
    order: -1;
  }

  .side-panel {
    overflow: visible;
  }

  .map-topbar {
    display: grid;
  }

  .map-topbar > div:first-child {
    max-width: none;
  }
}
</style>
