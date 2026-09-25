import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { workflowRuntimeAPI } from '../api/modules'

export type WorkflowStatus = 'PENDING' | 'READY' | 'RUNNING' | 'WAITING_FOR_INPUT' | 'COMPLETED' | 'FAILED' | 'UNAVAILABLE' | 'SKIPPED'

export type IncidentEvent = {
  event_id: string
  name: string
  status: string
  mode: string
  source_mode: string
  started_at?: string
  center?: [number, number]
}

export type WorkflowStage = {
  stage: string
  status: WorkflowStatus
  progress: number
  message: string
  result_id?: string | null
  error?: string | null
  metadata_json: Record<string, any>
}

const STORAGE_KEY = 'fire-command-incident-context-v1'

export const useIncidentContextStore = defineStore('incident-context', () => {
  const events = ref<IncidentEvent[]>([])
  const eventId = ref('dixie_fire_2021')
  const eventName = ref('Dixie Fire 2021')
  const mode = ref<'historical' | 'realtime' | 'exercise'>('historical')
  const candidateId = ref<string | null>(null)
  const visualCaseId = ref<string | null>(null)
  const confirmationId = ref<string | null>(null)
  const workflowRunId = ref<string | null>(null)
  const spreadRunId = ref<string | null>(null)
  const spatialAnalysisId = ref<string | null>(null)
  const scenarioId = ref<string | null>(null)
  const resourcePlanId = ref<string | null>(null)
  const routePlanId = ref<string | null>(null)
  const decisionRunId = ref<string | null>(null)
  const recommendationId = ref<string | null>(null)
  const currentStage = ref('data_preparation')
  const currentTime = ref<string | null>(null)
  const readiness = ref<any>(null)
  const workflow = ref<any>(null)
  const loading = ref(false)
  const error = ref('')
  let pollTimer: ReturnType<typeof setInterval> | null = null

  const selectedEvent = computed(() => events.value.find((item) => item.event_id === eventId.value) || null)
  const stages = computed<WorkflowStage[]>(() => workflow.value?.stages || [])
  const waitingForInput = computed(() => workflow.value?.status === 'WAITING_FOR_INPUT')

  function restore() {
    try {
      const saved = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || '{}')
      if (saved.event_id) eventId.value = saved.event_id
      if (saved.event_name) eventName.value = saved.event_name
      if (saved.mode) mode.value = saved.mode
      if (saved.workflow_run_id) workflowRunId.value = saved.workflow_run_id
      if (saved.current_time) currentTime.value = saved.current_time
    } catch {
      sessionStorage.removeItem(STORAGE_KEY)
    }
  }

  function persist() {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
      event_id: eventId.value,
      event_name: eventName.value,
      mode: mode.value,
      workflow_run_id: workflowRunId.value,
      current_time: currentTime.value,
    }))
  }

  function applyWorkflow(payload: any) {
    workflow.value = payload
    if (!payload) return
    workflowRunId.value = payload.workflow_run_id || null
    candidateId.value = payload.candidate_id || null
    visualCaseId.value = payload.visual_case_id || null
    confirmationId.value = payload.confirmation_id || null
    spreadRunId.value = payload.spread_run_id || null
    spatialAnalysisId.value = payload.spatial_analysis_id || null
    scenarioId.value = payload.scenario_id || null
    resourcePlanId.value = payload.resource_plan_id || null
    routePlanId.value = payload.route_plan_id || null
    decisionRunId.value = payload.decision_run_id || null
    recommendationId.value = payload.recommendation_id || null
    currentStage.value = payload.current_stage || currentStage.value
    persist()
  }

  async function loadEvents() {
    const response = await workflowRuntimeAPI.events()
    events.value = response.data || []
    if (!events.value.some((item) => item.event_id === eventId.value) && events.value.length) {
      eventId.value = events.value[0].event_id
    }
    const event = events.value.find((item) => item.event_id === eventId.value)
    if (event) {
      eventName.value = event.name
      mode.value = event.mode === 'realtime' ? 'realtime' : 'historical'
    }
    persist()
  }

  async function selectEvent(nextEventId: string) {
    eventId.value = nextEventId
    const event = events.value.find((item) => item.event_id === nextEventId)
    eventName.value = event?.name || nextEventId
    mode.value = event?.mode === 'realtime' ? 'realtime' : 'historical'
    workflowRunId.value = null
    workflow.value = null
    await Promise.all([loadReadiness(), loadLatestWorkflow()])
    persist()
  }

  async function loadReadiness() {
    const response = await workflowRuntimeAPI.readiness(eventId.value)
    readiness.value = response.data
  }

  async function loadLatestWorkflow() {
    const response = await workflowRuntimeAPI.latest(eventId.value)
    applyWorkflow(response.data)
  }

  async function refreshWorkflow() {
    if (!workflowRunId.value) return
    try {
      const response = await workflowRuntimeAPI.get(workflowRunId.value)
      applyWorkflow(response.data)
      error.value = ''
    } catch (cause: any) {
      error.value = cause?.message || '无法刷新工作流状态。'
    }
  }

  async function startWorkflow(horizonMinutes = 360) {
    loading.value = true
    error.value = ''
    try {
      const response = await workflowRuntimeAPI.create(eventId.value, { mode: mode.value, horizon_minutes: horizonMinutes })
      applyWorkflow(response.data)
      startPolling()
    } catch (cause: any) {
      error.value = cause?.message || '无法创建工作流。'
      throw cause
    } finally {
      loading.value = false
    }
  }

  async function rerunSpread(payload: any) {
    if (!workflowRunId.value) throw new Error('No active workflow is available for a fire-spread rerun.')
    loading.value = true
    error.value = ''
    try {
      const response = await workflowRuntimeAPI.rerunSpread(workflowRunId.value, payload)
      applyWorkflow(response.data)
      startPolling()
    } catch (cause: any) {
      error.value = cause?.message || 'Unable to rerun the workflow fire-spread calculation.'
      throw cause
    } finally {
      loading.value = false
    }
  }

  async function verify(action: 'confirm' | 'reject' | 'uncertain', note = '', confirmationId?: string) {
    if (!workflowRunId.value) return
    const response = await workflowRuntimeAPI.verify(workflowRunId.value, { action, note, confirmation_id: confirmationId })
    applyWorkflow(response.data)
  }

  async function updateVerificationProgress(payload: any) {
    if (!workflowRunId.value) return
    const response = await workflowRuntimeAPI.updateVerificationProgress(workflowRunId.value, payload)
    applyWorkflow(response.data)
  }

  async function resumeWorkflow() {
    if (!workflowRunId.value) return
    const response = await workflowRuntimeAPI.resume(workflowRunId.value)
    applyWorkflow(response.data)
    startPolling()
  }

  async function generateScenario(payload: any) {
    if (!workflowRunId.value) return
    const response = await workflowRuntimeAPI.generateScenario(workflowRunId.value, payload)
    applyWorkflow(response.data)
  }

  async function confirmScenario(payload: any = {}) {
    if (!workflowRunId.value) return
    const response = await workflowRuntimeAPI.confirmScenario(workflowRunId.value, { ...payload, run_downstream: true })
    applyWorkflow(response.data)
    startPolling()
  }

  async function reviewCommander(action: 'approve' | 'revise' | 'regenerate', note = '') {
    if (!workflowRunId.value) return
    const response = await workflowRuntimeAPI.reviewCommander(workflowRunId.value, { action, note })
    applyWorkflow(response.data)
    if (action === 'regenerate') startPolling()
  }

  function startPolling() {
    stopPolling()
    pollTimer = setInterval(refreshWorkflow, 2000)
  }

  function stopPolling() {
    if (pollTimer) clearInterval(pollTimer)
    pollTimer = null
  }

  restore()

  return {
    events, eventId, eventName, mode, candidateId, visualCaseId, confirmationId, workflowRunId,
    spreadRunId, spatialAnalysisId, scenarioId, resourcePlanId, routePlanId, decisionRunId,
    recommendationId, currentStage, currentTime, readiness, workflow, loading, error,
    selectedEvent, stages, waitingForInput, loadEvents, selectEvent, loadReadiness, loadLatestWorkflow,
    refreshWorkflow, startWorkflow, rerunSpread, verify, updateVerificationProgress, resumeWorkflow, generateScenario, confirmScenario, reviewCommander,
    startPolling, stopPolling,
  }
})
