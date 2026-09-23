<template>
  <aside class="situation-panel">
    <div class="panel-heading"><div><span>救援态势</span><h2>当前态势</h2></div><router-link to="/realtime-monitor">查看监测</router-link></div>
    <div class="metric-grid">
      <div><span>可信火点</span><strong>{{ confirmationText }}</strong></div><div><span>预测面积</span><strong>{{ spreadArea }}</strong></div>
      <div><span>主要方向</span><strong>{{ direction }}</strong></div><div><span>空间风险</span><strong>{{ risk }}</strong></div>
    </div>
    <dl class="rescue-list">
      <div><dt>重点目标是否受威胁</dt><dd>{{ targetThreat }}</dd></div>
      <div><dt>最先到达队伍</dt><dd>{{ nearestTeam }}</dd></div>
      <div><dt>资源是否满足计划</dt><dd>{{ resourceState }}</dd></div>
      <div><dt>周边通行条件</dt><dd>演练可达性，未接入真实 OSM 路网</dd></div>
      <div><dt>风场</dt><dd>{{ wind }}</dd></div>
    </dl>
    <div class="readiness-list"><div v-for="item in readiness" :key="item.name"><span>{{ item.name }}</span><b :data-status="item.status">{{ readinessLabel(item.status) }}</b></div></div>
  </aside>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useIncidentContextStore } from '../../stores/incidentContextStore'

const store = useIncidentContextStore()
const readiness = computed(() => store.readiness?.items || [])
const situation = computed(() => store.stages.find((stage) => stage.stage === 'situation')?.metadata_json || {})
const spread = computed(() => store.stages.find((stage) => stage.stage === 'spread')?.metadata_json || {})
const riskStage = computed(() => store.stages.find((stage) => stage.stage === 'spatial_risk')?.metadata_json || {})
const route = computed(() => store.workflow?.artifacts?.route?.result?.recommended_route || {})
const resource = computed(() => store.workflow?.artifacts?.resource_plan?.result?.resource_summary || {})
const scenario = computed(() => store.workflow?.scenario || null)
const confirmationText = computed(() => store.confirmationId ? '已确认' : '等待核验')
const spreadArea = computed(() => spread.value.final_area_km2 != null ? Number(spread.value.final_area_km2).toFixed(2) + ' km²' : '--')
const direction = computed(() => spread.value.direction_deg != null ? Math.round(Number(spread.value.direction_deg)) + '°' : '--')
const risk = computed(() => ({ low: '低', medium: '中', high: '高', extreme: '极高' } as Record<string, string>)[String(riskStage.value?.summary?.risk_level || spread.value.risk_level || '')] || '暂无数据')
const targetThreat = computed(() => scenario.value?.locations?.some((item: any) => item.type === 'protected_target') ? '模型传播方向存在演练目标威胁' : '暂无演练目标')
const nearestTeam = computed(() => route.value?.estimated_travel_time_minutes != null ? '演练灭火队伍 1，约 ' + Number(route.value.estimated_travel_time_minutes).toFixed(1) + ' 分钟' : '等待路线计算')
const resourceState = computed(() => resource.value?.shortage_count ? '存在 ' + resource.value.shortage_count + ' 项缺口' : resource.value?.selected_count != null ? '可满足已计算任务' : '等待资源评估')
const wind = computed(() => {
  const env = situation.value?.situation_packet?.environment || {}
  return env.wind_speed_m_s != null ? String(env.wind_speed_m_s) + ' m/s · ' + String(env.wind_direction_deg ?? '--') + '°' : '--'
})
function readinessLabel(status: string) { return status === 'Available' ? '可用' : status === 'Missing' ? '缺失' : status }
</script>

<style scoped>
.situation-panel { min-width: 0; padding: 16px; border-left: 1px solid #2b414f; background: #10202b; overflow: auto; }
.panel-heading { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
.panel-heading span { color: #78909d; font-size: 13px; font-weight: 700; } h2 { margin: 3px 0 0; color: #f4f7f8; font-size: 20px; } a { color: #68b7e8; font-size: 14px; text-decoration: none; }
.metric-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1px; margin: 18px 0; background: #2a414e; }.metric-grid div { min-width: 0; padding: 13px; background: #172a36; }.metric-grid span, .metric-grid strong { display: block; }.metric-grid span { color: #92a5af; font-size: 13px; }.metric-grid strong { margin-top: 6px; color: #fff; font-size: 18px; overflow-wrap: anywhere; }
.rescue-list { margin: 0; }.rescue-list div, .readiness-list div { display: flex; justify-content: space-between; gap: 12px; padding: 9px 0; border-bottom: 1px solid #263b47; font-size: 14px; } dt, .readiness-list span { color: #93a7b1; } dd { margin: 0; color: #e2e9ec; text-align: right; }.readiness-list { margin-top: 15px; }.readiness-list b { color: #63cf98; font-size: 13px; }.readiness-list b[data-status='Missing'] { color: #ef8f82; }
</style>
