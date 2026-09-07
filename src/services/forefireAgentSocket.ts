import { computed, ref } from 'vue'

type AgentStatus = 'idle' | 'connecting' | 'connected' | 'requesting' | 'streaming' | 'completed' | 'error' | 'closed'

type AgentRequest = {
  task_id?: string
  status?: string
  source?: string
  event_id?: string
  scene_id?: string
  ignition_point?: { longitude: number, latitude: number } | [number, number]
  forefire_json?: any
  file_path?: string
  weather?: Record<string, any> | null
  dem?: Record<string, any> | null
  resources?: Record<string, any> | null
  targets?: any[] | null
  include_coordinates?: boolean
}

const AGENT_API_BASE_URL = import.meta.env.VITE_AGENT_API_BASE_URL || 'http://localhost:8100'
const AGENT_WS_URL = import.meta.env.VITE_AGENT_WS_URL || 'ws://localhost:8100/ws/agent/forefire/decision'
const AGENT_WS_OPEN_TIMEOUT_MS = 10000
const AGENT_REST_TIMEOUT_MS = 180000

let socket: WebSocket | null = null

export const forefireAgentStatus = ref<AgentStatus>('idle')
export const forefireAgentConnected = computed(() => forefireAgentStatus.value === 'connected' || forefireAgentStatus.value === 'streaming')
export const forefireAgentMessages = ref<any[]>([])
export const forefireAgentResult = ref<any>(null)
export const forefireAgentError = ref('')

function pushAgentMessage(message: any) {
  forefireAgentMessages.value.unshift({
    received_at: new Date().toISOString(),
    ...message
  })
  if (forefireAgentMessages.value.length > 80) forefireAgentMessages.value.pop()
}

function normalizeSocketMessage(raw: string) {
  try {
    return JSON.parse(raw)
  } catch {
    return { type: 'text', content: raw }
  }
}

function extractAgentResult(message: any) {
  return message.payload || message.data || message
}

export function connectForeFireAgent() {
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) return socket

  forefireAgentStatus.value = 'connecting'
  forefireAgentError.value = ''

  socket = new WebSocket(AGENT_WS_URL)

  socket.onopen = () => {
    forefireAgentStatus.value = 'connected'
    pushAgentMessage({ type: 'connection', content: 'Agent WebSocket connected.' })
  }

  socket.onmessage = (event) => {
    const message = normalizeSocketMessage(event.data)
    const type = message.type || message.event || message.status
    forefireAgentStatus.value = type === 'completed' || type === 'decision_generated' || type === 'result'
      ? 'completed'
      : 'streaming'

    if (message.status === 'decision_generated' || message.type === 'result' || message.type === 'completed' || message.agent_outputs) {
      forefireAgentResult.value = extractAgentResult(message)
    }

    pushAgentMessage(message)
  }

  socket.onerror = () => {
    forefireAgentStatus.value = 'error'
    forefireAgentError.value = `Agent WebSocket connection failed: ${AGENT_WS_URL}`
  }

  socket.onclose = () => {
    if (forefireAgentStatus.value !== 'completed' && forefireAgentStatus.value !== 'error') {
      forefireAgentStatus.value = 'closed'
    }
    socket = null
  }

  return socket
}

export function closeForeFireAgent() {
  socket?.close()
  socket = null
  forefireAgentStatus.value = 'closed'
}

export function resetForeFireAgentState() {
  socket?.close()
  socket = null
  forefireAgentStatus.value = 'idle'
  forefireAgentMessages.value = []
  forefireAgentResult.value = null
  forefireAgentError.value = ''
}

async function waitForSocketOpen(ws: WebSocket) {
  if (ws.readyState === WebSocket.OPEN) return
  await new Promise<void>((resolve, reject) => {
    const timer = window.setTimeout(() => reject(new Error('Agent WebSocket connection timeout')), AGENT_WS_OPEN_TIMEOUT_MS)
    ws.addEventListener('open', () => {
      window.clearTimeout(timer)
      resolve()
    }, { once: true })
    ws.addEventListener('error', () => {
      window.clearTimeout(timer)
      reject(new Error('Agent WebSocket connection failed'))
    }, { once: true })
  })
}

async function requestByRest(payload: AgentRequest) {
  forefireAgentStatus.value = 'requesting'
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort('Agent REST request timeout'), AGENT_REST_TIMEOUT_MS)

  try {
    const response = await fetch(`${AGENT_API_BASE_URL}/api/agent/forefire/decision`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: controller.signal
    })

    if (!response.ok) {
      const text = await response.text()
      throw new Error(`Agent REST request failed: ${response.status} ${text}`)
    }

    const result = await response.json()
    forefireAgentResult.value = result
    forefireAgentStatus.value = 'completed'
    forefireAgentError.value = ''
    pushAgentMessage({
      type: 'result',
      transport: 'rest',
      status: result.status,
      content: `REST decision generated: ${result.recommended_plan?.name || result.status || 'done'}`,
      payload: result
    })
  } catch (error: any) {
    forefireAgentStatus.value = 'error'
    const errorMessage = error?.name === 'AbortError'
      ? `Agent REST request timed out after ${Math.round(AGENT_REST_TIMEOUT_MS / 1000)}s. The backend may still be busy generating the decision.`
      : (error?.message || '')
    forefireAgentError.value = `Agent backend is unreachable or failed: ${AGENT_API_BASE_URL}. ${errorMessage}`
    throw new Error(forefireAgentError.value)
  } finally {
    window.clearTimeout(timer)
  }
}

export async function requestForeFireAgentDecision(payload: AgentRequest) {
  forefireAgentError.value = ''
  forefireAgentResult.value = null
  forefireAgentMessages.value = []

  try {
    const ws = connectForeFireAgent()
    await waitForSocketOpen(ws)

    forefireAgentStatus.value = 'requesting'
    ws.send(JSON.stringify({
      type: 'forefire_decision_request',
      payload
    }))
    pushAgentMessage({ type: 'request', transport: 'websocket', content: 'Sent ForeFire decision request through WebSocket.' })
  } catch {
    pushAgentMessage({ type: 'fallback', transport: 'rest', content: 'WebSocket is unavailable, using REST fallback.' })
    await requestByRest(payload)
  }
}

export const forefireAgentConfig = {
  apiBaseUrl: AGENT_API_BASE_URL,
  wsUrl: AGENT_WS_URL
}
