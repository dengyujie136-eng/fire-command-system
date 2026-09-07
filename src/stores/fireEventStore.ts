import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import api from '../api'
import { clockAPI, decisionAPI, eventAPI, observationAPI, recalculationAPI, recommendationAPI, reportAPI, scenarioAPI, spreadAPI } from '../api/modules'

export const DEFAULT_MAP_CENTER: [number, number] = [101.269444, 28.530278]
export const MULI_COUNTY_CENTER: [number, number] = [101.2803, 28.6456]
// ERA5 风场覆盖范围约为 100.75E-102.0E、28.0N-29.0N。
// 所有页面默认以风场中心开图，避免初始视角露出大片没有风场动画的区域。
export const WIND_VIEW_CENTER: [number, number] = DEFAULT_MAP_CENTER
// 提高默认 zoom 并降低相机高度，让风场覆盖区占据更大画面比例。
export const WIND_VIEW_ZOOM = 11.25
export const WIND_VIEW_HEIGHT = 126000

type ArchivePayload = {
  event_id: string
  event_name: string
  ignition_point: {
    longitude: number
    latitude: number
  }
  archived_at: string
  forefire_result: any
  agent_result: any
  agent_messages: any[]
  derived_state: any
}

const ACTIVE_KEY = 'fire-command-active-event'
const LOCAL_ARCHIVE_KEY = 'fire-command-local-archives'

function safeParse<T>(raw: string | null, fallback: T): T {
  if (!raw) return fallback
  try {
    return JSON.parse(raw) as T
  } catch {
    return fallback
  }
}

function extractTasks(agentResult: any) {
  const packages = agentResult?.packages || {}
  return (
    packages.resource_package?.dispatch_tasks
    || packages.command_package?.active_tasks
    || packages.uav_package?.uav_tasks
    || packages.task_package?.tasks
    || agentResult?.agent_outputs?.resource_dispatch?.tasks
    || []
  )
}

function taskText(task: any) {
  return String([task?.owner, task?.action, task?.target, task?.task_id, task?.mission_name, task?.name, task?.reason].filter(Boolean).join(' '))
}

function numberOrFallback(value: any, fallback: number) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

export const useFireEventStore = defineStore('fireEvent', () => {
  localStorage.removeItem(ACTIVE_KEY)
  const saved: any = {}
  const eventId = ref<string | null>(saved.eventId || saved.event_id || null)
  const eventStatus = ref<string>(saved.eventStatus || saved.event_status || '')
  const eventDetail = ref<any>(saved.eventDetail || null)
  const eventTimeline = ref<any[]>(saved.eventTimeline || [])
  const eventLoading = ref(false)
  const eventError = ref('')
  const scenarios = ref<any[]>(saved.scenarios || [])
  const selectedScenarioId = ref<string>(saved.selectedScenarioId || saved.eventDetail?.scenario_id || 'muli_lier_village')
  const clockState = ref<any>(saved.clockState || null)
  const environmentSnapshot = ref<any>(saved.environmentSnapshot || null)
  const clockLoading = ref(false)
  const clockError = ref('')
  const observations = ref<any[]>(saved.observations || [])
  const evidenceChain = ref<any[]>(saved.evidenceChain || [])
  const backendFusionResult = ref<any>(saved.backendFusionResult || null)
  const trustedFirePoint = ref<any>(saved.trustedFirePoint || null)
  const observationLoading = ref(false)
  const observationError = ref('')
  const forefireResult = ref<any>(saved.forefireResult || null)
  const spreadRun = ref<any>(saved.spreadRun || null)
  const spreadSteps = ref<any[]>(saved.spreadSteps || [])
  const agentResult = ref<any>(saved.agentResult || null)
  const agentMessages = ref<any[]>(saved.agentMessages || [])
  const decisionRun = ref<any>(saved.decisionRun || null)
  const agentPackets = ref<any[]>(saved.agentPackets || [])
  const recommendationPackage = ref<any>(saved.recommendationPackage || null)
  const latestRecalculation = ref<any>(saved.latestRecalculation || null)
  const latestReport = ref<any>(saved.latestReport || null)
  const updatedAt = ref<string>(saved.updatedAt || '')
  const archiveStatus = ref<'idle' | 'archiving' | 'archived' | 'error'>('idle')
  const archiveMessage = ref('')
  const resetSignal = ref(0)

  const hasBackendEvent = computed(() => Boolean(eventId.value))
  const hasPredictedFire = computed(() => Boolean(forefireResult.value))
  const hasAgentDecision = computed(() => Boolean(agentResult.value))
  const hasActiveFire = computed(() => hasBackendEvent.value || hasPredictedFire.value || hasAgentDecision.value)
  const scenarioStage = computed<'idle' | 'forefire_done' | 'agent_done'>(() => {
    if (hasAgentDecision.value) return 'agent_done'
    if (hasPredictedFire.value) return 'forefire_done'
    return 'idle'
  })
  const inputSummary = computed(() => agentResult.value?.input_summary || {})
  const packages = computed(() => agentResult.value?.packages || {})
  const mapPackage = computed(() => packages.value.map_package || {})
  const uavPackage = computed(() => packages.value.uav_package || packages.value.uav_recommendation_packet || packages.value.uav_task_package || {})
  const routePackage = computed(() => packages.value.route_package || packages.value.route_recommendation_packet || {})
  const routeOptionsPackage = computed(() => packages.value.route_options_package || {})
  const resourcePackage = computed(() => packages.value.resource_package || packages.value.resource_recommendation_packet || {})
  const assessmentPackage = computed(() => packages.value.assessment_package || {})
  const commandPackage = computed(() => packages.value.command_package || {})
  const fusionPackage = computed(() => packages.value.fusion_package || {})
  const environmentPackage = computed(() => packages.value.environment_package || {})
  const recommendedPlan = computed(() => agentResult.value?.recommended_plan || null)
  const warnings = computed<any[]>(() => agentResult.value?.warnings || [])
  const rawTasks = computed<any[]>(() => extractTasks(agentResult.value))
  const finalAreaKm2 = computed(() => {
    if (!hasAgentDecision.value) return 0
    return numberOrFallback(inputSummary.value.final_area_km2, 0)
  })
  const riskLevel = computed(() => hasAgentDecision.value ? (inputSummary.value.risk_level || '') : '')
  const riskSummary = computed(() => {
    if (!hasAgentDecision.value) return ''
    const env = agentResult.value?.agent_outputs?.environment_assessment
    const spread = agentResult.value?.agent_outputs?.fire_spread_analysis
    return env?.environment_risk_summary || spread?.future_6h_summary || ''
  })

  const dispatchTasks = computed(() => hasAgentDecision.value ? rawTasks.value : [])
  const uavTasks = computed(() => {
    if (!hasAgentDecision.value) return []
    if (Array.isArray(uavPackage.value.uav_tasks)) return uavPackage.value.uav_tasks
    if (Array.isArray(uavPackage.value.tasks)) return uavPackage.value.tasks
    return rawTasks.value.filter((task) => /uav|drone|无人机|侦察|巡航|航拍|热成像/i.test(taskText(task)))
  })
  const evacuationTasks = computed(() => {
    if (!hasAgentDecision.value) return []
    if (Array.isArray(routePackage.value.evacuation_routes)) return routePackage.value.evacuation_routes
    if (Array.isArray(routeOptionsPackage.value.route_options)) return routeOptionsPackage.value.route_options
    return rawTasks.value.filter((task) => /evac|route|疏散|路线|撤离|保护|避难|下风向/i.test(taskText(task)))
  })

  const dataWarnings = computed(() => {
    if (!hasAgentDecision.value) return []
    return warnings.value.filter((warning) => /dem|weather|wind|fuel|data|气象|数据|风|燃料|地形/i.test(String(warning)))
  })

  const commandSummary = computed(() => ({
    event_name: hasAgentDecision.value ? (agentResult.value?.event_name || '木里县森林火灾演示事件') : '',
    final_area_km2: finalAreaKm2.value,
    risk_level: riskLevel.value,
    recommended_plan: hasAgentDecision.value ? (recommendedPlan.value?.name || recommendedPlan.value?.plan_id || '') : '',
    dispatch_count: dispatchTasks.value.length,
    uav_count: uavTasks.value.length,
    route_count: evacuationTasks.value.length,
  }))

  const damageAssessment = computed(() => {
    if (!hasAgentDecision.value) {
      return {
        severity: '',
        score: 0,
        final_area_km2: 0,
        burned_hectares: 0,
        economic_loss_million_cny: 0,
        affected_people: 0,
        ecological_impact: 0,
        recovery_months: '',
      }
    }
    const assessment = assessmentPackage.value || agentResult.value?.agent_outputs?.damage_assessment || agentResult.value?.damage_assessment || {}
    return {
      severity: assessment.severity || assessment.risk_level || riskLevel.value || '',
      score: numberOrFallback(assessment.severity_score ?? assessment.score, Math.min(9.5, Math.max(0, finalAreaKm2.value * 0.82))),
      final_area_km2: numberOrFallback(assessment.final_area_km2, finalAreaKm2.value),
      burned_hectares: numberOrFallback(assessment.burned_hectares, Math.round(finalAreaKm2.value * 100)),
      economic_loss_million_cny: numberOrFallback(assessment.economic_loss_million_cny, 0),
      affected_people: numberOrFallback(assessment.affected_people, 0),
      ecological_impact: numberOrFallback(assessment.ecological_impact, 0),
      recovery_months: assessment.recovery_months || '',
    }
  })

  const fusionDiagnostics = computed(() => ({
    confidence: hasAgentDecision.value ? numberOrFallback(fusionPackage.value.confidence ?? agentResult.value?.confidence, 0) : 0,
    data_sources: hasAgentDecision.value && Array.isArray(fusionPackage.value.data_sources)
      ? fusionPackage.value.data_sources
      : [
          { name: '高危火点监测', status: 'ready' },
          { name: '火势蔓延模型火线', status: forefireResult.value ? 'ready' : 'waiting' },
          { name: 'Agent 决策', status: agentResult.value ? 'ready' : 'waiting' },
          { name: '气象风场', status: 'ready' },
          { name: 'DEM/Fuel', status: forefireResult.value ? 'partial' : 'waiting' },
        ],
    warnings: hasAgentDecision.value ? (fusionPackage.value.warnings || dataWarnings.value) : dataWarnings.value,
    recommendation: hasAgentDecision.value ? (fusionPackage.value.recommendation || '') : '',
  }))

  function persist() {
    localStorage.removeItem(ACTIVE_KEY)
  }

  function applyBackendEvent(envelope: any) {
    const data = envelope?.data || envelope
    const event = data?.event || data
    if (!event?.event_id) return null
    eventId.value = event.event_id
    eventStatus.value = event.status || ''
    eventDetail.value = event
    selectedScenarioId.value = event.scenario_id || selectedScenarioId.value
    if (Array.isArray(data.timeline)) eventTimeline.value = data.timeline
    updatedAt.value = new Date().toISOString()
    persist()
    return event
  }

  async function startSimulatedEvent(payload: any = {}) {
    eventLoading.value = true
    eventError.value = ''
    try {
      const result = await eventAPI.startSimulated(payload)
      applyBackendEvent(result)
      if (eventId.value) await loadEventTimeline(eventId.value)
      return result
    } catch (error: any) {
      eventError.value = error?.message || 'Failed to start fire event'
      throw error
    } finally {
      eventLoading.value = false
    }
  }

  function applyClockState(envelope: any) {
    const data = envelope?.data || envelope
    if (!data?.clock) return null
    clockState.value = data.clock
    environmentSnapshot.value = data.environment || null
    observations.value = Array.isArray(data.observations) ? data.observations : observations.value
    backendFusionResult.value = data.fusion_result || null
    trustedFirePoint.value = data.trusted_fire_point || null
    if (trustedFirePoint.value) eventStatus.value = 'confirmed'
    else if (clockState.value?.status === 'running') eventStatus.value = 'observing'
    updatedAt.value = new Date().toISOString()
    persist()
    return data
  }

  async function loadScenarios() {
    try {
      const result = await scenarioAPI.getList()
      scenarios.value = Array.isArray(result?.data) ? result.data : []
      if (!scenarios.value.some((item) => item.scenario_id === selectedScenarioId.value) && scenarios.value[0]) {
        selectedScenarioId.value = scenarios.value[0].scenario_id
      }
      persist()
      return scenarios.value
    } catch (error: any) {
      eventError.value = error?.message || 'Failed to load scenarios'
      throw error
    }
  }

  async function ensureEventForScenario(scenarioId = selectedScenarioId.value) {
    if (eventId.value && eventDetail.value?.scenario_id === scenarioId) return eventId.value
    selectedScenarioId.value = scenarioId
    const result = await startSimulatedEvent({ scenario_id: scenarioId })
    return result?.data?.event_id || eventId.value
  }

  async function loadClockState(id = eventId.value) {
    if (!id) return null
    clockLoading.value = true
    clockError.value = ''
    try {
      const result = await clockAPI.get(id)
      return applyClockState(result)
    } catch (error: any) {
      clockError.value = error?.message || 'Failed to load scenario clock'
      throw error
    } finally {
      clockLoading.value = false
    }
  }

  async function startClock(payload: any = {}, id = eventId.value) {
    if (!id) throw new Error('No backend fire event is active.')
    clockLoading.value = true
    clockError.value = ''
    try {
      const result = await clockAPI.start(id, payload)
      return applyClockState(result)
    } catch (error: any) {
      clockError.value = error?.message || 'Failed to start scenario clock'
      throw error
    } finally {
      clockLoading.value = false
    }
  }

  async function pauseClock(id = eventId.value) {
    if (!id) return null
    const result = await clockAPI.pause(id)
    return applyClockState(result)
  }

  async function resumeClock(id = eventId.value) {
    if (!id) return null
    const result = await clockAPI.resume(id)
    return applyClockState(result)
  }

  async function resetClock(id = eventId.value) {
    if (!id) return null
    const result = await clockAPI.reset(id)
    return applyClockState(result)
  }

  async function stepClock(minutes?: number, id = eventId.value) {
    if (!id) return null
    const result = await clockAPI.step(id, minutes ? { minutes } : {})
    return applyClockState(result)
  }

  async function loadCurrentEvent() {
    eventLoading.value = true
    eventError.value = ''
    try {
      const result = await eventAPI.getCurrent()
      if (result?.data) {
        applyBackendEvent(result)
        if (eventId.value) await loadEventTimeline(eventId.value)
      }
      return result
    } catch (error: any) {
      eventError.value = error?.message || 'Failed to load current fire event'
      throw error
    } finally {
      eventLoading.value = false
    }
  }

  async function loadEventDetail(id = eventId.value) {
    if (!id) return null
    eventLoading.value = true
    eventError.value = ''
    try {
      const result = await eventAPI.getDetail(id)
      applyBackendEvent(result)
      return result
    } catch (error: any) {
      eventError.value = error?.message || 'Failed to load fire event detail'
      throw error
    } finally {
      eventLoading.value = false
    }
  }

  async function loadEventTimeline(id = eventId.value) {
    if (!id) return []
    try {
      const result = await eventAPI.getTimeline(id)
      eventTimeline.value = Array.isArray(result?.data) ? result.data : []
      persist()
      return eventTimeline.value
    } catch (error: any) {
      eventError.value = error?.message || 'Failed to load event timeline'
      throw error
    }
  }

  async function closeBackendEvent(id = eventId.value) {
    if (!id) return null
    eventLoading.value = true
    eventError.value = ''
    try {
      const result = await eventAPI.close(id)
      applyBackendEvent(result)
      return result
    } catch (error: any) {
      eventError.value = error?.message || 'Failed to close fire event'
      throw error
    } finally {
      eventLoading.value = false
    }
  }

  function applyObservationSimulation(envelope: any) {
    const data = envelope?.data || {}
    observations.value = Array.isArray(data.observations) ? data.observations : observations.value
    evidenceChain.value = Array.isArray(data.evidence_chain) ? data.evidence_chain : evidenceChain.value
    backendFusionResult.value = data.fusion_result || backendFusionResult.value
    trustedFirePoint.value = data.trusted_fire_point || trustedFirePoint.value
    if (backendFusionResult.value?.confirmed) eventStatus.value = 'confirmed'
    updatedAt.value = new Date().toISOString()
    persist()
    return data
  }

  async function simulateObservations(id = eventId.value) {
    if (!id) throw new Error('No backend fire event is active.')
    observationLoading.value = true
    observationError.value = ''
    try {
      const result = await observationAPI.simulate(id)
      return applyObservationSimulation(result)
    } catch (error: any) {
      observationError.value = error?.message || 'Failed to simulate observations'
      throw error
    } finally {
      observationLoading.value = false
    }
  }

  async function loadObservationState(id = eventId.value) {
    if (!id) return null
    observationLoading.value = true
    observationError.value = ''
    try {
      const [obs, evidence, fusion, trusted] = await Promise.all([
        observationAPI.getList(id),
        observationAPI.getEvidenceChain(id),
        observationAPI.getFusion(id),
        observationAPI.getTrustedFirePoint(id)
      ])
      observations.value = Array.isArray(obs?.data) ? obs.data : []
      evidenceChain.value = Array.isArray(evidence?.data) ? evidence.data : []
      backendFusionResult.value = fusion?.data || null
      trustedFirePoint.value = trusted?.data || null
      persist()
      return {
        observations: observations.value,
        evidenceChain: evidenceChain.value,
        fusion: backendFusionResult.value,
        trustedFirePoint: trustedFirePoint.value
      }
    } catch (error: any) {
      observationError.value = error?.message || 'Failed to load observation state'
      throw error
    } finally {
      observationLoading.value = false
    }
  }

  function setForeFireResult(result: any) {
    forefireResult.value = result
    updatedAt.value = new Date().toISOString()
    persist()
  }

  function applySpreadRun(envelope: any) {
    const data = envelope?.data || envelope
    if (!data?.run) return null
    spreadRun.value = data.run
    spreadSteps.value = Array.isArray(data.steps) ? data.steps : []
    forefireResult.value = {
      task_id: data.run.run_id,
      run_id: data.run.run_id,
      status: data.run.status,
      source: data.run.engine,
      engine: data.run.engine,
      fallback_used: data.run.fallback_used,
      forefire_available: data.run.forefire_available,
      area: Number(data.run.final_area_km2 || 0).toFixed(1),
      radius: Number(data.run.max_radius_km || 0).toFixed(1),
      speed: data.run.horizon_minutes ? ((Number(data.run.max_radius_km || 0) * 1000) / data.run.horizon_minutes).toFixed(1) : '',
      direction: `${Math.round(Number(data.run.spread_direction_deg || 0))}°`,
      risk: data.run.risk_level,
      geojson: data.geojson,
      summary: data.run.result_summary,
      input_snapshot: data.run.input_snapshot
    }
    updatedAt.value = new Date().toISOString()
    persist()
    return data
  }

  async function createSpreadRun(payload: any = {}, id = eventId.value) {
    if (!id) throw new Error('No backend fire event is active.')
    const result = await spreadAPI.create(id, payload)
    return applySpreadRun(result)
  }

  async function loadLatestSpreadRun(id = eventId.value) {
    if (!id) return null
    const result = await spreadAPI.getLatest(id)
    return result?.data ? applySpreadRun(result) : null
  }

  function setAgentResult(result: any, messages: any[] = []) {
    agentResult.value = result
    agentMessages.value = messages
    updatedAt.value = new Date().toISOString()
    persist()
  }

  function applyDecisionRun(envelope: any) {
    const data = envelope?.data || envelope
    if (!data?.run) return null
    decisionRun.value = data.run
    agentPackets.value = Array.isArray(data.packets) ? data.packets : []
    const result = {
      decision_run_id: data.run.decision_run_id,
      event_id: data.run.event_id,
      provider: data.run.provider,
      model: data.run.model,
      confidence: data.run.confidence,
      recommended_plan: data.recommended_plan || data.run.recommended_plan,
      input_summary: data.input_summary || data.run.input_summary,
      warnings: data.warnings || data.run.warnings || [],
      packages: data.packages || {},
      agent_outputs: {
        environment_assessment: data.packages?.situation_packet,
        fire_spread_analysis: data.packages?.risk_packet,
        command_decision: data.packages?.plan_packet,
        resource_dispatch: data.packages?.resource_recommendation_packet,
      },
      raw_llm_output: data.run.raw_llm_output
    }
    setAgentResult(result, agentPackets.value.map((packet: any) => ({
      type: packet.packet_type,
      content: packet.title,
      payload: packet.content,
      received_at: packet.created_at
    })))
    return data
  }

  async function createDecisionRun(payload: any = {}, id = eventId.value) {
    if (!id) throw new Error('No backend fire event is active.')
    const result = await decisionAPI.create(id, payload)
    return applyDecisionRun(result)
  }

  async function loadLatestDecisionRun(id = eventId.value) {
    if (!id) return null
    const result = await decisionAPI.getLatest(id)
    return result?.data ? applyDecisionRun(result) : null
  }

  function applyRecommendationPackage(envelope: any) {
    const data = envelope?.data || envelope
    if (!data?.package) return null
    recommendationPackage.value = data.package
    const current = agentResult.value || {
      event_id: data.package.event_id,
      recommended_plan: data.package.command_package?.recommended_plan || {},
      input_summary: {},
      warnings: [],
      packages: {}
    }
    const nextPackages = {
      ...(current.packages || {}),
      route_package: data.package.route_package || {},
      route_recommendation_packet: data.package.route_package || {},
      uav_package: data.package.uav_package || {},
      uav_recommendation_packet: data.package.uav_package || {},
      resource_package: data.package.resource_package || {},
      resource_recommendation_packet: data.package.resource_package || {},
      command_package: data.package.command_package || {}
    }
    setAgentResult({
      ...current,
      recommended_plan: data.package.command_package?.recommended_plan || current.recommended_plan,
      packages: nextPackages,
      recommendation_package: data.package,
      recommendation_records: {
        routes: data.routes || [],
        uavs: data.uavs || [],
        resources: data.resources || []
      }
    }, agentMessages.value)
    return data
  }

  async function loadLatestRecommendations(id = eventId.value) {
    if (!id) return null
    const result = await recommendationAPI.getLatest(id)
    return result?.data ? applyRecommendationPackage(result) : null
  }

  async function regenerateRecommendations(payload: any = {}, id = eventId.value) {
    if (!id) throw new Error('No backend fire event is active.')
    const result = await recommendationAPI.regenerate(id, payload)
    return applyRecommendationPackage(result)
  }

  function applyRecalculation(envelope: any) {
    const data = envelope?.data || envelope
    if (!data?.recalculation) return null
    latestRecalculation.value = data
    if (data.recommendation) {
      applyRecommendationPackage({ data: data.recommendation })
    }
    persist()
    return data
  }

  async function loadLatestRecalculation(id = eventId.value) {
    if (!id) return null
    const result = await recalculationAPI.getLatest(id)
    return result?.data ? applyRecalculation(result) : null
  }

  async function createDisturbance(payload: any, id = eventId.value) {
    if (!id) throw new Error('No backend fire event is active.')
    return recalculationAPI.createDisturbance(id, payload)
  }

  async function recalculateWithDisturbance(payload: any, id = eventId.value) {
    if (!id) throw new Error('No backend fire event is active.')
    const result = await recalculationAPI.recalculate(id, payload)
    return applyRecalculation(result)
  }

  function applyReport(envelope: any) {
    const data = envelope?.data || envelope
    if (!data?.report_id) return null
    latestReport.value = data
    persist()
    return data
  }

  async function loadLatestReport(id = eventId.value) {
    if (!id) return null
    const result = await reportAPI.getLatest(id)
    return result?.data ? applyReport(result) : null
  }

  async function generateReport(payload: any = { include_recalculation: true, format: 'markdown' }, id = eventId.value) {
    if (!id) throw new Error('No backend fire event is active.')
    const result = await reportAPI.create(id, payload)
    return applyReport(result)
  }

  function reportDownloadUrl(reportId = latestReport.value?.report_id) {
    return reportId ? reportAPI.downloadUrl(reportId) : ''
  }

  function clearActiveFire() {
    eventId.value = null
    eventStatus.value = ''
    eventDetail.value = null
    eventTimeline.value = []
    eventError.value = ''
    observations.value = []
    evidenceChain.value = []
    clockState.value = null
    environmentSnapshot.value = null
    clockError.value = ''
    backendFusionResult.value = null
    trustedFirePoint.value = null
    observationError.value = ''
    forefireResult.value = null
    spreadRun.value = null
    spreadSteps.value = []
    agentResult.value = null
    agentMessages.value = []
    decisionRun.value = null
    agentPackets.value = []
    recommendationPackage.value = null
    latestRecalculation.value = null
    latestReport.value = null
    updatedAt.value = ''
    resetSignal.value += 1
    localStorage.removeItem(ACTIVE_KEY)
  }

  async function archiveActiveFire() {
    if (!hasActiveFire.value) {
      archiveStatus.value = 'archived'
      archiveMessage.value = '当前没有需要归档的火灾事件。'
      resetSignal.value += 1
      return
    }

    archiveStatus.value = 'archiving'
    archiveMessage.value = ''
    const payload: ArchivePayload = {
      event_id: `muli-fire-demo-${new Date().toISOString().slice(0, 10)}`,
      event_name: '木里县森林火灾演示事件',
      ignition_point: {
        longitude: DEFAULT_MAP_CENTER[0],
        latitude: DEFAULT_MAP_CENTER[1]
      },
      archived_at: new Date().toISOString(),
      forefire_result: forefireResult.value,
      agent_result: agentResult.value,
      agent_messages: agentMessages.value,
      derived_state: {
        command_summary: commandSummary.value,
        damage_assessment: damageAssessment.value,
        fusion_diagnostics: fusionDiagnostics.value,
        dispatch_tasks: dispatchTasks.value,
        uav_tasks: uavTasks.value,
        evacuation_tasks: evacuationTasks.value,
        data_warnings: dataWarnings.value,
        risk_summary: riskSummary.value,
        warnings: warnings.value
      }
    }

    try {
      await api.post('/api/fire/archive', payload)
      archiveMessage.value = '火灾事件已归档到后端数据库。'
    } catch (error) {
      const archives = safeParse<ArchivePayload[]>(localStorage.getItem(LOCAL_ARCHIVE_KEY), [])
      archives.unshift(payload)
      localStorage.setItem(LOCAL_ARCHIVE_KEY, JSON.stringify(archives.slice(0, 20)))
      archiveMessage.value = '后端归档接口暂不可用，已先保存到本地归档。'
    }

    clearActiveFire()
    archiveStatus.value = 'archived'
  }

  return {
    eventId,
    eventStatus,
    eventDetail,
    eventTimeline,
    eventLoading,
    eventError,
    scenarios,
    selectedScenarioId,
    clockState,
    environmentSnapshot,
    clockLoading,
    clockError,
    observations,
    evidenceChain,
    backendFusionResult,
    trustedFirePoint,
    observationLoading,
    observationError,
    forefireResult,
    spreadRun,
    spreadSteps,
    agentResult,
    agentMessages,
    decisionRun,
    agentPackets,
    recommendationPackage,
    latestRecalculation,
    latestReport,
    updatedAt,
    archiveStatus,
    archiveMessage,
    resetSignal,
    hasBackendEvent,
    hasActiveFire,
    hasPredictedFire,
    hasAgentDecision,
    scenarioStage,
    inputSummary,
    packages,
    mapPackage,
    uavPackage,
    routePackage,
    routeOptionsPackage,
    resourcePackage,
    assessmentPackage,
    commandPackage,
    fusionPackage,
    environmentPackage,
    recommendedPlan,
    warnings,
    dispatchTasks,
    uavTasks,
    evacuationTasks,
    dataWarnings,
    riskSummary,
    commandSummary,
    damageAssessment,
    fusionDiagnostics,
    startSimulatedEvent,
    loadScenarios,
    ensureEventForScenario,
    loadClockState,
    startClock,
    pauseClock,
    resumeClock,
    resetClock,
    stepClock,
    loadCurrentEvent,
    loadEventDetail,
    loadEventTimeline,
    closeBackendEvent,
    simulateObservations,
    loadObservationState,
    setForeFireResult,
    applySpreadRun,
    createSpreadRun,
    loadLatestSpreadRun,
    setAgentResult,
    applyDecisionRun,
    createDecisionRun,
    loadLatestDecisionRun,
    applyRecommendationPackage,
    loadLatestRecommendations,
    regenerateRecommendations,
    applyRecalculation,
    loadLatestRecalculation,
    createDisturbance,
    recalculateWithDisturbance,
    applyReport,
    loadLatestReport,
    generateReport,
    reportDownloadUrl,
    clearActiveFire,
    archiveActiveFire
  }
})
