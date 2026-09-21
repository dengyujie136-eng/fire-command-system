import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { dixieFireAPI } from '../api/modules'

const HOTSPOT_RENDER_LIMIT = 1000

type LayerVisibility = {
  hotspots: boolean
  burnedArea: boolean
}

export const useDixieFireStore = defineStore('dixieFire', () => {
  const event = ref<any | null>(null)
  const hotspots = ref<any[]>([])
  const burnedArea = ref<any | null>(null)
  const weatherHourly = ref<any[]>([])
  const hotspotTotal = ref(0)
  const loading = ref(false)
  const error = ref('')
  const layerVisibility = ref<LayerVisibility>({
    hotspots: true,
    burnedArea: true,
  })

  const renderedHotspotCount = computed(() => hotspots.value.length)
  const isLoaded = computed(() => Boolean(event.value || burnedArea.value || hotspots.value.length))

  async function loadDixieFire() {
    loading.value = true
    error.value = ''
    try {
      const [eventResult, hotspotResult, burnedAreaResult] = await Promise.all([
        dixieFireAPI.getEvent(),
        dixieFireAPI.getHotspots({ status: 'candidate', limit: HOTSPOT_RENDER_LIMIT, offset: 0 }),
        dixieFireAPI.getBurnedArea(),
      ])
      event.value = eventResult?.data || null
      hotspots.value = Array.isArray(hotspotResult?.items) ? hotspotResult.items : []
      hotspotTotal.value = Number(hotspotResult?.total || hotspots.value.length || 0)
      burnedArea.value = burnedAreaResult?.data || null
      return { event: event.value, hotspots: hotspots.value, burnedArea: burnedArea.value }
    } catch (err: any) {
      error.value = err?.message || 'Failed to load Dixie Fire data'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function loadWeatherHourly(limit = 1000) {
    const result = await dixieFireAPI.getWeatherHourly({ limit, offset: 0 })
    weatherHourly.value = Array.isArray(result?.items) ? result.items : []
    return weatherHourly.value
  }

  function setLayerVisible(layer: keyof LayerVisibility, visible: boolean) {
    layerVisibility.value = { ...layerVisibility.value, [layer]: visible }
  }

  function clearDixieFire() {
    event.value = null
    hotspots.value = []
    burnedArea.value = null
    weatherHourly.value = []
    hotspotTotal.value = 0
    error.value = ''
  }

  return {
    event,
    hotspots,
    burnedArea,
    weatherHourly,
    hotspotTotal,
    loading,
    error,
    layerVisibility,
    renderedHotspotCount,
    isLoaded,
    loadDixieFire,
    loadWeatherHourly,
    setLayerVisible,
    clearDixieFire,
  }
})