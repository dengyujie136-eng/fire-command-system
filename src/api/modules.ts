const FIRE_AGENT_API_BASE_URL = import.meta.env.VITE_FIRE_AGENT_API_BASE_URL ?? ''

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
export const dixieFireAPI = {
  getEvent: () => fireAgentRequest('/api/data/events/dixie_fire_2021'),
  getHotspots: (params: { limit?: number; offset?: number; status?: string; aggregate?: boolean } = {}) => {
    const query = new URLSearchParams()
    query.set('limit', String(params.limit ?? 1000))
    query.set('offset', String(params.offset ?? 0))
    if (params.status) query.set('status', params.status)
    if (params.aggregate !== undefined) query.set('aggregate', String(params.aggregate))
    return fireAgentRequest(`/api/data/events/dixie_fire_2021/hotspots?${query.toString()}`)
  },
  getBurnedArea: () => fireAgentRequest('/api/data/events/dixie_fire_2021/burned-area?include_geometry=true'),
  getWeatherHourly: (params: { limit?: number; offset?: number } = {}) => {
    const query = new URLSearchParams()
    query.set('limit', String(params.limit ?? 1000))
    query.set('offset', String(params.offset ?? 0))
    return fireAgentRequest(`/api/data/events/dixie_fire_2021/weather-hourly?${query.toString()}`)
  }
}

export const dataCatalogAPI = {
  getHistorical: () => fireAgentRequest('/api/data-agent/catalog/dixie_fire_2021'),
  getRealtime: () => fireAgentRequest('/api/data-agent/realtime-catalog'),
  getGoesManifest: () => fireAgentRequest('/api/realtime-demo/manifest'),
  getFirmsArchiveManifest: () => fireAgentRequest('/api/realtime-demo/firms-archive/manifest')
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

export const workflowAPI = {
  rerunSpread: (eventId: string, data: any = {}) => fireAgentRequest(`/api/events/${eventId}/workflow/rerun-spread`, {
    method: 'POST',
    body: JSON.stringify(data)
  }),
  startHistorical: (historicalEventId: string, data: any = { include_report: true }) => fireAgentRequest(`/api/historical-events/${historicalEventId}/workflow/start`, {
    method: 'POST',
    body: JSON.stringify(data)
  })
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


export const historicalEventsAPI = {
  search: (params: { country?: string; region?: string; last_years?: number; sort_by?: string; limit?: number } = {}) => {
    const query = new URLSearchParams()
    query.set('country', params.country ?? 'United States')
    query.set('region', params.region ?? 'California')
    query.set('last_years', String(params.last_years ?? 5))
    query.set('sort_by', params.sort_by ?? 'burned_area_km2')
    query.set('limit', String(params.limit ?? 5))
    return fireAgentRequest(`/api/data-agent/historical-events?${query.toString()}`)
  },
  query: (data: any) => fireAgentRequest('/api/data-agent/historical-events/query', {
    method: 'POST',
    body: JSON.stringify(data)
  }),
  get: (eventId: string) => fireAgentRequest(`/api/data-agent/historical-events/${eventId}`)
}

export const assistantAPI = {
  chat: (data: any) => fireAgentRequest('/api/assistant/chat', {
    method: 'POST',
    body: JSON.stringify(data)
  })
}

export const disasterReviewAPI = {
  getAnalysis: (eventId: string) => fireAgentRequest(`/api/review/events/${eventId}/analysis`)
}

export const ruleBaseAPI = {
  getFireEmergencyRules: () => fireAgentRequest('/api/rules/fire-emergency')
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
