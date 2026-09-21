<template>
  <div class="ai-assistant">
    <section v-if="open" class="assistant-window" aria-label="智能应急助手">
      <header class="assistant-header">
        <div class="assistant-title">
          <div class="assistant-mark">AI</div>
          <div>
            <strong>智能应急助手</strong>
            <span><i class="online-dot"></i>在线 · 工具链已接入</span>
          </div>
        </div>
        <div class="header-actions">
          <button type="button" title="清空对话" @click="assistant.clearConversation">清空</button>
          <button type="button" title="关闭助手" @click="open = false">×</button>
        </div>
      </header>

      <div class="event-context">
        <span>当前事件</span>
        <strong>{{ currentEventLabel }}</strong>
        <small v-if="assistant.workflowId">流程 {{ assistant.workflowId }}</small>
      </div>

      <div ref="messagesRef" class="messages" aria-live="polite">
        <article v-for="item in assistant.messages" :key="item.id" :class="['message', item.role]">
          <div class="message-meta">{{ item.role === 'user' ? '你' : '智能应急助手' }}</div>
          <p>{{ item.content }}</p>
          <div v-if="item.trace?.length" class="message-trace">
            <span v-for="trace in item.trace" :key="item.id + trace.tool" :class="['trace-chip', trace.status]">
              <i></i>{{ toolLabel(trace.tool) }} · {{ statusLabel(trace.status) }}
            </span>
          </div>
        </article>
        <article v-if="assistant.loading" class="message assistant pending-message">
          <div class="message-meta">智能应急助手</div>
          <p>{{ activeStatus }}</p>
        </article>
      </div>

      <section v-if="assistant.toolStatus.length" class="tool-status" aria-label="工具调用状态">
        <div class="tool-status-title"><span>工作过程</span><b>{{ assistant.loading ? '执行中' : '最近一次' }}</b></div>
        <div v-for="item in assistant.toolStatus.slice(-4)" :key="item.tool + item.status + item.label" class="tool-row">
          <i :class="['tool-indicator', item.status]"></i>
          <span>{{ item.label || toolLabel(item.tool) }}</span>
          <small>{{ statusLabel(item.status) }}</small>
        </div>
      </section>

      <form class="composer" @submit.prevent="sendMessage">
        <textarea
          v-model="draft"
          rows="2"
          :disabled="assistant.loading"
          placeholder="输入指令，例如：推演近五年加州最大火灾"
          @keydown.enter.exact.prevent="sendMessage"
        ></textarea>
        <button type="submit" class="send-button" :disabled="assistant.loading || !draft.trim()">发送</button>
      </form>
    </section>

    <button class="assistant-toggle" type="button" :class="{ active: open }" :title="open ? '关闭智能应急助手' : '打开智能应急助手'" @click="toggleOpen">
      <span class="toggle-icon">AI</span>
      <span>助手</span>
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAssistantStore } from '../stores/assistantStore'
import { useFireEventStore } from '../stores/fireEventStore'

const assistant = useAssistantStore()
const fireEvent = useFireEventStore()
const router = useRouter()
const route = useRoute()
const open = ref(false)
const draft = ref('')
const messagesRef = ref<HTMLElement | null>(null)

const currentEventLabel = computed(() => {
  if (fireEvent.eventDetail?.name) return fireEvent.eventDetail.name
  if (assistant.currentHistoricalEventId) return assistant.currentHistoricalEventId.replaceAll('_', ' ')
  return '未选择事件'
})

const activeStatus = computed(() => {
  const active = [...assistant.toolStatus].reverse().find((item) => item.status === 'running')
  return active?.label || '正在调用应急分析工具...'
})

const labels: Record<string, string> = {
  Assistant: 'Assistant',
  'LLM.function_calling': 'LLM 工具选择',
  DeterministicToolRouter: '工具路由',
  'DataAgent.query_historical_fire_events': '历史火灾数据库',
  'WorkflowAgent.start_fire_workflow': '综合推演流程',
  'WorkflowAgent.rerun_spread': '火势重推演',
  'ReviewAgent.start_disaster_review': '灾前灾后复盘',
  'ReportAgent.generate_report': '灾情报告',
}

function toolLabel(tool: string) {
  return labels[tool] || tool
}

function statusLabel(status: string) {
  return ({ running: '进行中', completed: '完成', failed: '失败', ready: '待执行' } as Record<string, string>)[status] || status
}

function toggleOpen() {
  open.value = !open.value
  if (open.value) assistant.initialize()
}

async function hydrateWorkflowAction(action: any) {
  if (action.historical_event_id) assistant.currentHistoricalEventId = action.historical_event_id
  if (action.event_id) assistant.currentEventId = action.event_id
  if (action.route) await router.push(action.route)
  await fireEvent.loadCurrentEvent()
  await Promise.allSettled([
    fireEvent.loadEventDetail(),
    fireEvent.loadEventTimeline(),
    fireEvent.loadClockState(),
    fireEvent.loadObservationState(),
    fireEvent.loadLatestSpreadRun(),
    fireEvent.loadLatestDecisionRun(),
    fireEvent.loadLatestRecommendations(),
    fireEvent.loadLatestReport(),
  ])
}

async function executeActions(actions: any[] = []) {
  for (const action of actions) {
    if (action.type === 'hydrate_workflow') {
      await hydrateWorkflowAction(action)
    } else if (action.type === 'navigate') {
      if (action.query?.event_id) assistant.currentHistoricalEventId = action.query.event_id
      await router.push({ path: action.route, query: action.query || {} })
    }
  }
}

async function sendMessage() {
  const content = draft.value.trim()
  if (!content || assistant.loading) return
  draft.value = ''
  try {
    const data = await assistant.sendMessage(content, route.path)
    await executeActions(data?.actions || [])
    if (/风速|风向|温度|湿度|降水|降雨|燃料湿度|FWI|wind speed|wind direction|temperature|humidity/i.test(content) && route.path !== '/command-center') {
      await router.push('/command-center')
    }
  } catch {
    // The store records the error and exposes it in the conversation.
  }
}

async function scrollBottom() {
  await nextTick()
  if (messagesRef.value) messagesRef.value.scrollTop = messagesRef.value.scrollHeight
}

onMounted(() => assistant.initialize())
watch(() => assistant.messages.length, scrollBottom)
watch(() => assistant.loading, scrollBottom)
</script>

<style scoped>
.ai-assistant { position: fixed; right: 24px; bottom: 24px; z-index: 2100; color: #e5f2ff; font-family: inherit; }
.assistant-toggle { display: inline-flex; align-items: center; gap: 7px; min-height: 48px; padding: 0 16px 0 9px; border: 1px solid rgba(45,212,191,.68); border-radius: 999px; background: #0f766e; color: #fff; font: inherit; font-weight: 800; cursor: pointer; box-shadow: 0 12px 30px rgba(0,0,0,.38); }
.assistant-toggle.active { background: #134e4a; }
.toggle-icon, .assistant-mark { display: grid; place-items: center; width: 32px; height: 32px; border-radius: 50%; background: #ccfbf1; color: #115e59; font-size: 11px; font-weight: 900; }
.assistant-window { position: absolute; right: 0; bottom: 62px; width: min(430px, calc(100vw - 30px)); height: min(600px, calc(100vh - 100px)); display: grid; grid-template-rows: auto auto minmax(0,1fr) auto auto; overflow: hidden; border: 1px solid rgba(103,232,249,.28); border-radius: 10px; background: #081421; box-shadow: 0 24px 70px rgba(0,0,0,.5); }
.assistant-header, .event-context, .tool-status, .composer { border-color: rgba(148,163,184,.18); }
.assistant-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 14px; border-bottom: 1px solid rgba(148,163,184,.18); background: #0b1f2d; }
.assistant-title { display: flex; align-items: center; gap: 10px; }
.assistant-title strong, .assistant-title span { display: block; }
.assistant-title strong { font-size: 14px; }
.assistant-title span { margin-top: 4px; color: #8fb2c6; font-size: 11px; }
.online-dot { display: inline-block; width: 6px; height: 6px; margin-right: 5px; border-radius: 50%; background: #34d399; box-shadow: 0 0 10px #34d399; }
.header-actions { display: flex; gap: 5px; }
.header-actions button, .send-button { min-height: 30px; border: 1px solid rgba(45,212,191,.35); border-radius: 6px; background: #12394b; color: #d9f7ff; font: inherit; cursor: pointer; }
.header-actions button:first-child { padding: 0 8px; font-size: 11px; }
.header-actions button:last-child { width: 30px; font-size: 20px; line-height: 1; }
.event-context { display: grid; grid-template-columns: auto minmax(0,1fr) auto; align-items: center; gap: 8px; padding: 8px 14px; border-bottom: 1px solid rgba(148,163,184,.16); background: #0a1926; font-size: 11px; }
.event-context span, .event-context small { color: #7f9caf; }
.event-context strong { overflow: hidden; color: #99f6e4; text-overflow: ellipsis; white-space: nowrap; }
.messages { min-height: 0; overflow: auto; display: grid; align-content: start; gap: 11px; padding: 14px; background: #07111b; }
.message { max-width: 92%; padding: 10px 11px; border: 1px solid rgba(148,163,184,.16); border-radius: 8px; background: #0f2335; }
.message.user { justify-self: end; border-color: rgba(45,212,191,.27); background: #12556a; }
.message-meta { margin-bottom: 5px; color: #8fb2c6; font-size: 10px; font-weight: 800; }
.message p { margin: 0; color: #e6f3fb; font-size: 13px; line-height: 1.55; white-space: pre-wrap; }
.pending-message { border-color: rgba(45,212,191,.3); }
.message-trace { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 8px; }
.trace-chip { display: inline-flex; align-items: center; gap: 4px; padding: 3px 6px; border: 1px solid rgba(148,163,184,.2); border-radius: 4px; color: #a8c2d1; font-size: 10px; }
.trace-chip i, .tool-indicator { display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: #64748b; }
.trace-chip.completed i, .tool-indicator.completed { background: #34d399; }
.trace-chip.running i, .tool-indicator.running { background: #fbbf24; box-shadow: 0 0 8px #fbbf24; }
.trace-chip.failed i, .tool-indicator.failed { background: #fb7185; }
.tool-status { padding: 9px 14px; border-top: 1px solid rgba(148,163,184,.16); background: #0a1926; }
.tool-status-title, .tool-row { display: flex; align-items: center; gap: 8px; }
.tool-status-title { justify-content: space-between; margin-bottom: 6px; color: #99f6e4; font-size: 11px; font-weight: 800; }
.tool-status-title b { color: #7f9caf; font-size: 10px; font-weight: 500; }
.tool-row { min-height: 20px; color: #d3e6ef; font-size: 11px; }
.tool-row span { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tool-row small { margin-left: auto; color: #7f9caf; }
.composer { display: grid; grid-template-columns: minmax(0,1fr) auto; gap: 8px; padding: 10px 12px 12px; border-top: 1px solid rgba(148,163,184,.18); background: #081421; }
.composer textarea { min-width: 0; resize: none; padding: 8px 9px; border: 1px solid rgba(148,163,184,.28); border-radius: 6px; outline: none; background: #0e1a2a; color: #e5f0ff; font: inherit; font-size: 12px; line-height: 1.4; }
.composer textarea:focus { border-color: rgba(45,212,191,.7); }
.send-button { align-self: end; min-width: 52px; padding: 0 9px; background: #0f766e; border-color: #14b8a6; font-size: 12px; font-weight: 800; }
.send-button:disabled { cursor: not-allowed; opacity: .45; }
@media (max-width: 640px) { .ai-assistant { right: 12px; bottom: 12px; } .assistant-window { right: -2px; width: min(430px, calc(100vw - 24px)); height: min(600px, calc(100vh - 82px)); } }
</style>
