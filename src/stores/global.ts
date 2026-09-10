import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useGlobalStore = defineStore('global', () => {
  const scene_id = ref<string | null>(null)
  const selected_fire = ref<string | null>(null)
  const selected_uav = ref<string | null>(null)
  const wsConnected = ref(false)
  const currentTime = ref(new Date().toLocaleString('zh-CN'))

  const updateTimer = () => {
    currentTime.value = new Date().toLocaleString('zh-CN')
  }

  return {
    scene_id,
    selected_fire,
    selected_uav,
    wsConnected,
    currentTime,
    updateTimer
  }
})
