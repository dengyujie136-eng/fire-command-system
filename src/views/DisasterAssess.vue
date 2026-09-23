<template>
  <main class="review-page">
    <header class="review-header">
      <div><span class="eyebrow">HISTORICAL FIRE REVIEW</span><h1>灾前灾后复盘</h1><p>按事件回放环境、传播、影响与决策证据，明确已知结果和数据缺口。</p></div>
      <EventSelector />
    </header>
    <div class="review-grid">
      <section class="review-section"><span class="section-kicker">BEFORE</span><h2>灾前环境</h2><div class="metric-row"><div><span>Weather</span><strong>{{ readinessStatus('Weather') }}</strong></div><div><span>DEM</span><strong>{{ readinessStatus('DEM') }}</strong></div><div><span>Fuel</span><strong>{{ readinessStatus('Fuel') }}</strong></div></div><p>复用当前事件的数据目录和态势输入，避免把缺失影像误报为已完成分析。</p></section>
      <section class="review-section"><span class="section-kicker">DURING</span><h2>灾中传播与决策</h2><div class="metric-row"><div><span>火势推演</span><strong>{{ spreadRun ? '已运行' : 'Missing' }}</strong></div><div><span>空间风险</span><strong>{{ spatialRun ? '已运行' : 'Missing' }}</strong></div><div><span>决策记录</span><strong>{{ decisionRun ? '已生成' : 'Missing' }}</strong></div></div><router-link class="text-link" to="/command-center">打开综合推演与指挥</router-link></section>
      <section class="review-section"><span class="section-kicker">AFTER</span><h2>灾后真实结果</h2><div class="metric-row"><div><span>MTBS</span><strong>{{ readinessStatus('MTBS') }}</strong></div><div><span>Sentinel 变化检测</span><strong class="unavailable">{{ readinessStatus('Sentinel') === 'Missing' ? 'Unavailable' : 'Available' }}</strong></div><div><span>FIRMS</span><strong>{{ readinessStatus('FIRMS') }}</strong></div></div><p>Sentinel 缺失时，不生成 IoU、Hausdorff、变化面积等伪精度指标。</p></section>
      <section class="review-section wide"><span class="section-kicker">EVIDENCE</span><h2>结果摘要</h2><div class="evidence-list"><div><strong>事件</strong><span>{{ store.eventName }}</span></div><div><strong>工作流</strong><span>{{ workflowStatus }}</span></div><div><strong>人工确认</strong><span>{{ store.workflow?.human_confirmation_state || '尚未确认' }}</span></div><div><strong>可用数据</strong><span>{{ store.readiness?.available || 0 }} / {{ store.readiness?.total || 0 }}</span></div></div><details><summary>技术详情</summary><pre>{{ JSON.stringify({ event: store.eventId, workflow: store.workflowRunId, spread: store.spreadRunId, spatial: store.spatialAnalysisId, decision: store.decisionRunId }, null, 2) }}</pre></details></section>
    </div>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import EventSelector from '../components/command/EventSelector.vue'
import { useIncidentContextStore } from '../stores/incidentContextStore'
const store = useIncidentContextStore()
const workflowStatus = computed(() => store.workflow?.status || '尚未运行')
const spreadRun = computed(() => store.workflow?.spread_run_id)
const spatialRun = computed(() => store.workflow?.spatial_analysis_id)
const decisionRun = computed(() => store.workflow?.decision_run_id)
function readinessStatus(name: string) { return store.readiness?.items?.find((item: any) => item.name === name)?.status || 'Missing' }
onMounted(async () => { await store.loadEvents(); await Promise.all([store.loadReadiness(), store.loadLatestWorkflow()]) })
</script>

<style scoped>
.review-page { height: 100%; overflow: auto; padding: 30px 34px 46px; color: #edf3f5; background: #0b1821; }.review-header { display: flex; justify-content: space-between; gap: 24px; align-items: end; padding-bottom: 22px; border-bottom: 1px solid #29404d; }.eyebrow, .section-kicker { color: #7d97a5; font-size: 13px; font-weight: 800; }.review-header h1 { margin: 5px 0 8px; font-size: 30px; }.review-header p, .review-section p { color: #a7b8c0; font-size: 16px; line-height: 1.6; }.review-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 24px; }.review-section { padding: 22px; border: 1px solid #29404d; background: #122631; }.review-section.wide { grid-column: 1 / -1; }.review-section h2 { margin: 6px 0 18px; font-size: 21px; }.metric-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1px; margin-bottom: 18px; background: #29404d; }.metric-row div { min-height: 80px; padding: 14px; background: #182f3a; }.metric-row span, .metric-row strong { display: block; }.metric-row span { color: #98abb4; font-size: 14px; }.metric-row strong { margin-top: 10px; color: #63d19b; font-size: 21px; }.metric-row strong.unavailable { color: #f0ad5c; }.text-link { color: #69bde9; font-size: 15px; text-decoration: none; }.evidence-list { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1px; background: #29404d; }.evidence-list div { display: grid; gap: 7px; padding: 14px; background: #182f3a; }.evidence-list strong { color: #98abb4; font-size: 14px; }.evidence-list span { overflow-wrap: anywhere; font-size: 16px; }details { margin-top: 18px; color: #9fb0b8; font-size: 14px; }summary { cursor: pointer; }pre { overflow: auto; margin-top: 10px; padding: 12px; color: #cbdbe1; background: #09151c; font-size: 13px; }@media (max-width: 900px) { .review-header { align-items: flex-start; flex-direction: column; }.review-grid { grid-template-columns: 1fr; }.review-section.wide { grid-column: auto; }.evidence-list { grid-template-columns: 1fr 1fr; }}@media (max-width: 580px) { .review-page { padding: 22px 16px; }.metric-row { grid-template-columns: 1fr; }}

.review-page { padding: 16px 20px 26px; }
.review-header { padding-bottom: 12px; }
.review-header h1 { font-size: 22px; }
.review-header p, .review-section p { font-size: 12px; }
.review-grid { gap: 10px; margin-top: 14px; }
.review-section { padding: 14px; }
.review-section h2 { font-size: 17px; margin-bottom: 10px; }
.metric-row div { min-height: 58px; padding: 9px; }
.metric-row span, .evidence-list strong { font-size: 11px; }
.metric-row strong { font-size: 17px; margin-top: 5px; }
.evidence-list div { padding: 9px; }
.evidence-list span { font-size: 12px; }

</style>
