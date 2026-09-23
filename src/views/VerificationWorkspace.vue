<template>
  <div class="verification-workspace">
    <header class="verification-header"><div><span>IMAGE VERIFICATION PIPELINE</span><h1>卫星影像火点核验</h1><p>基础热异常检测 → 候选火点 → 目标识别与千问视觉理解 → 人工确认</p></div><div class="workflow-state">{{ incident.workflowRunId ? '工作流 '+incident.workflowRunId : '等待监测页启动工作流' }}</div></header>
    <nav class="pipeline-tabs" aria-label="核验步骤"><button type="button" :class="{active:mode==='detect'}" @click="setMode('detect')"><b>01</b> 基础算法与候选</button><button type="button" :class="{active:mode==='qwen'}" @click="setMode('qwen')"><b>02</b> 目标识别 · Qwen-VL</button></nav>
    <div class="verification-body"><SatelliteVerification v-if="mode==='detect'" /><VisualVerification v-else :event-id="incident.eventId" @reviewed="reviewedCaseId=$event" /></div>
    <p v-if="confirmError" class="confirm-error">{{ confirmError }}</p>
    <div v-if="mode==='qwen'" class="confirmation-bar"><span>{{ canConfirm ? '已有可信视觉核验记录，请人工确认后继续推演' : '待视觉复核结果；无影像时保持候选状态' }}</span><button type="button" :disabled="busy||!canConfirm||!incident.workflowRunId" @click="confirm('confirm')">确认火点</button><button type="button" :disabled="busy||!incident.workflowRunId" @click="confirm('uncertain')">需要补充影像</button><button type="button" :disabled="busy||!incident.workflowRunId" @click="confirm('reject')">排除候选</button></div>
  </div>
</template>
<script setup lang="ts">
import { computed,onMounted,ref } from 'vue'
import { useRoute,useRouter } from 'vue-router'
import SatelliteVerification from './SatelliteVerification.vue'
import VisualVerification from './VisualVerification.vue'
import { useIncidentContextStore } from '../stores/incidentContextStore'
const route=useRoute(),router=useRouter(),incident=useIncidentContextStore()
const mode=computed(()=>route.query.mode==='qwen'?'qwen':'detect')
const reviewedCaseId=ref(''),busy=ref(false),confirmError=ref('')
const canConfirm=computed(()=>Boolean(incident.confirmationId && incident.visualCaseId && (reviewedCaseId.value===incident.visualCaseId || incident.workflow?.human_confirmation_state==='AI_SUGGESTED')))
function setMode(value:'detect'|'qwen'){void router.replace({path:'/visual-verification',query:value==='qwen'?{mode:'qwen'}:{}})}
async function confirm(action:'confirm'|'uncertain'|'reject'){busy.value=true;confirmError.value='';try{await incident.verify(action)}catch(cause:any){confirmError.value=cause?.message||'火点确认失败'}finally{busy.value=false}}
onMounted(async()=>{try{await incident.loadEvents();await incident.loadLatestWorkflow()}catch{/* show no workflow state */}})
</script>
<style scoped>
.verification-workspace {height:100%;min-height:0;display:flex;flex-direction:column;background:#07111b;color:#eaf4ff}
.verification-header {flex:0 0 auto;display:flex;align-items:center;justify-content:space-between;gap:14px;padding:10px 14px;border-bottom:1px solid #244158;background:#0b1d2b}
.verification-header span {color:#5eead4;font-size:10px;font-weight:800;letter-spacing:.08em}.verification-header h1 {margin:3px 0;font-size:18px}.verification-header p {margin:0;color:#9eb4c5;font-size:11px}.workflow-state {max-width:34%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#8aabba;font-size:10px}
.pipeline-tabs {flex:0 0 40px;display:flex;gap:5px;padding:5px 12px;border-bottom:1px solid #244158}.pipeline-tabs button {padding:0 10px;border:1px solid #2b495e;border-radius:5px;background:#0f2637;color:#a9c0d1;font-size:11px;cursor:pointer}.pipeline-tabs button.active {border-color:#2dd4bf;background:#145367;color:white}.pipeline-tabs b {margin-right:5px;color:#5eead4}
.verification-body {flex:1;min-height:0}
.confirm-error {margin:0;padding:5px 12px;background:#521c1c;color:#fecaca;font-size:11px}.confirmation-bar {flex:0 0 auto;display:flex;align-items:center;gap:6px;padding:7px 12px;border-top:1px solid #244158;background:#0b1d2b}.confirmation-bar span {margin-right:auto;color:#a9bec9;font-size:11px}.confirmation-bar button {min-height:30px;padding:0 8px;border:1px solid #315669;border-radius:5px;background:#123848;color:white;font-size:11px;cursor:pointer}.confirmation-bar button:disabled {opacity:.45}
@media(max-width:800px){.verification-header {display:block}.workflow-state{max-width:100%;margin-top:5px}.confirmation-bar {flex-wrap:wrap}}
</style>
