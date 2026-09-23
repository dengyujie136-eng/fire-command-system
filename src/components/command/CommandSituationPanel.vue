<template>
  <aside class="situation-panel">
    <div class="panel-heading">
      <div>
        <span>综合态势</span>
        <h2>当前气象</h2>
      </div>
      <router-link to="/realtime-monitor">查看监测</router-link>
    </div>

    <div class="weather-grid">
      <div><span>风速</span><strong>{{ weather.windSpeed }}</strong></div>
      <div><span>风向</span><strong>{{ weather.windDirection }}</strong></div>
      <div><span>温度</span><strong>{{ weather.temperature }}</strong></div>
      <div><span>湿度</span><strong>{{ weather.humidity }}</strong></div>
    </div>

    <dl class="situation-list">
      <div><dt>可信火点</dt><dd>{{ confirmationText }}</dd></div>
      <div><dt>预测影响面积</dt><dd>{{ spreadArea }}</dd></div>
      <div><dt>主要扩散方向</dt><dd>{{ direction }}</dd></div>
      <div><dt>当前空间风险</dt><dd :data-risk="riskKey">{{ risk }}</dd></div>
      <div><dt>重点目标威胁</dt><dd>{{ targetThreat }}</dd></div>
      <div><dt>任务资源状态</dt><dd>{{ resourceState }}</dd></div>
    </dl>

    <p class="weather-note">气象数值来自当前工作流读取的小时气象记录。地图风矢量在指挥页关闭，避免以单条线替代真实风场。</p>
  </aside>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useIncidentContextStore } from '../../stores/incidentContextStore'

const store = useIncidentContextStore()
const situation = computed(() => store.stages.find((stage) => stage.stage === 'situation')?.metadata_json || {})
const spread = computed(() => store.stages.find((stage) => stage.stage === 'spread')?.metadata_json || {})
const riskStage = computed(() => store.stages.find((stage) => stage.stage === 'spatial_risk')?.metadata_json || {})
const scenario = computed(() => store.workflow?.scenario || null)
const resource = computed(() => store.workflow?.artifacts?.resource_plan?.result?.resource_summary || {})
const environment = computed(() => situation.value?.situation_packet?.environment || {})
const riskKey = computed(() => String(riskStage.value?.summary?.risk_level || spread.value.risk_level || ''))
const weather = computed(() => ({
  windSpeed: environment.value.wind_speed_m_s != null ? Number(environment.value.wind_speed_m_s).toFixed(1) + ' m/s' : '--',
  windDirection: environment.value.wind_direction_deg != null ? Math.round(Number(environment.value.wind_direction_deg)) + '°' : '--',
  temperature: environment.value.temperature_c != null ? Number(environment.value.temperature_c).toFixed(1) + '℃' : '--',
  humidity: environment.value.relative_humidity_percent != null
    ? Number(environment.value.relative_humidity_percent).toFixed(1) + '%'
    : environment.value.humidity_percent != null ? Number(environment.value.humidity_percent).toFixed(1) + '%' : '--',
}))
const confirmationText = computed(() => store.confirmationId ? '已确认' : '等待核验')
const spreadArea = computed(() => spread.value.final_area_km2 != null ? Number(spread.value.final_area_km2).toFixed(2) + ' km²' : '--')
const direction = computed(() => spread.value.direction_deg != null ? Math.round(Number(spread.value.direction_deg)) + '°' : '--')
const risk = computed(() => ({ low: '低', medium: '中', high: '高', extreme: '极高' } as Record<string, string>)[riskKey.value] || '暂无数据')
const targetThreat = computed(() => scenario.value?.locations?.some((item: any) => item.type === 'protected_target') ? '存在演练目标威胁方向' : '等待场景评估')
const resourceState = computed(() => resource.value?.shortage_count
  ? '存在 ' + resource.value.shortage_count + ' 项缺口'
  : resource.value?.selected_count != null ? '满足当前演练任务' : '等待资源评估')
</script>

<style scoped>
.situation-panel { min-width: 0; padding: 16px; border-left: 1px solid #2b414f; background: #10202b; overflow: auto; }
.panel-heading { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
.panel-heading span { color: #77919e; font-size: 13px; font-weight: 700; }
h2 { margin: 3px 0 0; color: #f4f7f8; font-size: 20px; }
a { color: #68b7e8; font-size: 14px; text-decoration: none; }
.weather-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1px; margin: 18px 0; background: #2a414e; }
.weather-grid div { min-width: 0; padding: 13px; background: #172a36; }
.weather-grid span, .weather-grid strong { display: block; }
.weather-grid span { color: #92a5af; font-size: 13px; }
.weather-grid strong { margin-top: 6px; color: #fff; font-size: 18px; overflow-wrap: anywhere; }
.situation-list { margin: 0; }
.situation-list div { display: flex; justify-content: space-between; gap: 12px; padding: 9px 0; border-bottom: 1px solid #263b47; font-size: 14px; }
dt { color: #93a7b1; }
dd { margin: 0; color: #e2e9ec; text-align: right; }
dd[data-risk='high'], dd[data-risk='extreme'] { color: #ffae78; font-weight: 700; }
.weather-note { margin: 15px 0 0; color: #91a6b0; font-size: 12px; line-height: 1.5; }

.situation-panel { padding: 11px; }
.situation-panel h2 { font-size: 16px; }
.situation-panel .weather-grid { margin: 10px 0; }
.situation-panel .weather-grid div { padding: 8px; }
.situation-panel .weather-grid span, .situation-panel .panel-heading span { font-size: 11px; }
.situation-panel .weather-grid strong { font-size: 15px; margin-top: 3px; }
.situation-panel .situation-list div { padding: 6px 0; font-size: 11px; }
.situation-panel .weather-note { font-size: 10px; }

</style>
