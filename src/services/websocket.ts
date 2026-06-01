import { ref } from 'vue'

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8080'
const alertListeners: Function[] = []
const uavListeners: Function[] = []
let wsAlert: WebSocket | null = null
let wsUav: WebSocket | null = null
export const wsConnected = ref(false)

export const wsAlertData = ref<any[]>([])
export const wsUavData = ref<any[]>([])

export function connectAlert() {
  try {
    wsAlert = new WebSocket(`${WS_URL}/ws/alert`)
    wsAlert.onopen = () => {
      wsConnected.value = true
    }
    wsAlert.onmessage = (event) => {
      const data = JSON.parse(event.data)
      wsAlertData.value.unshift(data)
      if (wsAlertData.value.length > 50) wsAlertData.value.pop()
      alertListeners.forEach(cb => cb(data))
    }
    wsAlert.onclose = () => {
      wsConnected.value = false
      setTimeout(connectAlert, 5000)
    }
    wsAlert.onerror = () => {
      wsAlert?.close()
    }
  } catch (e) {
    console.error('WebSocket alert connection failed:', e)
  }
}

export function connectUav() {
  try {
    wsUav = new WebSocket(`${WS_URL}/ws/uav`)
    wsUav.onmessage = (event) => {
      const data = JSON.parse(event.data)
      wsUavData.value = data
      uavListeners.forEach(cb => cb(data))
    }
    wsUav.onclose = () => {
      setTimeout(connectUav, 5000)
    }
    wsUav.onerror = () => {
      wsUav?.close()
    }
  } catch (e) {
    console.error('WebSocket UAV connection failed:', e)
  }
}

export function onAlertMessage(cb: Function) {
  alertListeners.push(cb)
}

export function onUavMessage(cb: Function) {
  uavListeners.push(cb)
}

export function initWebSocket() {
  connectAlert()
  connectUav()
}
