import api from './index'

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
