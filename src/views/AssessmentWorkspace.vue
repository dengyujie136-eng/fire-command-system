<template>
  <div class="assessment-workspace">
    <main class="assessment-page">
      <header><span>POST FIRE / IMAGE REVIEW</span><h1>灾前灾后影像对照</h1><p>选择同一地点、相近范围的影像，记录可见损失并生成待现场核查的重建建议。</p></header>
      <div class="assessment-pipeline" aria-label="灾情评估步骤">
        <div><b>01</b><strong>灾前灾后影像</strong><small>{{ beforeDisplayUrl && afterDisplayUrl ? '已选择两期影像' : '等待两期影像' }}</small></div>
        <div><b>02</b><strong>受灾区域与千问分析</strong><small>{{ analysisResult ? '已完成变化区域提取' : '点击按钮后执行' }}</small></div>
        <div><b>03</b><strong>灾后评估与重建建议</strong><small>{{ qwenAssessment ? '已生成待核查建议' : '等待千问视觉评估' }}</small></div>
      </div>
      <p class="model-notice">自动分析使用登记的多波段 GeoTIFF；若缺少影像或模型报错，仍可在下方记录人工判读，不会生成虚构的面积或模型结论。</p>
      <section class="auto-panel"><h2>灾前灾后影像与千问评估</h2><p>可选择数据库中的灾前、灾后影像，也可以上传 GeoTIFF 登记到当前事件。五波段影像执行空间变化提取；RGB 影像执行千问视觉对比，并明确标注无法从 RGB 直接计算面积。</p><div class="auto-controls"><label>灾前产品<select v-model="beforeAsset"><option value="">请选择</option><option v-for="item in beforeProducts" :key="item.asset_id" :value="item.asset_id">{{ item.scene_id || item.satellite }} · {{ item.acquired_at }} · {{ item.phase }} · {{ item.source_type }}</option></select></label><label>灾后产品<select v-model="afterAsset"><option value="">请选择</option><option v-for="item in afterProducts" :key="item.asset_id" :value="item.asset_id">{{ item.scene_id || item.satellite }} · {{ item.acquired_at }} · {{ item.phase }} · {{ item.source_type }}</option></select></label><button type="button" :disabled="analysisBusy||!beforeAsset||!afterAsset" @click="runAssessment">{{ analysisBusy?'分析中…':'执行变化检测与千问评估' }}</button><button type="button" @click="loadCatalog">刷新影像目录</button></div><div class="upload-grid"><label>上传灾前 GeoTIFF<input type="file" accept=".tif,.tiff,image/tiff" @change="pickUpload($event,'before')"><small>{{ beforeFile?.name || '选择文件后点击上传登记' }}</small></label><label>灾前拍摄时间<input v-model="beforeAcquiredAt" type="datetime-local"></label><label>上传灾后 GeoTIFF<input type="file" accept=".tif,.tiff,image/tiff" @change="pickUpload($event,'after')"><small>{{ afterFile?.name || '选择文件后点击上传登记' }}</small></label><label>灾后拍摄时间<input v-model="afterAcquiredAt" type="datetime-local"></label><label>影像波段<input v-model="uploadBands" placeholder="B02,B03,B04,B08,B12"></label><button type="button" :disabled="uploadBusy||!beforeFile||!afterFile" @click="uploadSelectedImagery">{{ uploadBusy?'上传中…':'上传并登记两期影像' }}</button></div><p v-if="uploadError" class="analysis-error">{{ uploadError }}</p><p v-if="catalogError||analysisError" class="analysis-error">{{ catalogError||analysisError }}</p><p v-if="!beforeProducts.length||!afterProducts.length">数据库当前没有符合条件的灾前或灾后影像。可以使用上方上传入口登记五波段 GeoTIFF，登记成功后从下拉框选择。</p><div v-if="analysisResult" class="analysis-result"><strong v-if="analysisResult.mode==='rgb_qwen'">RGB 影像已提交千问视觉对比</strong><strong v-else>提取受灾区域 {{ Number(analysisResult.area_hectares).toFixed(2) }} 公顷</strong><span>{{ analysisResult.method }} · {{ analysisResult.analysis_id }} · {{ analysisResult.is_simulated?'模拟数据':'真实影像计算' }}</span><p v-if="analysisResult.mode==='rgb_qwen'">当前数据库影像为 RGB 产品，千问可以描述可见受灾区域，但不会虚构精确面积和坐标。需要定量面积请上传或选择五波段产品。</p><p v-else>变化像元 {{ analysisResult.changed_pixel_count }} / 有效像元 {{ analysisResult.valid_pixel_count }}；空间参考 {{ analysisResult.source_crs }}</p><p v-for="warning in analysisResult.warnings||[]" :key="warning">{{ warning }}</p><div v-if="analysisResult.mode!=='rgb_qwen'" class="result-actions"><a :href="artifactUrl('area_geojson')" target="_blank" rel="noreferrer">查看受灾区域 GeoJSON</a><a :href="artifactUrl('changed_area_mask')" target="_blank" rel="noreferrer">查看变化掩膜</a></div><div class="result-images"><template v-if="analysisResult.mode==='rgb_qwen'"><img :src="catalogPreviewUrl(analysisResult.before_asset_id)" alt="数据库灾前影像"><img :src="catalogPreviewUrl(analysisResult.after_asset_id)" alt="数据库灾后影像"></template><template v-else><img :src="artifactUrl('before_rgb')" alt="真实灾前 RGB 影像"><img :src="artifactUrl('after_rgb')" alt="真实灾后 RGB 影像"><img :src="artifactUrl('change_index')" alt="灾前灾后变化指数"></template></div></div><div v-if="qwenAssessment" class="qwen-result"><h3>千问灾后评估 · {{ qwenModel }}</h3><p>{{ qwenAssessment.summary }}</p><strong v-if="qwenAssessment.affected_region?.length">受灾区域描述</strong><p v-for="item in qwenAssessment.affected_region||[]" :key="item">{{ item }}</p><strong>受灾特征</strong><p v-for="item in qwenAssessment.affected_features" :key="item">{{ item }}</p><strong>重建建议</strong><p v-for="item in qwenAssessment.reconstruction_advice" :key="item">{{ item }}</p><small v-for="item in qwenAssessment.limitations" :key="item">{{ item }}</small></div></section>
      <p v-if="selectedOverlap !== null" class="overlap-note" :class="{ invalid: selectedOverlap < 0.8 }">两期影像地理范围重合度：{{ (selectedOverlap * 100).toFixed(1) }}%（要求至少 80%，按较小影像覆盖范围计算）</p>
      <p v-else-if="beforeAsset && afterAsset" class="overlap-note invalid">无法读取两期影像地理范围，不能进行变化对比。</p>
      <section class="image-pair">
        <label class="image-slot"><b>灾前影像</b><img v-if="beforeDisplayUrl" :src="beforeDisplayUrl" alt="灾前影像"><span v-else>点击选择灾前影像</span><input type="file" accept="image/*" @change="pick($event,'before')"></label>
        <label class="image-slot"><b>灾后影像</b><img v-if="afterDisplayUrl" :src="afterDisplayUrl" alt="灾后影像" @load="captureAfterImageLayout"><svg v-if="vectorPolygons.length && !afterUrl" class="vector-overlay" :style="vectorOverlayStyle" viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="大致受灾区域"><polygon v-for="(points,index) in vectorPolygons" :key="index" :points="points" /></svg><span v-if="vectorPolygons.length && !afterUrl" class="vector-legend">大致受灾区域</span><span v-else-if="!afterDisplayUrl">点击选择灾后影像</span><input type="file" accept="image/*" @change="pick($event,'after')"></label>
      </section>
      <p class="source-note">影像仅在当前浏览器中预览。面积、植被损失等空间指标需要配准影像和分析服务；当前不以目测结果冒充计算值。</p>
      <section class="damage-panel"><div><span>IMAGE INTERPRETATION</span><h2>可见影响记录</h2></div><div class="impact-list"><label v-for="item in options" :key="item.id"><input v-model="impacts" type="checkbox" :value="item.id">{{ item.label }}</label></div><label class="notes">判读依据和位置<textarea v-model="notes" rows="3" placeholder="填写影像日期、范围、可见变化和不确定性"></textarea></label></section>
      <section class="suggestions"><div><span>RECOVERY / ACTIONS</span><h2>重建建议</h2></div><p v-if="!impacts.length">选择影像中可见的影响后显示对应的核查建议。</p><article v-for="item in selectedOptions" :key="item.id"><strong>{{ item.title }}</strong><p>{{ item.suggestion }}</p><small>依据：人工标记「{{ item.label }}」；实施前需现场核查。</small></article></section>
      <Teleport defer to="#business-panel"><aside class="assessment-dock"><h2>评估依据</h2><dl><dt>当前事件</dt><dd>{{ incident.eventName }}</dd><dt>灾前影像</dt><dd>{{ beforeDisplayUrl?'已选择':'未选择' }}</dd><dt>灾后影像</dt><dd>{{ afterDisplayUrl?'已选择':'未选择' }}</dd><dt>影响类型</dt><dd>{{ impacts.length }} 项</dd><dt>判读说明</dt><dd>{{ notes.trim()?'已填写':'未填写' }}</dd></dl><p>建议是人工影像判读的待核实清单，尚未产生自动变化检测或损失面积结果。</p></aside></Teleport>
      <section v-if="vectorUrl" class="vector-result"><div><span>VECTOR OUTPUT</span><h2>受灾区域矢量</h2><p>基于灾前、灾后全景影像的像元变化生成，仅用于定性区域划分。</p></div><a :href="vectorUrl" download="affected-zones.geojson">下载 GeoJSON</a></section>
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
const analysisResult=ref<any>(null),qwenAssessment=ref<any>(null),qwenModel=ref(''),vectorUrl=ref(''),vectorGeojson=ref<any>(null)
function setVectorGeojson(value:any){if(vectorUrl.value)URL.revokeObjectURL(vectorUrl.value);vectorGeojson.value=value||null;vectorUrl.value=value?URL.createObjectURL(new Blob([JSON.stringify(value)],{type:'application/geo+json'})):''}
function preferOverview(items:any[]){const overviews=items.filter(item=>/overview/i.test(String(item.satellite||item.scene_id||'')));return overviews.length?overviews:items}
const beforeProducts=computed(()=>preferOverview(catalog.value.filter(x=>['pre','comparison_pre'].includes(x.phase)&&x.available_locally&&['available','usable'].includes(x.quality_status))))
const afterProducts=computed(()=>preferOverview(catalog.value.filter(x=>['post','comparison_post'].includes(x.phase)&&x.available_locally&&['available','usable'].includes(x.quality_status))))
function overviewFirst(items:any[]){
 return [...items].sort((a,b)=>{
  const aIsOverview=/overview/i.test(String(a.satellite||a.scene_id||''))
  const bIsOverview=/overview/i.test(String(b.satellite||b.scene_id||''))
  return Number(!aIsOverview)-Number(!bIsOverview)
 })
}
function footprintBounds(footprint:any):[number,number,number,number]|null{
 const points:number[][]=[]
 const collect=(value:any)=>{if(!Array.isArray(value))return;if(value.length>=2&&typeof value[0]==='number'&&typeof value[1]==='number'){points.push([value[0],value[1]]);return}for(const item of value)collect(item)}
 collect(footprint?.coordinates)
 if(!points.length)return null
 const xs=points.map(point=>point[0]),ys=points.map(point=>point[1])
 return [Math.min(...xs),Math.min(...ys),Math.max(...xs),Math.max(...ys)]
}
function footprintOverlapRatio(before:any,after:any):number|null{
 const first=footprintBounds(before?.footprint),second=footprintBounds(after?.footprint)
 if(!first||!second)return null
 const intersection=Math.max(0,Math.min(first[2],second[2])-Math.max(first[0],second[0]))*Math.max(0,Math.min(first[3],second[3])-Math.max(first[1],second[1]))
 const firstArea=Math.max(0,first[2]-first[0])*Math.max(0,first[3]-first[1]),secondArea=Math.max(0,second[2]-second[0])*Math.max(0,second[3]-second[1])
 const smaller=Math.min(firstArea,secondArea)
 return smaller>0?intersection/smaller:null
}
const selectedOverlap=computed(()=>footprintOverlapRatio(catalog.value.find(x=>x.asset_id===beforeAsset.value),catalog.value.find(x=>x.asset_id===afterAsset.value)))
function ringArea(ring:number[][]){
 let area=0
 for(let index=0;index<ring.length;index++){
  const current=ring[index],next=ring[(index+1)%ring.length]
  area+=(current?.[0]||0)*(next?.[1]||0)-(next?.[0]||0)*(current?.[1]||0)
 }
 return Math.abs(area/2)
}
const vectorPolygons=computed(()=>{
 const asset=catalog.value.find(x=>x.asset_id===afterAsset.value)
 const bounds=footprintBounds(asset?.footprint)
 if(!bounds||!vectorGeojson.value)return []
 const [minX,minY,maxX,maxY]=bounds,width=maxX-minX,height=maxY-minY
 if(width<=0||height<=0)return []
 const rings:{ring:number[][];area:number}[]=[]
 const addGeometry=(geometry:any)=>{
  if(geometry?.type==='Polygon'&&Array.isArray(geometry.coordinates?.[0]))rings.push({ring:geometry.coordinates[0],area:ringArea(geometry.coordinates[0])})
  if(geometry?.type==='MultiPolygon')for(const polygon of geometry.coordinates||[])if(Array.isArray(polygon?.[0]))rings.push({ring:polygon[0],area:ringArea(polygon[0])})
 }
 if(vectorGeojson.value.type==='FeatureCollection')for(const feature of vectorGeojson.value.features||[])addGeometry(feature?.geometry)
 else if(vectorGeojson.value.type==='Feature')addGeometry(vectorGeojson.value.geometry)
 else addGeometry(vectorGeojson.value)
 return rings.sort((a,b)=>b.area-a.area).slice(0,400).map(({ring})=>ring.map(point=>{
  const x=Math.max(0,Math.min(100,((Number(point[0])-minX)/width)*100))
  const y=Math.max(0,Math.min(100,((maxY-Number(point[1]))/height)*100))
  return `${x.toFixed(3)},${y.toFixed(3)}`
 }).join(' ')).filter(Boolean)
})
function artifactUrl(name:string){return analysisResult.value?'/api/visual-verification/analyses/'+encodeURIComponent(analysisResult.value.analysis_id)+'/artifacts/'+name:''}
function catalogPreviewUrl(assetId:string){return '/api/visual-verification/imagery-catalog/'+encodeURIComponent(assetId)+'/preview'}
async function loadCatalog(){
 catalogError.value=''
 try{
  const response=await fetch('/api/data-agent/imagery/catalog/'+encodeURIComponent(incident.eventId))
  const payload=await response.json()
  if(!response.ok)throw new Error(typeof payload.detail==='string'?payload.detail:'影像目录读取失败')
  catalog.value=payload.data||[]
  beforeAsset.value=overviewFirst(beforeProducts.value)[0]?.asset_id||''
  afterAsset.value=overviewFirst(afterProducts.value)[0]?.asset_id||''
 }catch(error:any){catalogError.value=error?.message||'影像目录读取失败'}
}
const beforeUrl=ref(''),afterUrl=ref('')
const beforeDisplayUrl=computed(()=>beforeUrl.value || (beforeAsset.value ? catalogPreviewUrl(beforeAsset.value) : ''))
const afterDisplayUrl=computed(()=>afterUrl.value || (afterAsset.value ? catalogPreviewUrl(afterAsset.value) : ''))
const afterImageLayout=ref({left:0,top:0,width:100,height:100})
function captureAfterImageLayout(event:Event){
 const image=event.currentTarget as HTMLImageElement,slot=image.parentElement
 if(!slot||!image.naturalWidth||!image.naturalHeight||!slot.clientWidth||!slot.clientHeight)return
 const scale=Math.min(slot.clientWidth/image.naturalWidth,slot.clientHeight/image.naturalHeight)
 const width=image.naturalWidth*scale,height=image.naturalHeight*scale
 afterImageLayout.value={left:((slot.clientWidth-width)/2/slot.clientWidth)*100,top:((slot.clientHeight-height)/2/slot.clientHeight)*100,width:(width/slot.clientWidth)*100,height:(height/slot.clientHeight)*100}
}
const vectorOverlayStyle=computed(()=>({left:`${afterImageLayout.value.left}%`,top:`${afterImageLayout.value.top}%`,width:`${afterImageLayout.value.width}%`,height:`${afterImageLayout.value.height}%`}))
const beforeFile=ref<File|null>(null),afterFile=ref<File|null>(null)
const beforeAcquiredAt=ref(''),afterAcquiredAt=ref('')
const uploadBands=ref('B02,B03,B04,B08,B12')
const uploadBusy=ref(false),uploadError=ref('')
const impacts=ref<string[]>([]),notes=ref('')
const options=[
 {id:'slope',label:'坡面裸露或侵蚀迹象',title:'核查坡面稳定性',suggestion:'核查坡度、裸土和下游汇水路径，再决定覆盖与截排水措施。'},
 {id:'road',label:'道路与桥涵受损',title:'恢复关键通行路线',suggestion:'现场检查受损路段与桥涵，优先恢复救援和巡护通行。'},
 {id:'vegetation',label:'植被退化',title:'制定分区植被恢复计划',suggestion:'结合土壤和自然更新情况，划定保育、补植与持续监测区域。'},
 {id:'facility',label:'建筑或设施受损',title:'开展设施安全复核',suggestion:'逐项核查结构、供水和供电，再确定修复优先级。'}
]
const selectedOptions=computed(()=>options.filter(x=>impacts.value.includes(x.id)))
async function runAssessment(){
 analysisBusy.value=true;analysisError.value='';analysisResult.value=null;qwenAssessment.value=null;setVectorGeojson(null)
 try{
  if(!incident.visualCaseId)await incident.loadLatestWorkflow()
  if(!incident.visualCaseId)throw new Error('缺少真实候选火点案例，请先启动监测与核验工作流。')
  const before=catalog.value.find(x=>x.asset_id===beforeAsset.value),after=catalog.value.find(x=>x.asset_id===afterAsset.value)
  if(!before||!after)throw new Error('请先获取并选择灾前、灾后的多波段产品。')
  const overlap=footprintOverlapRatio(before,after)
  if(overlap===null)throw new Error('两期影像缺少可用地理范围，无法进行变化对比。')
  if(overlap<0.8)throw new Error(`两期影像地理范围重合度仅 ${(overlap*100).toFixed(1)}%，低于 80%；请重新选择同一区域影像。`)
  const requiredBands=['B02','B03','B04','B08','B12']
  const canRunRaster=requiredBands.every(b=>[...(before.bands||[]),...(after.bands||[])].map((item:string)=>item.toUpperCase()).includes(b))
  if(!canRunRaster){
   const visualResponse=await fetch('/api/data-agent/imagery/visual-assess',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({event_id:incident.eventId,before_asset_id:before.asset_id,after_asset_id:after.asset_id})})
   const visualPayload=await visualResponse.json()
   if(!visualResponse.ok)throw new Error(typeof visualPayload.detail==='string'?visualPayload.detail:visualPayload.detail?.message||'千问影像对比失败 '+visualResponse.status)
   analysisResult.value={mode:'rgb_qwen',analysis_id:`qwen-${Date.now()}`,before_asset_id:before.asset_id,after_asset_id:after.asset_id,method:'qwen_rgb_visual_comparison',is_simulated:false,area_hectares:null}
   qwenAssessment.value=visualPayload.data.assessment
   qwenModel.value=visualPayload.data.model
   setVectorGeojson(visualPayload.data.affected_area_geojson)
   return
  }
  const response=await fetch('/api/visual-verification/analyses/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({event_id:incident.eventId,analysis_type:'burned_area',time_range:{start_at:before.acquired_at,end_at:after.acquired_at},asset_ids:[before.asset_id,after.asset_id],visual_case_id:incident.visualCaseId})})
  const payload=await response.json()
  if(!response.ok)throw new Error(typeof payload.detail==='string'?payload.detail:payload.detail?.message||'变化检测失败 '+response.status)
  analysisResult.value=payload
  const vectorResponse=await fetch(artifactUrl('area_geojson'))
  if(vectorResponse.ok)setVectorGeojson(await vectorResponse.json())
  const qwenResponse=await fetch('/api/data-agent/imagery/assess/'+encodeURIComponent(payload.analysis_id),{method:'POST'})
  const qwenPayload=await qwenResponse.json()
  if(!qwenResponse.ok)throw new Error(typeof qwenPayload.detail==='string'?qwenPayload.detail:'千问视觉评估失败 '+qwenResponse.status)
  qwenAssessment.value=qwenPayload.data.assessment
  qwenModel.value=qwenPayload.data.model
  const assessmentState={
   event_id:incident.eventId,
   analysis_id:payload.analysis_id,
   area_hectares:payload.area_hectares,
   method:payload.method,
   qwen_model:qwenPayload.data.model,
   completed_at:new Date().toISOString()
  }
  sessionStorage.setItem('fire-assessment:'+incident.eventId,JSON.stringify(assessmentState))
  window.dispatchEvent(new CustomEvent('fire:assessment-completed',{detail:assessmentState}))
 }catch(error:any){analysisError.value=error?.message||'评估失败'}
 finally{analysisBusy.value=false}
}
function pickUpload(event:Event,kind:'before'|'after'){
 const file=(event.target as HTMLInputElement).files?.[0]
 if(!file)return
 if(kind==='before')beforeFile.value=file
 else afterFile.value=file
 pick(event,kind)
}
function uploadTimestamp(value:string){
 const parsed=value?new Date(value):new Date()
 return Number.isNaN(parsed.getTime())?new Date().toISOString():parsed.toISOString()
}
async function uploadOne(file:File,phase:'comparison_pre'|'comparison_post',acquiredAt:string){
 const sceneId=file.name.replace(/\.[^.]+$/,'').replace(/[^A-Za-z0-9_-]+/g,'_').slice(0,100)||phase
 const params=new URLSearchParams({event_id:incident.eventId,phase,scene_id:sceneId,acquired_at:uploadTimestamp(acquiredAt),bands:uploadBands.value})
 const response=await fetch('/api/data-agent/imagery/upload?'+params.toString(),{method:'POST',headers:{'Content-Type':'image/tiff'},body:file})
 const payload=await response.json()
 if(!response.ok)throw new Error(typeof payload.detail==='string'?payload.detail:payload.detail?.message||'影像上传失败 '+response.status)
 return payload.data
}
async function uploadSelectedImagery(){
 if(!beforeFile.value||!afterFile.value)return
 uploadBusy.value=true;uploadError.value=''
 try{
  const before=await uploadOne(beforeFile.value,'comparison_pre',beforeAcquiredAt.value)
  const after=await uploadOne(afterFile.value,'comparison_post',afterAcquiredAt.value)
  await loadCatalog()
  beforeAsset.value=before.asset_id
  afterAsset.value=after.asset_id
 }catch(error:any){uploadError.value=error?.message||'影像上传失败'}finally{uploadBusy.value=false}
}
async function handleImageryReady(){await loadCatalog();if(route.query.auto_assess==='1'&&beforeAsset.value&&afterAsset.value&&!analysisBusy.value&&!analysisResult.value)await runAssessment()}
onMounted(async()=>{window.addEventListener('fire:imagery-ready',handleImageryReady);try{await incident.loadLatestWorkflow()}catch{}await loadCatalog();if(route.query.auto_assess==='1'&&beforeAsset.value&&afterAsset.value)await runAssessment()})
function pick(event:Event,kind:'before'|'after'){const file=(event.target as HTMLInputElement).files?.[0];if(!file)return;const target=kind==='before'?beforeUrl:afterUrl;if(target.value)URL.revokeObjectURL(target.value);target.value=URL.createObjectURL(file)}
onBeforeUnmount(()=>{window.removeEventListener('fire:imagery-ready',handleImageryReady);if(beforeUrl.value)URL.revokeObjectURL(beforeUrl.value);if(afterUrl.value)URL.revokeObjectURL(afterUrl.value);if(vectorUrl.value)URL.revokeObjectURL(vectorUrl.value)})
</script>
<style scoped>
.assessment-workspace {height:100%;min-height:0;display:flex;flex-direction:column;background:#081521;color:#eaf4ff}
.workspace-tabs {flex:0 0 44px;display:flex;gap:7px;align-items:center;padding:5px 12px;border-bottom:1px solid #244158;background:#0b1d2b}
.workspace-tabs strong {margin-right:auto;font-size:14px}.workspace-tabs button {padding:6px 9px;border:1px solid #2b495e;border-radius:5px;background:#0f2637;color:#a9c0d1;font-size:11px;cursor:pointer}.workspace-tabs button.active {border-color:#2dd4bf;background:#145367;color:white}
.history-view {flex:1;min-height:0}.assessment-page {flex:1;min-height:0;overflow:auto;padding:14px}.assessment-page header {margin-bottom:12px}.assessment-page header span,.damage-panel span,.suggestions span {color:#5eead4;font-size:10px;font-weight:800;letter-spacing:.08em}
h1,h2,p {margin:0}h1 {margin:4px 0;font-size:21px}h2 {margin:3px 0 9px;font-size:16px}p {color:#9eb4c5;font-size:11px;line-height:1.5}
.assessment-pipeline {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:0 0 10px}.assessment-pipeline div {display:grid;gap:4px;min-width:0;padding:9px;border:1px solid #315669;border-radius:6px;background:#102838}.assessment-pipeline b{color:#5eead4;font-size:10px}.assessment-pipeline strong{font-size:11px}.assessment-pipeline small{color:#8ba9b8;font-size:10px}.model-notice{margin:0 0 10px;padding:8px;border-left:3px solid #fbbf24;background:#292820}.auto-panel{margin:0 0 12px;padding:12px;border:1px solid #315669;border-radius:7px;background:#0d2534}.auto-panel h2{font-size:15px}.auto-controls{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:10px 0}.auto-controls label{display:grid;gap:4px;color:#b5ccdb;font-size:10px}.auto-controls select,.auto-controls button{min-width:0;padding:7px;border:1px solid #315669;border-radius:5px;background:#102f40;color:#eaf4ff;font-size:11px}.auto-controls button{cursor:pointer}.auto-controls button:disabled{opacity:.5}.analysis-error{margin:7px 0;padding:8px;background:#4c2525;color:#fecaca}.analysis-result,.qwen-result{display:grid;gap:7px;margin-top:10px;padding:10px;border:1px solid #276778;border-radius:5px;background:#092031}.analysis-result strong{color:#5eead4;font-size:16px}.analysis-result span,.qwen-result small{color:#96b5c3;font-size:10px}.result-images{display:grid;grid-template-columns:1fr 1fr;gap:6px}.result-images img{width:100%;max-height:260px;object-fit:contain;background:#050d16}.qwen-result strong{font-size:11px;color:#5eead4}
.upload-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:10px 0;padding:9px;border:1px dashed #376076;background:#0a1e2b;align-items:start}.upload-grid label{display:grid;gap:4px;min-width:0;color:#b5ccdb;font-size:10px}.upload-grid input{min-width:0;width:100%;box-sizing:border-box;padding:6px;border:1px solid #315669;border-radius:5px;background:#081521;color:#eaf4ff;font-size:10px}.upload-grid small{color:#8ba9b8;line-height:1.2}.upload-grid button{align-self:end;min-height:34px;box-sizing:border-box;padding:7px;border:1px solid #2dd4bf;border-radius:5px;background:#115e59;color:#ecfeff;cursor:pointer}.upload-grid button:disabled{opacity:.5}.result-actions{display:flex;flex-wrap:wrap;gap:8px}.result-actions a{padding:5px 7px;border:1px solid #347286;border-radius:5px;color:#b9f6ed;background:#103b45;font-size:10px;text-decoration:none}
.image-pair {display:grid;grid-template-columns:1fr 1fr;gap:9px}.image-slot {position:relative;display:grid;place-items:center;min-width:0;min-height:230px;overflow:hidden;border:1px dashed #376076;border-radius:6px;background:#050d16;cursor:pointer}.image-slot b {position:absolute;top:7px;left:8px;z-index:3;padding:4px;background:#081521d9;font-size:11px}.image-slot img {width:100%;height:100%;max-height:350px;object-fit:contain}.image-slot span {color:#90a9bb;font-size:11px}.image-slot input {position:absolute;inset:0;z-index:4;opacity:0;cursor:pointer}.vector-overlay {position:absolute;z-index:2;pointer-events:none}.vector-overlay polygon {fill:#ef444459;stroke:#ff4d4f;stroke-width:.65;vector-effect:non-scaling-stroke}.image-slot .vector-legend {position:absolute;right:10px;bottom:10px;z-index:3;padding:5px 8px;border:1px solid #ff7373;border-radius:5px;background:#310d12d9;color:#ffe4e6;font-size:11px;font-weight:700}
.overlap-note {margin:7px 0;padding:7px 9px;border-left:3px solid #2dd4bf;background:#102f40;color:#b9f6ed;font-size:11px}.overlap-note.invalid {border-left-color:#f87171;background:#4c2525;color:#fecaca}
.overlap-note,.source-note,.damage-panel,.suggestions {display:none!important}
.image-pair {grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin:12px 0 0}
.image-slot {aspect-ratio:16 / 10;min-height:0;border:1px solid #29495c;border-radius:10px;background:#06111a;box-shadow:0 8px 24px #00000026}
.image-slot b {top:10px;left:10px;padding:5px 8px;border:1px solid #29495c;border-radius:5px;background:#071723e8;color:#d9f7ff;font-size:11px}
.vector-result {display:flex;align-items:center;justify-content:space-between;gap:14px;margin-top:14px;padding:12px 14px;border:1px solid #235b68;border-radius:9px;background:#0b2734}.vector-result span {color:#5eead4;font-size:10px;font-weight:800;letter-spacing:.08em}.vector-result h2 {margin:4px 0;font-size:15px}.vector-result a {flex:none;padding:7px 11px;border:1px solid #2dd4bf;border-radius:5px;background:#115e59;color:#ecfeff;font-size:11px;text-decoration:none}
.source-note {margin:9px 0 12px}.damage-panel,.suggestions {margin-bottom:10px;padding:12px;border:1px solid #29465a;border-radius:7px;background:#0d2230}
.impact-list {display:flex;flex-wrap:wrap;gap:10px;margin:8px 0}.impact-list label {color:#dcebf4;font-size:11px}.impact-list input {margin-right:5px;accent-color:#2dd4bf}
.notes {display:grid;gap:5px;color:#b5ccdb;font-size:11px}.notes textarea {padding:7px;border:1px solid #315669;border-radius:5px;background:#081521;color:#eaf4ff;font:inherit}
.suggestions article {margin-top:8px;padding:9px;border:1px solid #2d5662;border-radius:5px;background:#102f39}.suggestions article strong {font-size:12px}.suggestions article p {margin:5px 0}.suggestions article small {color:#8ba9b8;font-size:10px}
.assessment-dock {height:100%;overflow:auto;padding:14px;background:#081521}.assessment-dock h2 {font-size:16px}.assessment-dock dl {display:grid;grid-template-columns:auto 1fr;gap:8px;padding:10px;border:1px solid #29465a;font-size:11px}.assessment-dock dt {color:#8ba9b8}.assessment-dock dd {margin:0;text-align:right}.assessment-dock p {padding:9px;border-left:3px solid #fbbf24;background:#2c2a22}
@media(max-width:700px){.image-pair,.assessment-pipeline,.upload-grid{grid-template-columns:1fr}.result-images{grid-template-columns:1fr}}
</style>
