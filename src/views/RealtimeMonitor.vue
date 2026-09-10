<template>
  <main class="realtime-page">
    <aside class="data-panel">
      <header class="panel-header">
        <span class="eyebrow">REAL DATA / DIXIE FIRE</span>
        <h1>实时火情监测</h1>
        <p>{{ event?.name || 'Dixie Fire' }} · 数据智能体已连接</p>
      </header>

      <section class="status-strip" :class="{ ready: loaded, error: Boolean(error) }">
        <span class="status-dot"></span>
        <span>{{ error || (loaded ? '真实历史数据已加载' : '正在加载数据') }}</span>
      </section>

      <section class="metric-grid">
        <article class="metric"><span>候选火点</span><strong>{{ formatNumber(hotspotTotal) }}</strong><small>MTBS 边界内 FIRMS</small></article>
        <article class="metric"><span>聚合单元</span><strong>{{ formatNumber(clusterTotal) }}</strong><small>10 分钟 / 网格</small></article>
        <article class="metric"><span>最终过火</span><strong>{{ burnedArea ? formatArea(burnedArea.area_m2) : '--' }}</strong><small>MTBS 真实边界</small></article>
        <article class="metric"><span>气象记录</span><strong>{{ weatherTotal || '--' }}</strong><small>NASA POWER 日尺度</small></article>
      </section>

      <section class="data-section">
        <div class="section-heading"><h2>最新气象</h2><span>{{ latestWeather?.observed_on || '--' }}</span></div>
        <div class="weather-grid">
          <div><span>温度</span><b>{{ valueWithUnit(latestWeather?.temperature_c, '℃') }}</b></div>
          <div><span>湿度</span><b>{{ valueWithUnit(latestWeather?.relative_humidity_percent, '%') }}</b></div>
          <div><span>风速</span><b>{{ valueWithUnit(latestWeather?.wind_speed_m_s, 'm/s') }}</b></div>
          <div><span>风向</span><b>{{ valueWithUnit(latestWeather?.wind_direction_deg, '°') }}</b></div>
        </div>
      </section>

      <section class="data-section">
        <div class="section-heading"><h2>数据目录</h2><span>{{ datasetCount }} 个数据集</span></div>
        <ul class="dataset-list">
          <li v-for="item in datasetItems" :key="item.id"><span class="dataset-state"></span><div><strong>{{ item.label }}</strong><small>{{ item.detail }}</small></div></li>
        </ul>
      </section>

      <button class="refresh-button" type="button" :disabled="loading" @click="loadData">{{ loading ? '刷新中...' : '刷新真实数据' }}</button>
    </aside>

    <section class="map-panel">
      <CesiumMap v-if="mapReady" ref="mapRef" class="map" :longitude="mapCenter[0]" :latitude="mapCenter[1]" :height="65000" scene-id="dixie_fire_2021" />
      <div v-else class="map-loading">正在准备 Dixie Fire 研究区</div>
      <div class="map-overlay map-title"><span>历史事件回放</span><strong>Dixie Fire · California · 2021</strong></div>
      <div class="map-legend"><span><i class="hotspot-key"></i> FIRMS 聚合火点</span><span><i class="burned-key"></i> MTBS 过火边界</span></div>
    </section>

    <aside class="evidence-panel">
      <header class="panel-header compact"><span class="eyebrow">DATA AGENT HANDOFF</span><h2>数据交接状态</h2><p>此页面展示数据源头，不代表视觉确认或火势推演已经完成。</p></header>
      <section class="handoff-card"><span class="card-label">乙 · 视觉核验</span><strong>{{ clusterTotal ? '候选点可供 Qwen-VL 核验' : '等待候选点' }}</strong><p>使用聚合火点坐标和影像引用字段，不把 FIRMS 候选直接标记为真实火灾。</p></section>
      <section class="handoff-card"><span class="card-label">丙 · ForeFire 输入</span><strong>{{ rasterReady ? '地形与燃料栅格已就绪' : '等待栅格数据' }}</strong><p>DEM、坡度、坡向和 WorldCover 简化燃料栅格均为 30 m、EPSG:32610。</p></section>
      <section class="handoff-card"><span class="card-label">丁 · 影响分析</span><strong>{{ burnedArea ? '过火边界和气象可调用' : '等待基础数据' }}</strong><p>后续叠加道路、建筑、居民点和火势推演结果，生成资源与疏散方案。</p></section>
      <section class="source-section"><h3>事件信息</h3><dl><dt>事件状态</dt><dd>{{ event?.status || '--' }}</dd><dt>观测时段</dt><dd>{{ eventPeriod }}</dd><dt>起火参考点</dt><dd>{{ ignitionText }}</dd><dt>数据检索</dt><dd>deterministic manifest</dd><dt>大模型依赖</dt><dd>当前不需要 API Key</dd></dl></section>
    </aside>
  </main>
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
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
const latestWeather = ref<any>(null)
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

function formatNumber(value: number) { return new Intl.NumberFormat('zh-CN').format(value || 0) }
function formatArea(value: number) { return Number.isFinite(Number(value)) ? `${(Number(value) / 1_000_000).toFixed(1)} km²` : '--' }
function valueWithUnit(value: any, unit: string) { return Number.isFinite(Number(value)) ? `${Number(value).toFixed(1)}${unit}` : '--' }

function geometryRings(geometry: any): Array<[number, number][]> {
  if (!geometry) return []
  if (geometry.type === 'Polygon') return geometry.coordinates?.[0] || []
  if (geometry.type === 'MultiPolygon') return (geometry.coordinates || []).map((polygon: any) => polygon?.[0]).filter(Boolean)
  return []
}

function renderMap() {
  const map = mapRef.value
  if (!map) return
  map.setImageryOverlayVisible(true)
  map.clearHotspots()
  map.clearDemoEntities()
  if (hotspotGeoJson.value) map.addHotspotGeoJson(hotspotGeoJson.value)
  for (const [index, ring] of geometryRings(burnedGeometry.value).entries()) {
    if (ring.length >= 3) map.addDemoArea({ name: `MTBS 过火边界 ${index + 1}`, coordinates: ring, color: '#f97316', label: index === 0 ? 'MTBS 过火边界' : '' })
  }
  map.flyTo({ center: mapCenter.value, height: 72000 })
}

async function loadData() {
  loading.value = true
  error.value = ''
  try {
    const [eventResult, hotspotResult, clusterResult, burnedResult, weatherResult, catalogResult, resolvedResult] = await Promise.all([
      getJson(`/api/data/events/${eventId}`),
      getJson(`/api/data/events/${eventId}/hotspots?aggregate=false&limit=1`),
      getJson(`/api/data/events/${eventId}/hotspots?aggregate=true&limit=1000`),
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
    clusterTotal.value = clusterResult.total || 0
    catalog.value = catalogResult
    datasetCount.value = catalogResult.manifests?.length || 0
    rasterReady.value = Boolean(resolvedResult.selected_datasets?.length && resolvedResult.selected_datasets.every((item: any) => item.available))
    const ignition = eventResult.data?.ignition_point
    if (Number.isFinite(Number(ignition?.longitude)) && Number.isFinite(Number(ignition?.latitude))) mapCenter.value = [Number(ignition.longitude), Number(ignition.latitude)]
    eventPeriod.value = `${String(eventResult.data?.started_at || '').slice(0, 10)} 至 ${String(eventResult.data?.closed_at || '').slice(0, 10)}`
    ignitionText.value = ignition ? `${Number(ignition.longitude).toFixed(4)}, ${Number(ignition.latitude).toFixed(4)}` : '--'
    hotspotGeoJson.value = { type: 'FeatureCollection', features: (clusterResult.items || []).map((item: any) => ({ type: 'Feature', geometry: { type: 'Point', coordinates: [item.center.longitude, item.center.latitude] }, properties: { name: `FIRMS 聚合火点 · ${item.observed_at}`, cluster_id: item.cluster_id } })) }
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
</script>

<style scoped>
.realtime-page { width: 100%; height: 100%; min-height: 0; display: grid; grid-template-columns: minmax(290px, 23vw) minmax(520px, 1fr) minmax(300px, 25vw); background: #07111b; color: #edf6ff; overflow: hidden; }
.data-panel, .evidence-panel { min-width: 0; min-height: 0; overflow: auto; padding: 16px; background: linear-gradient(180deg, rgba(14, 29, 45, .98), rgba(7, 17, 27, .99)); }
.data-panel { border-right: 1px solid rgba(115, 139, 173, .22); } .evidence-panel { border-left: 1px solid rgba(115, 139, 173, .22); }
.panel-header { display: grid; gap: 6px; margin-bottom: 14px; } .panel-header.compact { margin-bottom: 16px; }
.eyebrow { color: #7dd3fc; font-size: 10px; font-weight: 800; letter-spacing: .08em; } h1, h2, h3, p { margin: 0; letter-spacing: 0; } h1 { font-size: 22px; } h2 { font-size: 17px; } h3 { font-size: 14px; }
.panel-header p, .handoff-card p { color: #9fb0c7; font-size: 12px; line-height: 1.5; }
.status-strip { display: flex; align-items: center; gap: 8px; min-height: 34px; padding: 0 10px; margin-bottom: 12px; border: 1px solid rgba(148, 163, 184, .2); border-radius: 7px; color: #fbbf24; font-size: 12px; background: rgba(30, 41, 59, .7); }
.status-strip.ready { color: #5eead4; border-color: rgba(45, 212, 191, .32); } .status-strip.error { color: #fca5a5; border-color: rgba(248, 113, 113, .35); } .status-dot { width: 7px; height: 7px; border-radius: 50%; background: currentColor; box-shadow: 0 0 10px currentColor; }
.metric-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; } .metric { display: grid; gap: 5px; min-height: 78px; padding: 10px; border: 1px solid rgba(148, 163, 184, .16); border-radius: 7px; background: rgba(15, 35, 53, .8); }
.metric span, .metric small, .section-heading span, .weather-grid span, .dataset-list small, .card-label, dt { color: #9fb0c7; font-size: 11px; } .metric strong { color: #f8fafc; font-size: 18px; line-height: 1.1; overflow-wrap: anywhere; }
.data-section, .source-section { display: grid; gap: 10px; margin-top: 12px; padding: 12px; border: 1px solid rgba(148, 163, 184, .18); border-radius: 8px; background: rgba(8, 19, 31, .72); }
.section-heading { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; } .weather-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; } .weather-grid div { display: grid; gap: 4px; padding: 8px; background: rgba(13, 28, 44, .78); border-radius: 6px; } .weather-grid b { color: #f8fafc; font-size: 13px; }
.dataset-list { display: grid; gap: 9px; padding: 0; margin: 0; list-style: none; } .dataset-list li { display: flex; gap: 8px; align-items: start; } .dataset-state { flex: 0 0 auto; width: 7px; height: 7px; margin-top: 5px; border-radius: 50%; background: #2dd4bf; box-shadow: 0 0 8px rgba(45, 212, 191, .8); } .dataset-list div { display: grid; gap: 2px; min-width: 0; } .dataset-list strong { font-size: 12px; }
.refresh-button { width: 100%; min-height: 36px; margin-top: 12px; border: 1px solid rgba(45, 212, 191, .45); border-radius: 6px; color: #ecfeff; background: #0f766e; cursor: pointer; font: inherit; font-weight: 700; } .refresh-button:disabled { opacity: .5; cursor: not-allowed; }
.map-panel { position: relative; min-width: 0; min-height: 0; overflow: hidden; background: #020712; } .map { position: absolute; inset: 0; } .map-loading { display: grid; place-items: center; height: 100%; color: #bfdbfe; font-size: 14px; }
.map-overlay { position: absolute; z-index: 5; pointer-events: none; padding: 10px 12px; border: 1px solid rgba(191, 219, 254, .2); border-radius: 7px; background: rgba(2, 8, 23, .7); backdrop-filter: blur(6px); } .map-title { top: 16px; left: 16px; display: grid; gap: 4px; } .map-title span { color: #93c5fd; font-size: 11px; } .map-title strong { font-size: 15px; }
.map-legend { position: absolute; right: 16px; bottom: 16px; z-index: 5; display: grid; gap: 6px; padding: 9px 11px; border: 1px solid rgba(191, 219, 254, .2); border-radius: 7px; color: #e5f0ff; font-size: 11px; background: rgba(2, 8, 23, .72); } .map-legend span { display: flex; align-items: center; gap: 6px; } .map-legend i { width: 9px; height: 9px; border-radius: 50%; display: inline-block; } .hotspot-key { background: #ef4444; box-shadow: 0 0 8px #ef4444; } .burned-key { border-radius: 2px !important; background: #f97316; }
.handoff-card { display: grid; gap: 7px; margin-bottom: 10px; padding: 12px; border: 1px solid rgba(45, 212, 191, .2); border-radius: 8px; background: rgba(8, 29, 39, .78); } .handoff-card strong { color: #ccfbf1; font-size: 13px; }
.source-section dl { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 8px 12px; margin: 0; font-size: 12px; } .source-section dd { margin: 0; color: #f8fafc; text-align: right; overflow-wrap: anywhere; }
@media (max-width: 1100px) { .realtime-page { grid-template-columns: minmax(260px, 28vw) minmax(420px, 1fr) minmax(260px, 27vw); } } @media (max-width: 900px) { .realtime-page { height: auto; overflow: auto; grid-template-columns: 1fr; } .map-panel { order: -1; height: 58vh; min-height: 420px; } .data-panel, .evidence-panel { overflow: visible; } }
</style>
