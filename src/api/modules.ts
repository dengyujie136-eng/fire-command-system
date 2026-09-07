import api from './index'

const FIRE_AGENT_API_BASE_URL = import.meta.env.VITE_FIRE_AGENT_API_BASE_URL || 'http://localhost:8200'

async function fireAgentRequest(path: string, options: RequestInit = {}) {
  const response = await fetch(`${FIRE_AGENT_API_BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {})
    },
    ...options
  })
  if (!response.ok) {
    const text = await response.text()
    throw new Error(`fire_agent_backend request failed: ${response.status} ${text}`)
  }
  return response.json()
}

export interface FireItem {
  id: string
  lat: number
  lng: number
  level: 'high' | 'medium' | 'low'
  risk_hint: string
  [key: string]: any
}

export interface FireStat {
  summary_cards: any[]
  chart_data: any
  wind_params: any
  level_distribution: any
  temperature: string
  weather: string
}

export const fireAPI = {
  getList: () => api.get<any, FireItem[]>('/api/fire/list'),
  getStat: () => api.get<any, FireStat>('/api/fire/stat'),
  getHistory: () => api.get('/api/fire/history'),
  getFireLine: (sceneId: string) => api.get(`/api/b/scene/${sceneId}/fire-line`),
  getSceneStatus: (sceneId: string) => api.get(`/api/b/scene/${sceneId}/status`),
}

export const eventAPI = {
  startSimulated: (data: any = {}) => fireAgentRequest('/api/events/simulated/start', {
    method: 'POST',
    body: JSON.stringify(data)
  }),
  getCurrent: () => fireAgentRequest('/api/events/current'),
  getDetail: (eventId: string) => fireAgentRequest(`/api/events/${eventId}`),
  getTimeline: (eventId: string) => fireAgentRequest(`/api/events/${eventId}/timeline`),
  close: (eventId: string) => fireAgentRequest(`/api/events/${eventId}/close`, {
    method: 'POST',
    body: JSON.stringify({})
  })
}

export const scenarioAPI = {
  getList: () => fireAgentRequest('/api/scenarios')
}

export const clockAPI = {
  get: (eventId: string) => fireAgentRequest(`/api/events/${eventId}/clock`),
  start: (eventId: string, data: any = {}) => fireAgentRequest(`/api/events/${eventId}/clock/start`, {
    method: 'POST',
    body: JSON.stringify(data)
  }),
  pause: (eventId: string) => fireAgentRequest(`/api/events/${eventId}/clock/pause`, {
    method: 'POST',
    body: JSON.stringify({})
  }),
  resume: (eventId: string) => fireAgentRequest(`/api/events/${eventId}/clock/resume`, {
    method: 'POST',
    body: JSON.stringify({})
  }),
  reset: (eventId: string) => fireAgentRequest(`/api/events/${eventId}/clock/reset`, {
    method: 'POST',
    body: JSON.stringify({})
  }),
  step: (eventId: string, data: any = {}) => fireAgentRequest(`/api/events/${eventId}/clock/step`, {
    method: 'POST',
    body: JSON.stringify(data)
  })
}

export const observationAPI = {
  simulate: (eventId: string) => fireAgentRequest(`/api/events/${eventId}/observations/simulate`, {
    method: 'POST',
    body: JSON.stringify({})
  }),
  getList: (eventId: string) => fireAgentRequest(`/api/events/${eventId}/observations`),
  getEvidenceChain: (eventId: string) => fireAgentRequest(`/api/events/${eventId}/evidence-chain`),
  getFusion: (eventId: string) => fireAgentRequest(`/api/events/${eventId}/fusion`),
  getTrustedFirePoint: (eventId: string) => fireAgentRequest(`/api/events/${eventId}/trusted-fire-point`)
}

export const spreadAPI = {
  create: (eventId: string, data: any = {}) => fireAgentRequest(`/api/events/${eventId}/spread-runs`, {
    method: 'POST',
    body: JSON.stringify(data)
  }),
  getLatest: (eventId: string) => fireAgentRequest(`/api/events/${eventId}/spread-runs/latest`),
  getSteps: (runId: string) => fireAgentRequest(`/api/spread-runs/${runId}/steps`)
}

export const decisionAPI = {
  create: (eventId: string, data: any = {}) => fireAgentRequest(`/api/events/${eventId}/decision-runs`, {
    method: 'POST',
    body: JSON.stringify(data)
  }),
  getLatest: (eventId: string) => fireAgentRequest(`/api/events/${eventId}/decision-runs/latest`),
  getPackets: (decisionRunId: string) => fireAgentRequest(`/api/decision-runs/${decisionRunId}/packets`)
}

export const recommendationAPI = {
  getLatest: (eventId: string) => fireAgentRequest(`/api/events/${eventId}/recommendations/latest`),
  regenerate: (eventId: string, data: any = {}) => fireAgentRequest(`/api/events/${eventId}/recommendations/regenerate`, {
    method: 'POST',
    body: JSON.stringify(data)
  })
}

export const recalculationAPI = {
  createDisturbance: (eventId: string, data: any) => fireAgentRequest(`/api/events/${eventId}/disturbances`, {
    method: 'POST',
    body: JSON.stringify(data)
  }),
  recalculate: (eventId: string, data: any) => fireAgentRequest(`/api/events/${eventId}/recalculate`, {
    method: 'POST',
    body: JSON.stringify(data)
  }),
  getLatest: (eventId: string) => fireAgentRequest(`/api/events/${eventId}/recalculations/latest`)
}

export const reportAPI = {
  create: (eventId: string, data: any = {}) => fireAgentRequest(`/api/events/${eventId}/reports`, {
    method: 'POST',
    body: JSON.stringify(data)
  }),
  getLatest: (eventId: string) => fireAgentRequest(`/api/events/${eventId}/reports/latest`),
  get: (reportId: string) => fireAgentRequest(`/api/reports/${reportId}`),
  downloadUrl: (reportId: string) => `${FIRE_AGENT_API_BASE_URL}/api/reports/${reportId}/download.pdf`,
  markdownDownloadUrl: (reportId: string) => `${FIRE_AGENT_API_BASE_URL}/api/reports/${reportId}/download`
}

export const resourceAPI = {
  getList: () => api.get('/api/resource/list'),
  getStat: () => api.get('/api/resource/stat'),
}

export const uavAPI = {
  getList: () => api.get('/api/uav/list'),
  getMissionList: () => api.get('/api/uav/mission/list'),
  getMission: (id: string) => api.get(`/api/uav/mission/${id}`),
  control: (data: any) => api.post('/api/uav/control', data),
  schedule: (data: any) => api.post('/api/b/decision/uav/schedule', data),
}

export const sensorAPI = {
  getList: () => api.get('/api/sensor/list'),
}

export const weatherAPI = {
  get: () => api.get('/api/weather'),
}

export const fusionAPI = {
  getResult: () => api.get('/api/fusion/result'),
  getPreview: () => api.get('/api/fusion/preview'),
}

export const mapAPI = {
  getAll: () => api.get('/api/map/all'),
  getElevation: () => api.get('/api/map/elevation'),
}

export const routeAPI = {
  planEscape: (data: any) => api.post('/api/b/decision/escape-route', data),
  planFirefighter: (data: any) => api.post('/api/b/decision/firefighter-route', data),
  save: (data: any) => api.post('/api/route/save', data),
}

export const dispatchAPI = {
  getList: () => api.get('/api/dispatch/list'),
  create: (data: any) => api.post('/api/dispatch/create', data),
  send: (data: any) => api.post('/api/dispatch/send', data),
  getResourceDispatch: (sceneId: string) => api.get(`/api/b/decision/resource-dispatch/${sceneId}`),
}

export const personnelAPI = {
  getList: () => api.get('/api/personnel/list'),
}

export const simulateAPI = {
  getHotspot: () => api.get('/hotspot'),
  start: (data: any) => api.post('/api/simulate', data),
  getResult: (taskId: string) => api.get(`/api/simulate/result/${taskId}`),
  getHistory: () => api.get('/api/simulate/history'),
}

export const agentAPI = {
  analyze: (data: any) => api.post('/api/agent/analyze', data),
  simulate: (data: any) => api.post('/api/agent/simulate', data),
}

export const videoAPI = {
  getList: () => api.get('/api/video/list'),
  getStream: (cameraId: string) => `/api/video/stream?camera_id=${cameraId}`,
}

export const commandAPI = {
  getOverview: () => api.get('/api/command/overview'),
}

export const systemAPI = {
  getStatus: () => api.get('/api/system/status'),
}
