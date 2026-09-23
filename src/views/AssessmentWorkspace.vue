<template>
  <div class="assessment-workspace">
    <main class="assessment-page">
      <header><span>POST FIRE / IMAGE REVIEW</span><h1>灾前灾后影像对照</h1><p>选择同一地点、相近范围的影像，记录可见损失并生成待现场核查的重建建议。</p></header>
      <div class="assessment-pipeline" aria-label="灾情评估步骤">
        <div><b>01</b><strong>灾前灾后影像</strong><small>{{ beforeUrl && afterUrl ? '已选择本地影像' : '等待两期影像' }}</small></div>
        <div><b>02</b><strong>千问视觉变化分析</strong><small>等待影像分析接口接入</small></div>
        <div><b>03</b><strong>受灾区域提取与重建</strong><small>等待空间结果；可先记录人工判读</small></div>
      </div>
      <p class="model-notice">自动分析使用登记的多波段 GeoTIFF；若缺少影像或模型报错，仍可在下方记录人工判读，不会生成虚构的面积或模型结论。</p>
      <section class="auto-panel"><h2>真实影像变化分析</h2><p>使用影像目录中同一区域的灾前和灾后多波段产品，调用现有 dNBR / dNDVI 区域提取，再由千问视觉解释可见损失。</p><div class="auto-controls"><label>灾前产品<select v-model="beforeAsset"><option value="">请选择</option><option v-for="item in beforeProducts" :key="item.asset_id" :value="item.asset_id">{{ item.scene_id }} · {{ item.acquired_at }}</option></select></label><label>灾后产品<select v-model="afterAsset"><option value="">请选择</option><option v-for="item in afterProducts" :key="item.asset_id" :value="item.asset_id">{{ item.scene_id }} · {{ item.acquired_at }}</option></select></label><button type="button" :disabled="analysisBusy||!beforeAsset||!afterAsset" @click="runAssessment">{{ analysisBusy?'分析中…':'执行变化检测与千问评估' }}</button><button type="button" @click="loadCatalog">刷新影像目录</button></div><p v-if="catalogError||analysisError" class="analysis-error">{{ catalogError||analysisError }}</p><p v-if="!beforeProducts.length||!afterProducts.length">缺少可分析的灾前或灾后影像。可在右侧对话请求数据智能体获取影像，或手动导入五波段 GeoTIFF。</p><div v-if="analysisResult" class="analysis-result"><strong>变化区域 {{ Number(analysisResult.area_hectares).toFixed(2) }} 公顷</strong><span>{{ analysisResult.method }} · {{ analysisResult.analysis_id }} · {{ analysisResult.is_simulated?'模拟数据':'真实影像计算' }}</span><p v-for="warning in analysisResult.warnings||[]" :key="warning">{{ warning }}</p><div class="result-images"><img :src="artifactUrl('before_rgb')" alt="真实灾前 RGB 影像"><img :src="artifactUrl('after_rgb')" alt="真实灾后 RGB 影像"></div></div><div v-if="qwenAssessment" class="qwen-result"><h3>千问视觉分析 · {{ qwenModel }}</h3><p>{{ qwenAssessment.summary }}</p><strong>可见受灾迹象</strong><p v-for="item in qwenAssessment.affected_features" :key="item">{{ item }}</p><strong>重建建议</strong><p v-for="item in qwenAssessment.reconstruction_advice" :key="item">{{ item }}</p><small v-for="item in qwenAssessment.limitations" :key="item">{{ item }}</small></div></section>
      <section class="image-pair">
        <label class="image-slot"><b>灾前影像</b><img v-if="beforeUrl" :src="beforeUrl" alt="灾前影像"><span v-else>点击选择灾前影像</span><input type="file" accept="image/*" @change="pick($event,'before')"></label>
        <label class="image-slot"><b>灾后影像</b><img v-if="afterUrl" :src="afterUrl" alt="灾后影像"><span v-else>点击选择灾后影像</span><input type="file" accept="image/*" @change="pick($event,'after')"></label>
      </section>
      <p class="source-note">影像仅在当前浏览器中预览。面积、植被损失等空间指标需要配准影像和分析服务；当前不以目测结果冒充计算值。</p>
      <section class="damage-panel"><div><span>IMAGE INTERPRETATION</span><h2>可见影响记录</h2></div><div class="impact-list"><label v-for="item in options" :key="item.id"><input v-model="impacts" type="checkbox" :value="item.id">{{ item.label }}</label></div><label class="notes">判读依据和位置<textarea v-model="notes" rows="3" placeholder="填写影像日期、范围、可见变化和不确定性"></textarea></label></section>
      <section class="suggestions"><div><span>RECOVERY / ACTIONS</span><h2>重建建议</h2></div><p v-if="!impacts.length">选择影像中可见的影响后显示对应的核查建议。</p><article v-for="item in selectedOptions" :key="item.id"><strong>{{ item.title }}</strong><p>{{ item.suggestion }}</p><small>依据：人工标记「{{ item.label }}」；实施前需现场核查。</small></article></section>
      <Teleport defer to="#business-panel"><aside class="assessment-dock"><h2>评估依据</h2><dl><dt>当前事件</dt><dd>{{ incident.eventName }}</dd><dt>灾前影像</dt><dd>{{ beforeUrl?'已选择':'未选择' }}</dd><dt>灾后影像</dt><dd>{{ afterUrl?'已选择':'未选择' }}</dd><dt>影响类型</dt><dd>{{ impacts.length }} 项</dd><dt>判读说明</dt><dd>{{ notes.trim()?'已填写':'未填写' }}</dd></dl><p>建议是人工影像判读的待核实清单，尚未产生自动变化检测或损失面积结果。</p></aside></Teleport>
    </main>
  </div>
</template>
<script setup lang="ts">
import { computed,onBeforeUnmount,onMounted,ref } from 'vue'
import { useRoute } from 'vue-router'
import { useIncidentContextStore } from '../stores/incidentContextStore'
const incident=useIncidentContextStore(),route=useRoute()
const catalog=ref<any[]>([]),beforeAsset=ref(''),afterAsset=ref('')
const analysisBusy=ref(false),analysisError=ref(''),catalogError=ref('')
const analysisResult=ref<any>(null),qwenAssessment=ref<any>(null),qwenModel=ref('')
const beforeProducts=computed(()=>catalog.value.filter(x=>x.phase==='comparison_pre'&&x.available_locally&&x.source_type==='analysis_composite'&&x.quality_status==='available'))
const afterProducts=computed(()=>catalog.value.filter(x=>x.phase==='comparison_post'&&x.available_locally&&x.source_type==='analysis_composite'&&x.quality_status==='available'))
function artifactUrl(name:string){return analysisResult.value?'/api/visual-verification/analyses/'+encodeURIComponent(analysisResult.value.analysis_id)+'/artifacts/'+name:''}
async function loadCatalog(){
 catalogError.value=''
 try{
  const response=await fetch('/api/data-agent/imagery/catalog/'+encodeURIComponent(incident.eventId))
  const payload=await response.json()
  if(!response.ok)throw new Error(typeof payload.detail==='string'?payload.detail:'影像目录读取失败')
  catalog.value=payload.data||[]
  beforeAsset.value=beforeProducts.value[0]?.asset_id||''
  afterAsset.value=afterProducts.value[0]?.asset_id||''
 }catch(error:any){catalogError.value=error?.message||'影像目录读取失败'}
}
const beforeUrl=ref(''),afterUrl=ref('')
const impacts=ref<string[]>([]),notes=ref('')
const options=[
 {id:'slope',label:'坡面裸露或侵蚀迹象',title:'核查坡面稳定性',suggestion:'核查坡度、裸土和下游汇水路径，再决定覆盖与截排水措施。'},
 {id:'road',label:'道路与桥涵受损',title:'恢复关键通行路线',suggestion:'现场检查受损路段与桥涵，优先恢复救援和巡护通行。'},
 {id:'vegetation',label:'植被退化',title:'制定分区植被恢复计划',suggestion:'结合土壤和自然更新情况，划定保育、补植与持续监测区域。'},
 {id:'facility',label:'建筑或设施受损',title:'开展设施安全复核',suggestion:'逐项核查结构、供水和供电，再确定修复优先级。'}
]
const selectedOptions=computed(()=>options.filter(x=>impacts.value.includes(x.id)))
async function runAssessment(){
 analysisBusy.value=true;analysisError.value='';analysisResult.value=null;qwenAssessment.value=null
 try{
  if(!incident.visualCaseId)await incident.loadLatestWorkflow()
  if(!incident.visualCaseId)throw new Error('缺少真实候选火点案例，请先启动监测与核验工作流。')
  const before=catalog.value.find(x=>x.asset_id===beforeAsset.value),after=catalog.value.find(x=>x.asset_id===afterAsset.value)
  if(!before||!after)throw new Error('请先获取并选择灾前、灾后的多波段产品。')
  const response=await fetch('/api/visual-verification/analyses/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({event_id:incident.eventId,analysis_type:'burned_area',time_range:{start_at:before.acquired_at,end_at:after.acquired_at},asset_ids:[before.asset_id,after.asset_id],visual_case_id:incident.visualCaseId})})
  const payload=await response.json()
  if(!response.ok)throw new Error(typeof payload.detail==='string'?payload.detail:payload.detail?.message||'变化检测失败 '+response.status)
  analysisResult.value=payload
  const qwenResponse=await fetch('/api/data-agent/imagery/assess/'+encodeURIComponent(payload.analysis_id),{method:'POST'})
  const qwenPayload=await qwenResponse.json()
  if(!qwenResponse.ok)throw new Error(typeof qwenPayload.detail==='string'?qwenPayload.detail:'千问视觉评估失败 '+qwenResponse.status)
  qwenAssessment.value=qwenPayload.data.assessment
  qwenModel.value=qwenPayload.data.model
 }catch(error:any){analysisError.value=error?.message||'评估失败'}
 finally{analysisBusy.value=false}
}
async function handleImageryReady(){await loadCatalog();if(route.query.auto_assess==='1'&&beforeAsset.value&&afterAsset.value&&!analysisBusy.value&&!analysisResult.value)await runAssessment()}
onMounted(async()=>{window.addEventListener('fire:imagery-ready',handleImageryReady);try{await incident.loadLatestWorkflow()}catch{}await loadCatalog();if(route.query.auto_assess==='1'&&beforeAsset.value&&afterAsset.value)await runAssessment()})
function pick(event:Event,kind:'before'|'after'){const file=(event.target as HTMLInputElement).files?.[0];if(!file)return;const target=kind==='before'?beforeUrl:afterUrl;if(target.value)URL.revokeObjectURL(target.value);target.value=URL.createObjectURL(file)}
onBeforeUnmount(()=>{window.removeEventListener('fire:imagery-ready',handleImageryReady);if(beforeUrl.value)URL.revokeObjectURL(beforeUrl.value);if(afterUrl.value)URL.revokeObjectURL(afterUrl.value)})
</script>
<style scoped>
.assessment-workspace {height:100%;min-height:0;display:flex;flex-direction:column;background:#081521;color:#eaf4ff}
.workspace-tabs {flex:0 0 44px;display:flex;gap:7px;align-items:center;padding:5px 12px;border-bottom:1px solid #244158;background:#0b1d2b}
.workspace-tabs strong {margin-right:auto;font-size:14px}.workspace-tabs button {padding:6px 9px;border:1px solid #2b495e;border-radius:5px;background:#0f2637;color:#a9c0d1;font-size:11px;cursor:pointer}.workspace-tabs button.active {border-color:#2dd4bf;background:#145367;color:white}
.history-view {flex:1;min-height:0}.assessment-page {flex:1;min-height:0;overflow:auto;padding:14px}.assessment-page header {margin-bottom:12px}.assessment-page header span,.damage-panel span,.suggestions span {color:#5eead4;font-size:10px;font-weight:800;letter-spacing:.08em}
h1,h2,p {margin:0}h1 {margin:4px 0;font-size:21px}h2 {margin:3px 0 9px;font-size:16px}p {color:#9eb4c5;font-size:11px;line-height:1.5}
.assessment-pipeline {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:0 0 10px}.assessment-pipeline div {display:grid;gap:4px;min-width:0;padding:9px;border:1px solid #315669;border-radius:6px;background:#102838}.assessment-pipeline b{color:#5eead4;font-size:10px}.assessment-pipeline strong{font-size:11px}.assessment-pipeline small{color:#8ba9b8;font-size:10px}.model-notice{margin:0 0 10px;padding:8px;border-left:3px solid #fbbf24;background:#292820}.auto-panel{margin:0 0 12px;padding:12px;border:1px solid #315669;border-radius:7px;background:#0d2534}.auto-panel h2{font-size:15px}.auto-controls{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:10px 0}.auto-controls label{display:grid;gap:4px;color:#b5ccdb;font-size:10px}.auto-controls select,.auto-controls button{min-width:0;padding:7px;border:1px solid #315669;border-radius:5px;background:#102f40;color:#eaf4ff;font-size:11px}.auto-controls button{cursor:pointer}.auto-controls button:disabled{opacity:.5}.analysis-error{margin:7px 0;padding:8px;background:#4c2525;color:#fecaca}.analysis-result,.qwen-result{display:grid;gap:7px;margin-top:10px;padding:10px;border:1px solid #276778;border-radius:5px;background:#092031}.analysis-result strong{color:#5eead4;font-size:16px}.analysis-result span,.qwen-result small{color:#96b5c3;font-size:10px}.result-images{display:grid;grid-template-columns:1fr 1fr;gap:6px}.result-images img{width:100%;max-height:260px;object-fit:contain;background:#050d16}.qwen-result strong{font-size:11px;color:#5eead4}
.image-pair {display:grid;grid-template-columns:1fr 1fr;gap:9px}.image-slot {position:relative;display:grid;place-items:center;min-width:0;min-height:230px;overflow:hidden;border:1px dashed #376076;border-radius:6px;background:#050d16;cursor:pointer}.image-slot b {position:absolute;top:7px;left:8px;z-index:1;padding:4px;background:#081521d9;font-size:11px}.image-slot img {width:100%;height:100%;max-height:350px;object-fit:contain}.image-slot span {color:#90a9bb;font-size:11px}.image-slot input {position:absolute;inset:0;opacity:0;cursor:pointer}
.source-note {margin:9px 0 12px}.damage-panel,.suggestions {margin-bottom:10px;padding:12px;border:1px solid #29465a;border-radius:7px;background:#0d2230}
.impact-list {display:flex;flex-wrap:wrap;gap:10px;margin:8px 0}.impact-list label {color:#dcebf4;font-size:11px}.impact-list input {margin-right:5px;accent-color:#2dd4bf}
.notes {display:grid;gap:5px;color:#b5ccdb;font-size:11px}.notes textarea {padding:7px;border:1px solid #315669;border-radius:5px;background:#081521;color:#eaf4ff;font:inherit}
.suggestions article {margin-top:8px;padding:9px;border:1px solid #2d5662;border-radius:5px;background:#102f39}.suggestions article strong {font-size:12px}.suggestions article p {margin:5px 0}.suggestions article small {color:#8ba9b8;font-size:10px}
.assessment-dock {height:100%;overflow:auto;padding:14px;background:#081521}.assessment-dock h2 {font-size:16px}.assessment-dock dl {display:grid;grid-template-columns:auto 1fr;gap:8px;padding:10px;border:1px solid #29465a;font-size:11px}.assessment-dock dt {color:#8ba9b8}.assessment-dock dd {margin:0;text-align:right}.assessment-dock p {padding:9px;border-left:3px solid #fbbf24;background:#2c2a22}
@media(max-width:700px){.image-pair,.assessment-pipeline{grid-template-columns:1fr}}
</style>
