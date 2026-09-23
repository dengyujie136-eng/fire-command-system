<template>
  <section class="simulation-output" aria-label="火势推演输出">
    <header><strong>推演输出</strong><span :class="task.status">{{ statusLabel }}</span></header>
    <p>{{ task.message || '在推演页设置时长与气象，或在对话中说“预测四小时之后的火势”。' }}</p>
    <dl>
      <dt>预测时长</dt><dd>{{ task.status==='idle' ? '--' : task.requestedHours+' 小时' }}</dd>
      <dt>运行编号</dt><dd>{{ task.resultRunId || incident.spreadRunId || '--' }}</dd>
      <dt>火线时间步</dt><dd>{{ fireEvent.spreadSteps.length || '--' }}</dd>
      <dt>最终过火面积</dt><dd>{{ finalArea }}</dd>
      <dt>蔓延方向</dt><dd>{{ spreadDirection }}</dd>
      <dt>预测范围</dt><dd>{{ extent }}</dd>
    </dl>
    <router-link to="/command-center">在地图查看火线与时间轴 →</router-link>
    <small>显示模型返回的结果；气象更新间隔不等于预测总时长。</small>
  </section>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import { useAssistantTaskStore } from '../stores/assistantTaskStore'
import { useIncidentContextStore } from '../stores/incidentContextStore'
import { useFireEventStore } from '../stores/fireEventStore'
const task=useAssistantTaskStore()
const incident=useIncidentContextStore()
const fireEvent=useFireEventStore()
const statusLabel=computed(()=>({idle:'待运行',queued:'待提交',running:'计算中',completed:'已完成',failed:'失败',blocked:'待补充条件'} as Record<string,string>)[task.status]||'待运行')
const finalArea=computed(()=>{const value=Number(fireEvent.spreadRun?.final_area_km2);return Number.isFinite(value)&&value>0 ? value.toFixed(3)+' km²' : '--'})
const spreadDirection=computed(()=>{const value=Number(fireEvent.spreadRun?.spread_direction_deg);return Number.isFinite(value)?Math.round(value)+'°':'--'})
const extent=computed(()=>{
  const step=fireEvent.spreadSteps.at(-1) as any
  const points:number[][]=[]
  function collect(value:any){
    if(Array.isArray(value)){if(value.length>=2&&typeof value[0]==='number'&&typeof value[1]==='number'){points.push(value);return}value.forEach(collect)}
    else if(value&&typeof value==='object'){if(value.coordinates)collect(value.coordinates);if(value.geometry)collect(value.geometry);if(value.features)collect(value.features)}
  }
  collect(step?.fireline_geojson)
  if(!points.length)return '--'
  let west=Infinity,east=-Infinity,south=Infinity,north=-Infinity
  for(const [lon,lat] of points){west=Math.min(west,lon);east=Math.max(east,lon);south=Math.min(south,lat);north=Math.max(north,lat)}
  return west.toFixed(3)+'–'+east.toFixed(3)+'°E，'+south.toFixed(3)+'–'+north.toFixed(3)+'°N'
})
</script>
<style scoped>
.simulation-output{flex:0 0 auto;display:grid;gap:6px;margin:9px;padding:10px;border:1px solid #2c6470;border-radius:8px;background:linear-gradient(145deg,#0d3541,#0a1d2a);color:#e8f7fb}
header{display:flex;justify-content:space-between;gap:8px;align-items:center}header strong{font-size:12px}header span{font-size:10px;color:#9bb4bf}header span.running{color:#fbbf24}header span.completed{color:#5eead4}header span.failed,header span.blocked{color:#fca5a5}
p{margin:0;color:#b8d2da;font-size:10px;line-height:1.45}dl{display:grid;grid-template-columns:auto 1fr;gap:4px 8px;margin:0;font-size:10px}dt{color:#8fafbc}dd{margin:0;text-align:right;overflow-wrap:anywhere}
a{color:#67e8f9;font-size:10px;text-decoration:none}small{color:#789ba8;font-size:9px}
</style>
