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
