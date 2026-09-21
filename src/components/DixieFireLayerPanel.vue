<template>
  <section class="dixie-panel">
    <header class="dixie-head">
      <div>
        <span>Dixie Fire</span>
        <strong>Historical Data</strong>
      </div>
      <button type="button" @click="load" :disabled="dixieFire.loading">
        {{ dixieFire.loading ? 'Loading' : dixieFire.isLoaded ? 'Reload' : 'Load' }}
      </button>
    </header>

    <div class="layer-switches">
      <label>
        <input
          type="checkbox"
          :checked="dixieFire.layerVisibility.burnedArea"
          @change="toggleLayer('burnedArea', $event)"
        />
        <span>MTBS burned area</span>
      </label>
      <label>
        <input
          type="checkbox"
          :checked="dixieFire.layerVisibility.hotspots"
          @change="toggleLayer('hotspots', $event)"
        />
        <span>FIRMS hotspots</span>
      </label>
    </div>

    <div class="dixie-stats">
      <article>
        <span>Total hotspots</span>
        <strong>{{ dixieFire.hotspotTotal || '-' }}</strong>
      </article>
      <article>
        <span>Rendered</span>
        <strong>{{ dixieFire.renderedHotspotCount }}</strong>
      </article>
    </div>

    <p v-if="dixieFire.error" class="dixie-error">{{ dixieFire.error }}</p>
    <p v-else class="dixie-note">First version renders up to 1000 candidate hotspots.</p>
  </section>
</template>

<script setup lang="ts">
import { useDixieFireStore } from '../stores/dixieFireStore'

const dixieFire = useDixieFireStore()

async function load() {
  await dixieFire.loadDixieFire()
}

function toggleLayer(layer: 'hotspots' | 'burnedArea', event: Event) {
  const input = event.target as HTMLInputElement
  dixieFire.setLayerVisible(layer, input.checked)
}
</script>

<style scoped>
.dixie-panel {
  position: absolute;
  z-index: 7;
  left: 18px;
  top: 18px;
  width: min(300px, calc(100% - 36px));
  display: grid;
  gap: 12px;
  padding: 12px;
  border: 1px solid rgba(191, 219, 254, 0.24);
  border-radius: 8px;
  background: rgba(2, 8, 23, 0.78);
  color: #e5f0ff;
  backdrop-filter: blur(12px);
  pointer-events: auto;
}

.dixie-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.dixie-head div {
  display: grid;
  gap: 3px;
}

.dixie-head span,
.dixie-stats span,
.dixie-note {
  color: #9fb0c7;
  font-size: 12px;
}

.dixie-head strong {
  color: #f8fafc;
  font-size: 15px;
}

.dixie-head button {
  min-height: 32px;
  padding: 0 10px;
  border: 1px solid rgba(20, 184, 166, 0.48);
  border-radius: 6px;
  background: #0f766e;
  color: #ecfeff;
  font: inherit;
  font-weight: 700;
  cursor: pointer;
}

.dixie-head button:disabled {
  cursor: wait;
  opacity: 0.6;
}

.layer-switches {
  display: grid;
  gap: 8px;
}

.layer-switches label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #dbeafe;
}

.layer-switches input {
  width: 16px;
  height: 16px;
  accent-color: #14b8a6;
}

.dixie-stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.dixie-stats article {
  display: grid;
  gap: 3px;
  padding: 8px;
  border-radius: 6px;
  background: rgba(15, 35, 53, 0.82);
  border: 1px solid rgba(148, 163, 184, 0.14);
}

.dixie-stats strong {
  font-size: 18px;
  color: #67e8f9;
}

.dixie-note,
.dixie-error {
  margin: 0;
  line-height: 1.4;
}

.dixie-error {
  color: #fecaca;
  font-size: 12px;
}
</style>