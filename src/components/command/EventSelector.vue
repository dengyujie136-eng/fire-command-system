<template>
  <div class="event-selector">
    <label for="incident-event">当前事件</label>
    <select id="incident-event" :value="store.eventId" @change="changeEvent">
      <option v-for="event in store.events" :key="event.event_id" :value="event.event_id">{{ event.name }}</option>
    </select>
    <span class="mode-badge">{{ modeLabel }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useIncidentContextStore } from '../../stores/incidentContextStore'

const store = useIncidentContextStore()
const modeLabel = computed(() => ({ historical: '历史复盘', realtime: '实时事件', exercise: '演练模式' }[store.mode] || store.mode))
function changeEvent(event: Event) { void store.selectEvent((event.target as HTMLSelectElement).value) }
</script>

<style scoped>
.event-selector { display: flex; align-items: center; gap: 10px; min-width: 0; }
label { color: #9fb1bd; font-size: 14px; font-weight: 700; }
select { min-width: 240px; height: 42px; padding: 0 34px 0 12px; border: 1px solid #526878; border-radius: 5px; color: #f4f7f8; background: #142532; font-size: 15px; }
.mode-badge { padding: 5px 9px; border: 1px solid #526878; border-radius: 4px; color: #b8cad3; font-size: 13px; }
@media (max-width: 760px) { .event-selector { flex-wrap: wrap; } select { min-width: 190px; flex: 1; } }
</style>
