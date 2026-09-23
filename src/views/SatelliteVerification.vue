<template>
  <div class="verification-page">
    <aside class="candidate-rail">
      <header class="page-heading">
        <span>IMAGE VERIFICATION / SIMULATED RECEPTION</span>
        <h1>卫星影像核验</h1>
        <p>真实历史 GOES-18 影像按时次模拟接收。检测点始终是候选火点。</p>
      </header>
      <div class="source-badge">Park Fire 2024 · GOES-18 ABI C07/C14</div>
      <label class="field"><span>观测时次 UTC</span>
        <select v-model.number="slotIndex" :disabled="loading || !slots.length" @change="runDetection">
          <option v-for="(slot, index) in slots" :key="slot.observed_at" :value="index">{{ formatTime(slot.observed_at) }}{{ slot.downloaded === false ? ' · 文件缺失' : '' }}</option>
        </select>
      </label>
      <button class="primary-action" type="button" :disabled="loading || !slots.length" @click="runDetection">{{ loading ? '正在执行目标检测…' : '重新执行目标检测' }}</button>
      <p v-if="error" class="notice error">{{ error }}</p>
      <div class="metrics">
        <div><span>检测候选</span><strong>{{ candidates.length }}</strong></div>
        <div><span>已保留</span><strong>{{ retainedCount }}</strong></div>
        <div><span>已排除</span><strong>{{ excludedCount }}</strong></div>
      </div>
      <label class="field"><span>最低检测置信度 {{ Math.round(minConfidence * 100) }}%</span><input v-model.number="minConfidence" type="range" min="0" max="1" step="0.05" /></label>
      <label class="field"><span>筛选状态</span><select v-model="statusFilter"><option value="all">全部候选</option><option value="pending">待筛选</option><option value="retained">已保留</option><option value="excluded">已排除</option></select></label>
      <div class="list-heading"><strong>候选点</strong><span>{{ filteredCandidates.length }} / {{ candidates.length }}</span></div>
      <div class="candidate-list">
        <button v-for="item in filteredCandidates" :key="item.detection_id" type="button" class="candidate" :class="{ selected: selectedId === item.detection_id }" @click="selectCandidate(item)">
          <span><strong>{{ item.detection_id }}</strong><small>{{ Number(item.longitude).toFixed(4) }}, {{ Number(item.latitude).toFixed(4) }}</small></span>
          <b :class="screeningStatus(item)">{{ statusLabel(item) }}</b>
        </button>
        <div v-if="!filteredCandidates.length" class="empty-state">{{ result ? '当前筛选条件下没有候选点' : '运行目标检测后显示候选点' }}</div>
      </div>
    </aside>

    <section class="image-stage">
      <div class="stage-head">
        <div><span>影像证据</span><strong>{{ result ? formatTime(result.observed_at) : '等待检测' }}</strong></div>
        <div class="view-tabs"><button type="button" :class="{ active: view === 'image' }" @click="view = 'image'">检测影像</button><button type="button" :class="{ active: view === 'map' }" @click="view = 'map'">地图位置</button></div>
      </div>
      <div v-if="view === 'image'" class="preview-area">
        <img v-if="result" :src="previewUrl" alt="GOES-18 热异常检测结果预览" />
        <div v-else class="preview-empty">选择可用时次并运行目标检测</div>
      </div>
      <div v-else class="map-area">
        <CesiumMap ref="mapRef" class="map" :longitude="-121.15" :latitude="40.05" :height="100000" scene-id="goes-verification" />
      </div>
      <footer class="stage-foot">
        <span>红色：算法候选</span><span>青色：官方 FDCC 参考</span><span>黄色：二者匹配</span>
        <strong v-if="result?.evaluation">F1 {{ Number(result.evaluation.f1).toFixed(2) }}</strong>
      </footer>
    </section>

    <Teleport defer to="#business-panel">
      <aside class="verification-detail">
        <header><span>候选火点筛选</span><h2>{{ selected ? selected.detection_id : '请选择候选点' }}</h2><p>影像来自历史数据，接收过程为模拟。保留与排除仅保存于当前浏览器会话。</p></header>
        <template v-if="selected">
          <dl>
            <dt>坐标 WGS84</dt><dd>{{ Number(selected.longitude).toFixed(5) }}, {{ Number(selected.latitude).toFixed(5) }}</dd>
            <dt>检测置信度</dt><dd>{{ Math.round(Number(selected.confidence) * 100) }}%</dd>
            <dt>C07 亮温</dt><dd>{{ selected.brightness_temperature_c07_k }} K</dd>
            <dt>C14 亮温</dt><dd>{{ selected.brightness_temperature_c14_k }} K</dd>
            <dt>亮温差</dt><dd>{{ selected.brightness_difference_k }} K</dd>
            <dt>算法</dt><dd>{{ selected.algorithm }}</dd>
            <dt>状态</dt><dd>{{ statusLabel(selected) }}</dd>
          </dl>
          <div class="screening-actions">
            <button type="button" @click="setStatus(selected, 'retained')">保留候选</button>
            <button type="button" @click="setStatus(selected, 'excluded')">排除候选</button>
            <button type="button" @click="setStatus(selected, 'pending')">撤销筛选</button>
          </div>
          <p class="detail-note">此处是候选筛选，不产生确认火点，也不自动触发推演。参考 FDCC 产品只用于演示验证，不参与检测输入。</p>
        </template>
        <div v-else class="empty-state">从左侧候选列表选择一个点，查看检测证据。</div>
      </aside>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import CesiumMap from '../components/CesiumMap.vue'

type Hotspot = {
  detection_id: string; longitude: number; latitude: number; confidence: number;
  brightness_temperature_c07_k: number; brightness_temperature_c14_k: number;
  brightness_difference_k: number; algorithm: string
}
type ScreenStatus = 'pending' | 'retained' | 'excluded'
const storageKey = 'fire-command-verification-screening'
const manifest = ref<any>(null)
const result = ref<any>(null)
const slotIndex = ref(0)
const loading = ref(false)
const error = ref('')
const minConfidence = ref(0)
const statusFilter = ref<'all' | ScreenStatus>('all')
const selectedId = ref('')
const view = ref<'image' | 'map'>('image')
const mapRef = ref<InstanceType<typeof CesiumMap> | null>(null)
const screening = ref<Record<string, ScreenStatus>>(readScreening())
const slots = computed(() => manifest.value?.slots || [])
const candidates = computed<Hotspot[]>(() => result.value?.hotspots || [])
const selected = computed(() => candidates.value.find(item => item.detection_id === selectedId.value) || null)
const screeningKey = (item: Hotspot) => `${slotIndex.value}:${item.detection_id}`
const screeningStatus = (item: Hotspot): ScreenStatus => screening.value[screeningKey(item)] || 'pending'
const statusLabel = (item: Hotspot) => ({ pending: '待筛选', retained: '已保留', excluded: '已排除' })[screeningStatus(item)]
const retainedCount = computed(() => candidates.value.filter(item => screeningStatus(item) === 'retained').length)
const excludedCount = computed(() => candidates.value.filter(item => screeningStatus(item) === 'excluded').length)
const filteredCandidates = computed(() => candidates.value.filter(item =>
  Number(item.confidence) >= minConfidence.value && (statusFilter.value === 'all' || screeningStatus(item) === statusFilter.value)
))
const previewUrl = computed(() => `/api/realtime-demo/preview/${slotIndex.value}?v=${encodeURIComponent(result.value?.processed_at || '')}`)
function readScreening(): Record<string, ScreenStatus> {
  try { return JSON.parse(sessionStorage.getItem(storageKey) || '{}') } catch { return {} }
}
function formatTime(value: string) { return value ? new Date(value).toLocaleString('zh-CN', { timeZone: 'UTC' }) + ' UTC' : '--' }
async function getJson(url: string, options?: RequestInit) {
  const response = await fetch(url, options)
  if (!response.ok) throw new Error(`${response.status} ${await response.text()}`)
  return response.json()
}
async function loadManifest() {
  loading.value = true; error.value = ''
  try {
    manifest.value = await getJson('/api/realtime-demo/manifest')
    if (slots.value.length) await runDetection()
    else error.value = '没有可用的影像时次'
  } catch (cause: any) { error.value = `影像清单加载失败：${cause?.message || '未知错误'}` }
  finally { loading.value = false }
}
async function runDetection() {
  if (!slots.value.length) return
  loading.value = true; error.value = ''; result.value = null; selectedId.value = ''
  try {
    result.value = await getJson(`/api/realtime-demo/detect?slot_index=${slotIndex.value}`, { method: 'POST' })
    selectedId.value = candidates.value[0]?.detection_id || ''
    await nextTick(); renderMap()
  } catch (cause: any) { error.value = `目标检测失败：${cause?.message || '未知错误'}` }
  finally { loading.value = false }
}
function setStatus(item: Hotspot, status: ScreenStatus) {
  screening.value = { ...screening.value, [screeningKey(item)]: status }
  sessionStorage.setItem(storageKey, JSON.stringify(screening.value))
  if (!filteredCandidates.value.some(candidate => candidate.detection_id === selectedId.value)) selectedId.value = filteredCandidates.value[0]?.detection_id || ''
  renderMap()
}
function selectCandidate(item: Hotspot) { selectedId.value = item.detection_id; renderMap() }
function renderMap() {
  if (view.value !== 'map' || !mapRef.value) return
  const map = mapRef.value
  map.clearDemoEntities()
  for (const item of filteredCandidates.value) {
    map.addDemoPoint({ name: item.detection_id, position: [Number(item.longitude), Number(item.latitude)], color: item.detection_id === selectedId.value ? '#22d3ee' : '#fb923c', label: item.detection_id === selectedId.value ? '当前候选' : '' })
  }
  if (selected.value) map.flyTo({ center: [Number(selected.value.longitude), Number(selected.value.latitude)], height: 32000 })
}
watch(view, async value => { if (value === 'map') { await nextTick(); mapRef.value?.on('load', renderMap); renderMap() } })
watch(filteredCandidates, renderMap)
onMounted(() => { void loadManifest() })
</script>

<style scoped>
.verification-workspace { height: 100%; min-height: 0; display: flex; flex-direction: column; }
.workspace-tabs { flex: 0 0 48px; display: flex; align-items: center; gap: 7px; padding: 6px 12px; border-bottom: 1px solid #244158; background: #0b1d2b; color: #eaf4ff; }
.workspace-tabs strong { margin-right: auto; font-size: 15px; }
.workspace-tabs button { padding: 7px 10px; border: 1px solid #2b495e; border-radius: 6px; background: #0f2637; color: #a9c0d1; font: inherit; font-size: 11px; cursor: pointer; }
.workspace-tabs button.active { color: #eaffff; border-color: #2dd4bf; background: #145367; }
.fusion-workspace { flex: 1; min-height: 0; }
.verification-page { flex: 1; width: 100%; min-height: 0; min-height: 0; display: grid; grid-template-columns: minmax(270px, 31vw) minmax(0, 1fr); background: #06111b; color: #eaf4ff; }
.candidate-rail, .verification-detail { min-height: 0; overflow: auto; padding: 16px; background: linear-gradient(180deg, #0d2333, #081521); }
.candidate-rail { border-right: 1px solid #244158; display: flex; flex-direction: column; gap: 12px; }
.page-heading { display: grid; gap: 6px; } .page-heading span, .verification-detail header span { color: #5eead4; font-size: 10px; font-weight: 800; letter-spacing: .08em; }
h1, h2, p { margin: 0; } h1 { font-size: 23px; } h2 { font-size: 18px; } p { color: #a8bdcd; font-size: 12px; line-height: 1.5; }
.source-badge, .notice { padding: 9px 11px; border: 1px solid #315669; border-radius: 7px; background: #102e40; color: #b9d7e4; font-size: 11px; }
.notice.error { color: #fecaca; border-color: #9f444b; background: #3e202b; }
.field { display: grid; gap: 6px; color: #a8bdcd; font-size: 11px; }
select { width: 100%; min-height: 36px; padding: 0 8px; border: 1px solid #365369; border-radius: 6px; background: #0b1b2a; color: #eaf4ff; font: inherit; }
input[type=range] { width: 100%; accent-color: #2dd4bf; }
.primary-action { min-height: 38px; border: 1px solid #2dd4bf; border-radius: 6px; background: #0f766e; color: white; font: inherit; font-weight: 700; cursor: pointer; }
.primary-action:disabled { opacity: .5; cursor: wait; }
.metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; }
.metrics div { display: grid; gap: 3px; padding: 9px; border: 1px solid #2a4357; border-radius: 6px; background: #102638; }
.metrics span { color: #9ab0c2; font-size: 10px; } .metrics strong { font-size: 18px; }
.list-heading { display: flex; justify-content: space-between; align-items: center; font-size: 12px; } .list-heading span { color: #9ab0c2; }
.candidate-list { min-height: 120px; overflow: auto; display: grid; align-content: start; gap: 7px; }
.candidate { width: 100%; display: flex; justify-content: space-between; align-items: center; gap: 8px; padding: 10px; text-align: left; color: #eaf4ff; border: 1px solid #2c475b; border-radius: 7px; background: #102638; cursor: pointer; }
.candidate.selected { border-color: #2dd4bf; background: #154254; } .candidate span { min-width: 0; display: grid; gap: 3px; } .candidate strong { font-size: 11px; overflow-wrap: anywhere; } .candidate small { color: #a0b5c7; font-size: 10px; }
.candidate b { flex: 0 0 auto; color: #fbbf24; font-size: 10px; } .candidate b.retained { color: #5eead4; } .candidate b.excluded { color: #94a3b8; }
.empty-state { padding: 20px; color: #91a9bb; font-size: 12px; text-align: center; }
.image-stage { min-width: 0; min-height: 0; display: flex; flex-direction: column; }
.stage-head, .stage-foot { flex: 0 0 auto; display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 11px 14px; border-bottom: 1px solid #244158; background: #0a1b29; }
.stage-head > div:first-child { display: grid; gap: 3px; } .stage-head span { color: #9ab0c2; font-size: 10px; } .stage-head strong { font-size: 14px; }
.view-tabs { display: flex; gap: 5px; }.view-tabs button { padding: 6px 9px; border: 1px solid #2b495e; border-radius: 5px; background: #0f2637; color: #9fb3c7; cursor: pointer; }.view-tabs button.active { color: #dff; border-color: #2dd4bf; }
.preview-area, .map-area { flex: 1; min-height: 0; position: relative; display: grid; place-items: center; overflow: hidden; background: #030912; }
.preview-area img { width: 100%; height: 100%; object-fit: contain; image-rendering: pixelated; }.preview-empty { color: #8fa7bb; font-size: 14px; }.map { position: absolute; inset: 0; }
.stage-foot { flex-wrap: wrap; justify-content: flex-start; border-top: 1px solid #244158; border-bottom: 0; color: #9fb3c7; font-size: 11px; }.stage-foot strong { margin-left: auto; color: #5eead4; }
.verification-detail { height: 100%; }.verification-detail header { display: grid; gap: 6px; margin-bottom: 16px; }.verification-detail dl { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 10px; margin: 0; padding: 13px; border: 1px solid #2b495e; border-radius: 8px; background: #0d2636; font-size: 11px; }.verification-detail dt { color: #9fb3c7; }.verification-detail dd { margin: 0; color: #eaf4ff; text-align: right; overflow-wrap: anywhere; }
.screening-actions { display: grid; gap: 8px; margin-top: 14px; }.screening-actions button { min-height: 36px; border: 1px solid #2a6472; border-radius: 6px; background: #124b5a; color: #eaffff; cursor: pointer; font: inherit; }.screening-actions button:nth-child(2) { border-color: #73535b; background: #3c2a37; }.screening-actions button:last-child { border-color: #3b5367; background: #13283a; }.detail-note { margin-top: 15px; padding: 10px; border-left: 3px solid #fbbf24; background: #2c2a22; }
@media (max-width: 950px) { .verification-page { grid-template-columns: minmax(230px, 36vw) minmax(0, 1fr); } }
</style>
