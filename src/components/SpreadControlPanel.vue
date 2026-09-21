<template>
  <section class="spread-control-panel">
    <header>
      <span>Spread Control</span>
      <h3>火势推演控制面板</h3>
    </header>
    <div class="control-grid">
      <label>风速 m/s<input v-model.number="form.wind_speed_m_s" type="number" min="0" step="0.1" /></label>
      <label>风向 °<input v-model.number="form.wind_direction_deg" type="number" min="0" max="359" step="1" /></label>
      <label>温度 ℃<input v-model.number="form.temperature_c" type="number" step="0.1" /></label>
      <label>湿度 %<input v-model.number="form.humidity_percent" type="number" min="0" max="100" step="1" /></label>
      <label>降水 mm<input v-model.number="form.precipitation_mm" type="number" min="0" step="0.1" /></label>
      <label>燃料湿度<input v-model.number="form.fuel_moisture" type="number" min="0" max="1" step="0.01" /></label>
      <label>FWI<input v-model.number="form.fire_weather_index" type="number" min="0" step="0.1" /></label>
      <label>预测时间 min<input v-model.number="form.horizon_minutes" type="number" min="30" max="720" step="30" /></label>
    </div>
    <div class="control-actions">
      <button type="button" @click="submit" :disabled="busy">重新推演</button>
      <span>{{ status }}</span>
    </div>
  </section>
</template>

<script setup lang="ts">
import { reactive, watch } from 'vue'

const props = defineProps<{
  environment?: any
  busy?: boolean
  status?: string
}>()

const emit = defineEmits<{
  run: [payload: any]
}>()

const form = reactive({
  wind_speed_m_s: 4,
  wind_direction_deg: 45,
  temperature_c: 30,
  humidity_percent: 32,
  precipitation_mm: 0,
  fuel_moisture: 0.16,
  fire_weather_index: 16,
  horizon_minutes: 120,
  step_minutes: 30,
})

watch(() => props.environment, (env) => {
  if (!env) return
  form.wind_speed_m_s = Number(env.wind_speed_m_s ?? form.wind_speed_m_s)
  form.wind_direction_deg = Number(env.wind_direction_deg ?? form.wind_direction_deg)
  form.temperature_c = Number(env.temperature_c ?? form.temperature_c)
  form.humidity_percent = Number(env.humidity_percent ?? form.humidity_percent)
  form.fuel_moisture = Number(env.fuel_moisture ?? form.fuel_moisture)
  form.fire_weather_index = Number(env.fire_weather_index ?? form.fire_weather_index)
}, { immediate: true })

function submit() {
  emit('run', {
    horizon_minutes: form.horizon_minutes,
    step_minutes: form.step_minutes,
    prefer_forefire: true,
    user_environment_override: {
      wind_speed_m_s: form.wind_speed_m_s,
      wind_direction_deg: form.wind_direction_deg,
      temperature_c: form.temperature_c,
      humidity_percent: form.humidity_percent,
      precipitation_mm: form.precipitation_mm,
      fuel_moisture: form.fuel_moisture,
      fire_weather_index: form.fire_weather_index,
      source_mode: 'user_input',
    }
  })
}
</script>

<style scoped>
.spread-control-panel {
  display: grid;
  gap: 10px;
  margin-bottom: 12px;
  padding: 12px;
  border-radius: 8px;
  border: 1px solid rgba(45, 212, 191, 0.28);
  background: rgba(8, 29, 39, 0.82);
}

header {
  display: grid;
  gap: 3px;
}

header span {
  color: #7dd3fc;
  font-size: 11px;
  font-weight: 800;
  text-transform: uppercase;
}

h3 {
  margin: 0;
  font-size: 14px;
  color: #dbeafe;
}

.control-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

label {
  min-width: 0;
  display: grid;
  gap: 4px;
  color: #9fb0c7;
  font-size: 12px;
}

input {
  min-width: 0;
  height: 32px;
  border-radius: 6px;
  border: 1px solid rgba(148, 163, 184, 0.28);
  background: #0e1a2a;
  color: #e5f0ff;
  padding: 0 8px;
}

.control-actions {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 8px;
  align-items: center;
}

button {
  min-height: 34px;
  border-radius: 6px;
  border: 1px solid #14b8a6;
  background: #0f766e;
  color: #fff;
  cursor: pointer;
  font-weight: 700;
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.control-actions span {
  color: #93c5fd;
  font-size: 12px;
  overflow-wrap: anywhere;
}
</style>