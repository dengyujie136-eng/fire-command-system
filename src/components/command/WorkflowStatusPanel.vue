<template>
  <nav class="workflow-status-panel" aria-label="指挥工作流状态">
    <button
      v-for="(stage, index) in stages"
      :key="stage.stage"
      type="button"
      class="stage-button"
      :class="{ selected: stage.stage === activeStage, current: stage.status === 'RUNNING' || stage.status === 'WAITING_FOR_INPUT' }"
      :data-status="stage.status"
      @click="$emit('select', stage.stage)"
    >
      <span class="stage-marker" aria-hidden="true">{{ marker(stage.status) }}</span>
      <span class="stage-copy">
        <strong>{{ labels[stage.stage] || stage.stage }}</strong>
        <small>{{ statusLabel(stage.status) }}</small>
        <small v-if="details?.[stage.stage]" class="stage-detail">{{ details[stage.stage] }}</small>
      </span>
      <span class="stage-number">{{ String(index + 1).padStart(2, '0') }}</span>
    </button>
  </nav>
</template>

<script setup lang="ts">
import type { WorkflowStage } from '../../stores/incidentContextStore'

defineProps<{
  stages: WorkflowStage[]
  activeStage: string
  details?: Record<string, string>
}>()

defineEmits<{ select: [stage: string] }>()

const labels: Record<string, string> = {
  data_preparation: '数据准备',
  fire_verification: '火点核验',
  situation: '态势评估',
  spread: '火势推演',
  spatial_risk: '空间风险',
  scenario: '应急场景',
  resource_dispatch: '资源调度',
  route_planning: '路径规划',
  commander: '指挥决策',
}

function marker(status: string) {
  if (status === 'COMPLETED') return '✓'
  if (status === 'RUNNING') return '▶'
  if (status === 'WAITING_FOR_INPUT') return '◆'
  if (status === 'FAILED') return '!'
  return '○'
}

function statusLabel(status: string) {
  return ({
    PENDING: '等待',
    READY: '就绪',
    RUNNING: '当前执行',
    WAITING_FOR_INPUT: '等待人工确认',
    COMPLETED: '已完成',
    FAILED: '失败',
    UNAVAILABLE: '不可用',
    SKIPPED: '已跳过',
  } as Record<string, string>)[status] || status
}
</script>

<style scoped>
.workflow-status-panel { display: flex; flex-direction: column; min-width: 0; border-right: 1px solid #2b414f; background: #10202b; }
.stage-button { display: grid; grid-template-columns: 25px minmax(0, 1fr) 24px; gap: 9px; align-items: center; min-height: 64px; padding: 10px 12px; border: 0; border-bottom: 1px solid #243946; color: #b9c9d0; background: transparent; text-align: left; cursor: pointer; }
.stage-button:hover, .stage-button.selected { background: #1a303d; color: #fff; }
.stage-button.current { box-shadow: inset 3px 0 0 #e6a93d; background: #21343a; }
.stage-marker { display: grid; place-items: center; width: 22px; height: 22px; border: 1px solid #607583; border-radius: 50%; font-size: 13px; font-weight: 800; }
.stage-copy strong, .stage-copy small { display: block; }
.stage-copy strong { font-size: 15px; }
.stage-copy small { margin-top: 3px; color: #91a7b2; font-size: 12px; line-height: 1.25; }
.stage-copy .stage-detail { color: #ffd178; font-family: Consolas, monospace; }
.stage-number { color: #667d89; font: 12px Consolas, monospace; }
[data-status='COMPLETED'] .stage-marker { border-color: #34a871; color: #68d69d; }
[data-status='RUNNING'] .stage-marker { border-color: #e6a93d; color: #ffc866; animation: pulse-stage 1.4s infinite; }
[data-status='WAITING_FOR_INPUT'] .stage-marker { border-color: #e6a93d; color: #ffc866; }
[data-status='FAILED'] .stage-marker { border-color: #e45e58; color: #ff8982; }
@keyframes pulse-stage { 50% { opacity: .42; } }

.workflow-status-panel { min-height: 0; overflow-y: auto; }
.stage-button { min-height: 47px; padding: 6px 8px; gap: 6px; grid-template-columns: 20px minmax(0, 1fr) 18px; }
.stage-button strong { font-size: 12px; }
.stage-button small { font-size: 10px; }

</style>
