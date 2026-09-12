<template>
  <main class="realtime-page">
    <aside class="data-panel">
      <header class="panel-header">
        <span class="eyebrow">FIRE MONITORING CENTER</span>
        <div class="mode-control">
          <label for="monitor-mode">监测模式</label>
          <select id="monitor-mode" v-model="monitorMode" @change="handleModeChange">
            <option value="history">历史火灾复盘</option>
            <option value="realtime">实时火情监测</option>
          </select>
        </div>
        <h1>{{ monitorMode === 'history' ? '历史火灾复盘' : '实时火情监测' }}</h1>
        <p v-if="monitorMode === 'history'">{{ event?.name || 'Dixie Fire' }} · 历史观测回放</p>
        <p v-else>全球实时监测框架 · 当前显示支持的卫星区域</p>
      </header>

      <section class="status-strip" :class="{ ready: monitorMode === 'history' ? loaded : realtimeReady, error: Boolean(activeError) }">
        <span class="status-dot"></span>
        <span>{{ activeError || (monitorMode === 'history' ? (loaded ? '真实历史数据已加载' : '正在加载数据') : realtimeStatusText) }}</span>
      </section>

      <section v-if="monitorMode === 'history'" class="metric-grid">
        <article class="metric"><span>候选火点</span><strong>{{ formatNumber(hotspotTotal) }}</strong><small>MTBS 边界内 FIRMS</small></article>
        <article class="metric"><span>日聚合单元</span><strong>{{ formatNumber(clusterTotal) }}</strong><small>日尺度 / 空间网格</small></article>
        <article class="metric"><span>最终过火</span><strong>{{ burnedArea ? formatArea(burnedArea.area_m2) : '--' }}</strong><small>MTBS 真实边界</small></article>
        <article class="metric"><span>气象记录</span><strong>{{ weatherTotal || '--' }}</strong><small>NASA POWER 日尺度</small></article>
      </section>

      <section v-else class="metric-grid">
        <article class="metric"><span>当前候选火点</span><strong>{{ formatNumber(realtimeHotspotTotal) }}</strong><small>{{ selectedRealtimeRegion?.satellite || '--' }}</small></article>
        <article class="metric"><span>数据延迟</span><strong>{{ realtimeLatencyText }}</strong><small>卫星观测至系统获取</small></article>
        <article class="metric"><span>观测时间</span><strong>{{ realtimeObservedAtText }}</strong><small>UTC</small></article>
        <article class="metric"><span>检测状态</span><strong>{{ realtimeDetectionText }}</strong><small>热异常候选提取</small></article>
      </section>

      <section v-if="monitorMode === 'history'" class="data-section">
        <div class="section-heading"><h2>当前日期气象</h2><span>{{ currentWeather?.observed_on || '--' }}</span></div>
        <div class="weather-grid">
          <div><span>平均温度</span><b>{{ valueWithUnit(currentWeather?.temperature_c, '℃') }}</b></div>
          <div><span>相对湿度</span><b>{{ valueWithUnit(currentWeather?.relative_humidity_percent, '%') }}</b></div>
          <div><span>风速</span><b>{{ valueWithUnit(currentWeather?.wind_speed_m_s, 'm/s') }}</b></div>
          <div><span>风向</span><b>{{ valueWithUnit(currentWeather?.wind_direction_deg, '°') }}</b></div>
          <div><span>日降水</span><b>{{ valueWithUnit(currentWeather?.precipitation_mm, ' mm') }}</b></div>
          <div><span>日照辐射</span><b>{{ valueWithUnit(currentWeather?.solar_radiation_kwh_m2_day, ' kWh') }}</b></div>
        </div>
        <p class="weather-note">火点为 FIRMS 历史观测；气象为 NASA POWER 日尺度数据，随回放日期匹配。</p>
      </section>

      <section v-else class="data-section realtime-section">
        <div class="section-heading"><h2>实时监测区域</h2><span>{{ supportedRealtimeRegions.length }} 个区域可用</span></div>
        <select v-model="selectedRegionId" class="region-select" @change="handleRegionChange">
          <option v-for="region in realtimeRegions" :key="region.id" :value="region.id">
            {{ region.label }} · {{ region.satellite }}{{ region.supported ? '' : ' · 暂不支持' }}
          </option>
        </select>
        <div v-if="selectedRealtimeRegion" class="region-card">
          <div><span>数据源</span><b>{{ selectedRealtimeRegion.satellite }}</b></div>
          <div><span>覆盖范围</span><b>{{ selectedRealtimeRegion.coverage }}</b></div>
          <div><span>更新周期</span><b>{{ selectedRealtimeRegion.refresh }}</b></div>
          <div><span>数据状态</span><b>{{ selectedRealtimeRegion.supported ? realtimeDataState : '区域暂不支持' }}</b></div>
        </div>
        <div class="realtime-source-list">
          <div><strong>GOES ABI 热红外波段</strong><span>候选热异常检测</span></div>
          <div><strong>FIRMS NRT</strong><span>全球火点参考与交叉校验</span></div>
          <div><strong>GOES FDCC 产品</strong><span>卫星火点结果校验</span></div>
          <div><strong>Himawari-8/9</strong><span>亚洲区域实时适配器</span></div>
        </div>
        <p class="realtime-note">进入实时模式时请求最新观测。后端同步服务负责下载原始卫星数据、执行热异常检测，并清理过期影像，仅保留最近可用时相。</p>
      </section>

      <section v-if="monitorMode === 'history'" class="data-section">
        <div class="section-heading"><h2>数据目录</h2><span>{{ datasetCount }} 个数据集</span></div>
        <ul class="dataset-list">
          <li v-for="item in datasetItems" :key="item.id"><span class="dataset-state"></span><div><strong>{{ item.label }}</strong><small>{{ item.detail }}</small></div></li>
        </ul>
      </section>

      <button v-if="monitorMode === 'history'" class="refresh-button" type="button" :disabled="loading" @click="loadData">{{ loading ? '刷新中...' : '刷新历史数据' }}</button>
      <button v-else class="refresh-button realtime-refresh" type="button" :disabled="realtimeLoading || !selectedRealtimeRegion?.supported" @click="syncRealtimeData">{{ realtimeLoading ? '同步最新卫星数据...' : '获取最新实时数据' }}</button>
    </aside>

    <section class="map-panel">
      <CesiumMap v-if="mapReady" :key="`${monitorMode}-${selectedRegionId}`" ref="mapRef" class="map" :longitude="mapCenter[0]" :latitude="mapCenter[1]" :height="monitorMode === 'history' ? 65000 : 120000" :scene-id="monitorMode === 'history' ? 'dixie_fire_2021' : selectedRegionId" />
      <div v-else class="map-loading">{{ monitorMode === 'history' ? '正在准备 Dixie Fire 研究区' : '正在准备实时监测区域' }}</div>
      <div v-if="monitorMode === 'history'" class="map-overlay map-title"><span>历史事件回放 · {{ currentReplayDate }}</span><strong>Dixie Fire · California · 2021</strong></div>
      <div v-else class="map-overlay map-title"><span>实时卫星监测 · {{ selectedRealtimeRegion?.satellite || '--' }}</span><strong>{{ selectedRealtimeRegion?.label || '实时监测区域' }}</strong></div>
      <div class="map-legend">
        <template v-if="monitorMode === 'history'"><span><i class="hotspot-key"></i> FIRMS 日聚合火点</span><span><i class="burned-key"></i> MTBS 过火边界</span></template>
        <template v-else><span><i class="hotspot-key"></i> 实时热异常候选点</span><span><i class="source-key"></i> {{ selectedRealtimeRegion?.satellite || '实时卫星' }}</span></template>
      </div>
      <div v-if="monitorMode === 'history'" class="weather-simulation" :class="{ 'is-visible': simulationVisible }" :style="weatherLayerStyle" aria-hidden="true">
        <div v-if="showWind" class="weather-effect wind-effect"></div>
        <div v-if="showCloud" class="weather-effect cloud-effect"></div>
        <div v-if="showRain && hasRain" class="weather-effect rain-effect"></div>
      </div>
      <section v-if="monitorMode === 'history'" class="replay-dock" aria-label="历史火情日回放">
        <div class="replay-dock-header">
          <div>
            <span class="dock-kicker">HISTORICAL FIRE MONITORING</span>
            <strong>{{ currentReplayDate }}</strong>
            <small>{{ replayFrames.length ? `${replayIndex + 1} / ${replayFrames.length} 天` : '等待数据' }}</small>
          </div>
          <div class="simulation-summary">
            <span>当前点位 {{ formatNumber(currentFramePointCount) }}</span>
            <span>最大 FRP {{ valueWithUnit(currentFrame?.max_frp_mw, ' MW') }}</span>
          </div>
        </div>
        <input
          v-model.number="replayIndex"
          class="replay-slider"
          type="range"
          min="0"
          :max="Math.max(0, replayFrames.length - 1)"
          :disabled="!replayFrames.length || loading"
          aria-label="火情历史回放日期时间轴"
          @input="stopReplay"
        />
        <div class="replay-scale"><span>{{ replayStartTime }}</span><span>{{ replayEndTime }}</span></div>
        <div class="replay-dock-footer">
          <button class="replay-button" type="button" :disabled="replayFrames.length < 2" @click="toggleReplay">
            {{ isPlaying ? '暂停回放' : '播放回放' }}
          </button>
          <div class="simulation-toggles" aria-label="气象模拟图层">
            <label><input v-model="showWind" type="checkbox" />风</label>
            <label><input v-model="showCloud" type="checkbox" />云</label>
            <label :class="{ disabled: !hasRain }"><input v-model="showRain" type="checkbox" :disabled="!hasRain" />雨</label>
          </div>
          <span class="simulation-note">气象效果为基于当前日期参数的可选模拟</span>
        </div>
      </section>
      <section v-else class="realtime-map-dock" aria-label="实时卫星监测状态">
        <div class="realtime-map-dock-header">
          <div><span class="dock-kicker">LIVE SATELLITE MONITORING</span><strong>{{ selectedRealtimeRegion?.satellite || '--' }}</strong></div>
          <span class="live-indicator" :class="{ ready: realtimeReady }"><i></i>{{ realtimeReady ? '在线数据' : '等待服务' }}</span>
        </div>
        <div class="realtime-map-stats"><span>候选火点 <b>{{ formatNumber(realtimeHotspotTotal) }}</b></span><span>观测时间 <b>{{ realtimeObservedAtText }}</b></span><span>更新时间 <b>{{ realtimeFetchedAtText }}</b></span></div>
        <p>{{ realtimeError || realtimeStatusText }}</p>
      </section>
    </section>

    <aside class="evidence-panel">
      <header class="panel-header compact"><span class="eyebrow">DATA AGENT HANDOFF</span><h2>数据交接状态</h2><p>此页面展示数据源头，不代表视觉确认或火势推演已经完成。</p></header>
      <section class="handoff-card"><span class="card-label">乙 · 视觉核验</span><strong>{{ clusterTotal ? '候选点可供 Qwen-VL 核验' : '等待候选点' }}</strong><p>使用聚合火点坐标和影像引用字段，不把 FIRMS 候选直接标记为真实火灾。</p></section>
      <section class="handoff-card"><span class="card-label">丙 · ForeFire 输入</span><strong>{{ rasterReady ? '地形与燃料栅格已就绪' : '等待栅格数据' }}</strong><p>DEM、坡度、坡向和 WorldCover 简化燃料栅格均为 30 m、EPSG:32610。</p></section>
      <section class="handoff-card"><span class="card-label">丁 · 影响分析</span><strong>{{ burnedArea ? '过火边界和气象可调用' : '等待基础数据' }}</strong><p>后续叠加道路、建筑、居民点和火势推演结果，生成资源与疏散方案。</p></section>
      <section v-if="monitorMode === 'history'" class="source-section"><h3>事件信息</h3><dl><dt>事件状态</dt><dd>{{ event?.status || '--' }}</dd><dt>观测时段</dt><dd>{{ eventPeriod }}</dd><dt>起火参考点</dt><dd>{{ ignitionText }}</dd><dt>数据检索</dt><dd>deterministic manifest</dd><dt>大模型依赖</dt><dd>当前不需要 API Key</dd></dl></section>
      <section v-else class="source-section"><h3>实时数据说明</h3><dl><dt>监测区域</dt><dd>{{ selectedRealtimeRegion?.label || '--' }}</dd><dt>卫星数据</dt><dd>{{ selectedRealtimeRegion?.satellite || '--' }}</dd><dt>观测时间</dt><dd>{{ realtimeObservedAtText }}</dd><dt>数据获取</dt><dd>{{ realtimeFetchedAtText }}</dd><dt>候选点状态</dt><dd>{{ realtimeDetectionText }}</dd></dl></section>
    </aside>
  </main>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import CesiumMap from '../components/CesiumMap.vue'

const apiBase = String(import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')
const eventId = 'dixie_fire_2021'
const mapRef = ref<InstanceType<typeof CesiumMap> | null>(null)
const mapReady = ref(false)
const loading = ref(false)
const loaded = ref(false)
const error = ref('')
const event = ref<any>(null)
const burnedArea = ref<any>(null)
const weatherRows = ref<any[]>([])
const weatherTotal = ref(0)
const hotspotTotal = ref(0)
const clusterTotal = ref(0)
const catalog = ref<any>(null)
const rasterReady = ref(false)
const mapCenter = ref<[number, number]>([-120.8, 40.3])
const burnedGeometry = ref<any>(null)
const hotspotGeoJson = ref<any>(null)
const realtimeGeoJson = ref<any>({ type: 'FeatureCollection', features: [] })
const latestWeather = ref<any>(null)
const replayFrames = ref<Array<{ observed_at: string, rows: any[], point_count: number, max_frp_mw: number | null }>>([])
const replayIndex = ref(0)
const isPlaying = ref(false)
let replayTimer: ReturnType<typeof setInterval> | null = null
const showWind = ref(false)
const showCloud = ref(false)
const showRain = ref(false)
type MonitorMode = 'history' | 'realtime'
type RealtimeRegion = { id: string, label: string, satellite: string, coverage: string, refresh: string, supported: boolean, bbox: [number, number, number, number] }
const monitorMode = ref<MonitorMode>('history')
const realtimeLoading = ref(false)
const realtimeReady = ref(false)
const realtimeError = ref('')
const realtimeHotspots = ref<any[]>([])
const realtimeObservedAt = ref('')
const realtimeFetchedAt = ref('')
const realtimeDetectionStatus = ref('未启动')
const selectedRegionId = ref('goes18_north_america_west')
let realtimeTimer: ReturnType<typeof setInterval> | null = null
const realtimeRegions: RealtimeRegion[] = [
  { id: 'goes18_north_america_west', label: '美国西部及北美西部', satellite: 'GOES-18 ABI', coverage: '北美西部', refresh: '约 5–10 分钟', supported: true, bbox: [-140, 15, -80, 60] },
  { id: 'himawari_asia_pacific', label: '亚洲、澳大利亚及太平洋', satellite: 'Himawari-8/9', coverage: '亚洲及太平洋', refresh: '约 10 分钟', supported: true, bbox: [80, -20, 180, 60] },
  { id: 'meteosat_europe_africa', label: '欧洲及非洲', satellite: 'Meteosat', coverage: '欧洲及非洲', refresh: '后续适配', supported: false, bbox: [-60, -45, 60, 70] },
  { id: 'fy4_china', label: '中国及西北太平洋', satellite: 'FY-4A/4B', coverage: '中国及邻近区域', refresh: '后续适配', supported: false, bbox: [70, -10, 180, 60] },
]
const supportedRealtimeRegions = computed(() => realtimeRegions.filter((region) => region.supported))
const selectedRealtimeRegion = computed(() => realtimeRegions.find((region) => region.id === selectedRegionId.value) || realtimeRegions[0])
const realtimeHotspotTotal = computed(() => realtimeHotspots.value.length)
const realtimeStatusText = computed(() => realtimeLoading.value ? '正在请求最新实时观测' : realtimeReady.value ? '实时观测已更新' : '实时数据接口未配置')
const realtimeDataState = computed(() => realtimeReady.value ? '已获取' : realtimeError.value ? '获取失败' : '待获取')
const realtimeDetectionText = computed(() => realtimeDetectionStatus.value)
const realtimeObservedAtText = computed(() => formatRealtimeStamp(realtimeObservedAt.value))
const realtimeFetchedAtText = computed(() => formatRealtimeStamp(realtimeFetchedAt.value))
const realtimeLatencyText = computed(() => {
  if (!realtimeObservedAt.value || !realtimeFetchedAt.value) return '--'
  const minutes = Math.max(0, Math.round((Date.parse(realtimeFetchedAt.value) - Date.parse(realtimeObservedAt.value)) / 60000))
  return `${minutes} 分钟`
})
const activeError = computed(() => monitorMode.value === 'history' ? error.value : realtimeError.value)
const datasetCount = ref(0)
const eventPeriod = ref('--')
const ignitionText = ref('--')
const datasetItems = [
  { id: 'firms', label: 'FIRMS VIIRS 火点', detail: '候选火点与时空聚合' },
  { id: 'mtbs', label: 'MTBS 过火边界', detail: '最终真实过火面积' },
  { id: 'weather', label: 'NASA POWER 气象', detail: '温度、湿度、风速、风向' },
  { id: 'dem', label: 'Copernicus DEM', detail: 'DEM、坡度、坡向' },
  { id: 'fuel', label: 'ESA WorldCover', detail: '土地覆盖与简化燃料' },
]

async function getJson(path: string) {
  const response = await fetch(`${apiBase}${path}`)
  if (!response.ok) throw new Error(`${response.status} ${path}`)
  return response.json()
}

async function resolveData(needs: string[]) {
  const response = await fetch(`${apiBase}/api/data-agent/resolve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ event_id: eventId, needs }),
  })
  if (!response.ok) throw new Error(`${response.status} /api/data-agent/resolve`)
  return response.json()
}

async function loadReplayRows(startAt: string, endAt: string) {
  const rows: any[] = []
  const pageSize = 5000
  let offset = 0
  let total = 0
  do {
    const params = new URLSearchParams({ start_at: startAt, end_at: endAt, limit: String(pageSize), offset: String(offset) })
    const result = await getJson(`/api/data/events/${eventId}/realtime-replay?${params.toString()}`)
    rows.push(...(result.items || []))
    total = Number(result.total || rows.length)
    offset += (result.items || []).length
    if (!(result.items || []).length) break
  } while (rows.length < total)
  return rows
}

function groupReplayRows(rows: any[]) {
  const groups = new Map<string, Map<string, any>>()
  for (const row of rows) {
    const observedAt = String(row.observed_at || '')
    const date = observedAt.slice(0, 10)
    if (!date) continue
    const longitude = Number(row.location?.longitude)
    const latitude = Number(row.location?.latitude)
    if (!Number.isFinite(longitude) || !Number.isFinite(latitude)) continue
    let cells = groups.get(date)
    if (!cells) {
      cells = new Map<string, any>()
      groups.set(date, cells)
    }
    const cellKey = `${Math.round(longitude / 0.02)}:${Math.round(latitude / 0.02)}`
    const existing = cells.get(cellKey)
    if (!existing) {
      cells.set(cellKey, {
        ...row,
        observed_at: `${date}T00:00:00Z`,
        location: { ...row.location },
        point_count: Number(row.point_count || 0),
        max_frp_mw: Number.isFinite(Number(row.max_frp_mw)) ? Number(row.max_frp_mw) : null,
        candidate_ids: [...(row.candidate_ids || [])],
      })
      continue
    }
    existing.point_count += Number(row.point_count || 0)
    const frp = Number(row.max_frp_mw)
    if (Number.isFinite(frp)) existing.max_frp_mw = existing.max_frp_mw === null ? frp : Math.max(existing.max_frp_mw, frp)
    existing.candidate_ids = [...new Set([...(existing.candidate_ids || []), ...(row.candidate_ids || [])])]
  }
  return [...groups.entries()]
    .map(([date, cells]) => {
      const rowsForDate = [...cells.values()]
      return {
        observed_at: `${date}T00:00:00Z`,
        rows: rowsForDate,
        point_count: rowsForDate.reduce((total, row) => total + Number(row.point_count || 0), 0),
        max_frp_mw: rowsForDate.reduce((max, row) => {
          const value = Number(row.max_frp_mw)
          return Number.isFinite(value) ? Math.max(max ?? value, value) : max
        }, null as number | null),
      }
    })
    .sort((a, b) => a.observed_at.localeCompare(b.observed_at))
}

function formatReplayTime(value?: string) {
  if (!value) return '--'
  return `${value.slice(0, 10)} UTC`
}

function formatReplayDate(value?: string) {
  return value ? value.slice(0, 10) : '--'
}

function formatRealtimeStamp(value?: string) {
  if (!value) return '--'
  return value.replace('T', ' ').slice(0, 16)
}

const currentFrame = computed(() => replayFrames.value[replayIndex.value] || null)
const currentReplayTime = computed(() => formatReplayTime(currentFrame.value?.observed_at))
const currentReplayDate = computed(() => currentFrame.value?.observed_at?.slice(0, 10) || '--')
const replayStartTime = computed(() => formatReplayDate(replayFrames.value[0]?.observed_at))
const replayEndTime = computed(() => formatReplayDate(replayFrames.value[replayFrames.value.length - 1]?.observed_at))
const currentFramePointCount = computed(() => currentFrame.value?.point_count || 0)
const currentWeather = computed(() => {
  const date = currentFrame.value?.observed_at?.slice(0, 10)
  if (!date) return latestWeather.value
  return weatherRows.value.find((row) => String(row.observed_on).slice(0, 10) === date) || latestWeather.value
})
const hasRain = computed(() => Number(currentWeather.value?.precipitation_mm) > 0)
const simulationVisible = computed(() => showWind.value || showCloud.value || (showRain.value && hasRain.value))
const weatherLayerStyle = computed(() => ({
  '--weather-opacity': `${Math.min(0.7, Math.max(0.12, Number(currentWeather.value?.relative_humidity_percent || 0) / 140))}`,
  '--wind-angle': `${Number(currentWeather.value?.wind_direction_deg || 0)}deg`,
  '--rain-opacity': `${Math.min(0.68, Math.max(0.22, Number(currentWeather.value?.precipitation_mm || 0) / 12))}`,
}))

function updateReplayGeoJson() {
  const frame = currentFrame.value
  hotspotGeoJson.value = {
    type: 'FeatureCollection',
    features: (frame?.rows || []).map((item: any) => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [item.location.longitude, item.location.latitude] },
      properties: {
        name: `FIRMS 聚合火点 · ${item.observed_at}`,
        cluster_id: item.cluster_id,
        point_count: item.point_count,
        max_frp_mw: item.max_frp_mw,
      },
    })),
  }
}

function renderReplayHotspots() {
  updateReplayGeoJson()
  if (!mapReady.value || !mapRef.value) return
  mapRef.value.clearHotspots()
  if (hotspotGeoJson.value) mapRef.value.addHotspotGeoJson(hotspotGeoJson.value)
}

function stopReplay() {
  isPlaying.value = false
  if (replayTimer) {
    clearInterval(replayTimer)
    replayTimer = null
  }
}

function toggleReplay() {
  if (isPlaying.value) {
    stopReplay()
    return
  }
  if (replayFrames.value.length < 2) return
  if (replayIndex.value >= replayFrames.value.length - 1) replayIndex.value = 0
  isPlaying.value = true
  replayTimer = setInterval(() => {
    if (replayIndex.value >= replayFrames.value.length - 1) {
      stopReplay()
      return
    }
    replayIndex.value += 1
  }, 520)
}

function formatNumber(value: number) { return new Intl.NumberFormat('zh-CN').format(value || 0) }
function formatArea(value: number) { return Number.isFinite(Number(value)) ? `${(Number(value) / 1_000_000).toFixed(1)} km²` : '--' }
function valueWithUnit(value: any, unit: string) { return value === null || value === undefined || value === '' ? '--' : Number.isFinite(Number(value)) ? `${Number(value).toFixed(1)}${unit}` : '--' }

function geometryRings(geometry: any): Array<[number, number][]> {
  if (!geometry) return []
  if (geometry.type === 'Polygon') return geometry.coordinates?.[0] || []
  if (geometry.type === 'MultiPolygon') return (geometry.coordinates || []).map((polygon: any) => polygon?.[0]).filter(Boolean)
  return []
}

function renderMap() {
  const map = mapRef.value
  if (!map) return
  if (monitorMode.value === 'realtime') {
    renderRealtimeMap()
    return
  }
  map.setImageryOverlayVisible(true)
  map.clearHotspots()
  map.clearDemoEntities()
  if (hotspotGeoJson.value) map.addHotspotGeoJson(hotspotGeoJson.value)
  for (const [index, ring] of geometryRings(burnedGeometry.value).entries()) {
    if (ring.length >= 3) map.addDemoArea({ name: `MTBS 过火边界 ${index + 1}`, coordinates: ring, color: '#f97316', label: index === 0 ? 'MTBS 过火边界' : '' })
  }
  map.flyTo({ center: mapCenter.value, height: 72000 })
}

function regionCenter(region: RealtimeRegion | undefined): [number, number] {
  if (!region) return [0, 0]
  return [(region.bbox[0] + region.bbox[2]) / 2, (region.bbox[1] + region.bbox[3]) / 2]
}

function updateRealtimeGeoJson() {
  realtimeGeoJson.value = {
    type: 'FeatureCollection',
    features: realtimeHotspots.value
      .map((item: any) => {
        const longitude = Number(item.longitude ?? item.location?.longitude)
        const latitude = Number(item.latitude ?? item.location?.latitude)
        if (!Number.isFinite(longitude) || !Number.isFinite(latitude)) return null
        return {
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [longitude, latitude] },
          properties: {
            name: `实时热异常候选点 · ${formatRealtimeStamp(item.observed_at)}`,
            confidence: item.confidence,
            source: item.source,
            detection_id: item.detection_id,
          },
        }
      })
      .filter(Boolean),
  }
}

function renderRealtimeMap() {
  if (!mapReady.value || !mapRef.value) return
  mapRef.value.clearHotspots()
  mapRef.value.clearDemoEntities()
  updateRealtimeGeoJson()
  if (realtimeGeoJson.value.features.length) mapRef.value.addHotspotGeoJson(realtimeGeoJson.value)
  mapRef.value.flyTo({ center: regionCenter(selectedRealtimeRegion.value), height: 120000 })
}

async function syncRealtimeData() {
  const region = selectedRealtimeRegion.value
  if (!region?.supported) return
  realtimeLoading.value = true
  realtimeError.value = ''
  realtimeDetectionStatus.value = '同步中'
  try {
    const response = await fetch(`${apiBase}/api/realtime/sync`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ region_id: region.id }),
    })
    if (!response.ok) throw new Error(`${response.status} /api/realtime/sync`)
    const result = await response.json()
    realtimeReady.value = Boolean(result?.ready ?? result?.status === 'ready')
    realtimeObservedAt.value = String(result?.observed_at || result?.observation?.observed_at || '')
    realtimeFetchedAt.value = String(result?.fetched_at || result?.downloaded_at || result?.updated_at || '')
    realtimeDetectionStatus.value = String(result?.detection_status || result?.status_text || (realtimeReady.value ? '已完成' : '待检测'))
    realtimeHotspots.value = Array.isArray(result?.hotspots)
      ? result.hotspots
      : Array.isArray(result?.items)
        ? result.items
        : Array.isArray(result?.data?.hotspots)
          ? result.data.hotspots
          : []
    if (result?.error) realtimeError.value = String(result.error)
    updateRealtimeGeoJson()
    renderRealtimeMap()
  } catch (cause: any) {
    realtimeReady.value = false
    realtimeHotspots.value = []
    realtimeObservedAt.value = ''
    realtimeFetchedAt.value = ''
    realtimeDetectionStatus.value = '待后端接入'
    realtimeError.value = cause?.message?.includes('404')
      ? '实时数据接口尚未配置，请先部署实时卫星同步服务。'
      : `实时数据获取失败：${cause?.message || '未知错误'}`
    renderRealtimeMap()
  } finally {
    realtimeLoading.value = false
  }
}

function handleModeChange() {
  stopReplay()
  stopRealtimePolling()
  realtimeError.value = ''
  if (monitorMode.value === 'history') {
    void nextTick().then(() => mapRef.value?.on('load', renderMap))
    return
  }
  mapCenter.value = regionCenter(selectedRealtimeRegion.value)
  void nextTick().then(() => mapRef.value?.on('load', renderRealtimeMap))
  void syncRealtimeData()
  realtimeTimer = setInterval(() => { void syncRealtimeData() }, 60000)
}

function stopRealtimePolling() {
  if (realtimeTimer) {
    clearInterval(realtimeTimer)
    realtimeTimer = null
  }
}

function handleRegionChange() {
  realtimeReady.value = false
  realtimeHotspots.value = []
  realtimeDetectionStatus.value = selectedRealtimeRegion.value?.supported ? '待获取' : '区域暂不支持'
  realtimeError.value = selectedRealtimeRegion.value?.supported ? '' : '抱歉，该区域当前暂不支持实时火点监测。'
  mapCenter.value = regionCenter(selectedRealtimeRegion.value)
  if (monitorMode.value === 'realtime') {
    void nextTick().then(() => mapRef.value?.on('load', renderRealtimeMap))
    if (selectedRealtimeRegion.value?.supported) void syncRealtimeData()
  }
}

async function loadData() {
  loading.value = true
  error.value = ''
  stopReplay()
  try {
    const eventResult = await getJson(`/api/data/events/${eventId}`)
    const studyPeriod = eventResult.data?.metadata?.study_event_period
    const replayStart = studyPeriod?.[0] ? `${studyPeriod[0]}T00:00:00Z` : '2021-07-13T00:00:00Z'
    const replayEnd = studyPeriod?.[1] ? `${studyPeriod[1]}T23:59:59Z` : '2021-10-25T23:59:59Z'
    const [hotspotResult, replayRows, burnedResult, weatherResult, catalogResult, resolvedResult] = await Promise.all([
      getJson(`/api/data/events/${eventId}/hotspots?aggregate=false&limit=1`),
      loadReplayRows(replayStart, replayEnd),
      getJson(`/api/data/events/${eventId}/burned-area?include_geometry=true`),
      getJson(`/api/data/events/${eventId}/weather?limit=1000`),
      getJson(`/api/data-agent/catalog/${eventId}`),
      resolveData(['terrain', 'slope', 'aspect', 'fuel']),
    ])
    event.value = eventResult.data
    burnedArea.value = burnedResult.data
    burnedGeometry.value = burnedResult.data?.geometry
    weatherRows.value = weatherResult.items || []
    weatherTotal.value = weatherResult.total || weatherRows.value.length
    latestWeather.value = weatherRows.value[weatherRows.value.length - 1] || null
    hotspotTotal.value = hotspotResult.total || 0
    replayFrames.value = groupReplayRows(replayRows)
    replayIndex.value = 0
    clusterTotal.value = replayFrames.value.reduce((total, frame) => total + frame.rows.length, 0)
    catalog.value = catalogResult
    datasetCount.value = catalogResult.manifests?.length || 0
    rasterReady.value = Boolean(resolvedResult.selected_datasets?.length && resolvedResult.selected_datasets.every((item: any) => item.available))
    const ignition = eventResult.data?.ignition_point
    if (Number.isFinite(Number(ignition?.longitude)) && Number.isFinite(Number(ignition?.latitude))) mapCenter.value = [Number(ignition.longitude), Number(ignition.latitude)]
    eventPeriod.value = `${String(eventResult.data?.started_at || '').slice(0, 10)} 至 ${String(eventResult.data?.closed_at || '').slice(0, 10)}`
    ignitionText.value = ignition ? `${Number(ignition.longitude).toFixed(4)}, ${Number(ignition.latitude).toFixed(4)}` : '--'
    updateReplayGeoJson()
    loaded.value = true
    mapReady.value = true
    await nextTick()
    mapRef.value?.on('load', renderMap)
  } catch (cause: any) {
    error.value = `数据加载失败：${cause?.message || '未知错误'}`
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
watch(replayIndex, renderReplayHotspots)
onUnmounted(() => {
  stopReplay()
  stopRealtimePolling()
})
</script>

<style scoped>
.realtime-page { width: 100%; height: 100%; min-height: 0; display: grid; grid-template-columns: minmax(290px, 23vw) minmax(520px, 1fr) minmax(300px, 25vw); background: #07111b; color: #edf6ff; overflow: hidden; }
.data-panel, .evidence-panel { min-width: 0; min-height: 0; overflow: auto; padding: 16px; background: linear-gradient(180deg, rgba(14, 29, 45, .98), rgba(7, 17, 27, .99)); }
.data-panel { border-right: 1px solid rgba(115, 139, 173, .22); } .evidence-panel { border-left: 1px solid rgba(115, 139, 173, .22); }
.panel-header { display: grid; gap: 6px; margin-bottom: 14px; } .panel-header.compact { margin-bottom: 16px; }
.mode-control { display: grid; grid-template-columns: auto minmax(0, 1fr); align-items: center; gap: 8px; margin: 2px 0 4px; } .mode-control label { color: #9fb0c7; font-size: 11px; } .mode-control select, .region-select { min-height: 32px; padding: 0 9px; border: 1px solid rgba(125, 211, 252, .3); border-radius: 5px; color: #e5f0ff; background: #102438; font: inherit; font-size: 12px; } .mode-control select:focus, .region-select:focus { outline: 2px solid rgba(45, 212, 191, .45); outline-offset: 1px; }
.eyebrow { color: #7dd3fc; font-size: 10px; font-weight: 800; letter-spacing: .08em; } h1, h2, h3, p { margin: 0; letter-spacing: 0; } h1 { font-size: 22px; } h2 { font-size: 17px; } h3 { font-size: 14px; }
.panel-header p, .handoff-card p { color: #9fb0c7; font-size: 12px; line-height: 1.5; }
.status-strip { display: flex; align-items: center; gap: 8px; min-height: 34px; padding: 0 10px; margin-bottom: 12px; border: 1px solid rgba(148, 163, 184, .2); border-radius: 7px; color: #fbbf24; font-size: 12px; background: rgba(30, 41, 59, .7); }
.status-strip.ready { color: #5eead4; border-color: rgba(45, 212, 191, .32); } .status-strip.error { color: #fca5a5; border-color: rgba(248, 113, 113, .35); } .status-dot { width: 7px; height: 7px; border-radius: 50%; background: currentColor; box-shadow: 0 0 10px currentColor; }
.metric-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; } .metric { display: grid; gap: 5px; min-height: 78px; padding: 10px; border: 1px solid rgba(148, 163, 184, .16); border-radius: 7px; background: rgba(15, 35, 53, .8); }
.metric span, .metric small, .section-heading span, .weather-grid span, .dataset-list small, .card-label, dt { color: #9fb0c7; font-size: 11px; } .metric strong { color: #f8fafc; font-size: 18px; line-height: 1.1; overflow-wrap: anywhere; }
.data-section, .source-section { display: grid; gap: 10px; margin-top: 12px; padding: 12px; border: 1px solid rgba(148, 163, 184, .18); border-radius: 8px; background: rgba(8, 19, 31, .72); }
.section-heading { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; } .weather-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; } .weather-grid div { display: grid; gap: 4px; padding: 8px; background: rgba(13, 28, 44, .78); border-radius: 6px; } .weather-grid b { color: #f8fafc; font-size: 13px; }
.replay-section { gap: 9px; } .replay-time, .replay-scale { display: flex; justify-content: space-between; gap: 8px; } .replay-time strong { color: #f8fafc; font-size: 13px; } .replay-time span, .replay-scale { color: #9fb0c7; font-size: 11px; } .replay-slider { width: 100%; accent-color: #2dd4bf; cursor: pointer; } .replay-slider:disabled { cursor: not-allowed; opacity: .5; } .replay-stats { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 6px; } .replay-stats div { display: grid; gap: 3px; min-width: 0; padding: 7px; border: 1px solid rgba(148, 163, 184, .14); border-radius: 5px; background: rgba(13, 28, 44, .78); } .replay-stats span { color: #9fb0c7; font-size: 10px; overflow-wrap: anywhere; } .replay-stats b { color: #f8fafc; font-size: 12px; overflow-wrap: anywhere; } .replay-button { min-height: 32px; padding: 0 12px; border: 1px solid rgba(125, 211, 252, .36); border-radius: 5px; color: #e0f2fe; background: rgba(14, 116, 144, .72); cursor: pointer; font: inherit; font-size: 12px; font-weight: 700; } .replay-button:disabled { cursor: not-allowed; opacity: .5; } .replay-note { color: #8ea3bb; font-size: 10px; line-height: 1.45; }
.weather-note { color: #8ea3bb; font-size: 10px; line-height: 1.45; }
.realtime-note { color: #8ea3bb; font-size: 10px; line-height: 1.5; } .region-card { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 7px; } .region-card div { display: grid; gap: 3px; padding: 8px; border-radius: 6px; background: rgba(13, 28, 44, .78); } .region-card span { color: #9fb0c7; font-size: 10px; } .region-card b { color: #f8fafc; font-size: 12px; overflow-wrap: anywhere; } .realtime-refresh { background: #155e75; }
.realtime-source-list { display: grid; gap: 7px; } .realtime-source-list div { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; padding-bottom: 6px; border-bottom: 1px solid rgba(148, 163, 184, .12); } .realtime-source-list strong { color: #dbeafe; font-size: 11px; } .realtime-source-list span { color: #8ea3bb; font-size: 10px; text-align: right; }
.dataset-list { display: grid; gap: 9px; padding: 0; margin: 0; list-style: none; } .dataset-list li { display: flex; gap: 8px; align-items: start; } .dataset-state { flex: 0 0 auto; width: 7px; height: 7px; margin-top: 5px; border-radius: 50%; background: #2dd4bf; box-shadow: 0 0 8px rgba(45, 212, 191, .8); } .dataset-list div { display: grid; gap: 2px; min-width: 0; } .dataset-list strong { font-size: 12px; }
.refresh-button { width: 100%; min-height: 36px; margin-top: 12px; border: 1px solid rgba(45, 212, 191, .45); border-radius: 6px; color: #ecfeff; background: #0f766e; cursor: pointer; font: inherit; font-weight: 700; } .refresh-button:disabled { opacity: .5; cursor: not-allowed; }
.map-panel { position: relative; min-width: 0; min-height: 0; overflow: hidden; background: #020712; } .map { position: absolute; inset: 0; } .map-loading { display: grid; place-items: center; height: 100%; color: #bfdbfe; font-size: 14px; }
.map-overlay { position: absolute; z-index: 5; pointer-events: none; padding: 10px 12px; border: 1px solid rgba(191, 219, 254, .2); border-radius: 7px; background: rgba(2, 8, 23, .7); backdrop-filter: blur(6px); } .map-title { top: 16px; left: 16px; display: grid; gap: 4px; } .map-title span { color: #93c5fd; font-size: 11px; } .map-title strong { font-size: 15px; }
.map-legend { position: absolute; right: 16px; bottom: 184px; z-index: 5; display: grid; gap: 6px; padding: 9px 11px; border: 1px solid rgba(191, 219, 254, .2); border-radius: 7px; color: #e5f0ff; font-size: 11px; background: rgba(2, 8, 23, .72); } .map-legend span { display: flex; align-items: center; gap: 6px; } .map-legend i { width: 9px; height: 9px; border-radius: 50%; display: inline-block; } .hotspot-key { background: #ef4444; box-shadow: 0 0 8px #ef4444; } .burned-key { border-radius: 2px !important; background: #f97316; }
.source-key { border-radius: 2px !important; background: #22d3ee; }
.weather-simulation { position: absolute; inset: 0; z-index: 3; pointer-events: none; opacity: 0; transition: opacity .25s ease; overflow: hidden; } .weather-simulation.is-visible { opacity: 1; } .weather-effect { position: absolute; inset: 0; }
.wind-effect { opacity: .22; background: repeating-linear-gradient(calc(var(--wind-angle) + 25deg), transparent 0 18px, rgba(147, 232, 255, .5) 19px 20px, transparent 21px 46px); mix-blend-mode: screen; animation: wind-drift 2.8s linear infinite; }
.cloud-effect { opacity: var(--weather-opacity); background: radial-gradient(ellipse at 20% 18%, rgba(226, 241, 255, .24), transparent 30%), radial-gradient(ellipse at 78% 28%, rgba(191, 219, 254, .2), transparent 32%), linear-gradient(180deg, rgba(148, 163, 184, .12), transparent 42%); mix-blend-mode: screen; }
.rain-effect { opacity: var(--rain-opacity); background: repeating-linear-gradient(105deg, transparent 0 12px, rgba(147, 197, 253, .6) 13px 14px, transparent 15px 25px); animation: rain-fall .55s linear infinite; }
.replay-dock { position: absolute; left: 16px; right: 16px; bottom: 16px; z-index: 6; display: grid; gap: 8px; padding: 11px 13px; border: 1px solid rgba(125, 211, 252, .26); border-radius: 8px; color: #e5f0ff; background: rgba(2, 8, 23, .84); backdrop-filter: blur(10px); box-shadow: 0 12px 34px rgba(0, 0, 0, .25); }
.replay-dock-header, .replay-dock-footer { display: flex; align-items: center; justify-content: space-between; gap: 14px; } .replay-dock-header > div:first-child { display: flex; align-items: baseline; flex-wrap: wrap; gap: 7px 10px; } .dock-kicker { color: #67e8f9; font-size: 9px; font-weight: 800; letter-spacing: .08em; } .replay-dock-header strong { font-size: 15px; } .replay-dock-header small, .simulation-summary, .simulation-note { color: #9fb0c7; font-size: 10px; } .simulation-summary { display: flex; flex-wrap: wrap; gap: 10px; }
.replay-dock .replay-slider { margin: 0 2px; } .replay-dock-footer { align-items: center; flex-wrap: wrap; } .simulation-toggles { display: flex; align-items: center; gap: 10px; } .simulation-toggles label { display: inline-flex; align-items: center; gap: 4px; min-height: 28px; color: #dbeafe; font-size: 11px; cursor: pointer; } .simulation-toggles label.disabled { color: #64748b; cursor: not-allowed; } .simulation-toggles input { accent-color: #22d3ee; }
.realtime-map-dock { position: absolute; left: 16px; right: 16px; bottom: 16px; z-index: 6; display: grid; gap: 8px; padding: 12px 14px; border: 1px solid rgba(34, 211, 238, .28); border-radius: 8px; color: #e5f0ff; background: rgba(2, 8, 23, .86); backdrop-filter: blur(10px); box-shadow: 0 12px 34px rgba(0, 0, 0, .25); } .realtime-map-dock-header { display: flex; justify-content: space-between; align-items: center; gap: 12px; } .realtime-map-dock-header > div { display: flex; align-items: baseline; flex-wrap: wrap; gap: 8px; } .realtime-map-dock-header strong { font-size: 15px; } .live-indicator { display: inline-flex; align-items: center; gap: 6px; color: #fbbf24; font-size: 10px; } .live-indicator.ready { color: #5eead4; } .live-indicator i { width: 7px; height: 7px; border-radius: 50%; background: currentColor; box-shadow: 0 0 8px currentColor; } .realtime-map-stats { display: flex; flex-wrap: wrap; gap: 10px 18px; color: #9fb0c7; font-size: 10px; } .realtime-map-stats b { color: #f8fafc; font-size: 11px; } .realtime-map-dock p { color: #8ea3bb; font-size: 10px; line-height: 1.4; }
@keyframes wind-drift { from { transform: translateX(-18px); } to { transform: translateX(18px); } } @keyframes rain-fall { from { transform: translateY(-24px); } to { transform: translateY(24px); } }
.handoff-card { display: grid; gap: 7px; margin-bottom: 10px; padding: 12px; border: 1px solid rgba(45, 212, 191, .2); border-radius: 8px; background: rgba(8, 29, 39, .78); } .handoff-card strong { color: #ccfbf1; font-size: 13px; }
.source-section dl { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 8px 12px; margin: 0; font-size: 12px; } .source-section dd { margin: 0; color: #f8fafc; text-align: right; overflow-wrap: anywhere; }
@media (max-width: 1100px) { .realtime-page { grid-template-columns: minmax(260px, 28vw) minmax(420px, 1fr) minmax(260px, 27vw); } } @media (max-width: 900px) { .realtime-page { height: auto; overflow: auto; grid-template-columns: 1fr; } .map-panel { order: -1; height: 66vh; min-height: 500px; } .data-panel, .evidence-panel { overflow: visible; } .replay-dock, .realtime-map-dock { left: 10px; right: 10px; bottom: 10px; } .map-legend { right: 10px; bottom: 230px; } .simulation-note { width: 100%; } }
</style>
