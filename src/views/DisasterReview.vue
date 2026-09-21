<template>
  <main class="review-page">
    <header class="review-header">
      <div>
        <span>Disaster Review</span>
        <h1>{{ title }}</h1>
      </div>
      <div class="event-select">
        <select v-model="eventId" @change="loadReview">
          <option value="dixie_fire_2021">Dixie Fire 2021</option>
          <option value="park_fire_2024">Park Fire 2024</option>
          <option value="caldor_fire_2021">Caldor Fire 2021</option>
          <option value="mosquito_fire_2022">Mosquito Fire 2022</option>
        </select>
        <button type="button" @click="loadReview" :disabled="loading">刷新</button>
      </div>
    </header>

    <section v-if="loading" class="status-band">正在读取历史事件库和专题图数据...</section>
    <section v-else-if="error" class="status-band error">{{ error }}</section>

    <template v-if="review">
      <section class="source-strip">
        <article v-for="(value, key) in review.source_modes" :key="key">
          <span>{{ key }}</span>
          <strong>{{ value }}</strong>
        </article>
      </section>

      <section class="analysis-grid">
        <article class="analysis-panel">
          <h2>灾前分析</h2>
          <p>{{ review.pre_fire.summary }}</p>
          <div class="map-list">
            <div v-for="item in review.pre_fire.maps" :key="item.id">
              <strong>{{ item.title }}</strong>
              <span>{{ item.source_mode }} · {{ item.source }}</span>
            </div>
          </div>
          <dl>
            <dt>平均风速</dt><dd>{{ numberText(review.pre_fire.weather_stats?.avg_wind_speed_m_s, 'm/s') }}</dd>
            <dt>总降雨</dt><dd>{{ numberText(review.pre_fire.weather_stats?.total_precipitation_mm, 'mm') }}</dd>
          </dl>
        </article>

        <article class="analysis-panel">
          <h2>灾中分析</h2>
          <p>{{ review.during_fire.summary }}</p>
          <div class="map-list">
            <div v-for="item in review.during_fire.maps" :key="item.id">
              <strong>{{ item.title }}</strong>
              <span>{{ item.source_mode }} · {{ item.source }}</span>
            </div>
          </div>
          <div class="wind-grid">
            <span v-for="sample in windSamples" :key="sample.observed_at" :style="windStyle(sample)">
              <i></i><b>{{ numberText(sample.wind_speed_m_s, 'm/s') }}</b>
            </span>
          </div>
        </article>

        <article class="analysis-panel">
          <h2>灾后分析</h2>
          <p>{{ review.post_fire.summary }}</p>
          <div class="map-list">
            <div v-for="item in review.post_fire.maps" :key="item.id">
              <strong>{{ item.title }}</strong>
              <span>{{ item.source_mode }} · {{ item.source }}</span>
            </div>
          </div>
          <dl>
            <dt>MTBS面积</dt><dd>{{ burnedAreaText }}</dd>
            <dt>NDVI变化</dt><dd>未注册数据产品</dd>
          </dl>
        </article>
      </section>

      <section class="report-section">
        <div class="report-main">
          <h2>{{ review.report.title }}</h2>
          <article v-for="section in review.report.sections" :key="section.title">
            <h3>{{ section.title }}</h3>
            <p>{{ section.content }}</p>
          </article>
        </div>
        <aside class="rule-summary">
          <h2>规则库摘要</h2>
          <strong>{{ review.rule_base.rule_count }} 条规则</strong>
          <div v-for="category in review.rule_base.categories" :key="category.category">
            <span>{{ category.label }}</span>
            <b>{{ category.rule_count }}</b>
          </div>
        </aside>
      </section>
    </template>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { disasterReviewAPI } from '../api/modules'

const HISTORICAL_EVENT_KEY = 'fire-command-current-historical-event'

const route = useRoute()
const router = useRouter()
const eventId = ref(String(route.query.event_id || localStorage.getItem(HISTORICAL_EVENT_KEY) || 'dixie_fire_2021'))
const review = ref<any>(null)
const loading = ref(false)
const error = ref('')

const title = computed(() => review.value?.event?.name ? `${review.value.event.name} 灾害分析报告` : '灾前-灾中-灾后复盘')
const windSamples = computed(() => (review.value?.during_fire?.wind_rain_samples || []).slice(0, 12))
const burnedAreaText = computed(() => {
  const areaM2 = Number(review.value?.post_fire?.burned_area?.area_m2)
  if (Number.isFinite(areaM2) && areaM2 > 0) return `${(areaM2 / 1_000_000).toFixed(1)} km²`
  return review.value?.event?.burned_area_km2 ? `${review.value.event.burned_area_km2} km²` : '未注册'
})

function numberText(value: any, unit: string) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? `${parsed.toFixed(1)} ${unit}` : '--'
}

function windStyle(sample: any) {
  const deg = Number(sample.wind_direction_deg || 0)
  const rain = Number(sample.precipitation_mm || 0)
  return {
    '--wind-deg': `${deg}deg`,
    '--rain-alpha': String(Math.min(0.85, Math.max(0.12, rain / 8)))
  }
}

async function loadReview() {
  loading.value = true
  error.value = ''
  try {
    localStorage.setItem(HISTORICAL_EVENT_KEY, eventId.value)
    const result = await disasterReviewAPI.getAnalysis(eventId.value)
    review.value = result?.data || result
    await router.replace({ path: '/disaster-review', query: { event_id: eventId.value } })
  } catch (err: any) {
    error.value = err?.message || '复盘分析加载失败'
  } finally {
    loading.value = false
  }
}

watch(() => route.query.event_id, (value) => {
  if (value && value !== eventId.value) {
    eventId.value = String(value)
    loadReview()
  }
})

onMounted(loadReview)
</script>

<style scoped>
.review-page {
  height: 100%;
  overflow: auto;
  background: #07111b;
  color: #edf6ff;
  padding: 18px;
}

.review-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.review-header span,
.analysis-panel p,
.map-list span,
.source-strip span,
.rule-summary span,
dl dt {
  color: #9fb0c7;
  font-size: 12px;
}

.review-header h1,
h2,
h3,
p {
  margin: 0;
  letter-spacing: 0;
}

.review-header h1 {
  margin-top: 4px;
  font-size: 24px;
}

.event-select {
  display: flex;
  gap: 8px;
}

select,
button {
  min-height: 36px;
  border-radius: 6px;
  border: 1px solid rgba(148, 163, 184, 0.28);
  background: #0e1a2a;
  color: #e5f0ff;
  padding: 0 10px;
}

button {
  background: #0f766e;
  border-color: #14b8a6;
  cursor: pointer;
}

.status-band,
.source-strip,
.analysis-panel,
.report-main,
.rule-summary {
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 8px;
  background: rgba(8, 19, 31, 0.76);
}

.status-band {
  padding: 12px;
  margin-bottom: 12px;
}

.status-band.error {
  color: #fecaca;
  border-color: rgba(248, 113, 113, 0.45);
}

.source-strip {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 8px;
  padding: 10px;
  margin-bottom: 12px;
}

.source-strip article {
  min-width: 0;
  display: grid;
  gap: 4px;
}

.source-strip strong {
  color: #67e8f9;
  font-size: 12px;
  overflow-wrap: anywhere;
}

.analysis-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.analysis-panel {
  padding: 14px;
  display: grid;
  gap: 12px;
}

.analysis-panel h2,
.report-main h2,
.rule-summary h2 {
  font-size: 18px;
}

.map-list {
  display: grid;
  gap: 8px;
}

.map-list div {
  display: grid;
  gap: 3px;
  padding: 9px;
  border-radius: 7px;
  background: rgba(15, 35, 53, 0.72);
}

.map-list strong {
  font-size: 13px;
}

dl {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 8px 12px;
  margin: 0;
}

dl dd {
  margin: 0;
  color: #e5f0ff;
}

.wind-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}

.wind-grid span {
  min-height: 54px;
  display: grid;
  place-items: center;
  gap: 3px;
  border-radius: 7px;
  background: linear-gradient(180deg, rgba(14, 116, 144, 0.2), rgba(30, 64, 175, var(--rain-alpha)));
}

.wind-grid i {
  width: 28px;
  height: 2px;
  background: #93c5fd;
  transform: rotate(var(--wind-deg));
  transform-origin: center;
  position: relative;
}

.wind-grid i::after {
  content: '';
  position: absolute;
  right: -1px;
  top: -4px;
  border-left: 7px solid #93c5fd;
  border-top: 5px solid transparent;
  border-bottom: 5px solid transparent;
}

.wind-grid b {
  font-size: 11px;
  color: #dbeafe;
}

.report-section {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(260px, 24vw);
  gap: 12px;
  margin-top: 12px;
}

.report-main,
.rule-summary {
  padding: 16px;
}

.report-main {
  display: grid;
  gap: 14px;
}

.report-main article {
  display: grid;
  gap: 6px;
}

.report-main h3 {
  font-size: 15px;
  color: #bfdbfe;
}

.report-main p {
  color: #d6e8f8;
  line-height: 1.6;
}

.rule-summary {
  align-self: start;
  display: grid;
  gap: 10px;
}

.rule-summary > strong {
  color: #5eead4;
  font-size: 22px;
}

.rule-summary div {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid rgba(148, 163, 184, 0.14);
}

@media (max-width: 1100px) {
  .source-strip,
  .analysis-grid,
  .report-section {
    grid-template-columns: 1fr;
  }
}
</style>