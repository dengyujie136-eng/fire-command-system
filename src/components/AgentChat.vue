<template>
  <section class="agent-chat" aria-label="智能体对话">
    <header class="agent-header">
      <div>
        <span class="eyebrow">XINGHUO AGENT</span>
        <strong>智能应急助手</strong>
        <small>{{ pageLabel }} · {{ incident.eventName }}</small>
      </div>
      <div class="header-actions">
        <button class="quiet-button" type="button" title="查看已保存的本地对话记录" :disabled="busy || actionBusyId !== ''" @click="historyOpen = !historyOpen">
          {{ historyOpen ? '收起记录' : '对话记录' }}<span v-if="conversations.length" class="history-count">{{ conversations.length }}</span>
        </button>
        <button class="new-chat-button" type="button" title="开始一轮新对话" :disabled="busy || actionBusyId !== ''" @click="newConversation">
          <span aria-hidden="true">＋</span>新建对话
        </button>
        <button class="quiet-button" type="button" title="仅清空当前消息记录" :disabled="busy || actionBusyId !== ''" @click="clearMessages">清空消息</button>
      </div>
    </header>

    <section v-if="historyOpen" class="conversation-history" aria-label="对话记录">
      <div class="history-heading"><strong>本地对话记录</strong><small>只保存在当前浏览器，不会上传到服务器</small></div>
      <div v-if="!conversations.length" class="history-empty">还没有已保存的对话。点击“新建对话”或发送第一条消息后会自动保存。</div>
      <div v-else class="history-list">
        <button v-for="conversation in conversations" :key="conversation.id" type="button" class="history-item" :class="{ active: conversation.id === conversationId }" @click="selectConversation(conversation.id)">
          <span><strong>{{ conversation.title }}</strong><small>{{ formatConversationTime(conversation.updatedAt) }} · {{ conversation.messages.filter(item => item.role === 'user').length }} 条提问</small></span>
          <i aria-hidden="true" @click.stop="deleteConversation(conversation.id)">×</i>
        </button>
      </div>
    </section>

    <section class="guidance" aria-label="工作流引导">
      <div v-if="guidance?.phase !== 'idle'" class="guidance-meta">
        <span class="phase" :data-phase="guidance?.phase">{{ guidance?.phase_label || '正在读取状态' }}</span>
        <span>{{ guidance?.progress ?? 0 }}%</span>
      </div>
      <div v-if="guidance?.phase !== 'idle'" class="progress-track" role="progressbar" :aria-valuenow="guidance?.progress || 0" aria-valuemin="0" aria-valuemax="100">
        <span :style="{ width: `${guidance?.progress || 0}%` }"></span>
      </div>
      <div class="guidance-copy">
        <p class="stage-name">{{ guidance?.current_stage_label || stageLabel(incident.currentStage) }}</p>
        <h2>{{ guidance?.title || '正在分析当前任务' }}</h2>
        <p>{{ guidance?.message || '正在读取事件和工作流状态。' }}</p>
      </div>
      <div v-if="incident.workflowRunId && guidance?.phase !== 'idle'" class="run-line">
        <span>{{ incident.workflow?.status || 'READY' }}</span>
        <code>{{ incident.workflowRunId }}</code>
        <span>{{ completedCount }}/9 已完成</span>
      </div>

      <section v-if="showSpreadConfiguration" class="spread-configuration" aria-label="火情推演参数">
        <div class="spread-data-summary">
          <span>可用气象数据</span>
          <strong v-if="weatherAvailabilityLoading">正在读取...</strong>
          <strong v-else-if="weatherAvailabilityError">读取失败</strong>
          <strong v-else>{{ weatherAvailability.total }} 条 · 间隔 {{ weatherAvailability.intervalMinutes }} 分钟</strong>
          <small v-if="weatherAvailability.startAt && weatherAvailability.endAt">
            {{ formatWeatherTime(weatherAvailability.startAt) }} 至 {{ formatWeatherTime(weatherAvailability.endAt) }}
          </small>
          <small v-else-if="weatherAvailabilityError">{{ weatherAvailabilityError }}</small>
        </div>
        <form class="spread-configuration-form" @submit.prevent="queueSpreadConfiguration">
          <label>
            <span>需要推理的时间</span>
            <div><input v-model.number="spreadHours" type="number" min="1" max="24" step="1" required><em>小时</em></div>
          </label>
          <label>
            <span>气象更新间隔</span>
            <div><input v-model.number="spreadWeatherInterval" type="number" :min="minimumWeatherInterval" max="1440" :step="minimumWeatherInterval" required><em>分钟</em></div>
          </label>
          <p>保存参数后仍需在推理页面点击开始推演，系统不会自动运行模型。</p>
          <button type="submit" :disabled="busy || actionBusyId !== '' || weatherAvailabilityLoading">保存推演参数</button>
        </form>
      </section>

      <div v-if="guidance?.choices?.length" class="next-actions">
        <span class="section-label">建议下一步</span>
        <button v-for="choice in guidance.choices" :key="choice.id" type="button"
          :class="['choice', choice.kind || 'secondary']" :disabled="busy || actionBusyId !== ''"
          @click="executeChoice(choice)">
          <span><em>{{ choiceTypeLabel(choice) }}</em><b>{{ choice.label }}</b><small>{{ choice.description }}</small></span>
          <i aria-hidden="true">{{ actionBusyId === choice.id ? '…' : '→' }}</i>
        </button>
      </div>

      <div v-if="actionFeedback" class="action-feedback" :class="actionFeedback.state" role="status" aria-live="polite">
        <span>{{ actionFeedback.state === 'running' ? '正在处理' : actionFeedback.state === 'success' ? '操作完成' : '操作失败' }}</span>
        <strong>{{ actionFeedback.label }}</strong>
        <p>{{ actionFeedback.message }}</p>
      </div>

      <a v-if="lastReport && lastUserMessage" class="report-link" :href="reportAPI.downloadUrl(lastReport.report_id)" target="_blank" rel="noreferrer">
        下载最新综合报告 PDF · {{ lastReport.report_id }}
      </a>
      <p v-if="guidanceError" class="guidance-error">{{ guidanceError }}</p>
    </section>

    <div class="conversation-heading"><span>任务对话</span><small>回答基于当前事件与真实接口状态</small></div>
    <div ref="messagesEl" class="messages" aria-live="polite">
      <article v-for="item in messages" :key="item.id" :class="item.role">
        <small>{{ item.role === 'user' ? '你' : '智能体' }}</small>
        <p>{{ item.text }}</p>
        <span v-if="item.source">{{ item.source }}</span>
      </article>
      <p v-if="busy" class="pending">正在分析当前事件与可用工具…</p>
    </div>

    <details class="agent-tools">
      <summary>数据工具</summary>
      <div class="import-fields">
        <label>影像阶段<select v-model="importPhase"><option value="primary">灾中核验</option><option value="comparison_pre">灾前</option><option value="comparison_post">灾后</option></select></label>
        <label>场景 ID<input v-model="importScene" placeholder="Sentinel 场景编号"></label>
        <label>拍摄时间<input v-model="importDate" type="datetime-local"></label>
        <label>实际波段<input v-model="importBands" placeholder="B02,B03,B04,B08,B12"></label>
        <input type="file" accept=".tif,.tiff,image/tiff" @change="selectImportFile">
        <button type="button" :disabled="importing || !importFile" @click="uploadImagery">{{ importing ? '正在导入…' : '上传并登记 GeoTIFF' }}</button>
      </div>
    </details>

    <form @submit.prevent="send()">
      <textarea v-model="draft" rows="2" :disabled="busy" placeholder="描述地点、时间和你要完成的任务…" @keydown.enter.exact.prevent="send()"></textarea>
      <button type="submit" :disabled="busy || !draft.trim()" title="发送">发送</button>
    </form>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { assistantAPI, fireDataAPI, reportAPI } from '../api/modules'
import { useIncidentContextStore } from '../stores/incidentContextStore'
import { useAssistantTaskStore } from '../stores/assistantTaskStore'

type Message = { id: string; role: 'user' | 'assistant'; text: string; source?: string }
type Conversation = { id: string; title: string; messages: Message[]; createdAt: string; updatedAt: string; eventId?: string; eventName?: string }
type AssistantChoice = {
  id: string
  label: string
  description?: string
  kind?: 'primary' | 'secondary' | 'danger'
  navigate_to?: string
  navigate_query?: Record<string, string>
  prompt?: string
  action?: Record<string, any> | null
}
type AssistantGuidance = {
  phase: 'idle' | 'pre_fire' | 'during_fire' | 'post_fire' | 'report'
  phase_label: string
  title: string
  message: string
  progress: number
  current_stage: string
  current_stage_label: string
  waiting_for?: string | null
  completed_steps: string[]
  choices: AssistantChoice[]
}
type ActionFeedback = {
  state: 'running' | 'success' | 'error'
  label: string
  message: string
}

const route = useRoute()
const router = useRouter()
const incident = useIncidentContextStore()
const task = useAssistantTaskStore()
const links = [
  { path: '/realtime-monitor', label: '监测' }, { path: '/visual-verification', label: '核验' },
  { path: '/command-center', label: '推演' }, { path: '/planning', label: '规划' },
  { path: '/disaster-assess', label: '评估' },
]
const labels: Record<string, string> = {
  data_preparation: '数据准备', fire_verification: '火点核验', situation: '态势评估',
  spread: '火势推演', spatial_risk: '空间风险', scenario: '应急场景',
  resource_dispatch: '资源调度', route_planning: '路径规划', commander: '指挥决策',
}

const pageLabel = computed(() => links.find((item) => item.path === route.path)?.label || '工作台')
const completedCount = computed(() => guidance.value?.completed_steps?.length || incident.stages.filter((item) => item.status === 'COMPLETED').length)
const messages = ref<Message[]>([{ id: 'welcome', role: 'assistant', text: '我会根据事件状态主动推进监测、核验、推演、规划、灾后评估和报告；遇到需要人工判断的节点，会在上方给出明确选项。' }])
const conversations = ref<Conversation[]>([])
const conversationId = ref('')
const historyOpen = ref(false)
const historyReady = ref(false)
const draft = ref('')
const busy = ref(false)
const actionBusyId = ref('')
const lastUserMessage = ref('')
const lastAgentResult = ref<Record<string, any> | null>(null)
const guidance = ref<AssistantGuidance | null>(null)
const guidanceError = ref('')
const actionFeedback = ref<ActionFeedback | null>(null)
const messagesEl = ref<HTMLElement | null>(null)
const lastReport = ref<any>(null)
const assessmentState = ref<any>(null)
const importPhase = ref('primary')
const importScene = ref('')
const importDate = ref('')
const importBands = ref('B02,B03,B04,B08,B12')
const importFile = ref<File | null>(null)
const importing = ref(false)
const spreadHours = ref(task.requestedHours)
const spreadWeatherInterval = ref(task.weatherUpdateMinutes)
const weatherAvailabilityLoading = ref(false)
const weatherAvailabilityError = ref('')
const weatherAvailability = ref({ total: 0, intervalMinutes: 60, startAt: '', endAt: '' })
const imageryNotified = new Set<string>()
let guidanceRequest = 0
const CONVERSATIONS_KEY = 'xinghuo-agent-conversations-v1'

const showSpreadConfiguration = computed(() => route.path === '/command-center' && Boolean(incident.confirmationId))
const minimumWeatherInterval = computed(() => Math.max(1, weatherAvailability.value.intervalMinutes || 60))

function formatWeatherTime(value: string) {
  if (!value) return '--'
  return new Date(value).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

async function loadWeatherAvailability() {
  if (!showSpreadConfiguration.value || !incident.eventId) return
  weatherAvailabilityLoading.value = true
  weatherAvailabilityError.value = ''
  try {
    const response = await fireDataAPI.getHourlyWeather(incident.eventId)
    const data = response.data || response
    const items = Array.isArray(data.items) ? data.items : []
    const timestamps = items
      .map((item: any) => new Date(item.observed_at).getTime())
      .filter(Number.isFinite)
      .sort((a: number, b: number) => a - b)
    const intervals = timestamps
      .slice(1)
      .map((value: number, index: number) => Math.round((value - timestamps[index]) / 60000))
      .filter((value: number) => value > 0)
    const actualInterval = intervals.length ? Math.min(...intervals) : Number(data.interval_minutes || 60)
    weatherAvailability.value = {
      total: Number(data.total || items.length),
      intervalMinutes: actualInterval,
      startAt: items[0]?.observed_at || '',
      endAt: items[items.length - 1]?.observed_at || '',
    }
    if (!Number.isFinite(spreadWeatherInterval.value) || spreadWeatherInterval.value < actualInterval) {
      spreadWeatherInterval.value = actualInterval
    }
  } catch (error: any) {
    weatherAvailabilityError.value = error?.message || '气象目录请求失败'
  } finally {
    weatherAvailabilityLoading.value = false
  }
}

async function queueSpreadConfiguration() {
  const hours = Math.max(1, Math.min(24, Math.round(Number(spreadHours.value || 1))))
  const interval = Math.max(
    minimumWeatherInterval.value,
    Math.min(1440, Math.round(Number(spreadWeatherInterval.value || minimumWeatherInterval.value))),
  )
  spreadHours.value = hours
  spreadWeatherInterval.value = interval
  task.queue(hours, incident.spreadRunId, true, {}, interval)
  await router.replace({
    path: '/command-center',
    query: { ...route.query, forecast_hours: String(hours), weather_interval: String(interval) },
  })
  actionFeedback.value = {
    state: 'success',
    label: '推演参数已保存',
    message: `已设置推理 ${hours} 小时，气象每 ${interval} 分钟更新。请在推理页面点击开始推演。`,
  }
  append(`推演参数已保存：推理 ${hours} 小时，气象更新间隔 ${interval} 分钟。模型尚未运行。`, '智能体参数配置')
}

function stageLabel(stage: string) { return labels[stage] || stage || '尚未启动' }
function choiceTypeLabel(choice: AssistantChoice) {
  if (choice.prompt) return '继续询问'
  if (choice.action && choice.navigate_to) return '执行并打开'
  if (choice.action) return '执行任务'
  return '打开页面'
}
function append(text: string, source = '真实接口结果') { messages.value.push({ id: crypto.randomUUID(), role: 'assistant', text, source }) }
function welcomeMessage(text = '请描述地点、时间和想完成的任务。我会根据当前事件状态重新分析。'): Message {
  return { id: crypto.randomUUID(), role: 'assistant', text }
}
function conversationTitle(items: Message[]) {
  const firstQuestion = items.find((item) => item.role === 'user')?.text?.trim()
  if (!firstQuestion) return '新对话'
  return firstQuestion.length > 28 ? `${firstQuestion.slice(0, 28)}…` : firstQuestion
}
function formatConversationTime(value: string) {
  if (!value) return '刚刚'
  return new Date(value).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}
function persistConversation() {
  if (!historyReady.value || !conversationId.value) return
  const now = new Date().toISOString()
  const index = conversations.value.findIndex((item) => item.id === conversationId.value)
  const next: Conversation = {
    id: conversationId.value,
    title: conversationTitle(messages.value),
    messages: messages.value.map((item) => ({ ...item })),
    createdAt: index >= 0 ? conversations.value[index].createdAt : now,
    updatedAt: now,
    eventId: incident.eventId,
    eventName: incident.eventName,
  }
  if (index >= 0) conversations.value[index] = next
  else conversations.value.unshift(next)
  conversations.value = conversations.value.slice(0, 30)
  localStorage.setItem(CONVERSATIONS_KEY, JSON.stringify(conversations.value))
}
function loadConversationHistory() {
  try {
    const saved = JSON.parse(localStorage.getItem(CONVERSATIONS_KEY) || '[]')
    conversations.value = Array.isArray(saved) ? saved.filter((item) => item?.id && Array.isArray(item.messages)) : []
  } catch {
    conversations.value = []
  }
  const latest = conversations.value[0]
  conversationId.value = latest?.id || crypto.randomUUID()
  if (latest) messages.value = latest.messages.length ? latest.messages : [welcomeMessage()]
  historyReady.value = true
  persistConversation()
}
function selectConversation(id: string) {
  if (id === conversationId.value) { historyOpen.value = false; return }
  persistConversation()
  const target = conversations.value.find((item) => item.id === id)
  if (!target) return
  conversationId.value = target.id
  messages.value = target.messages.length ? target.messages.map((item) => ({ ...item })) : [welcomeMessage()]
  lastUserMessage.value = messages.value.findLast((item) => item.role === 'user')?.text || ''
  lastAgentResult.value = null
  guidance.value = null
  historyOpen.value = false
  void refreshGuidance()
}
function deleteConversation(id: string) {
  conversations.value = conversations.value.filter((item) => item.id !== id)
  localStorage.setItem(CONVERSATIONS_KEY, JSON.stringify(conversations.value))
  if (id === conversationId.value) newConversation()
}
function newConversation() {
  persistConversation()
  guidanceRequest += 1
  conversationId.value = crypto.randomUUID()
  messages.value = [welcomeMessage()]
  draft.value = ''
  lastUserMessage.value = ''
  lastAgentResult.value = null
  guidance.value = null
  guidanceError.value = ''
  actionFeedback.value = null
  historyOpen.value = false
  persistConversation()
  void refreshGuidance()
}
function clearMessages() {
  messages.value = [welcomeMessage('消息记录已清空。当前对话上下文和工作流状态仍然保留。')]
  persistConversation()
}
function selectImportFile(event: Event) { importFile.value = (event.target as HTMLInputElement).files?.[0] || null }

function assistantContext() {
  return {
    event_id: incident.eventId, event_name: incident.eventName, mode: incident.mode,
    workflow_run_id: incident.workflowRunId, workflow_status: incident.workflow?.status || '尚未运行',
    workflow_error: incident.workflow?.error || '', current_stage: incident.currentStage,
    confirmed: !!incident.confirmationId, confirmation_id: incident.confirmationId, spread_run_id: incident.spreadRunId,
    scenario_id: incident.scenarioId, route_plan_id: incident.routePlanId,
    resource_plan_id: incident.resourcePlanId, decision_run_id: incident.decisionRunId,
    report_id: lastReport.value?.report_id || null, last_user_message: lastUserMessage.value,
    assessment_completed: Boolean(assessmentState.value?.analysis_id), assessment: assessmentState.value,
    last_agent_result: lastAgentResult.value,
    workflow_metadata: incident.workflow?.metadata_json || {},
    verification_substage: incident.workflow?.metadata_json?.verification_substage || '',
    stages: incident.stages.map((item) => ({ stage: item.stage, status: item.status, progress: item.progress })),
  }
}

async function refreshGuidance() {
  const requestId = ++guidanceRequest
  try {
    const result = await assistantAPI.nextSteps({ page: route.path, context: assistantContext() })
    if (requestId !== guidanceRequest) return
    guidance.value = result.data || result
    guidanceError.value = ''
  } catch (error: any) {
    if (requestId !== guidanceRequest) return
    guidanceError.value = '工作流建议暂时不可用：' + (error?.message || '请求失败')
  }
}

function targetPageLabel(path?: string) {
  return links.find((item) => item.path === path)?.label || '目标'
}

async function navigate(path?: string, query: Record<string, string> = {}) {
  if (!path) return ''
  if (!links.some((item) => item.path === path)) throw new Error(`不支持的页面：${path}`)
  const label = targetPageLabel(path)
  const currentQuery = Object.fromEntries(Object.entries(route.query).map(([key, value]) => [key, String(value ?? '')]))
  const queryChanged = JSON.stringify(currentQuery) !== JSON.stringify(query)
  if (route.path === path && !queryChanged) {
    window.dispatchEvent(new CustomEvent('fire:agent-focus', { detail: { path, query } }))
    return `当前已经位于${label}页。请按页面中的业务流程完成本阶段操作。`
  }
  await router.push({ path, query })
  return `已打开${label}页。`
}

async function executeAction(action?: Record<string, any> | null) {
  if (!action) return ''
  if (action.type === 'start_workflow') {
    const eventId = String(action.event_id || incident.eventId)
    if (eventId !== incident.eventId) await incident.selectEvent(eventId)
    await incident.startWorkflow(Number(action.horizon_minutes) || 240)
    if (action.acquire_imagery) await acquireImagery(eventId, 'primary')
    append(`工作流 ${incident.workflowRunId || ''} 已创建，将自动运行到下一个人工决策门。`, '工作流接口')
    return `工作流 ${incident.workflowRunId || ''} 已启动。`
  } else if (action.type === 'acquire_imagery') {
    const data = await acquireImagery(String(action.event_id || incident.eventId), String(action.phase || 'primary'))
    return `影像任务 ${String(data?.task_id || '')} 已提交，当前状态：${String(data?.status || 'submitted')}。`
  } else if (action.type === 'acquire_assessment_imagery') {
    const eventId = String(action.event_id || incident.eventId)
    await Promise.all([acquireImagery(eventId, 'comparison_pre'), acquireImagery(eventId, 'comparison_post')])
    return '灾前、灾后影像任务均已提交。'
  } else if (action.type === 'run_spread' && Number.isInteger(Number(action.horizon_minutes))) {
    const overrides = Object.fromEntries(['wind_speed_m_s', 'wind_direction_deg', 'temperature_c', 'humidity_percent']
      .filter((key) => action[key] !== undefined).map((key) => [key, Number(action[key])]))
    const updateMinutes = Number(action.weather_update_interval_minutes || route.query.weather_interval || weatherAvailability.value.intervalMinutes || 60)
    task.queue(Number(action.horizon_minutes) / 60, incident.spreadRunId, true, overrides, updateMinutes)
    return `已保存 ${Number(action.horizon_minutes) / 60} 小时火势推演参数，气象更新间隔 ${updateMinutes} 分钟；请在推理页手动开始。`
  } else if (action.type === 'resume_workflow') {
    await incident.resumeWorkflow()
    append('已开始使用人工确认火点执行首次态势分析和火势推演。', '工作流接口')
    return '首次火势推演已启动。'
  } else if (action.type === 'confirm_scenario') {
    await incident.confirmScenario({ note: '由用户在智能体工作流面板确认当前应急场景。' })
    append('已记录场景人工确认，资源调度、路线规划和指挥建议将继续运行。', '人工决策门')
    return '当前应急场景已确认，工作流将继续运行。'
  } else if (action.type === 'review_commander') {
    const reviewAction = String(action.review_action || 'approve') as 'approve' | 'revise' | 'regenerate'
    await incident.reviewCommander(reviewAction, '由用户在智能体工作流面板提交。')
    append(reviewAction === 'approve' ? '辅助决策已由人工接受，可以继续灾后评估和报告。' : '辅助决策已退回处理。', '人工决策门')
    return reviewAction === 'approve' ? '辅助决策已接受。' : '辅助决策已退回调整。'
  } else if (action.type === 'generate_report') {
    const result = await reportAPI.create(String(action.event_id || incident.eventId), { include_recalculation: true, format: 'markdown' })
    lastReport.value = result.data || result
    append(`综合报告已生成：${lastReport.value.report_id}。可在工作流引导区下载 PDF。`, '报告服务')
    return `综合报告 ${lastReport.value.report_id} 已生成。`
  }
  throw new Error(`当前前端尚未实现动作：${String(action.type || 'unknown')}`)
}

async function executeChoice(choice: AssistantChoice) {
  if (actionBusyId.value) return
  actionBusyId.value = choice.id
  actionFeedback.value = { state: 'running', label: choice.label, message: choice.description || '正在执行所选操作。' }
  try {
    if (choice.prompt) {
      await submitMessage(choice.prompt, true)
      actionFeedback.value = { state: 'success', label: choice.label, message: '智能体已根据该选项继续分析并返回结果。' }
    }
    else {
      const actionMessage = await executeAction(choice.action)
      if (choice.action) await incident.refreshWorkflow()
      const navigationMessage = await navigate(choice.navigate_to, choice.navigate_query)
      if (choice.action) lastAgentResult.value = null
      await refreshGuidance()
      const message = [actionMessage, navigationMessage].filter(Boolean).join(' ') || '选项已处理，当前工作流状态已刷新。'
      actionFeedback.value = { state: 'success', label: choice.label, message }
      append(message, choice.action ? '智能体任务执行' : '智能体页面导航')
    }
  } catch (error: any) {
    const message = error?.message || '请求失败'
    actionFeedback.value = { state: 'error', label: choice.label, message }
    append(`${choice.label}失败：${message}`, '任务异常')
  }
  finally { actionBusyId.value = '' }
}

async function uploadImagery() {
  if (!importFile.value || !importScene.value.trim() || !importDate.value) { append('请填写场景 ID、拍摄时间、实际波段并选择 GeoTIFF。', '影像导入'); return }
  importing.value = true
  try {
    const params = new URLSearchParams({ event_id: incident.eventId, phase: importPhase.value, scene_id: importScene.value.trim(), acquired_at: new Date(importDate.value).toISOString(), bands: importBands.value })
    const response = await fetch('/api/data-agent/imagery/upload?' + params, { method: 'POST', headers: { 'Content-Type': 'image/tiff' }, body: importFile.value })
    const payload = await response.json()
    if (!response.ok) throw new Error(typeof payload.detail === 'string' ? payload.detail : JSON.stringify(payload.detail || payload))
    append(`影像已登记：${payload.data.asset_id}；波段 ${(payload.data.bands || []).join('、')}。`, '数据智能体 / 手动导入')
    await incident.refreshWorkflow(); await refreshGuidance()
  } catch (error: any) { append('影像导入失败：' + (error?.message || '请求失败'), '数据智能体 / 手动导入') }
  finally { importing.value = false }
}

async function acquireImagery(eventId: string, phase: string) {
  const response = await fetch('/api/data-agent/imagery/acquire', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ event_id: eventId, phase }) })
  const payload = await response.json()
  if (!response.ok) throw new Error(typeof payload.detail === 'string' ? payload.detail : '影像检索失败 ' + response.status)
  const data = payload.data || payload
  append(`影像任务 ${String(data.task_id || '')}：${String(data.status || '已提交')}。${String(data.message || '')}${data.download_url ? ' 来源：' + data.download_url : ''}`, '数据智能体 / 影像目录')
  if (data.task_id && ['searching', 'downloading'].includes(data.status)) void pollImagery(String(data.task_id))
  if (data.status === 'reused') window.dispatchEvent(new CustomEvent('fire:imagery-ready', { detail: data }))
  return data
}

async function pollImagery(taskId: string) {
  await new Promise((resolve) => setTimeout(resolve, 3000))
  try {
    const response = await fetch('/api/data-agent/imagery/tasks/' + encodeURIComponent(taskId))
    if (!response.ok) throw new Error('任务查询返回 ' + response.status)
    const payload = await response.json(), data = payload.data || payload
    if (['searching', 'downloading'].includes(data.status)) {
      if (Number(data.elapsed_seconds) >= 60 && !imageryNotified.has(taskId)) {
        imageryNotified.add(taskId)
        append(`${data.message} 官方入口：${data.download_url || '未返回'}；手动导入目录 ${data.manual_import_folder || 'data/raw/imagery/import'}`, '数据智能体 / 超时反馈')
      }
      void pollImagery(taskId)
    } else {
      append(`影像任务 ${taskId}：${data.status}。${data.message}。已有波段：${(data.available_bands || []).join('、')}；缺少：${(data.missing_bands || []).join('、')}。`, '数据智能体 / 最终结果')
      if (data.status === 'completed' || data.status === 'reused') {
        window.dispatchEvent(new CustomEvent('fire:imagery-ready', { detail: data }))
        actionFeedback.value = { state: 'success', label: '影像数据准备', message: `影像任务 ${taskId} 已完成，可以继续当前核验或评估阶段。` }
      } else if (data.status === 'failed' || data.status === 'no_match') {
        actionFeedback.value = { state: 'error', label: '影像数据准备', message: data.message || `影像任务 ${taskId} 未完成。` }
      }
      await refreshGuidance()
    }
  } catch (error: any) { append('影像任务状态查询失败：' + (error?.message || '请求失败'), '数据智能体 / 异常') }
}

async function submitMessage(text: string, supplied = false) {
  const message = text.trim()
  if (!message || busy.value) return
  lastUserMessage.value = message
  if (!supplied) draft.value = ''
  messages.value.push({ id: crypto.randomUUID(), role: 'user', text: message })
  busy.value = true
  try {
    const result = await assistantAPI.chat({ message, page: route.path, context: assistantContext() })
    const data = result.data || result
    lastAgentResult.value = {
      message: String(data.message || ''), source_mode: data.source_mode,
      action: data.action || null, navigate_to: data.navigate_to || null,
      navigate_query: data.navigate_query || {},
    }
    const source = data.source_mode === 'llm'
      ? `${data.provider || 'Qwen'} 文本智能体${data.model ? ' / ' + data.model : ''}`
      : data.source_mode === 'tool_agent'
        ? `${data.provider || 'Qwen'} 工具智能体${data.model ? ' / ' + data.model : ''} / 真实数据证据`
        : data.source_mode === 'structured_location_plan' ? '地点识别 / 数据准备计划' : '工作流编排 / 当前状态'
    messages.value.push({ id: crypto.randomUUID(), role: 'assistant', text: String(data.message || '服务没有返回内容'), source })
    // Mutating operations require an explicit click in the guidance panel.
    // Navigation-only results remain safe to show immediately.
    if (!data.action) await navigate(data.navigate_to, data.navigate_query || {})
    await refreshGuidance()
  } catch (error: any) { append('对话服务暂不可用：' + (error?.message || '请求失败'), '任务异常') }
  finally { busy.value = false }
}

async function send() { await submitMessage(draft.value) }

async function loadLatestReport() {
  try {
    const result = await reportAPI.getLatest(incident.eventId)
    lastReport.value = result.data || null
  } catch {
    lastReport.value = null
  }
}

function loadAssessmentState() {
  try {
    assessmentState.value = JSON.parse(sessionStorage.getItem('fire-assessment:' + incident.eventId) || 'null')
  } catch {
    assessmentState.value = null
  }
}

function handleAssessmentCompleted(event: Event) {
  assessmentState.value = (event as CustomEvent).detail || null
  void refreshGuidance()
}

const workflowKey = computed(() => JSON.stringify({
  route: route.path, run: incident.workflowRunId, status: incident.workflow?.status,
  stage: incident.currentStage, confirmation: incident.confirmationId,
  scenario: incident.scenarioId, decision: incident.decisionRunId, report: lastReport.value?.report_id,
  assessment: assessmentState.value?.analysis_id,
  stages: incident.stages.map((item) => [item.stage, item.status, item.progress]),
}))
watch(workflowKey, () => { void refreshGuidance() })
watch(messages, () => persistConversation(), { deep: true })
watch(() => messages.value.length, async () => { await nextTick(); if (messagesEl.value) messagesEl.value.scrollTop = messagesEl.value.scrollHeight })
watch(() => task.status, (status) => {
  if (status === 'completed') append('火势推演已完成，运行 ID：' + (task.resultRunId || '请在推演页查看。'), '模型结果')
  if (status === 'failed' || status === 'blocked') append(task.message, '任务状态')
  void refreshGuidance()
})
watch(() => incident.eventId, async () => { loadAssessmentState(); await loadLatestReport(); await refreshGuidance(); await loadWeatherAvailability() })
watch(showSpreadConfiguration, (visible) => { if (visible) void loadWeatherAvailability() }, { immediate: true })
onMounted(async () => {
  loadConversationHistory()
  window.addEventListener('fire:assessment-completed', handleAssessmentCompleted)
  loadAssessmentState()
  try {
    await incident.loadEvents()
    await Promise.all([incident.loadReadiness(), incident.loadLatestWorkflow(), loadLatestReport()])
    await refreshGuidance()
    await loadWeatherAvailability()
  } catch (error: any) {
    guidanceError.value = `事件状态同步失败：${error?.message || '请求失败'}`
  }
})
onBeforeUnmount(() => window.removeEventListener('fire:assessment-completed', handleAssessmentCompleted))
</script>

<style scoped>
.agent-chat{height:100%;min-height:0;display:flex;flex-direction:column;background:#09131c;color:#edf5f7;font-size:14px;letter-spacing:0}
.agent-header{flex:0 0 auto;display:flex;align-items:center;justify-content:space-between;gap:16px;padding:16px 18px 14px;border-bottom:1px solid #253945;background:#0d1d28}.agent-header div{min-width:0}.agent-header strong,.agent-header small{display:block}.agent-header strong{margin-top:2px;font-size:18px;line-height:1.3}.agent-header small{margin-top:4px;color:#9bb0bc;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.eyebrow{color:#59cbb7;font-size:10px;font-weight:800;letter-spacing:1.2px}
.header-actions{flex:0 0 auto;display:flex;align-items:center;gap:6px}.new-chat-button,.quiet-button{min-height:31px;padding:0 9px;border:1px solid #35505e;border-radius:5px;background:#102733;color:#bcd0d8;font-size:11px;cursor:pointer}.new-chat-button{display:inline-flex;align-items:center;gap:4px;border-color:#348f80;background:#12443e;color:#d9fff5;font-weight:800}.new-chat-button span{font-size:17px;line-height:1}.new-chat-button:hover{background:#185d53}.quiet-button:hover{border-color:#59cbb7;color:#fff}.new-chat-button:disabled,.quiet-button:disabled{opacity:.45;cursor:wait}
.history-count{display:inline-grid;place-items:center;min-width:16px;height:16px;margin-left:5px;padding:0 3px;border-radius:8px;color:#d9fff5;background:#25665d;font-size:9px;font-weight:800}
.conversation-history{flex:0 0 auto;max-height:250px;overflow:auto;padding:10px 18px;border-bottom:1px solid #253945;background:#0b1a23}.history-heading{display:flex;align-items:baseline;justify-content:space-between;gap:8px;margin-bottom:8px}.history-heading strong{font-size:12px}.history-heading small{color:#718994;font-size:9px}.history-list{display:grid;gap:5px}.history-item{width:100%;display:flex;align-items:center;justify-content:space-between;gap:8px;padding:8px 9px;border:1px solid #294451;border-radius:5px;background:#102733;color:#dcecef;text-align:left;cursor:pointer}.history-item:hover,.history-item.active{border-color:#4ebca8;background:#143b3d}.history-item span{min-width:0;display:grid;gap:3px}.history-item strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:11px}.history-item small{color:#8fa7b0;font-size:9px}.history-item i{flex:0 0 auto;color:#78949c;font-size:16px;font-style:normal;line-height:1}.history-item i:hover{color:#ff9b9b}.history-empty{padding:8px 0;color:#8298a2;font-size:10px;line-height:1.45}
.guidance{flex:0 0 auto;padding:16px 18px 15px;border-bottom:1px solid #253945;background:#10212b}.guidance-meta{display:flex;align-items:center;justify-content:space-between;color:#9db2bd;font-size:12px;font-weight:700}.phase{padding:3px 7px;border:1px solid #397063;border-radius:4px;background:#12372f;color:#85e1c7}.phase[data-phase="post_fire"]{border-color:#526a89;background:#1a2d45;color:#b9d7ff}.phase[data-phase="pre_fire"]{border-color:#77662f;background:#332d15;color:#f1d783}
.progress-track{height:4px;margin:10px 0 14px;overflow:hidden;background:#2a3a42}.progress-track span{display:block;height:100%;background:#42c7ad;transition:width .25s ease}.guidance-copy .stage-name{margin:0 0 5px;color:#69d4bd;font-size:12px;font-weight:800}.guidance-copy h2{margin:0;color:#f5fafb;font-size:18px;line-height:1.35}.guidance-copy>p:last-child{margin:7px 0 0;color:#b8c8cf;font-size:14px;line-height:1.55}.run-line{display:flex;align-items:center;gap:8px;margin-top:11px;color:#91a6b0;font-size:11px}.run-line code{min-width:0;overflow:hidden;text-overflow:ellipsis;color:#c3d3d9}.run-line span:last-child{margin-left:auto;white-space:nowrap}
.spread-configuration{display:grid;gap:10px;margin-top:13px;padding:11px;border:1px solid #356458;border-radius:6px;background:#0c2928}.spread-data-summary{display:grid;gap:3px}.spread-data-summary span{color:#8fb2ad;font-size:10px;font-weight:800}.spread-data-summary strong{color:#effffb;font-size:14px}.spread-data-summary small{color:#90aaa9;font-size:10px}.spread-configuration-form{display:grid;grid-template-columns:1fr 1fr;gap:8px}.spread-configuration-form label{display:grid;gap:4px;color:#a9c2c0;font-size:10px}.spread-configuration-form label div{display:flex;align-items:center;gap:5px}.spread-configuration-form input{width:100%;min-width:0;padding:7px 8px;border:1px solid #39665e;border-radius:4px;background:#081d20;color:#f4fffd}.spread-configuration-form em{color:#8fa8a6;font-size:10px;font-style:normal;white-space:nowrap}.spread-configuration-form p{grid-column:1/-1;margin:0;color:#87a29f;font-size:10px;line-height:1.45}.spread-configuration-form button{grid-column:1/-1;padding:8px;border:1px solid #42a18e;border-radius:4px;background:#176558;color:#edfffb;font-weight:800;cursor:pointer}.spread-configuration-form button:disabled{opacity:.5;cursor:wait}
.next-actions{display:grid;gap:7px;margin-top:14px}.section-label{color:#8299a4;font-size:11px;font-weight:800}.choice{width:100%;min-height:58px;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:9px 11px;border:1px solid #34505d;border-radius:6px;background:#122b36;color:#eaf4f6;text-align:left;cursor:pointer}.choice:hover{border-color:#5ebead;background:#173540}.choice.primary{border-color:#2b8d7d;background:#145047}.choice:disabled{opacity:.55;cursor:wait}.choice span{min-width:0}.choice em,.choice b,.choice small{display:block}.choice em{margin-bottom:3px;color:#69d4bd;font-size:9px;font-style:normal;font-weight:800}.choice b{font-size:14px;line-height:1.35}.choice small{margin-top:3px;color:#a9bec6;font-size:12px;line-height:1.4}.choice i{flex:0 0 auto;color:#83dfcb;font-size:18px;font-style:normal}.action-feedback{display:grid;gap:4px;margin-top:10px;padding:9px 10px;border-left:3px solid #4ec9ae;background:#0c302e}.action-feedback.running{border-color:#eab308;background:#302b12}.action-feedback.error{border-color:#ef6464;background:#341a20}.action-feedback span{color:#8edbca;font-size:9px;font-weight:800}.action-feedback.running span{color:#f3d96b}.action-feedback.error span{color:#f3a1a1}.action-feedback strong{font-size:12px}.action-feedback p{margin:0;color:#bdccd2;font-size:11px;line-height:1.45}.report-link{display:block;margin-top:10px;color:#88d8ff;font-size:12px;text-decoration:none}.guidance-error{margin:10px 0 0;color:#f2a9a9;font-size:12px;line-height:1.45}
.conversation-heading{flex:0 0 auto;display:flex;justify-content:space-between;align-items:center;gap:10px;padding:11px 18px 7px;color:#dce8ec;font-size:13px;font-weight:800}.conversation-heading small{color:#718994;font-size:10px;font-weight:500;text-align:right}
.messages{flex:1;min-height:90px;overflow:auto;display:flex;flex-direction:column;gap:10px;padding:5px 18px 14px}.messages article{max-width:94%;padding:10px 12px;border-left:2px solid #3c5966;background:#10232e}.messages article.user{align-self:flex-end;border-left:0;border-right:2px solid #48bda7;background:#123c3d}.messages article small{color:#91a7b2;font-size:11px;font-weight:700}.messages article p{margin:4px 0 0;color:#e7f0f3;font-size:14px;line-height:1.6;white-space:pre-wrap}.messages article span{display:block;margin-top:6px;color:#69cbb7;font-size:10px;line-height:1.4}.pending{margin:0;color:#9bb0ba;font-size:13px}
.agent-tools{flex:0 0 auto;border-top:1px solid #253945;background:#0d1d28}.agent-tools summary{padding:9px 18px;color:#9fb3bc;font-size:12px;cursor:pointer}.import-fields{display:grid;grid-template-columns:1fr 1fr;gap:8px;padding:2px 18px 13px}.import-fields label{display:grid;gap:4px;color:#829aa5;font-size:11px}.import-fields input,.import-fields select,.import-fields button{min-width:0;padding:8px;border:1px solid #35515e;border-radius:4px;background:#102733;color:#ecf5f7;font-size:12px}.import-fields>input[type=file],.import-fields>button{grid-column:span 2}.import-fields button{cursor:pointer}.import-fields button:disabled{opacity:.5}
form{flex:0 0 auto;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;padding:12px 18px 14px;border-top:1px solid #253945;background:#0b1821}textarea{min-width:0;resize:none;padding:10px 11px;border:1px solid #38515e;border-radius:6px;background:#10242f;color:#f2f7f8;font:inherit;font-size:14px;line-height:1.5}textarea:focus{outline:1px solid #49baa6;border-color:#49baa6}form button{align-self:stretch;min-width:58px;border:1px solid #38bda5;border-radius:6px;background:#147a6d;color:#fff;font-size:13px;font-weight:800;cursor:pointer}form button:disabled{opacity:.45}
@media (max-height:760px){.guidance{padding-top:12px;padding-bottom:11px}.guidance-copy>p:last-child{display:none}.choice{min-height:46px}.choice small{display:none}.messages{min-height:70px}}
</style>
