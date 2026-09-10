<template>
  <div v-if="visible" class="agent-insight-card" :class="variant">
    <div class="ai-head">
      <span class="ai-title">{{ title }}</span>
      <span v-if="statusText" class="ai-badge">{{ statusText }}</span>
    </div>
    <p v-if="summaryText" class="ai-summary">{{ summaryText }}</p>
    <div v-if="primaryText" class="ai-primary">{{ primaryText }}</div>
    <div v-if="items.length" class="ai-items">
      <div v-for="item in items.slice(0, limit)" :key="item" class="ai-item">{{ item }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useFireEventStore } from '../stores/fireEventStore'

const props = withDefaults(defineProps<{
  context?: 'command' | 'assess' | 'dispatch' | 'uav' | 'route' | 'monitor' | 'fusion'
  title?: string
  limit?: number
  variant?: 'compact' | 'normal'
}>(), {
  context: 'command',
  title: 'AI 联动建议',
  limit: 3,
  variant: 'normal'
})

const fireEvent = useFireEventStore()

// 没有后端 Agent 决策前，整张卡片保持空白隐藏；返回数据后再显示对应内容。
const visible = computed(() => fireEvent.hasAgentDecision)
const statusText = computed(() => fireEvent.hasAgentDecision ? '已联动' : '')

const summaryText = computed(() => {
  if (!fireEvent.hasAgentDecision) return ''
  return fireEvent.riskSummary || ''
})

const primaryText = computed(() => {
  if (!fireEvent.hasAgentDecision) return ''
  const plan = fireEvent.recommendedPlan
  if (props.context === 'command' && plan) return `推荐方案：${plan.name || plan.plan_id || '未命名方案'}${plan.score ? ` · ${plan.score}分` : ''}`
  if (props.context === 'assess') return `最终过火面积：${fireEvent.inputSummary.final_area_km2 ?? '--'} km² · 风险：${fireEvent.inputSummary.risk_level || '--'}`
  if (props.context === 'dispatch') return `推荐调度任务：${fireEvent.dispatchTasks.length} 项`
  if (props.context === 'uav') return `无人机相关任务：${fireEvent.uavTasks.length} 项`
  if (props.context === 'route') return `疏散/保护建议：${fireEvent.evacuationTasks.length || fireEvent.dispatchTasks.length} 项`
  if (props.context === 'monitor') return `风险等级：${fireEvent.inputSummary.risk_level || '--'}`
  if (props.context === 'fusion') return `数据诊断：${fireEvent.dataWarnings.length || fireEvent.warnings.length} 条`
  return ''
})

const items = computed(() => {
  if (!fireEvent.hasAgentDecision) return []
  if (props.context === 'dispatch') return fireEvent.dispatchTasks.map((task) => `${task.owner || task.task_id || '任务'}：${task.action || task.target || '待执行'}`)
  if (props.context === 'uav') return fireEvent.uavTasks.map((task) => `${task.owner || '无人机'}：${task.action || task.target || '执行侦察任务'}`)
  if (props.context === 'route') {
    const source = fireEvent.evacuationTasks.length ? fireEvent.evacuationTasks : fireEvent.dispatchTasks
    return source.map((task) => `${task.owner || task.task_id || '路线'}：${task.action || task.target || '避让高风险区域'}`)
  }
  if (props.context === 'fusion') return (fireEvent.dataWarnings.length ? fireEvent.dataWarnings : fireEvent.warnings).map(String)
  if (props.context === 'assess') return fireEvent.warnings.map(String)
  const reasons = fireEvent.recommendedPlan?.reasons || []
  return reasons.length ? reasons.map(String) : fireEvent.warnings.map(String)
})
</script>

<style scoped>
.agent-insight-card {
  padding: clamp(8px, 1vh, 12px);
  border-radius: 8px;
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.1), rgba(245, 158, 11, 0.08));
  border: 1px solid rgba(96, 165, 250, 0.18);
  box-shadow: inset 0 0 24px rgba(255, 255, 255, 0.03);
  overflow: hidden;
}

.agent-insight-card.compact {
  padding: 7px 8px;
}

.ai-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 5px;
}

.ai-title {
  color: #dbeafe;
  font-size: clamp(11px, 0.76vw, 13px);
  font-weight: 700;
}

.ai-badge {
  flex: 0 0 auto;
  padding: 2px 6px;
  border-radius: 999px;
  background: rgba(34, 197, 94, 0.12);
  color: #86efac;
  font-size: 10px;
}

.ai-summary {
  margin: 0;
  color: #94a3b8;
  font-size: clamp(10px, 0.7vw, 12px);
  line-height: 1.35;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.ai-primary {
  margin-top: 6px;
  color: #fbbf24;
  font-size: clamp(10px, 0.72vw, 12px);
  font-weight: 700;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.ai-items {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 6px;
}

.ai-item {
  color: #cbd5e1;
  font-size: 10px;
  line-height: 1.3;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
</style>
