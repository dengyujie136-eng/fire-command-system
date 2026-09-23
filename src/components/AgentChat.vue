<template>
  <section class="agent-chat" aria-label="智能体对话">
    <header><div><strong>智能应急助手</strong><small>{{ pageLabel }} · {{ incident.eventName }}</small></div><button type="button" @click="clear">清空</button></header>
    <div v-if="trackedRunId" class="task-progress"><strong>任务 {{ trackedRunId }}</strong><span>{{ incident.workflow?.status || '提交中' }} · {{ stageLabel(incident.currentStage) }}</span><small v-for="step in activeStages" :key="step.stage">{{ stageLabel(step.stage) }} · {{ step.status }} · {{ step.message }}<em v-if="step.result_id"> · {{ step.result_id }}</em></small></div>
    <SimulationOutput />
    <div ref="messagesEl" class="messages" aria-live="polite">
      <article v-for="item in messages" :key="item.id" :class="item.role"><small>{{ item.role==='user'?'你':'智能体' }}</small><p>{{ item.text }}</p><span v-if="item.source">{{ item.source }}</span></article>
      <p v-if="busy" class="pending">正在分析当前事件…</p>
    </div>
    <details class="image-import"><summary>手动导入 GeoTIFF 影像</summary><div class="import-fields"><select v-model="importPhase"><option value="primary">灾中核验</option><option value="comparison_pre">灾前</option><option value="comparison_post">灾后</option></select><input v-model="importScene" placeholder="场景 ID"><input v-model="importDate" type="datetime-local"><input v-model="importBands" placeholder="波段，如 B04,B08,B12"><input type="file" accept=".tif,.tiff,image/tiff" @change="selectImportFile"><button type="button" :disabled="importing||!importFile" @click="uploadImagery">{{ importing?'正在导入…':'上传并登记' }}</button></div></details>
    <div class="quick-links"><button v-for="item in links" :key="item.path" type="button" @click="router.push(item.path)">{{ item.label }}</button></div>
    <form @submit.prevent="send"><textarea v-model="draft" rows="2" :disabled="busy" placeholder="询问火情、证据、推演或规划…" @keydown.enter.exact.prevent="send"></textarea><button type="submit" :disabled="busy||!draft.trim()">发送</button></form>
  </section>
</template>
<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useIncidentContextStore } from '../stores/incidentContextStore'
import { useAssistantTaskStore } from '../stores/assistantTaskStore'
import SimulationOutput from './SimulationOutput.vue'
type Message={id:string;role:'user'|'assistant';text:string;source?:string}
const route=useRoute()
const router=useRouter()
const incident=useIncidentContextStore()
const task=useAssistantTaskStore()
const links=[{path:'/realtime-monitor',label:'监测'},{path:'/visual-verification',label:'核验'},{path:'/command-center',label:'推演'},{path:'/planning',label:'规划'},{path:'/disaster-assess',label:'评估'}]
const pageLabel=computed(()=>links.find(x=>x.path===route.path)?.label||'工作台')
const messages=ref<Message[]>([{id:'welcome',role:'assistant',text:'可以说“查看实时火点”“聚焦加州大火”“推演火情，每两小时更新气象”或“规划救援路线”，我会打开对应页面。'}])
const draft=ref('')
const busy=ref(false)
const messagesEl=ref<HTMLElement|null>(null)
const trackedRunId=ref('')
const importPhase=ref('primary'),importScene=ref(''),importDate=ref(''),importBands=ref('B02,B03,B04,B08,B12'),importFile=ref<File|null>(null),importing=ref(false)
const imageryNotified=new Set<string>()
function selectImportFile(event:Event){importFile.value=(event.target as HTMLInputElement).files?.[0]||null}
async function uploadImagery(){
 if(!importFile.value||!importScene.value.trim()||!importDate.value){append('请填写场景 ID、拍摄时间、实际波段并选择 GeoTIFF。','影像导入');return}
 importing.value=true
 try{
  const params=new URLSearchParams({event_id:incident.eventId,phase:importPhase.value,scene_id:importScene.value.trim(),acquired_at:new Date(importDate.value).toISOString(),bands:importBands.value})
  const response=await fetch('/api/data-agent/imagery/upload?'+params,{method:'POST',headers:{'Content-Type':'image/tiff'},body:importFile.value})
  const payload=await response.json()
  if(!response.ok)throw new Error(typeof payload.detail==='string'?payload.detail:JSON.stringify(payload.detail||payload))
  append('影像已登记：'+payload.data.asset_id+'；波段 '+payload.data.bands.join('、')+'。'+(payload.data.analysis_ready?'文件包含波段标识。':'波段名称由用户声明，分析前请核实文件元数据。'),'数据智能体 / 手动导入')
  await incident.refreshWorkflow()
 }catch(error:any){append('影像导入失败：'+(error?.message||'请求失败'),'数据智能体 / 手动导入')}
 finally{importing.value=false}
}
const activeStages=computed(()=>trackedRunId.value===incident.workflowRunId ? incident.stages.filter(x=>x.status!=='PENDING') : [])
const labels:Record<string,string>={data_preparation:'数据智能体',fire_verification:'火点核验',situation:'态势评估',spread:'火势推演',spatial_risk:'空间风险',scenario:'应急场景',resource_dispatch:'资源调度',route_planning:'路径规划',commander:'指挥决策'}
function stageLabel(stage:string){return labels[stage]||stage}
function append(text:string,source='真实接口结果'){messages.value.push({id:crypto.randomUUID(),role:'assistant',text,source})}
watch(()=>[incident.workflow?.current_stage,incident.workflow?.status] as const,async([stage,status],[oldStage,oldStatus])=>{
 if(!trackedRunId.value||trackedRunId.value!==incident.workflowRunId||!stage)return
 const step=incident.stages.find(x=>x.stage===stage)
 if(stage!==oldStage||status!==oldStatus) append(stageLabel(stage)+'：'+(step?.message||status)+(step?.result_id?' · '+step.result_id:''),'工作流 '+trackedRunId.value)
 if(status==='WAITING_FOR_INPUT'&&stage==='fire_verification') await router.push({path:'/visual-verification',query:{mode:'qwen'}})
 else if(stage==='spread'&&stage!==oldStage) await router.push('/command-center')
 else if(stage==='scenario'&&status==='WAITING_FOR_INPUT') await router.push('/planning')
 else if((stage==='route_planning'||stage==='resource_dispatch')&&stage!==oldStage) await router.push('/planning')
 if(status==='COMPLETED'||status==='FAILED'){append(status==='COMPLETED'?'工作流已完成，结果来自各阶段的运行记录。':'工作流失败：'+(incident.workflow?.error||step?.error||'请查看阶段错误'),'工作流 '+trackedRunId.value);trackedRunId.value=''}
})
function clear(){messages.value=[{id:crypto.randomUUID(),role:'assistant',text:'对话已清空。'}]}
watch(()=>messages.value.length,async()=>{await nextTick();if(messagesEl.value)messagesEl.value.scrollTop=messagesEl.value.scrollHeight})
watch(()=>task.status,(status)=>{if(status==='completed')append('火势推演已完成，运行 ID：'+(task.resultRunId||'请在推演页查看。'),'模型结果');if(status==='failed'||status==='blocked')append(task.message,'任务状态')})
async function acquireImagery(eventId:string,phase:string){
 const response=await fetch('/api/data-agent/imagery/acquire',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({event_id:eventId,phase})})
 const payload=await response.json()
 if(!response.ok)throw new Error(typeof payload.detail==='string'?payload.detail:'影像检索失败 '+response.status)
 const data=payload.data||payload
 append('影像任务 '+String(data.task_id||'')+'：'+String(data.status||'已提交')+'。'+String(data.message||'')+(data.download_url?' 下载或检索入口：'+data.download_url:''),'数据智能体 / 影像目录')
 if(data.task_id&&['searching','downloading'].includes(data.status))void pollImagery(String(data.task_id))
 if(data.status==='reused')window.dispatchEvent(new CustomEvent('fire:imagery-ready',{detail:data}))
}
async function pollImagery(taskId:string){
 await new Promise(resolve=>setTimeout(resolve,3000))
 try{
  const response=await fetch('/api/data-agent/imagery/tasks/'+encodeURIComponent(taskId))
  if(!response.ok)throw new Error('任务查询返回 '+response.status)
  const payload=await response.json(),data=payload.data||payload
  if(['searching','downloading'].includes(data.status)){
   if(Number(data.elapsed_seconds)>=60&&!imageryNotified.has(taskId)){imageryNotified.add(taskId);append(data.message+' 场景或官方入口：'+data.download_url+'；手动导入目录 '+data.manual_import_folder,'数据智能体 / 超时反馈')}
   void pollImagery(taskId)
  }else{
   append('影像任务 '+taskId+'：'+data.status+'。'+data.message+'。已有波段：'+(data.available_bands||[]).join('、')+'；缺少：'+(data.missing_bands||[]).join('、')+'。'+(data.download_url?' 来源：'+data.download_url:''),'数据智能体 / 最终结果')
   if(data.status==='completed'||data.status==='reused')window.dispatchEvent(new CustomEvent('fire:imagery-ready',{detail:data}))
  }
 }catch(error:any){append('影像任务状态查询失败：'+(error?.message||'请求失败'),'数据智能体 / 异常')}
}
async function send(){
 const text=draft.value.trim();if(!text||busy.value)return
 draft.value='';messages.value.push({id:crypto.randomUUID(),role:'user',text});busy.value=true
 try{
   const response=await fetch('/api/assistant/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
     message:text,page:route.path,
     context:{event_id:incident.eventId,event_name:incident.eventName,mode:incident.mode,workflow_status:incident.workflow?.status||'尚未运行',current_stage:incident.currentStage,confirmed:!!incident.confirmationId,spread_run_id:incident.spreadRunId,route_plan_id:incident.routePlanId,resource_plan_id:incident.resourcePlanId}
   })})
   if(!response.ok)throw new Error('对话服务返回 '+response.status)
   const result=await response.json()
   const data=result.data||result
   messages.value.push({id:crypto.randomUUID(),role:'assistant',text:String(data.message||'服务没有返回内容'),source:'本地页面操作 / 当前状态'})
   if(data.action?.type==='start_workflow'){
     const eventId=String(data.action.event_id||incident.eventId)
     if(eventId!==incident.eventId) await incident.selectEvent(eventId)
     await incident.startWorkflow(Number(data.action.horizon_minutes)||240)
     trackedRunId.value=incident.workflowRunId||''
     if(data.action.acquire_imagery) await acquireImagery(eventId,'primary')
     append('已创建工作流 '+trackedRunId.value+'。当前状态 '+(incident.workflow?.status||'RUNNING')+'；正在读取真实阶段结果。','工作流接口')
   } else if(data.action?.type==='acquire_imagery'){
     await acquireImagery(String(data.action.event_id||incident.eventId),String(data.action.phase||'primary'))
   } else if(data.action?.type==='acquire_assessment_imagery'){
     const eventId=String(data.action.event_id||incident.eventId)
     await Promise.all([acquireImagery(eventId,'comparison_pre'),acquireImagery(eventId,'comparison_post')])
   } else if(data.action?.type==='run_spread' && Number.isInteger(Number(data.action.horizon_minutes))) {
     const hours=Number(data.action.horizon_minutes)/60
     task.queue(hours,incident.spreadRunId,true,Object.fromEntries(['wind_speed_m_s','wind_direction_deg','temperature_c','humidity_percent'].filter(key=>data.action[key]!==undefined).map(key=>[key,Number(data.action[key])])))
   }
   if(data.navigate_to&&links.some(x=>x.path===data.navigate_to))await router.push({path:data.navigate_to,query:data.navigate_query||{}})
 }catch(cause:any){messages.value.push({id:crypto.randomUUID(),role:'assistant',text:'对话服务暂不可用：'+(cause?.message||'请求失败')})}
 finally{busy.value=false}
}
</script>
<style scoped>
.agent-chat {height:100%;min-height:0;display:flex;flex-direction:column;background:#081521;color:#e8f2f7}
header {display:flex;align-items:center;justify-content:space-between;padding:11px;border-bottom:1px solid #29404d;background:#0d2331}
header strong,header small {display:block}header strong {font-size:14px}header small {margin-top:4px;color:#91aabb;font-size:10px}
header button {padding:5px 8px;border:1px solid #335365;border-radius:5px;background:#123244;color:#c8e5ed;font-size:10px;cursor:pointer}
.task-progress{display:grid;gap:4px;max-height:125px;overflow:auto;padding:8px 11px;border-bottom:1px solid #29404d;background:#102b37;font-size:10px}.task-progress span{color:#5eead4}.task-progress small{color:#b8cbd4}.task-progress em{font-style:normal;color:#77d4bd}
.messages {flex:1;min-height:0;overflow:auto;display:flex;flex-direction:column;gap:9px;padding:11px}
article {max-width:96%;padding:9px;border:1px solid #2c4757;border-radius:7px;background:#102636}
article.user {align-self:flex-end;background:#155464;border-color:#238993}
article small {color:#98b5c7;font-size:10px}article p {margin:4px 0;color:#e9f4f9;font-size:12px;line-height:1.5;white-space:pre-wrap}article span {display:block;color:#65d6b4;font-size:10px}
.pending {color:#98b5c7;font-size:11px}
.image-import{border-top:1px solid #29404d;padding:6px 9px;font-size:10px}.image-import summary{cursor:pointer;color:#9ed9d8}.import-fields{display:grid;grid-template-columns:1fr 1fr;gap:5px;margin-top:7px}.import-fields input,.import-fields select,.import-fields button{min-width:0;padding:5px;border:1px solid #31566a;border-radius:4px;background:#102c39;color:#eaf5fa;font-size:10px}.import-fields input[type=file]{grid-column:span 2}.import-fields button{cursor:pointer}.import-fields button:disabled{opacity:.5}
.quick-links {display:flex;gap:4px;flex-wrap:wrap;padding:7px 9px;border-top:1px solid #29404d}
.quick-links button {padding:4px 6px;border:1px solid #284d5c;border-radius:4px;background:#102c39;color:#a9cbd6;font-size:10px;cursor:pointer}
form {display:grid;grid-template-columns:1fr auto;gap:6px;padding:9px;border-top:1px solid #29404d}
textarea {min-width:0;resize:none;padding:8px;border:1px solid #335365;border-radius:5px;background:#0d1e2b;color:#eef8fa;font:inherit;font-size:11px}
form button {align-self:end;min-height:32px;padding:0 9px;border:1px solid #2dd4bf;border-radius:5px;background:#0f766e;color:white;font-size:11px;cursor:pointer}
form button:disabled {opacity:.5}
</style>
