<template>
  <div class="verification-workspace">
    <div class="verification-body">
      <VisualVerification :event-id="incident.eventId" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import VisualVerification from './VisualVerification.vue'
import { useIncidentContextStore } from '../stores/incidentContextStore'

const incident = useIncidentContextStore()
onMounted(async () => {
  try {
    await incident.loadEvents()
    await incident.loadLatestWorkflow()
  } catch {
    // Local candidates remain inspectable without an active workflow.
  }
})
</script>

<style scoped>
.verification-workspace { height: 100%; min-height: 0; display: flex; flex-direction: column; color: #eaf4ff; background: #07111b; }
.verification-body { flex: 1; min-height: 0; }
</style>
