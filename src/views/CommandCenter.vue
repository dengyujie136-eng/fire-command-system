<template>
  <main class="command-page">
    <header class="page-header">
      <div>
        <span class="eyebrow">UNIFIED INCIDENT COMMAND</span>
        <h1>指挥决策中心</h1>
        <p>经视觉确认的可信火点驱动火势推演、空间风险分析和多智能体决策。</p>
      </div>
      <span class="overall-status" :data-status="workflowStatus">{{ statusLabel(workflowStatus) }}</span>
    </header>

    <section class="control-band" aria-label="指挥工作流参数">
      <label>
        <span>事件 ID</span>
        <input v-model.trim="eventId" type="text" />
      </label>
      <label>
        <span>视觉确认 ID</span>
        <input v-model.trim="confirmationId" type="text" placeholder="留空则使用最新确认" />
      </label>
      <label>
        <span>候选点 ID</span>
        <input v-model.trim="candidateId" type="text" placeholder="可选" />
      </label>
      <label>
        <span>推演时长</span>
        <select v-model.number="horizonMinutes">
          <option :value="60">1 小时</option>
          <option :value="180">3 小时</option>
          <option :value="360">6 小时</option>
          <option :value="720">12 小时</option>
        </select>
      </label>
      <button type="button" :disabled="running || !eventId" @click="runWorkflow">
        {{ running ? '正在计算…' : '运行闭环决策' }}
      </button>
    </section>

    <p v-if="error" class="error-message" role="alert">{{ error }}</p>

    <section class="pipeline" aria-label="工作流执行状态">
      <article v-for="step in steps" :key="step.key" class="pipeline-step" :data-status="step.status">
        <span class="step-index">{{ step.index }}</span>
        <div>
          <strong>{{ step.title }}</strong>
          <small>{{ step.detail }}</small>
        </div>
        <span class="step-status">{{ statusLabel(step.status) }}</span>
      </article>
    </section>

    <section class="content-grid">
      <div class="results-panel">
        <div class="section-heading">
          <div><span class="eyebrow">PROVENANCE</span><h2>闭环证据链</h2></div>
          <button class="quiet-button" type="button" :disabled="loading || !eventId" @click="loadLatest">刷新</button>
        </div>
        <dl v-if="identifiers" class="identifier-list">
          <template v-for="item in identifierRows" :key="item.label">
            <dt>{{ item.label }}</dt>
            <dd>{{ item.value || '--' }}</dd>
          </template>
        </dl>
        <p v-else class="empty-state">{{ loading ? '正在读取最新工作流…' : '当前事件尚无已完成的指挥工作流。' }}</p>
      </div>

      <div class="results-panel">
        <div class="section-heading"><div><span class="eyebrow">COMMAND PLAN</span><h2>推荐方案</h2></div></div>
        <template v-if="commandPlan">
          <div class="plan-title"><strong>{{ commandPlan.name || '结构化指挥方案' }}</strong><span>{{ commandPlan.score ?? '--' }} 分</span></div>
          <p class="strategy">{{ commandPlan.strategy || recommendation?.summary || '暂无策略摘要。' }}</p>
          <h3>行动项</h3>
          <ol class="action-list"><li v-for="action in commandPlan.actions || []" :key="action">{{ action }}</li></ol>
          <h3>决策依据</h3>
          <ul class="reason-list"><li v-for="reason in commandPlan.reasons || []" :key="reason">{{ reason }}</li></ul>
        </template>
        <p v-else class="empty-state">运行闭环决策后显示指挥建议。</p>
      </div>
    </section>

    <section v-if="warnings.length" class="warning-band">
      <strong>工作流提示</strong>
      <ul><li v-for="warning in warnings" :key="warning">{{ warning }}</li></ul>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { commandWorkflowAPI } from '../api/modules'

type WorkflowStatus = 'ready' | 'running' | 'completed' | 'unavailable' | 'failed'

const eventId = ref('dixie_fire_2021')
const confirmationId = ref('')
const candidateId = ref('')
const horizonMinutes = ref(180)
const loading = ref(false)
const running = ref(false)
const error = ref('')
const result = ref<any>(null)

const workflowStatus = computed<WorkflowStatus>(() => {
  if (running.value) return 'running'
  if (error.value) return 'failed'
  return result.value?.workflow_status === 'completed' ? 'completed' : 'ready'
})
const identifiers = computed(() => result.value?.identifiers || null)
const commandPlan = computed(() => result.value?.command_plan || null)
const recommendation = computed(() => result.value?.recommendation || null)
const warnings = computed<string[]>(() => result.value?.warnings || [])

const identifierRows = computed(() => [
  { label: '候选点', value: identifiers.value?.candidate_id },
  { label: '视觉案例', value: identifiers.value?.visual_case_id },
  { label: '火点确认', value: identifiers.value?.confirmation_id },
  { label: '火势推演', value: identifiers.value?.spread_run_id },
  { label: '空间分析', value: identifiers.value?.spatial_analysis_id },
  { label: '决策运行', value: identifiers.value?.decision_run_id },
  { label: '推荐方案', value: identifiers.value?.recommendation_id }
])

const steps = computed(() => {
  const ids = identifiers.value || {}
  const active = workflowStatus.value
  const resource = result.value?.resource?.status || (ids.decision_run_id ? 'unavailable' : 'ready')
  const route = result.value?.route?.status || (ids.decision_run_id ? 'unavailable' : 'ready')
  return [
    { key: 'candidate', index: '01', title: '数据候选点', status: ids.candidate_id ? 'completed' : active, detail: ids.candidate_id || '等待数据候选点' },
    { key: 'confirmation', index: '02', title: '视觉确认', status: ids.confirmation_id ? 'completed' : active, detail: ids.confirmation_id || '仅接受已确认火点' },
    { key: 'spread', index: '03', title: '火势推演', status: ids.spread_run_id ? 'completed' : active, detail: ids.spread_run_id || '等待可信起火点' },
    { key: 'spatial', index: '04', title: '空间风险', status: ids.spatial_analysis_id ? 'completed' : active, detail: ids.spatial_analysis_id || '等待推演结果' },
    { key: 'resource', index: '05', title: '资源调度', status: resource, detail: result.value?.resource?.reason || '等待真实资源清单' },
    { key: 'route', index: '06', title: '路径规划', status: route, detail: result.value?.route?.reason || '等待真实路网' },
    { key: 'command', index: '07', title: '指挥决策', status: ids.decision_run_id ? 'completed' : active, detail: ids.decision_run_id || '等待上游分析' }
  ] as Array<{ key: string; index: string; title: string; status: WorkflowStatus; detail: string }>
})

function statusLabel(status: WorkflowStatus) {
  return ({ ready: '待运行', running: '运行中', completed: '已完成', unavailable: '不可用', failed: '失败' } as const)[status] || status
}

async function loadLatest() {
  if (!eventId.value) return
  loading.value = true
  error.value = ''
  try {
    const response = await commandWorkflowAPI.getLatest(eventId.value)
    result.value = response?.data || null
  } catch (cause: any) {
    error.value = cause?.message || '无法读取最新指挥工作流。'
  } finally {
    loading.value = false
  }
}

async function runWorkflow() {
  running.value = true
  error.value = ''
  try {
    const payload: Record<string, any> = { horizon_minutes: horizonMinutes.value, threat_buffer_km: 0.45 }
    if (confirmationId.value) payload.confirmation_id = confirmationId.value
    if (candidateId.value) payload.candidate_id = candidateId.value
    const response = await commandWorkflowAPI.run(eventId.value, payload)
    result.value = response?.data || null
    confirmationId.value = identifiers.value?.confirmation_id || confirmationId.value
    candidateId.value = identifiers.value?.candidate_id || candidateId.value
  } catch (cause: any) {
    error.value = cause?.message || '指挥工作流运行失败。'
  } finally {
    running.value = false
  }
}

onMounted(loadLatest)
</script>

<style scoped>
.command-page { min-height: calc(100vh - 64px); padding: 28px 32px 44px; color: #17212b; background: #f3f6f7; }
.page-header, .section-heading, .plan-title { display: flex; align-items: center; justify-content: space-between; gap: 20px; }
.page-header { padding-bottom: 22px; border-bottom: 1px solid #cbd4d8; }
.eyebrow { display: block; margin-bottom: 6px; color: #52636c; font-size: 11px; font-weight: 700; }
h1, h2, h3, p { margin-top: 0; }
h1 { margin-bottom: 7px; font-size: 30px; }
h2 { margin-bottom: 0; font-size: 19px; }
h3 { margin: 20px 0 8px; font-size: 14px; }
.page-header p { margin-bottom: 0; color: #5d6b72; }
.overall-status, .step-status { font-size: 12px; font-weight: 700; }
[data-status='completed'] .step-status, .overall-status[data-status='completed'] { color: #147548; }
[data-status='unavailable'] .step-status { color: #8a641c; }
[data-status='failed'] .step-status, .overall-status[data-status='failed'] { color: #b42318; }
[data-status='running'] .step-status, .overall-status[data-status='running'] { color: #1769aa; }
.control-band { display: grid; grid-template-columns: 1.1fr 1.4fr 1.4fr 150px auto; gap: 12px; align-items: end; padding: 18px 0; border-bottom: 1px solid #d8e0e3; }
label span { display: block; margin-bottom: 6px; color: #53636b; font-size: 12px; font-weight: 600; }
input, select { width: 100%; min-width: 0; height: 38px; padding: 0 10px; border: 1px solid #b9c5ca; border-radius: 4px; color: #17212b; background: #fff; }
button { min-height: 38px; padding: 0 16px; border: 1px solid #9d2f24; border-radius: 4px; color: #fff; background: #a83427; font-weight: 700; cursor: pointer; }
button:disabled { cursor: not-allowed; opacity: .55; }
.quiet-button { color: #31444d; border-color: #aebcc2; background: transparent; }
.error-message { margin: 16px 0 0; padding: 12px 14px; border-left: 3px solid #b42318; color: #8e1b14; background: #fff0ee; }
.pipeline { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); margin: 22px 0; border: 1px solid #cbd4d8; background: #fff; }
.pipeline-step { min-width: 0; padding: 14px; border-right: 1px solid #dce3e6; }
.pipeline-step:last-child { border-right: 0; }
.step-index { color: #89969c; font-size: 11px; }
.pipeline-step strong, .pipeline-step small { display: block; }
.pipeline-step strong { margin: 8px 0 5px; font-size: 13px; }
.pipeline-step small { min-height: 32px; overflow: hidden; color: #718087; font-size: 11px; overflow-wrap: anywhere; }
.step-status { display: block; margin-top: 9px; }
.content-grid { display: grid; grid-template-columns: minmax(360px, .85fr) minmax(460px, 1.15fr); gap: 18px; }
.results-panel { min-width: 0; padding: 20px; border: 1px solid #cbd4d8; border-radius: 6px; background: #fff; }
.identifier-list { display: grid; grid-template-columns: 100px minmax(0, 1fr); margin: 18px 0 0; }
.identifier-list dt, .identifier-list dd { margin: 0; padding: 9px 0; border-bottom: 1px solid #e7ecee; }
.identifier-list dt { color: #65747b; font-size: 12px; }
.identifier-list dd { overflow-wrap: anywhere; font-family: Consolas, monospace; font-size: 12px; }
.plan-title { margin-top: 18px; padding-bottom: 12px; border-bottom: 1px solid #e0e6e8; }
.plan-title span { color: #a83427; font-weight: 800; }
.strategy { margin: 14px 0; color: #43535b; line-height: 1.65; }
.action-list, .reason-list, .warning-band ul { margin: 0; padding-left: 20px; color: #3c4b52; line-height: 1.7; }
.empty-state { margin: 22px 0 4px; color: #718087; }
.warning-band { margin-top: 18px; padding: 15px 18px; border-left: 3px solid #b2781e; background: #fff7e6; }
.warning-band strong { display: block; margin-bottom: 6px; }
@media (max-width: 1100px) { .control-band { grid-template-columns: repeat(2, minmax(0, 1fr)); } .pipeline { grid-template-columns: repeat(4, minmax(0, 1fr)); } .pipeline-step { border-bottom: 1px solid #dce3e6; } .content-grid { grid-template-columns: 1fr; } }
@media (max-width: 680px) { .command-page { padding: 20px 16px 34px; } .page-header { align-items: flex-start; } .control-band, .pipeline { grid-template-columns: 1fr; } .pipeline-step { border-right: 0; } h1 { font-size: 25px; } }
</style>
