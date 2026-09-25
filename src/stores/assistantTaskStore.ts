import { ref } from 'vue'
import { defineStore } from 'pinia'

export type SpreadTaskStatus = 'idle' | 'queued' | 'running' | 'completed' | 'failed' | 'blocked'

export const useAssistantTaskStore = defineStore('assistant-task', () => {
  const status = ref<SpreadTaskStatus>('idle')
  const requestedHours = ref(4)
  const weatherUpdateMinutes = ref(60)
  const baseRunId = ref<string | null>(null)
  const resultRunId = ref<string | null>(null)
  const message = ref('')
  const requestedByAgent = ref(false)
  const weatherOverrides = ref<Record<string, number>>({})

  function queue(
    hours: number,
    currentRunId: string | null,
    byAgent = false,
    overrides: Record<string, number> = {},
    updateMinutes = 60,
  ) {
    requestedHours.value = Math.max(1, Math.min(24, Math.round(hours)))
    weatherUpdateMinutes.value = Math.max(1, Math.min(1440, Math.round(updateMinutes)))
    baseRunId.value = currentRunId
    resultRunId.value = null
    requestedByAgent.value = byAgent
    weatherOverrides.value = { ...overrides }
    status.value = 'queued'
    message.value = '等待提交火势推演。'
  }
  function start() { status.value = 'running'; message.value = '模型正在计算火线序列…' }
  function complete(runId: string) {
    resultRunId.value = runId
    status.value = 'completed'
    message.value = '火势推演已完成，地图和时间序列已更新。'
  }
  function fail(reason: string, blocked = false) {
    status.value = blocked ? 'blocked' : 'failed'
    message.value = reason
  }
  return { status, requestedHours, weatherUpdateMinutes, baseRunId, resultRunId, message, requestedByAgent, weatherOverrides, queue, start, complete, fail }
})
