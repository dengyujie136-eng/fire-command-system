import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { assistantAPI, workflowAPI } from '../api/modules'
import { useFireEventStore } from './fireEventStore'

export type AssistantTrace = {
  tool: string
  status: string
  [key: string]: any
}

export type AssistantMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  trace?: AssistantTrace[]
  createdAt: string
}

const HISTORY_KEY = 'fire-command-ai-assistant-history'
const EVENT_KEY = 'fire-command-current-historical-event'

function readJson<T>(key: string, fallback: T): T {
  try {
    const value = JSON.parse(localStorage.getItem(key) || '')
    return value as T
  } catch {
    return fallback
  }
}

function text(value: any) {
  return String(value || '').toLowerCase()
}

function extractUserOverride(message: string) {
  const rules = [
    { keys: ['风速', 'wind speed'], field: 'wind_speed_m_s' },
    { keys: ['风向', 'wind direction'], field: 'wind_direction_deg' },
    { keys: ['温度', 'temperature'], field: 'temperature_c' },
    { keys: ['湿度', 'humidity'], field: 'humidity_percent' },
    { keys: ['降水', '降雨', 'precipitation'], field: 'precipitation_mm' },
    { keys: ['燃料湿度', 'fuel moisture'], field: 'fuel_moisture' },
    { keys: ['fwi'], field: 'fire_weather_index' },
  ]
  const overrides: Record<string, number> = {}
  for (const rule of rules) {
    if (!rule.keys.some((key) => text(message).includes(key))) continue
    const matchedKey = rule.keys.find((key) => text(message).includes(key)) || rule.keys[0]
    const escapedKey = matchedKey.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    const match = message.match(new RegExp(`${escapedKey}\\s*(?:为|to|=|:)?\\s*(-?\\d+(?:\\.\\d+)?)`, 'i'))
    if (match) overrides[rule.field] = Number(match[1])
  }
  return Object.keys(overrides).length ? overrides : null
}

export const useAssistantStore = defineStore('assistant', () => {
  const messages = ref<AssistantMessage[]>(readJson<AssistantMessage[]>(HISTORY_KEY, []))
  const currentEventId = ref<string | null>(null)
  const currentHistoricalEventId = ref(localStorage.getItem(EVENT_KEY) || 'dixie_fire_2021')
  const workflowId = ref<string | null>(null)
  const toolStatus = ref<AssistantTrace[]>([])
  const loading = ref(false)
  const error = ref('')
  const initialized = ref(false)
  const fireEvent = useFireEventStore()

  const hasMessages = computed(() => messages.value.length > 0)
  const latestMessage = computed(() => messages.value[messages.value.length - 1] || null)

  function persist() {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(messages.value.slice(-40)))
    if (currentHistoricalEventId.value) localStorage.setItem(EVENT_KEY, currentHistoricalEventId.value)
  }

  function initialize() {
    if (initialized.value) return
    initialized.value = true
    currentEventId.value = fireEvent.eventId
    if (!messages.value.length) {
      messages.value.push({
        id: crypto.randomUUID(),
        role: 'assistant',
        content: '智能应急助手已在线。我可以查询历史火灾、启动综合推演、执行灾前灾后复盘并生成报告。',
        createdAt: new Date().toISOString(),
      })
      persist()
    }
  }

  function pushMessage(message: Omit<AssistantMessage, 'id' | 'createdAt'>) {
    messages.value.push({ ...message, id: crypto.randomUUID(), createdAt: new Date().toISOString() })
    persist()
  }

  function setToolStatus(trace: AssistantTrace[]) {
    toolStatus.value = trace.map((item) => ({
      ...item,
      label: item.tool,
      status: item.status || 'completed',
    }))
  }

  async function rerunFromUserInput(message: string) {
    const override = extractUserOverride(message)
    if (!override || !currentEventId.value) return null
    toolStatus.value = [{ tool: 'WorkflowAgent.rerun_spread', status: 'running', label: '正在重新推演火势...' }]
    const result = await workflowAPI.rerunSpread(currentEventId.value, {
      horizon_minutes: 120,
      step_minutes: 30,
      prefer_forefire: true,
      include_report: false,
      user_environment_override: { ...override, source_mode: 'user_input' },
    })
    const data = result?.data || result
    fireEvent.applySpreadRun(data.spread)
    fireEvent.applyDecisionRun({ data: data.decision })
    fireEvent.applyRecommendationPackage({ data: data.recommendations })
    workflowId.value = data.spread?.run?.run_id || workflowId.value
    toolStatus.value = [
      { tool: 'WorkflowAgent.rerun_spread', status: 'completed', label: '火势、风险、路线和指挥结果已更新' },
    ]
    return data
  }

  async function sendMessage(content: string, page: string) {
    const message = content.trim()
    if (!message || loading.value) return null
    initialize()
    error.value = ''
    loading.value = true
    toolStatus.value = [{ tool: 'Assistant', status: 'running', label: '正在理解请求...' }]
    pushMessage({ role: 'user', content: message })
    try {
      const result = await assistantAPI.chat({
        message,
        current_event_id: currentEventId.value || fireEvent.eventId,
        current_historical_event_id: currentHistoricalEventId.value,
        page,
      })
      const data = result?.data || result
      if (data.selected_event?.event_id) {
        currentHistoricalEventId.value = data.selected_event.event_id
        persist()
      }
      const workflowResult = data.tool_results?.find((item: any) => item.tool === 'start_fire_workflow')?.result
      currentEventId.value = workflowResult?.event_id || fireEvent.eventId || currentEventId.value
      workflowId.value = workflowResult?.spread_run_id || workflowId.value
      setToolStatus(data.tool_trace || [])
      pushMessage({ role: 'assistant', content: data.message || '工具调用已完成。', trace: data.tool_trace || [] })
      if (extractUserOverride(message)) await rerunFromUserInput(message)
      return data
    } catch (cause: any) {
      error.value = cause?.message || 'Assistant 请求失败'
      toolStatus.value = [{ tool: 'Assistant', status: 'failed', label: error.value }]
      pushMessage({ role: 'assistant', content: error.value })
      throw cause
    } finally {
      loading.value = false
    }
  }

  function clearConversation() {
    messages.value = []
    toolStatus.value = []
    error.value = ''
    persist()
    initialize()
  }

  return {
    messages,
    currentEventId,
    currentHistoricalEventId,
    workflowId,
    toolStatus,
    loading,
    error,
    hasMessages,
    latestMessage,
    initialize,
    sendMessage,
    clearConversation,
  }
})
