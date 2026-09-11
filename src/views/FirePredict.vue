<template>
  <main class="predict-workbench">
    <aside class="predict-panel control-panel">
      <header class="panel-heading">
        <span>AGENT TOOL + GIS</span>
        <h1>火势推演与空间决策</h1>
        <p>动态环境时间序列驱动的智能体工具</p>
      </header>

      <section class="work-section">
        <label for="scenario">研究场景</label>
        <select id="scenario" v-model="scenarioId">
          <option v-for="item in fireEvent.scenarios" :key="item.scenario_id" :value="item.scenario_id">
            {{ item.name || item.scenario_id }}
          </option>
        </select>
        <div class="input-source">
          <span class="source-dot"></span>
          <div>
            <strong>上游模拟输入</strong>
            <small>火点可替换，风速、风向、湿度和燃料含水率按时步更新</small>
          </div>
        </div>
        <div class="coordinate-grid">
          <label>
            <span>经度</span>
            <input v-model.number="mockPoint.longitude" type="number" step="0.000001">
          </label>
          <label>
            <span>纬度</span>
            <input v-model.number="mockPoint.latitude" type="number" step="0.000001">
          </label>
        </div>
        <div class="section-title input-title">
          <h2>动态环境输入</h2>
          <span>线性插值</span>
        </div>
        <div class="environment-input-grid">
          <label>
            <span>温度 °C</span>
            <input v-model.number="environmentInput.temperatureC" type="number" min="-30" max="65" step="1">
          </label>
          <label>
            <span>湿度 %</span>
            <input v-model.number="environmentInput.humidityPercent" type="number" min="0" max="100" step="1">
          </label>
          <label>
            <span>起始风速 m/s</span>
            <input v-model.number="environmentInput.startWindSpeed" type="number" min="0" max="60" step="0.5">
          </label>
          <label>
            <span>末端风速 m/s</span>
            <input v-model.number="environmentInput.endWindSpeed" type="number" min="0" max="60" step="0.5">
          </label>
          <label>
            <span>起始风向（吹向）</span>
            <input v-model.number="environmentInput.startWindDirection" type="number" min="0" max="359" step="5">
          </label>
          <label>
            <span>末端风向（吹向）</span>
            <input v-model.number="environmentInput.endWindDirection" type="number" min="0" max="359" step="5">
          </label>
          <label>
            <span>燃料含水率</span>
            <input v-model.number="environmentInput.fuelMoisture" type="number" min="0.01" max="0.8" step="0.01">
          </label>
          <label>
            <span>火险指数 FWI</span>
            <input v-model.number="environmentInput.fireWeatherIndex" type="number" min="0" max="100" step="1">
          </label>
          <label class="weather-update-input">
            <span>本轮预测至下次气象更新（分钟）</span>
            <input v-model.number="environmentInput.nextWeatherUpdateMinutes" type="number" min="1" max="1440" step="1">
          </label>
        </div>
        <button class="primary-command" :disabled="busy" @click="runWorkflow">
          {{ busy ? '正在计算...' : '从火点开始推演' }}
        </button>
        <button class="continue-command" :disabled="!canContinue" @click="continueWorkflow">
          {{ continueButtonLabel }}
        </button>
        <button class="secondary-command" :disabled="busy || !fireEvent.spatialAnalysisRun" @click="replanForBlockedRoad">
          {{ roadBlocked ? '恢复道路并重算' : '模拟道路阻断并重算' }}
        </button>
        <div v-if="fireEvent.spreadRun" class="run-lineage">
          <span>{{ runModeLabel }}</span>
          <strong>{{ currentRunWindow }}</strong>
          <small v-if="parentRunId">父运行 {{ shortRunId(parentRunId) }}</small>
          <small v-else>根运行 {{ shortRunId(fireEvent.spreadRun.run_id) }}</small>
        </div>
        <p class="operation-message" :class="{ error: hasError }">{{ message }}</p>
      </section>

      <section class="metric-grid">
        <article>
          <span>推演引擎</span>
          <strong>{{ engineLabel }}</strong>
          <small>{{ environmentSourceLabel }}</small>
        </article>
        <article>
          <span>气象有效期</span>
          <strong>{{ weatherUpdateLabel }}</strong>
          <small>{{ fireEvent.spreadSteps.length }} 个气象有效时刻</small>
        </article>
        <article>
          <span>最终过火面积</span>
          <strong>{{ formatNumber(summary.final_fire_area_km2, 3) }}</strong>
          <small>km²</small>
        </article>
        <article>
          <span>最大蔓延距离</span>
          <strong>{{ formatNumber(summary.maximum_spread_distance_km, 3) }}</strong>
          <small>km</small>
        </article>
      </section>

      <section class="work-section timeline-section">
        <div class="section-title">
          <h2>火线时间序列</h2>
          <span>{{ fireEvent.spreadSteps.length }}</span>
        </div>
        <div v-if="fireEvent.spreadSteps.length" class="timeline-list">
          <button
            v-for="(step, index) in fireEvent.spreadSteps"
            :key="step.step_id"
            :class="{ active: selectedStep === index }"
            @click="selectStep(index)"
          >
            <span>T+{{ step.time_minute }} min</span>
            <strong>{{ formatNumber(step.area_km2, 3) }} km²</strong>
          </button>
        </div>
        <div v-if="fireEvent.spreadSteps.length" class="playback-controls">
          <div class="playback-state">
            <span>动画</span>
            <strong>{{ playbackStatusLabel }}</strong>
          </div>
          <div class="playback-actions">
            <button
              type="button"
              :title="animationPlaying ? '暂停动画' : '播放动画'"
              :aria-label="animationPlaying ? '暂停动画' : '播放动画'"
              @click="toggleFirePlayback"
            >
              {{ animationPlaying ? 'Ⅱ' : '▶' }}
            </button>
            <button
              type="button"
              title="跳到最终火线"
              aria-label="跳到最终火线"
              @click="skipToLatestFireline"
            >
              ⏭
            </button>
          </div>
          <div class="playback-speed" aria-label="动画速度">
            <button
              v-for="item in playbackSpeedOptions"
              :key="item.value"
              type="button"
              :class="{ active: playbackSpeed === item.value }"
              @click="setPlaybackSpeed(item.value)"
            >
              {{ item.label }}
            </button>
          </div>
        </div>
        <p v-else class="empty-state">运行后显示多时步火线。</p>
      </section>

      <section class="work-section environment-section">
        <div class="section-title">
          <h2>当前时步环境</h2>
          <span>{{ selectedStep >= 0 ? `T+${selectedElapsedMinutes} min` : '--' }}</span>
        </div>
        <div v-if="selectedEnvironment" class="environment-grid">
          <div><span>温度</span><strong>{{ formatNumber(selectedEnvironment.temperature_c, 1) }} °C</strong></div>
          <div><span>湿度</span><strong>{{ formatNumber(selectedEnvironment.humidity_percent, 1) }}%</strong></div>
          <div><span>风速</span><strong>{{ formatNumber(selectedEnvironment.wind_speed_m_s, 1) }} m/s</strong></div>
          <div><span>风向</span><strong>{{ formatNumber(selectedEnvironment.wind_direction_deg, 0) }}°</strong></div>
          <div><span>燃料含水率</span><strong>{{ formatNumber(selectedEnvironment.fuel_moisture, 3) }}</strong></div>
          <div><span>火险指数</span><strong>{{ formatNumber(selectedEnvironment.fire_weather_index, 1) }}</strong></div>
          <div v-if="selectedLandscape"><span>最大上坡坡度</span><strong>{{ formatNumber(selectedLandscape.max_uphill_slope_deg, 1) }}°</strong></div>
          <div v-if="selectedLandscape"><span>最大下坡坡度</span><strong>{{ formatNumber(selectedLandscape.max_downhill_slope_deg, 1) }}°</strong></div>
        </div>
        <p v-else class="empty-state">选择火线时步后显示对应环境输入。</p>
      </section>
    </aside>

    <section class="map-stage">
      <CesiumMap ref="mapRef" class="map" :scene-id="scenarioId" />
      <div class="map-toolbar">
        <button :class="{ active: layerState.fire }" @click="toggleLayer('fire')">火线</button>
        <button :class="{ active: layerState.impact }" @click="toggleLayer('impact')">影响对象</button>
        <button :class="{ active: layerState.route }" @click="toggleLayer('route')">应急路线</button>
      </div>
      <div class="map-legend">
        <strong>地图图例</strong>
        <span><i class="fireline"></i>当前火线</span>
        <span><i class="fire"></i>火场范围</span>
        <span><i class="risk-high"></i>高风险区</span>
        <span><i class="risk-medium"></i>中风险区</span>
        <span><i class="risk-low"></i>低风险区</span>
        <span><i class="critical"></i>受威胁目标</span>
        <small>风险区：火线范围及边缘缓冲内的综合风险</small>
      </div>
      <div v-if="roadBlocked" class="map-alert">林区巡护道路已设置为阻断，路线已重新规划</div>
    </section>

    <aside class="predict-panel analysis-panel">
      <header class="panel-heading">
         <span>RISK ASSESSMENT</span>
        <h1>风险评估</h1>
        <p>最终火线、遥感与地物暴露的综合评估</p>
      </header>

      <div class="risk-model-note">
        <strong>演示级综合风险指数</strong>
        <span>用于方案比较，尚未经过历史火灾样本校准，不作为官方灾害等级。</span>
      </div>

      <section class="impact-summary">
        <article>
          <span>受影响居民点</span>
          <strong>{{ summary.affected_settlement_count || 0 }}</strong>
        </article>
        <article>
          <span>受影响人口</span>
          <strong>{{ summary.affected_population || 0 }}</strong>
        </article>
        <article>
          <span>中断道路</span>
          <strong>{{ summary.interrupted_road_count || 0 }}</strong>
        </article>
        <article>
          <span>受影响资源</span>
          <strong>{{ summary.affected_resource_count || 0 }}</strong>
        </article>
      </section>

      <section class="work-section list-section">
        <div class="section-title">
          <h2>影响对象</h2>
          <span>{{ affectedImpacts.length }}</span>
        </div>
        <div v-if="affectedImpacts.length" class="result-list">
          <article v-for="item in affectedImpacts" :key="item.record_id">
            <div>
              <strong>{{ item.name }}</strong>
              <span>{{ impactTypeLabel(item.object_type) }} · 距火线 {{ formatNumber(item.distance_to_fire_km, 2) }} km</span>
            </div>
            <b :class="`severity-${item.severity}`">{{ severityLabel(item.severity) }}</b>
          </article>
        </div>
        <p v-else class="empty-state">等待空间影响分析结果。</p>
      </section>

      <section class="work-section list-section risk-area-section">
        <div class="section-title">
          <h2>空间风险区域</h2>
          <span>{{ riskAreas.length }}</span>
        </div>
        <div v-if="riskAreas.length" class="result-list">
          <article v-for="area in riskAreas" :key="area.properties.object_id">
            <div>
              <strong>{{ riskLabel(area.properties.risk_level) }}区域</strong>
              <span>风险值 {{ formatNumber(area.properties.risk_score, 0) }} · {{ area.properties.grid_cell_count || area.properties.sector_count }} 个风险网格</span>
            </div>
            <b :class="`severity-${area.properties.risk_level}`">{{ riskLabel(area.properties.risk_level) }}</b>
          </article>
        </div>
        <p v-else class="empty-state">推演完成后生成空间风险区域。</p>
      </section>

       <section class="work-section list-section route-section">
        <div class="section-title">
          <h2>A* 应急路线</h2>
          <span>{{ fireEvent.emergencyRoutes.length }}</span>
        </div>
        <div v-if="fireEvent.emergencyRoutes.length" class="route-list">
          <article v-for="route in fireEvent.emergencyRoutes" :key="route.route_id">
            <div class="route-head">
              <strong>{{ route.name }}</strong>
              <b :class="`risk-${route.risk_level}`">{{ riskLabel(route.risk_level) }}</b>
            </div>
            <div class="route-metrics">
              <span>{{ formatNumber(route.distance_km, 2) }} km</span>
              <span>{{ formatNumber(route.eta_minutes, 1) }} min</span>
              <span>{{ route.status === 'replanned' ? '已重算' : '可用' }}</span>
            </div>
            <small>A* 代价面：火线距离、下风向、坡度、燃料与道路可达性</small>
          </article>
        </div>
        <p v-else class="empty-state">等待路线规划结果。</p>
      </section>

    </aside>
  </main>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import CesiumMap from '../components/CesiumMap.vue'
import { useFireEventStore } from '../stores/fireEventStore'

type LayerName = 'fire' | 'impact' | 'route'

const fireEvent = useFireEventStore()
const mapRef = ref<InstanceType<typeof CesiumMap> | null>(null)
const scenarioId = ref(fireEvent.selectedScenarioId || 'muli_lier_village')
const mockPoint = ref({ longitude: 101.269444, latitude: 28.530278, confidence: 0.96 })
const busy = ref(false)
const hasError = ref(false)
const message = ref('等待运行成员丙模拟链路。')
const selectedStep = ref(-1)
const roadBlocked = ref(false)
const animationPlaying = ref(false)
const animationCompleted = ref(false)
const playbackProgress = ref(0)
const playbackSpeed = ref<'fast' | 'normal' | 'slow'>('fast')
const playbackSpeedOptions = [
  { value: 'fast' as const, label: '快速', durationMs: 3200 },
  { value: 'normal' as const, label: '标准', durationMs: 5200 },
  { value: 'slow' as const, label: '慢速', durationMs: 8000 },
]
let renderedFireRunId = ''
const layerState = ref({ fire: true, impact: true, route: false })
const environmentInput = ref({
  temperatureC: 30,
  humidityPercent: 32,
  startWindSpeed: 4,
  endWindSpeed: 7,
  startWindDirection: 315,
  endWindDirection: 340,
  fuelMoisture: 0.16,
  fireWeatherIndex: 18,
  nextWeatherUpdateMinutes: 30,
})

const summary = computed(() => fireEvent.spatialAnalysisRun?.summary || {})
const affectedImpacts = computed(() => fireEvent.spatialImpacts.filter((item: any) => item.affected))
const riskAreas = computed(() => (
  fireEvent.spatialAnalysisRun?.impact_geojson?.features
    ?.filter((feature: any) => feature?.properties?.object_type === 'risk_area') || []
))
const selectedFireStep = computed(() => fireEvent.spreadSteps[selectedStep.value] || null)
const selectedEnvironment = computed(() => selectedFireStep.value?.fireline_geojson?.properties?.environment || null)
const selectedLandscape = computed(() => selectedFireStep.value?.fireline_geojson?.properties?.landscape || null)
const selectedElapsedMinutes = computed(() => Number(selectedFireStep.value?.time_minute || 0))
const parentRunId = computed(() => fireEvent.spreadRun?.result_summary?.parent_run_id || null)
const runModeLabel = computed(() => {
  const mode = fireEvent.spreadRun?.result_summary?.run_mode
  return mode === 'rolling_forecast' ? '滚动续推' : '初始推演'
})
const currentRunWindow = computed(() => {
  const run = fireEvent.spreadRun
  if (!run) return '--'
  return `T+${run.start_minute} 至 T+${run.start_minute + run.horizon_minutes} min`
})
const weatherUpdateLabel = computed(() => {
  const run = fireEvent.spreadRun
  if (!run) return '--'
  const validUntil = Number(
    run.result_summary?.forecast_valid_until_minute
      ?? run.start_minute + run.horizon_minutes,
  )
  return `T+${validUntil} min`
})
const playbackDurationMs = computed(() => (
  playbackSpeedOptions.find((item) => item.value === playbackSpeed.value)?.durationMs
  ?? 3200
))
const playbackStatusLabel = computed(() => {
  if (animationCompleted.value) return '最终火线已就绪'
  if (animationPlaying.value) return `播放中 ${Math.round(playbackProgress.value)}%`
  return `已暂停 ${Math.round(playbackProgress.value)}%`
})
const canContinue = computed(() => (
  Boolean(fireEvent.spreadRun)
  && !busy.value
  && animationCompleted.value
  && !animationPlaying.value
))
const continueButtonLabel = computed(() => {
  if (!fireEvent.spreadRun) return '等待首次推演'
  if (!animationCompleted.value) return '等待最终火线检查点'
  return '从最终火线继续推演'
})
const engineLabel = computed(() => {
  if (!fireEvent.spreadRun) return '待推演'
  return fireEvent.spreadRun.engine === 'dynamic_agent_tool' ? '动态推演工具' : fireEvent.spreadRun.engine
})
const environmentSourceLabel = computed(() => {
  const result = fireEvent.spreadRun?.result_summary || {}
  const count = Number(result.environment_frame_count || 0)
  const source = result.environment_source
  if (!source) return '等待环境时间序列'
  if (source === 'agent_supplied_timeline') return `${count} 个智能体环境帧`
  if (source === 'database_trend_projection') return `${count} 个观测趋势环境帧`
  return `${count} 个动态环境帧`
})

function formatNumber(value: any, digits = 2) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed.toFixed(digits) : '--'
}

function shortRunId(value: string) {
  return value ? `${value.slice(0, 12)}...` : '--'
}

function environmentTimeline(horizonMinutes: number, source: string) {
  const input = environmentInput.value
  return [
    {
      elapsed_minutes: 0,
      temperature_c: input.temperatureC,
      humidity_percent: input.humidityPercent,
      wind_speed_m_s: input.startWindSpeed,
      wind_direction_deg: input.startWindDirection,
      fuel_moisture: input.fuelMoisture,
      fire_weather_index: input.fireWeatherIndex,
      precipitation_mm_h: 0,
      source,
    },
    {
      elapsed_minutes: horizonMinutes,
      temperature_c: input.temperatureC,
      humidity_percent: input.humidityPercent,
      wind_speed_m_s: input.endWindSpeed,
      wind_direction_deg: input.endWindDirection,
      fuel_moisture: input.fuelMoisture,
      fire_weather_index: input.fireWeatherIndex,
      precipitation_mm_h: 0,
      source,
    },
  ]
}

function severityLabel(value: string) {
  return ({ critical: '火线内', high: '高威胁', medium: '关注', low: '低' } as Record<string, string>)[value] || value
}

function riskLabel(value: string) {
  return ({ high: '高风险', medium: '中风险', low: '低风险' } as Record<string, string>)[value] || value
}

function impactTypeLabel(value: string) {
  return ({
    settlement: '居民点',
    facility: '设施',
    road: '道路',
    power: '输电设施',
    watchtower: '瞭望塔',
    water_source: '水源',
  } as Record<string, string>)[value] || value
}

function routeCoordinates(route: any): [number, number][] {
  return route?.geometry?.geojson?.coordinates || []
}

function handleFireFrame(payload: { index: number, total: number, progress: number }) {
  playbackProgress.value = payload.progress
  selectedStep.value = Math.max(
    0,
    Math.min(fireEvent.spreadSteps.length - 1, payload.index),
  )
}

function handleFirePlaybackState(playing: boolean) {
  animationPlaying.value = playing
}

function handleFirePlaybackComplete() {
  animationPlaying.value = false
  animationCompleted.value = true
  playbackProgress.value = 100
  selectedStep.value = Math.max(0, fireEvent.spreadSteps.length - 1)
  if (!busy.value) {
    message.value = '最终火线检查点已就绪，可更新气象条件后继续推演。'
  }
}

function renderMap(options: { replayFire?: boolean, autoPlay?: boolean } = {}) {
  const map = mapRef.value
  if (!map) return
  map.clearDemoEntities?.()
  map.clearHotspots?.()

  const center: [number, number] = [mockPoint.value.longitude, mockPoint.value.latitude]
  map.addHotspotGeoJson?.({
    type: 'FeatureCollection',
    features: [{
      type: 'Feature',
      properties: { name: '模拟确认火点', source: 'upstream_mock' },
      geometry: { type: 'Point', coordinates: center },
    }],
  })

  const currentRunId = String(fireEvent.spreadRun?.run_id || '')
  if (!layerState.value.fire) {
    map.clearFireFronts?.()
    renderedFireRunId = ''
    animationPlaying.value = false
  } else if (
    fireEvent.forefireResult?.geojson?.features?.length
    && (options.replayFire || renderedFireRunId !== currentRunId)
  ) {
    animationCompleted.value = false
    animationPlaying.value = false
    playbackProgress.value = 0
    selectedStep.value = 0
    map.addFireFrontTimeline?.(fireEvent.forefireResult.geojson, {
      durationMs: playbackDurationMs.value,
      autoPlay: options.autoPlay !== false,
      onFrame: handleFireFrame,
      onPlaybackState: handleFirePlaybackState,
      onComplete: handleFirePlaybackComplete,
    })
    renderedFireRunId = currentRunId
    if (options.autoPlay === false) {
      map.setFireTimelineProgress?.(100)
    }
  }

  if (layerState.value.impact) {
    affectedImpacts.value.forEach((item: any) => {
      if (item.geometry?.type !== 'Point') return
      const color = item.severity === 'critical' ? '#ef4444' : item.severity === 'high' ? '#f59e0b' : '#38bdf8'
      map.addDemoPoint?.({
        name: item.name,
        label: item.name,
        position: item.geometry.coordinates,
        color,
        size: item.severity === 'critical' ? 15 : 11,
      })
    })
  }

  riskAreas.value.forEach((area: any) => {
    const coordinates = area.geometry?.coordinates?.[0]
    if (!Array.isArray(coordinates) || coordinates.length < 3) return
    const colors: Record<string, string> = { high: '#ef4444', medium: '#f59e0b', low: '#38bdf8' }
    map.addDemoArea?.({
      name: `${riskLabel(area.properties?.risk_level)}风险区域`,
      coordinates,
      color: colors[area.properties?.risk_level] || '#94a3b8',
    })
  })

  if (layerState.value.route) {
    const colors: Record<string, string> = {
      rescue_approach: '#38bdf8',
      evacuation: '#22c55e',
      evacuation_backup: '#f59e0b',
    }
    fireEvent.emergencyRoutes.forEach((route: any) => {
      const coordinates = routeCoordinates(route)
      if (coordinates.length < 2) return
      map.addDemoRoute?.({
        name: route.name,
        coordinates,
        color: colors[route.route_type] || '#e2e8f0',
        width: route.route_type === 'evacuation' ? 7 : 5,
        arrow: true,
      })
    })
  }
  // 风险面通常只覆盖火场周边几公里，使用研究区总览高度会让它几乎不可见。
  map.flyTo?.({ center, zoom: riskAreas.value.length ? 14 : 11.5 })
}

async function ensureEvent() {
  const currentScenario = fireEvent.eventDetail?.scenario_id
  if (fireEvent.eventId && currentScenario === scenarioId.value) return
  await fireEvent.startSimulatedEvent({
    scenario_id: scenarioId.value,
    name: '成员丙火势推演模拟事件',
    ignition_point: mockPoint.value,
    metadata: {
      input_source: 'upstream_mock',
      owner: 'member/wydze',
      simulated: true,
    },
  })
}

async function runWorkflow() {
  busy.value = true
  hasError.value = false
  message.value = '正在准备模拟火点与环境快照...'
  try {
    await ensureEvent()
    message.value = '正在调用动态火情推演工具...'
    const weatherUpdateMinutes = Math.max(1, Number(environmentInput.value.nextWeatherUpdateMinutes || 1))
    await fireEvent.createSpreadRun({
      ignition_point: mockPoint.value,
      input_source: 'upstream_mock',
      run_mode: 'initial_forecast',
      environment_timeline: environmentTimeline(weatherUpdateMinutes, 'manual_initial_forecast'),
    })
    message.value = '正在计算影响对象和 A* 应急路线...'
    await fireEvent.createSpatialAnalysis({
      include_routes: false,
      threat_buffer_km: 0.55,
      blocked_road_ids: roadBlocked.value ? ['road_forest_01'] : [],
    })
    selectedStep.value = 0
    message.value = `计算已完成，正在快速播放至 ${weatherUpdateMinutes} 分钟后的火线。`
    await nextTick()
    renderMap({ autoPlay: true })
  } catch (error: any) {
    hasError.value = true
    message.value = error?.message || '计算失败，请检查后端服务。'
  } finally {
    busy.value = false
  }
}

async function continueWorkflow() {
  const previousRunId = fireEvent.spreadRun?.run_id
  if (!previousRunId) return

  busy.value = true
  hasError.value = false
  message.value = '正在从当前最终火线应用新环境继续推演...'
  try {
    const weatherUpdateMinutes = Math.max(1, Number(environmentInput.value.nextWeatherUpdateMinutes || 1))
    await fireEvent.createSpreadRun({
      continue_from_run_id: previousRunId,
      run_mode: 'rolling_forecast',
      input_source: 'manual_environment_update',
      environment_timeline: environmentTimeline(weatherUpdateMinutes, 'manual_rolling_update'),
    })
    message.value = '新火线已生成，正在重算影响对象和 A* 路线...'
    await fireEvent.createSpatialAnalysis({
      include_routes: false,
      threat_buffer_km: 0.55,
      blocked_road_ids: roadBlocked.value ? ['road_forest_01'] : [],
    })
    selectedStep.value = 0
    message.value = `续推计算已完成，正在播放 ${shortRunId(previousRunId)} 之后的新火线。`
    await nextTick()
    renderMap({ autoPlay: true })
  } catch (error: any) {
    hasError.value = true
    message.value = error?.message || '续推失败，请检查父运行和环境输入。'
  } finally {
    busy.value = false
  }
}

async function replanForBlockedRoad() {
  busy.value = true
  hasError.value = false
  roadBlocked.value = !roadBlocked.value
  message.value = roadBlocked.value ? '正在绕开阻断道路重新规划...' : '正在恢复道路条件重新规划...'
  try {
    await fireEvent.createSpatialAnalysis({
      threat_buffer_km: 0.55,
      blocked_road_ids: roadBlocked.value ? ['road_forest_01'] : [],
    })
    message.value = roadBlocked.value ? '道路阻断情景重算完成。' : '道路条件已恢复并完成重算。'
    await nextTick()
    renderMap()
  } catch (error: any) {
    roadBlocked.value = !roadBlocked.value
    hasError.value = true
    message.value = error?.message || '路线重算失败。'
  } finally {
    busy.value = false
  }
}

function selectStep(index: number) {
  selectedStep.value = index
  const progress = fireEvent.spreadSteps.length <= 1 ? 1 : index / (fireEvent.spreadSteps.length - 1)
  mapRef.value?.pauseFireTimeline?.()
  animationPlaying.value = false
  animationCompleted.value = index === fireEvent.spreadSteps.length - 1
  mapRef.value?.setFireTimelineProgress?.(progress * 100)
}

function toggleFirePlayback() {
  if (animationPlaying.value) {
    mapRef.value?.pauseFireTimeline?.()
    return
  }
  if (animationCompleted.value) {
    animationCompleted.value = false
    playbackProgress.value = 0
  }
  mapRef.value?.playFireTimeline?.()
}

function skipToLatestFireline() {
  mapRef.value?.setFireTimelineProgress?.(100)
}

function setPlaybackSpeed(value: 'fast' | 'normal' | 'slow') {
  playbackSpeed.value = value
  mapRef.value?.setFireTimelineDuration?.(playbackDurationMs.value)
}

function toggleLayer(layer: LayerName) {
  layerState.value[layer] = !layerState.value[layer]
  renderMap({ autoPlay: false })
}

onMounted(async () => {
  await fireEvent.loadScenarios()
  if (fireEvent.eventId) {
    await Promise.allSettled([
      fireEvent.loadLatestSpreadRun(),
      fireEvent.loadLatestSpatialAnalysis(),
      fireEvent.loadClockState(),
    ])
    await nextTick()
    renderMap({ autoPlay: false })
  }
})

watch(scenarioId, (value) => {
  const scenario = fireEvent.scenarios.find((item: any) => item.scenario_id === value)
  if (!scenario) return
  mockPoint.value = {
    longitude: Number(scenario.longitude),
    latitude: Number(scenario.latitude),
    confidence: 0.96,
  }
})

watch(
  () => [fireEvent.forefireResult, fireEvent.spatialAnalysisRun, fireEvent.emergencyRoutes],
  () => {
    if (busy.value) return
    nextTick(() => renderMap())
  },
  { deep: true },
)
</script>

<style scoped>
.predict-workbench {
  width: 100%;
  height: 100%;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(300px, 21vw) minmax(520px, 1fr) minmax(360px, 26vw);
  overflow: hidden;
  color: #e8f2fb;
  background: #07111b;
}

.predict-panel {
  min-width: 0;
  min-height: 0;
  overflow-y: auto;
  padding: 16px;
  background: #0a1926;
}

.control-panel { border-right: 1px solid rgba(125, 211, 252, 0.18); }
.analysis-panel {
  border-left: 1px solid rgba(45, 212, 191, 0.2);
  background: #091a22;
}
.analysis-panel .panel-heading h1 {
  font-size: 0;
}
.analysis-panel .panel-heading h1::after {
  content: '风险评估';
  font-size: 20px;
}

.panel-heading { margin-bottom: 14px; }
.panel-heading span {
  color: #67e8f9;
  font-size: 11px;
  font-weight: 800;
}
.panel-heading h1 {
  margin: 5px 0 3px;
  font-size: 20px;
  letter-spacing: 0;
}
.panel-heading p,
.empty-state,
.operation-message {
  color: #8fa6ba;
  font-size: 12px;
  line-height: 1.5;
}

.work-section {
  display: grid;
  gap: 10px;
  padding: 12px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 8px;
  background: rgba(4, 15, 25, 0.66);
}
.work-section + .work-section { margin-top: 12px; }
.work-section > label,
.coordinate-grid label span {
  color: #a8bacb;
  font-size: 12px;
}

select,
input,
button {
  min-width: 0;
  min-height: 36px;
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 6px;
  background: #0d2130;
  color: #edf6ff;
  font: inherit;
}
select,
input {
  width: 100%;
  padding: 0 9px;
}
button {
  cursor: pointer;
  font-weight: 700;
}
button:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.input-source {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 9px;
  border: 1px solid rgba(245, 158, 11, 0.26);
  border-radius: 7px;
  background: rgba(120, 53, 15, 0.16);
}
.source-dot {
  width: 8px;
  height: 8px;
  flex: 0 0 8px;
  border-radius: 50%;
  background: #f59e0b;
  box-shadow: 0 0 8px rgba(245, 158, 11, 0.7);
}
.input-source div {
  min-width: 0;
  display: grid;
  gap: 2px;
}
.input-source strong {
  color: #fcd34d;
  font-size: 12px;
}
.input-source small {
  color: #bca477;
  font-size: 10px;
}
.landscape-source {
  min-width: 0;
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 3px 8px;
  padding: 8px 9px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-left: 3px solid #64748b;
  background: rgba(30, 41, 59, 0.28);
}
.landscape-source.active {
  border-left-color: #22c55e;
  background: rgba(20, 83, 45, 0.2);
}
.landscape-source span {
  color: #a7f3d0;
  font-size: 11px;
  font-weight: 800;
}
.landscape-source strong {
  min-width: 0;
  color: #ecfdf5;
  font-size: 11px;
  text-align: right;
  word-break: break-word;
}
.landscape-source small {
  grid-column: 1 / -1;
  color: #93b6a1;
  font-size: 10px;
}

.coordinate-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.coordinate-grid label {
  display: grid;
  gap: 5px;
}
.input-title {
  margin-top: 2px;
}
.environment-input-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}
.environment-input-grid label {
  min-width: 0;
  display: grid;
  gap: 5px;
}
.environment-input-grid span {
  color: #a8bacb;
  font-size: 11px;
}
.weather-update-input {
  grid-column: 1 / -1;
}
.primary-command {
  background: #0f766e;
  border-color: #2dd4bf;
}
.continue-command {
  color: #ecfeff;
  background: #9a3412;
  border-color: #fb923c;
}
.secondary-command {
  background: #164e63;
  border-color: #38bdf8;
}
.run-lineage {
  min-width: 0;
  display: grid;
  grid-template-columns: auto 1fr;
  align-items: center;
  gap: 3px 8px;
  padding: 8px 9px;
  border-left: 3px solid #fb923c;
  background: rgba(124, 45, 18, 0.2);
}
.run-lineage span {
  color: #fed7aa;
  font-size: 11px;
  font-weight: 800;
}
.run-lineage strong {
  color: #fff7ed;
  font-size: 11px;
  text-align: right;
}
.run-lineage small {
  grid-column: 1 / -1;
  color: #c8a98f;
  font-size: 10px;
}
.operation-message.error { color: #fca5a5; }

.metric-grid,
.impact-summary {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin: 12px 0;
}
.metric-grid article,
.impact-summary article {
  min-height: 80px;
  display: grid;
  align-content: center;
  gap: 4px;
  padding: 10px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  border-radius: 8px;
  background: #0d2232;
}
.metric-grid span,
.metric-grid small,
.impact-summary span {
  color: #91a8bb;
  font-size: 11px;
}
.metric-grid strong,
.impact-summary strong {
  color: #f8fafc;
  font-size: 20px;
  word-break: break-word;
}
.impact-summary strong {
  color: #5eead4;
  font-size: 24px;
}
.risk-model-note {
  display: grid;
  gap: 4px;
  padding: 9px 10px;
  border-left: 3px solid #f59e0b;
  background: rgba(120, 53, 15, 0.18);
}
.risk-model-note strong {
  color: #fde68a;
  font-size: 12px;
}
.risk-model-note span {
  color: #c7b79a;
  font-size: 10px;
  line-height: 1.45;
}

.section-title,
.route-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.section-title h2 {
  margin: 0;
  font-size: 14px;
}
.section-title > span {
  color: #67e8f9;
  font-size: 12px;
}
.timeline-list,
.result-list,
.route-list,
.landcover-list {
  display: grid;
  gap: 7px;
}
.timeline-list button {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 38px;
  padding: 0 9px;
  color: #9fb4c7;
  background: #0c1d2b;
  border-color: rgba(148, 163, 184, 0.14);
}
.timeline-list button.active {
  color: #ecfeff;
  border-color: #22d3ee;
  background: #164e63;
}
.playback-controls {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  padding-top: 3px;
}
.playback-state {
  min-width: 0;
  display: grid;
  gap: 2px;
}
.playback-state span {
  color: #829bad;
  font-size: 10px;
}
.playback-state strong {
  color: #dff7ff;
  font-size: 11px;
}
.playback-actions {
  display: flex;
  gap: 5px;
}
.playback-actions button {
  width: 36px;
  min-height: 34px;
  color: #cffafe;
  border-color: rgba(34, 211, 238, 0.32);
  background: #103246;
  font-size: 13px;
}
.playback-speed {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  padding: 3px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 6px;
  background: #081722;
}
.playback-speed button {
  min-height: 29px;
  color: #829bad;
  border-color: transparent;
  background: transparent;
  font-size: 10px;
}
.playback-speed button.active {
  color: #ecfeff;
  border-color: rgba(34, 211, 238, 0.3);
  background: #155e75;
}

.map-stage {
  position: relative;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  background: #02070d;
}
.map {
  position: absolute;
  inset: 0;
}
.map-toolbar,
.map-legend,
.map-alert {
  position: absolute;
  z-index: 5;
  border: 1px solid rgba(186, 230, 253, 0.2);
  border-radius: 7px;
  background: rgba(3, 12, 21, 0.84);
  backdrop-filter: blur(8px);
}
.route-section {
  display: none;
}
.map-toolbar {
  top: 14px;
  left: 14px;
  display: flex;
  gap: 5px;
  padding: 5px;
}
.map-toolbar button {
  min-height: 30px;
  padding: 0 10px;
  color: #8fa6ba;
  background: transparent;
  border-color: transparent;
  font-size: 12px;
}
.map-toolbar button.active {
  color: #ecfeff;
  background: #155e75;
  border-color: #22d3ee;
}
.map-toolbar button:nth-child(3) {
  display: none;
}
.map-legend {
  left: 14px;
  bottom: 14px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, auto));
  gap: 8px 13px;
  max-width: min(360px, calc(100% - 28px));
  padding: 10px 12px;
  color: #cbd5e1;
  font-size: 11px;
}
.map-legend strong {
  grid-column: 1 / -1;
  color: #f8fafc;
  font-size: 12px;
}
.map-legend span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.map-legend i {
  display: inline-block;
  width: 9px;
  height: 9px;
  border-radius: 2px;
}
.map-legend .fireline {
  width: 13px;
  height: 3px;
  border-radius: 0;
  background: #fff;
  box-shadow: 0 0 0 1px #ef4444;
}
.map-legend .fire { background: rgba(239, 68, 68, 0.78); }
.map-legend .risk-high { background: #ef4444; }
.map-legend .risk-medium { background: #f59e0b; }
.map-legend .risk-low { background: #38bdf8; }
.map-legend .critical { background: #f59e0b; }
.map-legend .rescue { background: #38bdf8; }
.map-legend .evacuation { background: #22c55e; }
.map-legend small {
  grid-column: 1 / -1;
  color: #93a9ba;
  line-height: 1.4;
}
.map-alert {
  top: 14px;
  right: 14px;
  padding: 9px 12px;
  color: #fde68a;
  border-color: rgba(245, 158, 11, 0.38);
  background: rgba(69, 26, 3, 0.86);
  font-size: 12px;
}

.result-list article,
.route-list article {
  padding: 10px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-radius: 7px;
  background: #0b2029;
}
.result-list article {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.result-list article > div {
  min-width: 0;
  display: grid;
  gap: 3px;
}
.result-list strong,
.route-head strong { font-size: 13px; }
.result-list span,
.route-metrics,
.route-list small {
  color: #91a8bb;
  font-size: 11px;
}
.result-list b,
.route-head b {
  flex: 0 0 auto;
  padding: 3px 6px;
  border-radius: 4px;
  font-size: 10px;
}
.severity-critical,
.risk-high {
  color: #fecaca;
  background: rgba(220, 38, 38, 0.22);
}
.severity-high,
.risk-medium {
  color: #fde68a;
  background: rgba(217, 119, 6, 0.2);
}
.severity-medium,
.risk-low {
  color: #a7f3d0;
  background: rgba(5, 150, 105, 0.2);
}
.route-list article {
  display: grid;
  gap: 8px;
}
.route-metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;
}
.route-metrics span {
  padding: 5px;
  text-align: center;
  border-radius: 4px;
  background: rgba(15, 118, 110, 0.16);
}
.landcover-list div {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  padding-bottom: 7px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
  font-size: 12px;
}
.landcover-list span { color: #9fb4c7; }
.landcover-list strong { color: #e2e8f0; }

.environment-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 7px;
}
.environment-grid div {
  min-width: 0;
  display: grid;
  gap: 3px;
  padding: 7px 8px;
  border-radius: 6px;
  background: rgba(14, 116, 144, 0.13);
}
.environment-grid span {
  color: #8fa6ba;
  font-size: 10px;
}
.environment-grid strong {
  color: #dff7ff;
  font-size: 12px;
  word-break: break-word;
}

@media (max-width: 1180px) {
  .predict-workbench {
    grid-template-columns: 280px minmax(430px, 1fr) 330px;
  }
}
@media (max-width: 900px) {
  .predict-workbench {
    height: auto;
    grid-template-columns: 1fr;
    overflow: auto;
  }
  .map-stage {
    min-height: 520px;
    order: -1;
  }
  .predict-panel { overflow: visible; }
}
</style>
