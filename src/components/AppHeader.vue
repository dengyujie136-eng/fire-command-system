<template>
  <header class="app-header">
    <div class="header-left">
      <div class="logo">
        <img class="logo-image" src="../assets/system-logo.png" alt="星火智援" />
        <h1>智慧消防指挥系统</h1>
      </div>
    </div>
    <nav class="header-nav">
      <router-link
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        class="nav-item"
        active-class="active"
      >
        <span class="nav-icon">{{ item.icon }}</span>
        <span class="nav-label">{{ item.label }}</span>
      </router-link>
    </nav>
    <div class="header-right">
      <button
        class="archive-btn"
        :class="{ active: hasActiveFire, busy: archiveBusy }"
        @click="archiveFire"
        :title="hasActiveFire ? '归档当前火灾事件并恢复默认态' : '当前没有火灾事件'"
      >
        归档
      </button>
      <button
        class="fullscreen-btn"
        @click="toggleFullscreen"
        :title="isFullscreen ? '退出全屏' : '进入全屏'"
      >
        <svg v-if="!isFullscreen" class="fullscreen-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/>
        </svg>
        <svg v-else class="fullscreen-icon exit-fullscreen" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M8 3v3a2 2 0 0 1-2 2H3m18 0h-3a2 2 0 0 1-2-2V3m0 18v-3a2 2 0 0 1 2-2h3M3 16h3a2 2 0 0 1 2 2v3"/>
        </svg>
      </button>
      <div class="status-indicator">
        <span class="status-dot" :class="{ online: fireEvent.hasActiveFire || wsStatus }"></span>
        <span class="status-text">{{ wsStatusText }}</span>
      </div>
      <div class="time-display">{{ currentTime }}</div>
    </div>
  </header>
  <transition name="fullscreen-toast">
    <div v-if="showToast" class="fullscreen-toast">
      {{ toastText }}
    </div>
  </transition>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { initWebSocket, wsConnected } from '../services/websocket'
import { useFireEventStore } from '../stores/fireEventStore'

const wsStatus = ref(false)
const currentTime = ref(new Date().toLocaleString('zh-CN'))
const isFullscreen = ref(false)
const showToast = ref(false)
const fireEvent = useFireEventStore()
const hasActiveFire = computed(() => fireEvent.hasActiveFire)
const archiveBusy = computed(() => fireEvent.archiveStatus === 'archiving')
const toastText = computed(() => fireEvent.archiveMessage || (isFullscreen.value ? '已进入全屏模式' : '已退出全屏模式'))
const wsStatusText = computed(() => {
  if (fireEvent.hasAgentDecision) return '已决策'
  if (fireEvent.hasPredictedFire) return '已模拟'
  return wsStatus.value ? '已连接' : '待命'
})

const navItems = [
  { path: '/', label: '首页', icon: '首' },
  { path: '/realtime-monitor', label: '监测', icon: '测' },
  { path: '/fire-predict', label: '推演', icon: '火' },
  { path: '/multi-source-fusion', label: '融合', icon: '融' },
  { path: '/uav-dispatch', label: '无人机', icon: '空' },
  { path: '/emergency-route', label: '路径', icon: '路' },
  { path: '/resource-dispatch', label: '资源', icon: '资' },
  { path: '/disaster-assess', label: '评估', icon: '评' },
  { path: '/command-center', label: '指挥', icon: '令' },
]

let timer: ReturnType<typeof setInterval>
let syncTimer: ReturnType<typeof setInterval>
let toastTimer: ReturnType<typeof setTimeout>

const toggleFullscreen = async () => {
  try {
    if (!isFullscreen.value) {
      const elem = document.documentElement
      if (elem.requestFullscreen) {
        await elem.requestFullscreen()
      } else if ((elem as any).webkitRequestFullscreen) {
        await (elem as any).webkitRequestFullscreen()
      } else if ((elem as any).msRequestFullscreen) {
        await (elem as any).msRequestFullscreen()
      }
    } else {
      if (document.exitFullscreen) {
        await document.exitFullscreen()
      } else if ((document as any).webkitExitFullscreen) {
        await (document as any).webkitExitFullscreen()
      } else if ((document as any).msExitFullscreen) {
        await (document as any).msExitFullscreen()
      }
    }
  } catch (error) {
    console.warn('鍏ㄥ睆鍒囨崲澶辫触:', error)
  }
}

const handleFullscreenChange = () => {
  isFullscreen.value = !!(document.fullscreenElement || (document as any).webkitFullscreenElement)
  showToast.value = true
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    showToast.value = false
  }, 2000)
}

const archiveFire = async () => {
  // 归档后清空全局火灾态，各页面会监听 resetSignal 并把地图复位到木里县默认中心。
  await fireEvent.archiveActiveFire()
  showToast.value = true
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    showToast.value = false
  }, 2400)
}

onMounted(() => {
  initWebSocket()
  timer = setInterval(() => {
    currentTime.value = new Date().toLocaleString('zh-CN')
  }, 1000)
  syncTimer = setInterval(() => {
    wsStatus.value = wsConnected.value
  }, 1000)

  document.addEventListener('fullscreenchange', handleFullscreenChange)
  document.addEventListener('webkitfullscreenchange', handleFullscreenChange)
  document.addEventListener('msfullscreenchange', handleFullscreenChange)

  isFullscreen.value = !!(document.fullscreenElement || (document as any).webkitFullscreenElement)
})

onUnmounted(() => {
  clearInterval(timer)
  clearInterval(syncTimer)
  if (toastTimer) clearTimeout(toastTimer)
  document.removeEventListener('fullscreenchange', handleFullscreenChange)
  document.removeEventListener('webkitfullscreenchange', handleFullscreenChange)
  document.removeEventListener('msfullscreenchange', handleFullscreenChange)
})
</script>

<style scoped>
.app-header {
  width: 100%;
  /* clamp 楂樺害鍦ㄤ綆灞忓箷涓嬪帇缂╋紝鍑忓皯瀵逛笟鍔￠〉闈㈠彲鐢ㄩ珮搴︾殑鍗犵敤銆?*/
  height: clamp(48px, 7vh, 56px);
  flex: 0 0 clamp(48px, 7vh, 56px);
  background: linear-gradient(180deg, rgba(10, 22, 40, 0.98) 0%, rgba(15, 30, 55, 0.95) 100%);
  border-bottom: 1px solid rgba(59, 130, 246, 0.2);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 clamp(10px, 1.2vw, 20px);
  position: relative;
  z-index: 1000;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.4);
}

.app-header::after {
  content: '';
  position: absolute;
  bottom: -1px;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(59, 130, 246, 0.5), transparent);
}

.header-left {
  display: flex;
  align-items: center;
  min-width: 220px;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
}

.logo-image {
  width: 34px;
  height: 34px;
  object-fit: contain;
  border-radius: 50%;
  filter: drop-shadow(0 0 10px rgba(56, 189, 248, 0.45));
}

.logo h1 {
  font-size: clamp(14px, 1vw, 18px);
  font-weight: 700;
  background: linear-gradient(135deg, #60a5fa, #34d399);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  letter-spacing: 1px;
}

.header-nav {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1;
  justify-content: center;
  min-width: 0;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: clamp(5px, 0.8vh, 8px) clamp(8px, 0.8vw, 14px);
  border-radius: 6px;
  text-decoration: none;
  color: #94a3b8;
  font-size: clamp(11px, 0.72vw, 13px);
  font-weight: 500;
  white-space: nowrap;
  transition: all 0.25s ease;
  position: relative;
  cursor: pointer;
}

.nav-item:hover {
  color: #e0e6ed;
  background: rgba(59, 130, 246, 0.1);
}

.nav-item.active {
  color: #60a5fa;
  background: rgba(59, 130, 246, 0.15);
}

.nav-item.active::after {
  content: '';
  position: absolute;
  bottom: -1px;
  left: 14px;
  right: 14px;
  height: 2px;
  background: linear-gradient(90deg, #3b82f6, #6366f1);
  border-radius: 1px;
}

.nav-icon {
  font-size: 11px;
  width: 18px;
  height: 18px;
  border-radius: 6px;
  background: rgba(148, 163, 184, 0.12);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
}

.nav-item.active .nav-icon {
  box-shadow: 0 0 6px currentColor;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
  min-width: 220px;
  justify-content: flex-end;
}

.fullscreen-btn {
  width: clamp(30px, 4.6vh, 36px);
  height: clamp(30px, 4.6vh, 36px);
  border-radius: 6px;
  border: 1px solid rgba(59, 130, 246, 0.3);
  background: rgba(59, 130, 246, 0.1);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s ease;
  color: #94a3b8;
  padding: 0;
}

.fullscreen-btn:hover {
  background: rgba(59, 130, 246, 0.2);
  border-color: rgba(59, 130, 246, 0.5);
  color: #60a5fa;
  transform: scale(1.05);
}

.fullscreen-btn:active {
  transform: scale(0.95);
}

.archive-btn {
  height: clamp(28px, 4.4vh, 34px);
  padding: 0 clamp(9px, 0.8vw, 14px);
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  background: rgba(15, 23, 42, 0.62);
  color: #94a3b8;
  font-size: clamp(11px, 0.7vw, 12px);
  cursor: pointer;
  transition: all 0.25s ease;
  white-space: nowrap;
}

.archive-btn.active {
  border-color: rgba(245, 158, 11, 0.55);
  background: rgba(245, 158, 11, 0.13);
  color: #fbbf24;
  box-shadow: 0 0 12px rgba(245, 158, 11, 0.18);
}

.archive-btn.busy {
  opacity: 0.7;
  pointer-events: none;
}

.fullscreen-icon {
  width: 18px;
  height: 18px;
  transition: all 0.3s ease;
}

.fullscreen-icon.exit-fullscreen {
  animation: rotate-icon 0.3s ease;
}

@keyframes rotate-icon {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(180deg);
  }
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #94a3b8;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #64748b;
}

.status-dot.online {
  background: #34d399;
  box-shadow: 0 0 6px rgba(52, 211, 153, 0.5);
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.time-display {
  font-size: 12px;
  color: #64748b;
  font-variant-numeric: tabular-nums;
}

.fullscreen-toast {
  position: fixed;
  top: 70px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(59, 130, 246, 0.95);
  color: white;
  padding: 10px 20px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
  z-index: 9999;
  backdrop-filter: blur(10px);
}

.fullscreen-toast-enter-active {
  animation: toast-in 0.3s ease;
}

.fullscreen-toast-leave-active {
  animation: toast-out 0.3s ease;
}

@keyframes toast-in {
  from {
    opacity: 0;
    transform: translateX(-50%) translateY(-20px);
  }
  to {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }
}

@keyframes toast-out {
  from {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }
  to {
    opacity: 0;
    transform: translateX(-50%) translateY(-20px);
  }
}

@media (max-width: 1400px) {
  .header-nav {
    gap: 4px;
  }

  .nav-item {
    padding: 7px 8px;
    font-size: 11px;
  }

  .nav-label {
    display: inline;
  }

  .nav-icon {
    display: none;
  }
}

@media (max-width: 1200px) {
  .header-left {
    min-width: auto;
  }

  .logo h1 {
    font-size: 16px;
  }

  .header-right {
    min-width: auto;
    gap: 12px;
  }

  .status-indicator .status-text,
  .time-display {
    display: none;
  }
}

@media (max-width: 980px) {
  .nav-label {
    display: none;
  }

  .nav-icon {
    display: inline-flex;
  }
}

@media (max-height: 700px) {
  .logo h1 {
    font-size: 14px;
  }

  .header-right {
    gap: 8px;
  }
}
</style>
