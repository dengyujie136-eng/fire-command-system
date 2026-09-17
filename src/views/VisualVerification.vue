<template>
  <main class="verification-page">
    <aside class="candidate-panel">
      <header>
        <span class="eyebrow">MEMBER B / QWEN-VL</span>
        <h1>候选火点视觉复核</h1>
        <p>候选异常不等于真实起火，逐点检查影像证据。</p>
      </header>

      <div class="summary-row">
        <span>候选 {{ candidates.length }}</span>
        <span>已分析 {{ analyzedCount }}</span>
      </div>

      <div v-if="loadError" class="notice error">{{ loadError }}</div>
      <div v-else-if="loadingCandidates" class="notice">正在读取候选点…</div>

      <button
        v-for="item in candidates"
        :key="item.visual_case_id"
        class="candidate-card"
        :class="{ active: item.visual_case_id === selectedId }"
        type="button"
        @click="selectCandidate(item.visual_case_id)"
      >
        <span class="candidate-title">{{ compactId(item.source_candidate_id) }}</span>
        <span class="candidate-meta">{{ coordinateText(item) }}</span>
        <span class="status-pill" :class="resultClass(results[item.visual_case_id])">
          {{ resultText(results[item.visual_case_id], item.status) }}
        </span>
        <small v-if="item.is_simulated">模拟样例</small>
      </button>
    </aside>

    <section class="map-panel">
      <CesiumMap
        v-if="selectedCase"
        ref="mapRef"
        class="map"
        :longitude="selectedCase.longitude"
        :latitude="selectedCase.latitude"
        :height="22000"
        scene-id="visual-verification"
      />
      <div v-else class="empty-map">请选择候选点</div>
      <div v-if="selectedCase" class="map-caption">
        <span>候选位置</span>
        <strong>{{ coordinateText(selectedCase) }}</strong>
      </div>
    </section>

    <aside class="evidence-panel">
      <template v-if="selectedCase">
        <header>
          <span class="eyebrow">EVIDENCE CHAIN</span>
          <h2>影像与模型结论</h2>
          <p>{{ selectedCase.event_name }}</p>
        </header>

        <div v-if="selectedCase.is_simulated" class="notice warning">
          当前记录为模拟样例，不得作为真实火点交付。
        </div>

        <section class="image-card">
          <img v-if="selectedImageUrl" :src="selectedImageUrl" alt="候选点标准化影像" />
          <div v-else class="image-placeholder">运行复核后显示标准化模型影像</div>
        </section>

        <section class="asset-section">
          <div class="section-title"><h3>可用影像</h3><span>{{ assets.length }} 项</span></div>
          <label v-for="asset in assets" :key="asset.source_asset_id" class="asset-option">
            <input v-model="selectedAssetId" type="radio" :value="asset.source_asset_id" />
            <span><strong>{{ asset.source_name || asset.source_type }}</strong><small>{{ asset.source_asset_id }}</small></span>
          </label>
        </section>

        <button class="analyze-button" type="button" :disabled="analyzing || !selectedAssetId" @click="runAnalysis">
          {{ analyzing ? analysisStage : '生成标准图并调用 Qwen-VL' }}
        </button>

        <div v-if="analysisError" class="notice error">{{ analysisError }}</div>

        <section v-if="currentResult" class="result-card" :class="resultClass(currentResult)">
          <div class="decision-row">
            <span>视觉结论</span>
            <strong>{{ decisionLabel(currentResult) }}</strong>
          </div>
          <div class="probability">
            <span>火灾概率</span><b>{{ probabilityText(currentResult.wildfire_likelihood) }}</b>
          </div>
          <dl>
            <dt>火焰</dt><dd>{{ boolText(currentResult.flame_detected) }}</dd>
            <dt>烟羽</dt><dd>{{ boolText(currentResult.smoke_detected) }}</dd>
            <dt>火烧迹地</dt><dd>{{ boolText(currentResult.burn_scar_detected) }}</dd>
            <dt>图像质量</dt><dd>{{ currentResult.image_quality || '--' }}</dd>
            <dt>场景类型</dt><dd>{{ currentResult.scene_type || '--' }}</dd>
            <dt>模型</dt><dd>{{ currentResult.model_name || '--' }}</dd>
          </dl>
          <p>{{ currentResult.reasoning_summary || currentResult.error_message }}</p>
        </section>
      </template>
      <div v-else class="empty-detail">等待候选点数据</div>
    </aside>
  </main>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import CesiumMap from '../components/CesiumMap.vue'
import { visualVerificationAPI } from '../api/modules'

const candidates = ref<any[]>([])
const selectedId = ref('')
const selectedCase = ref<any>(null)
const assets = ref<any[]>([])
const selectedAssetId = ref('')
const selectedImageUrl = ref('')
const results = ref<Record<string, any>>({})
const loadingCandidates = ref(false)
const analyzing = ref(false)
const analysisStage = ref('准备影像…')
const loadError = ref('')
const analysisError = ref('')
const mapRef = ref<InstanceType<typeof CesiumMap> | null>(null)

const currentResult = computed(() => results.value[selectedId.value] || null)
const analyzedCount = computed(() => Object.keys(results.value).length)

function compactId(value: string) {
  if (!value) return '未命名候选点'
  const parts = value.split('-')
  return parts.length > 5 ? parts.slice(-3).join('-') : value
}
function coordinateText(item: any) { return `${Number(item.longitude).toFixed(4)}, ${Number(item.latitude).toFixed(4)}` }
function boolText(value: boolean | null) { return value === true ? '存在' : value === false ? '未发现' : '--' }
function probabilityText(value: any) { return Number.isFinite(Number(value)) ? `${(Number(value) * 100).toFixed(0)}%` : '--' }
function decisionLabel(result: any) {
  if (result?.run_status && result.run_status !== 'succeeded') return '分析失败'
  return ({ confirmed: '确认火情', rejected: '排除火情', uncertain: '需要复核' } as any)[result?.decision] || '等待分析'
}
function resultText(result: any, status: string) { return result ? decisionLabel(result) : ({ imagery_ready: '影像就绪', received: '待影像' } as any)[status] || '待复核' }
function resultClass(result: any) {
  if (!result) return 'pending'
  if (result.run_status !== 'succeeded') return 'failed'
  return result.decision || 'pending'
}

function renderCandidate() {
  const map = mapRef.value
  if (!map || !selectedCase.value) return
  const point: [number, number] = [selectedCase.value.longitude, selectedCase.value.latitude]
  map.clearDemoEntities()
  map.addDemoPoint({ name: '待复核候选点', position: point, color: '#fb923c', label: '待复核' })
  map.flyTo({ center: point, height: 22000 })
}

async function selectCandidate(visualCaseId: string) {
  selectedId.value = visualCaseId
  selectedImageUrl.value = ''
  analysisError.value = ''
  try {
    const detail = await visualVerificationAPI.getCandidate(visualCaseId)
    selectedCase.value = detail.case
    assets.value = detail.assets || []
    selectedAssetId.value = assets.value[0]?.source_asset_id || ''
    await nextTick()
    mapRef.value?.on('load', renderCandidate)
    renderCandidate()
  } catch (cause: any) {
    analysisError.value = `候选详情加载失败：${cause?.message || '未知错误'}`
  }
}

async function runAnalysis() {
  if (!selectedCase.value || !selectedAssetId.value) return
  analyzing.value = true
  analysisError.value = ''
  try {
    analysisStage.value = '生成标准影像…'
    const derivative = await visualVerificationAPI.prepareDerivative(
      selectedCase.value.visual_case_id,
      selectedAssetId.value,
      { source_kind: 'auto', output_format: 'jpeg', max_dimension: 1536, thumbnail_dimension: 512, jpeg_quality: 90 }
    )
    selectedImageUrl.value = visualVerificationAPI.derivativeImageUrl(derivative.derivative_id)
    analysisStage.value = 'Qwen-VL 分析中…'
    const result = await visualVerificationAPI.analyze(selectedCase.value.visual_case_id, [derivative.derivative_id])
    results.value = { ...results.value, [selectedCase.value.visual_case_id]: result }
  } catch (cause: any) {
    analysisError.value = `视觉复核失败：${cause?.message || '未知错误'}`
  } finally {
    analyzing.value = false
  }
}

async function loadCandidates() {
  loadingCandidates.value = true
  loadError.value = ''
  try {
    candidates.value = await visualVerificationAPI.getCandidates()
    if (candidates.value.length) await selectCandidate(candidates.value[0].visual_case_id)
  } catch (cause: any) {
    loadError.value = `候选点加载失败：${cause?.message || '未知错误'}`
  } finally {
    loadingCandidates.value = false
  }
}

onMounted(loadCandidates)
</script>

<style scoped>
.verification-page { width: 100%; height: 100%; min-height: 0; display: grid; grid-template-columns: minmax(280px, 22vw) minmax(480px, 1fr) minmax(340px, 27vw); color: #eaf4ff; background: #050c14; overflow: hidden; }
.candidate-panel, .evidence-panel { min-width: 0; min-height: 0; overflow: auto; padding: 16px; background: linear-gradient(180deg, #0d1c2b, #07111b); }
.candidate-panel { border-right: 1px solid #21364a; } .evidence-panel { border-left: 1px solid #21364a; }
header { display: grid; gap: 6px; margin-bottom: 14px; } h1, h2, h3, p { margin: 0; } h1 { font-size: 21px; } h2 { font-size: 18px; } h3 { font-size: 13px; }
header p, .result-card p { color: #9db0c5; font-size: 12px; line-height: 1.55; } .eyebrow { color: #67e8f9; font-size: 10px; font-weight: 800; letter-spacing: .1em; }
.summary-row, .section-title, .decision-row, .probability { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.summary-row { margin-bottom: 10px; color: #9db0c5; font-size: 11px; }
.candidate-card { position: relative; width: 100%; display: grid; gap: 5px; margin-bottom: 8px; padding: 11px; text-align: left; color: inherit; border: 1px solid #20374b; border-radius: 8px; background: #0d2233; cursor: pointer; }
.candidate-card:hover, .candidate-card.active { border-color: #38bdf8; background: #102b40; } .candidate-title { font-size: 12px; font-weight: 700; overflow-wrap: anywhere; } .candidate-meta, .candidate-card small { color: #91a7bd; font-size: 10px; }
.status-pill { justify-self: start; padding: 3px 7px; border-radius: 99px; color: #cbd5e1; background: #334155; font-size: 10px; } .status-pill.confirmed, .result-card.confirmed { color: #bbf7d0; border-color: #15803d; } .status-pill.rejected, .result-card.rejected { color: #bfdbfe; border-color: #2563eb; } .status-pill.uncertain, .result-card.uncertain { color: #fde68a; border-color: #d97706; } .status-pill.failed, .result-card.failed { color: #fecaca; border-color: #dc2626; }
.map-panel { position: relative; min-width: 0; min-height: 0; background: #020712; } .map { position: absolute; inset: 0; } .empty-map, .empty-detail, .image-placeholder { display: grid; place-items: center; height: 100%; color: #7790a9; font-size: 12px; }
.map-caption { position: absolute; top: 15px; left: 15px; z-index: 5; display: grid; gap: 3px; padding: 9px 11px; border: 1px solid #31485c; border-radius: 7px; background: rgba(3, 12, 22, .78); } .map-caption span { color: #7dd3fc; font-size: 10px; } .map-caption strong { font-size: 13px; }
.notice { padding: 9px 10px; margin-bottom: 10px; border: 1px solid #334155; border-radius: 7px; color: #bfdbfe; background: #10243a; font-size: 11px; line-height: 1.45; } .notice.warning { color: #fde68a; border-color: #854d0e; background: #33240c; } .notice.error { color: #fecaca; border-color: #7f1d1d; background: #321414; }
.image-card { height: 220px; overflow: hidden; margin-bottom: 10px; border: 1px solid #263d51; border-radius: 8px; background: #02070c; } .image-card img { width: 100%; height: 100%; object-fit: contain; }
.asset-section, .result-card { display: grid; gap: 9px; margin-bottom: 10px; padding: 11px; border: 1px solid #263d51; border-radius: 8px; background: #0a1a28; } .section-title span { color: #8fa6bd; font-size: 10px; }
.asset-option { display: flex; gap: 8px; align-items: start; cursor: pointer; } .asset-option span { min-width: 0; display: grid; gap: 2px; } .asset-option strong { font-size: 11px; } .asset-option small { color: #8299b1; font-size: 9px; overflow-wrap: anywhere; }
.analyze-button { width: 100%; min-height: 38px; margin-bottom: 10px; border: 1px solid #0891b2; border-radius: 7px; color: #ecfeff; background: #0e7490; font-weight: 700; cursor: pointer; } .analyze-button:disabled { opacity: .55; cursor: wait; }
.result-card { border-color: #334155; } .decision-row span, .probability span, dt { color: #8fa6bd; font-size: 10px; } .decision-row strong { font-size: 16px; } .probability b { font-size: 20px; }
.result-card dl { display: grid; grid-template-columns: auto 1fr; gap: 6px 12px; margin: 0; } .result-card dd { margin: 0; text-align: right; font-size: 11px; overflow-wrap: anywhere; }
@media (max-width: 1000px) { .verification-page { grid-template-columns: 260px minmax(420px, 1fr) 310px; } } @media (max-width: 820px) { .verification-page { height: auto; overflow: auto; grid-template-columns: 1fr; } .map-panel { height: 50vh; min-height: 380px; } .candidate-panel, .evidence-panel { overflow: visible; } }
</style>
