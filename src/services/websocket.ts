import { ref } from 'vue'

const configuredBase = import.meta.env.VITE_FIRE_AGENT_WS_BASE_URL?.trim()
const defaultProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
const WS_BASE_URL = configuredBase || `${defaultProtocol}//${window.location.host}`

let socket: WebSocket | null = null
let reconnectTimer: ReturnType<typeof setTimeout> | undefined

export const wsConnected = ref(false)

function connectSystemChannel() {
  if (socket?.readyState === WebSocket.OPEN || socket?.readyState === WebSocket.CONNECTING) return

  socket = new WebSocket(`${WS_BASE_URL}/ws/system`)
  socket.onopen = () => {
    wsConnected.value = true
    socket?.send(JSON.stringify({ type: 'ping', payload: { source: 'frontend' } }))
  }
  socket.onclose = () => {
    wsConnected.value = false
    reconnectTimer = window.setTimeout(connectSystemChannel, 5000)
  }
  socket.onerror = () => socket?.close()
}

export function initWebSocket() {
  if (reconnectTimer) window.clearTimeout(reconnectTimer)
  connectSystemChannel()
}
