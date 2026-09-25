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

export const assistantAPI = {
  chat: (data: any) => fireAgentRequest('/api/assistant/chat', {
    method: 'POST',
    body: JSON.stringify(data)
  }),
  nextSteps: (data: any) => fireAgentRequest('/api/assistant/next-steps', {
    method: 'POST',
    body: JSON.stringify(data)
  })
}

export const planningAPI = {
  preview: (data: any) => fireAgentRequest('/api/planning/preview', {
    method: 'POST',
    body: JSON.stringify(data)
  }),
  explainRoute: (data: any) => fireAgentRequest('/api/planning/explain-route', {
    method: 'POST',
    body: JSON.stringify(data)
  })
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

export const fireDataAPI = {
  getHourlyWeather: (eventId: string, limit = 5000) => fireAgentRequest(
    `/api/data/events/${encodeURIComponent(eventId)}/weather-hourly?limit=${encodeURIComponent(String(limit))}`
  )
}

export const visualVerificationAPI = {
  getCandidates: (eventId?: string) => fireAgentRequest(
    `/api/visual-verification/candidates${eventId ? `?event_id=${encodeURIComponent(eventId)}` : ''}`
  ),
  getImageryCatalog: (eventId: string) => fireAgentRequest(
    `/api/visual-verification/events/${encodeURIComponent(eventId)}/imagery-catalog`
  ),
  discoverLocalImagery: (eventId: string) => fireAgentRequest(
    `/api/visual-verification/events/${encodeURIComponent(eventId)}/discover-local-imagery`,
    { method: 'POST', body: JSON.stringify({}) }
  ),
  imageryPreviewUrl: (assetId: string) => (
    `${FIRE_AGENT_API_BASE_URL}/api/visual-verification/imagery-catalog/${encodeURIComponent(assetId)}/preview`
  ),
  extractImageCandidates: (assetId: string) => fireAgentRequest(
    `/api/visual-verification/imagery-catalog/${encodeURIComponent(assetId)}/extract-candidates`,
    { method: 'POST', body: JSON.stringify({}) }
  ),
  autoDetectCandidates: (assetId: string, candidateIds: string[], data: any = {}) => fireAgentRequest(
    `/api/visual-verification/imagery-catalog/${encodeURIComponent(assetId)}/auto-detect`,
    { method: 'POST', body: JSON.stringify({ candidate_ids: candidateIds, ...data }) }
  ),
  getCandidate: (visualCaseId: string) => fireAgentRequest(
    `/api/visual-verification/candidates/${encodeURIComponent(visualCaseId)}`
  ),
  excludeCandidate: (visualCaseId: string) => fireAgentRequest(
    `/api/visual-verification/candidates/${encodeURIComponent(visualCaseId)}`,
    { method: 'DELETE' }
  ),
  prepareDerivative: (visualCaseId: string, sourceAssetId: string, data: any = {}) => fireAgentRequest(
    `/api/visual-verification/candidates/${encodeURIComponent(visualCaseId)}/assets/${encodeURIComponent(sourceAssetId)}/derivatives`,
    { method: 'POST', body: JSON.stringify(data) }
  ),
  analyze: (visualCaseId: string, derivativeIds: string[]) => fireAgentRequest(
    `/api/visual-verification/candidates/${encodeURIComponent(visualCaseId)}/analyses`,
    { method: 'POST', body: JSON.stringify({ derivative_ids: derivativeIds }) }
  ),
  detect: (visualCaseId: string, derivativeIds: string[]) => fireAgentRequest(
    `/api/visual-verification/candidates/${encodeURIComponent(visualCaseId)}/professional-detections`,
    { method: 'POST', body: JSON.stringify({ derivative_ids: derivativeIds, image_size: 640 }) }
  ),
  review: (visualCaseId: string, derivativeIds: string[]) => fireAgentRequest(
    `/api/visual-verification/candidates/${encodeURIComponent(visualCaseId)}/review`,
    { method: 'POST', body: JSON.stringify({ derivative_ids: derivativeIds }) }
  ),
  derivativeImageUrl: (derivativeId: string) => (
    `${FIRE_AGENT_API_BASE_URL}/api/visual-verification/derivatives/${encodeURIComponent(derivativeId)}/image`
  ),
}

export const spreadAPI = {
  create: (eventId: string, data: any = {}) => fireAgentRequest(`/api/events/${eventId}/spread-runs`, {
    method: 'POST',
    body: JSON.stringify(data)
  }),
  createHistorical: (eventId: string, data: any = {}) => fireAgentRequest(`/api/events/${eventId}/spread-runs/historical`, {
    method: 'POST',
    body: JSON.stringify(data)
  }),
  calibrate: (eventId: string, data: any = {}) => fireAgentRequest(`/api/events/${eventId}/spread-runs/calibrate`, {
    method: 'POST',
    body: JSON.stringify(data)
  }),
  getLatest: (eventId: string) => fireAgentRequest(`/api/events/${eventId}/spread-runs/latest`),
  getSteps: (runId: string) => fireAgentRequest(`/api/spread-runs/${runId}/steps`)
}

export const spatialAnalysisAPI = {
  create: (eventId: string, data: any = {}) => fireAgentRequest(`/api/events/${eventId}/spatial-analysis`, {
    method: 'POST',
    body: JSON.stringify(data)
  }),
  getLatest: (eventId: string) => fireAgentRequest(`/api/events/${eventId}/spatial-analysis/latest`)
}

export const decisionAPI = {
  create: (eventId: string, data: any = {}) => fireAgentRequest(`/api/events/${eventId}/decision-runs`, {
    method: 'POST',
    body: JSON.stringify(data)
  }),
  getLatest: (eventId: string) => fireAgentRequest(`/api/events/${eventId}/decision-runs/latest`),
  getPackets: (decisionRunId: string) => fireAgentRequest(`/api/decision-runs/${decisionRunId}/packets`)
}

export const commandWorkflowAPI = {
  run: (eventId: string, data: any = {}) => fireAgentRequest(`/api/events/${eventId}/command-workflow`, {
    method: 'POST',
    body: JSON.stringify(data)
  }),
  getLatest: (eventId: string) => fireAgentRequest(`/api/events/${eventId}/command-workflow/latest`)
}

export const workflowRuntimeAPI = {
  events: () => fireAgentRequest('/api/workflow/events'),
  rerunSpread: (workflowRunId: string, data: any) => fireAgentRequest('/api/workflow-runs/' + encodeURIComponent(workflowRunId) + '/spread-reruns', {
    method: 'POST', body: JSON.stringify(data)
  }),
  readiness: (eventId: string) => fireAgentRequest(`/api/events/${encodeURIComponent(eventId)}/workflow-readiness`),
  create: (eventId: string, data: any = {}) => fireAgentRequest(`/api/events/${encodeURIComponent(eventId)}/workflow-runs`, {
    method: 'POST', body: JSON.stringify(data)
  }),
  latest: (eventId: string) => fireAgentRequest(`/api/events/${encodeURIComponent(eventId)}/workflow-runs/latest`),
  get: (workflowRunId: string) => fireAgentRequest(`/api/workflow-runs/${encodeURIComponent(workflowRunId)}`),
  verify: (workflowRunId: string, data: any) => fireAgentRequest(`/api/workflow-runs/${encodeURIComponent(workflowRunId)}/verification`, {
    method: 'POST', body: JSON.stringify(data)
  }),
  updateVerificationProgress: (workflowRunId: string, data: any) => fireAgentRequest(`/api/workflow-runs/${encodeURIComponent(workflowRunId)}/verification-progress`, {
    method: 'POST', body: JSON.stringify(data)
  }),
  generateScenario: (workflowRunId: string, data: any) => fireAgentRequest(`/api/workflow-runs/${encodeURIComponent(workflowRunId)}/scenario`, {
    method: 'POST', body: JSON.stringify(data)
  }),
  confirmScenario: (workflowRunId: string, data: any) => fireAgentRequest(`/api/workflow-runs/${encodeURIComponent(workflowRunId)}/scenario/confirm`, {
    method: 'POST', body: JSON.stringify(data)
  }),
  reviewCommander: (workflowRunId: string, data: any) => fireAgentRequest(`/api/workflow-runs/${encodeURIComponent(workflowRunId)}/commander/review`, {
    method: 'POST', body: JSON.stringify(data)
  }),
  resume: (workflowRunId: string) => fireAgentRequest(`/api/workflow-runs/${encodeURIComponent(workflowRunId)}/resume`, {
    method: 'POST', body: JSON.stringify({})
  })
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
