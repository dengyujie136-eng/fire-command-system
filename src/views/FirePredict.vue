<template>
  <div class="fire-predict-container" :class="{ compact: compactMode }">
    <!-- 顶部状态条 -->
    <div class="top-status-bar">
      <div class="capsule-item">
        <span class="capsule-value">{{ simResult?.speed || '2.5' }}</span>
        <span class="capsule-unit">m/min</span>
      </div>
      <div class="capsule-item">
        <span class="capsule-icon">↗</span>
        <span class="capsule-text">{{ simResult?.direction || '东北' }}</span>
      </div>
      <div class="capsule-item risk" :class="(simResult?.risk || '中')">
        <span class="risk-dot"></span>
        <span class="capsule-text">{{ simResult?.risk || '中' }}</span>
      </div>
      <div class="capsule-item">
        <span class="capsule-icon">📅</span>
        <span class="capsule-text">{{ formatTime(simForm.time) }}</span>
      </div>
    </div>

    <!-- 主内容区 -->
    <div class="main-content">
      <!-- 左侧面板 -->
      <div class="side-panel left" :class="{ collapsed: leftCollapsed }">
        <button class="collapse-btn" @click="leftCollapsed = !leftCollapsed">
          {{ leftCollapsed ? '→' : '←' }}
        </button>
        
        <template v-if="!leftCollapsed">
          <!-- 环境快照卡片 -->
          <div class="glass-card">
            <div class="card-title">环境快照</div>
            <div class="env-grid">
              <div class="env-item">
                <span class="env-icon">🌡️</span>
                <span class="env-val">{{ statData?.temperature || '24°' }}</span>
              </div>
              <div class="env-item">
                <span class="env-icon">{{ weatherIcon }}</span>
                <span class="env-val">{{ weatherText }}</span>
              </div>
              <div class="env-item">
                <span class="env-icon">🌿</span>
                <span class="env-val">灌木</span>
              </div>
              <div class="env-item">
                <span class="env-icon">💧</span>
                <span class="env-val">{{ statData?.humidity || '40%' }}</span>
              </div>
            </div>
          </div>

          <!-- 预测数据卡片 -->
          <div class="glass-card">
            <div class="card-title">预测数据</div>
            <div class="pred-grid">
              <div class="pred-item">
                <span class="pred-label">预测面积</span>
                <span class="pred-value">{{ simResult?.area || '--' }} km²</span>
              </div>
              <div class="pred-item">
                <span class="pred-label">影响范围</span>
                <span class="pred-value">{{ simResult?.radius || '--' }} km</span>
              </div>
            </div>
            <div ref="miniTrendRef" class="mini-trend"></div>
          </div>

          <!-- 模拟控制卡片 -->
          <div class="glass-card">
            <div class="card-title">模拟控制</div>
            <div class="sim-controls">
              <div class="sim-row">
                <span class="sim-label">模型</span>
                <el-select v-model="simForm.model" size="small" style="width: 120px">
                  <el-option label="标准模型" value="static" />
                  <el-option label="动态模型" value="dynamic" />
                </el-select>
              </div>
              <div class="sim-row">
                <span class="sim-label">方向</span>
                <span class="sim-val">{{ simResult?.direction || '东北' }}</span>
              </div>
              <el-button type="primary" size="small" @click="startSimulation" :loading="simulating" style="width:100%;margin-top:8px">
                开始模拟
              </el-button>
            </div>
          </div>
        </template>

        <!-- 折叠状态图标 -->
        <template v-else>
          <div class="collapsed-icons">
            <div v-for="i in 3" :key="i" class="ico-item" :title="icoTitles[i]">
              {{ icoIcons[i] }}
            </div>
          </div>
        </template>
      </div>

      <!-- 中央地图 -->
      <div class="map-area">
        <div ref="mapRef" class="map-container"></div>
        <div class="map-float-controls">
          <button class="float-btn" @click="zoomIn">+</button>
          <button class="float-btn" @click="zoomOut">−</button>
          <button class="float-btn" @click="resetView">⌂</button>
          <div class="dir-indicator" :style="{ transform: `rotate(${dirDeg}deg)` }">↑</div>
        </div>
      </div>

      <!-- 右侧面板 -->
      <div class="side-panel right" :class="{ collapsed: rightCollapsed }">
        <button class="collapse-btn" @click="rightCollapsed = !rightCollapsed">
          {{ rightCollapsed ? '←' : '→' }}
        </button>

        <template v-if="!rightCollapsed">
          <div class="tabs">
            <div 
              v-for="tab in tabs" 
              :key="tab.id" 
              class="tab-item"
              :class="{ active: activeTab === tab.id }"
              @click="activeTab = tab.id"
            >
              {{ tab.icon }} <span class="tab-text">{{ tab.label }}</span>
            </div>
          </div>

          <div class="tab-content">
            <!-- 图层控制 -->
            <div v-if="activeTab === 'layers'" class="tab-inner">
              <div class="layer-grid">
                <button 
                  v-for="ly in layerOptions" 
                  :key="ly.id" 
                  class="layer-btn"
                  :class="{ on: viewOptions[ly.id] }"
                  @click="viewOptions[ly.id] = !viewOptions[ly.id]"
                >
                  <span class="ly-icon">{{ ly.icon }}</span>
                  <span>{{ ly.label }}</span>
                </button>
              </div>
              <button class="more-link" @click="showMoreDrawer = true">+ 更多图层</button>
            </div>

            <!-- 历史记录 -->
            <div v-if="activeTab === 'history'" class="tab-inner">
              <div class="history-list">
                <div v-for="(h, idx) in historyList.slice(0,3)" :key="idx" class="history-item">
                  <span class="h-time">{{ h.time }}</span>
                  <span class="h-area">{{ h.area }}</span>
                  <el-tag :type="h.status==='done'?'success':'warning'" size="small">{{ h.status==='done'?'完成':'运行中' }}</el-tag>
                </div>
              </div>
              <button class="more-link" @click="showHistoryModal = true">查看全部历史</button>
            </div>

            <!-- Agent分析 -->
            <div v-if="activeTab === 'agent'" class="tab-inner">
              <p class="agent-summary">基于当前气象条件，火势预计在未来2小时内向东北方向扩散，速度约2.5m/min。建议加强东北方向防控。</p>
              <button class="more-link" @click="showAgentDrawer = true">展开详情 →</button>
            </div>
          </div>
        </template>

        <!-- 折叠状态 -->
        <template v-else>
          <div class="collapsed-icons">
            <div 
              v-for="tab in tabs" 
              :key="tab.id" 
              class="ico-item"
              :class="{ active: activeTab === tab.id }"
              :title="tab.label"
            >
              {{ tab.icon }}
            </div>
          </div>
        </template>
      </div>
    </div>

    <!-- 底部控制条 -->
    <div class="bottom-control-bar">
      <div class="bc-left">
        <button class="bc-btn" :class="{ on: playing }" @click="playTimeline">
          {{ playing ? '⏸' : '▶' }}
        </button>
        <button class="bc-btn" @click="resetTimeline">⟲</button>
      </div>
      <div class="bc-center">
        <div class="slider-container">
          <div class="slider-track"></div>
          <div 
            class="slider-thumb" 
            :style="{ left: `${timelineProgress}%` }"
            @mousedown="startDrag"
          >
            <div class="slider-tooltip">{{ getSliderTime() }}</div>
          </div>
          <div class="slider-marks">
            <span v-for="m in sliderMarks" :key="m.t" class="mark" :style="{ left: `${m.p}%` }">{{ m.t }}</span>
          </div>
        </div>
      </div>
      <div class="bc-right">
        <span class="area-display">{{ simResult?.area || '8.1' }} km²</span>
        <span class="summary-display">影响北区林地</span>
      </div>
    </div>

    <!-- 更多图层抽屉 -->
    <transition name="drawer">
      <div v-if="showMoreDrawer" class="drawer-overlay" @click="showMoreDrawer = false">
        <div class="drawer-content" @click.stop>
          <div class="drawer-header">
            高级图层控制
            <button class="close-drawer" @click="showMoreDrawer = false">✕</button>
          </div>
          <div class="drawer-body">
            <div v-for="opt in advancedLayers" :key="opt.id" class="drawer-item">
              <span>{{ opt.label }}</span>
              <el-switch v-model="opt.val" size="small" />
            </div>
          </div>
        </div>
      </div>
    </transition>

    <!-- Agent详情抽屉 -->
    <transition name="drawer">
      <div v-if="showAgentDrawer" class="drawer-overlay" @click="showAgentDrawer = false">
        <div class="drawer-content" @click.stop>
          <div class="drawer-header">
            Agent 完整分析报告
            <button class="close-drawer" @click="showAgentDrawer = false">✕</button>
          </div>
          <div class="drawer-body agent-full">
            <p>基于当前气象条件（温度24°C，湿度40%，东北风2.3m/s），结合燃料分布类型（灌木占40%），火势预计在未来2小时内向东北方向扩散，速度约2.5m/min。</p>
            <p class="suggestions-title">建议：</p>
            <ul>
              <li>加强东北方向防火隔离带建设</li>
              <li>调派无人机编队前往东北区域巡航</li>
              <li>准备充足水源和灭火器材</li>
            </ul>
          </div>
        </div>
      </div>
    </transition>

    <!-- 历史记录模态框 -->
    <el-dialog v-model="showHistoryModal" title="历史模拟记录" width="50%" draggable>
      <div class="full-history">
        <div v-for="(h, idx) in historyList" :key="idx" class="full-history-item">
          <span class="fh-time">{{ h.time }}</span>
          <span class="fh-area">{{ h.area }}</span>
          <el-tag :type="h.status==='done'?'success':'warning'">{{ h.status==='done'?'完成':'运行中' }}</el-tag>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted, computed, nextTick } from 'vue'
import { fireAPI, simulateAPI } from '../api/modules'
import * as echarts from 'echarts'
import mapboxgl from 'mapbox-gl'

const mapRef = ref<HTMLDivElement>()
const miniTrendRef = ref<HTMLDivElement>()

// 状态
const leftCollapsed = ref(false)
const rightCollapsed = ref(false)
const autoCompactMode = ref(false)
const manualCompactMode = ref(false)
/* 自动紧凑与手动紧凑叠加：小屏强制 compact，键盘 C 保留人工切换能力。 */
const compactMode = computed(() => autoCompactMode.value || manualCompactMode.value)
const activeTab = ref('layers')
const playing = ref(false)
const timelineProgress = ref(50)
const showMoreDrawer = ref(false)
const showAgentDrawer = ref(false)
const showHistoryModal = ref(false)
const simulating = ref(false)

const tabs = [
  { id: 'layers', label: '图层', icon: '📚' },
  { id: 'history', label: '历史', icon: '📜' },
  { id: 'agent', label: 'AI', icon: '🤖' }
]

const layerOptions = [
  { id: 'heatmap', label: '热力图', icon: '🔥' },
  { id: 'contour', label: '等值线', icon: '〰️' },
  { id: 'model', label: '模型', icon: '🔧' },
  { id: 'satellite', label: '卫星', icon: '🛰️' },
  { id: 'terrain', label: '地形', icon: '🏔️' },
  { id: 'weather', label: '气象', icon: '🌤️' }
]

const viewOptions = reactive({ heatmap: false, contour: false, model: true, satellite: false, terrain: true, weather: true })

const advancedLayers = reactive([
  { id: 'wind', label: '风场矢量', val: false },
  { id: 'pressure', label: '气压等值线', val: false },
  { id: 'temp', label: '温度场', val: true }
])

const simForm = reactive({ model: 'static', time: new Date(), duration: 6 })
const statData = ref<any>({})
const weatherIcon = ref('☀️')
const weatherText = computed(() => {
  const w = statData.value?.weather || 'sunny'
  return w === 'sunny' ? '晴' : w === 'rainy' ? '雨' : '阴'
})
const simResult = ref<any>({ area: '8.1', radius: '3.2', speed: '2.5', direction: '东北', risk: '高' })
const historyList = ref<any[]>([
  { time: '10:00', area: '5.2km²', status: 'done' },
  { time: '12:00', area: '8.1km²', status: 'done' },
  { time: '14:00', area: '12.5km²', status: 'running' }
])

const icoTitles = ['环境快照', '预测数据', '模拟控制']
const icoIcons = ['🌡️', '📊', '⚙️']

const dirDeg = 45 // 东北方向45度

const sliderMarks = [
  { t: '10:00', p: 0 },
  { t: '12:00', p: 33 },
  { t: '14:00', p: 66 },
  { t: '16:00', p: 100 }
]

function formatTime(d: Date) {
  return `${(d.getMonth()+1).toString().padStart(2,'0')}/${d.getDate().toString().padStart(2,'0')} ${d.getHours()}:${String(d.getMinutes()).padStart(2,'0')}`
}

function getSliderTime() {
  const m = Math.round(10 + timelineProgress.value/10)
  return `${m}:00`
}

let map: mapboxgl.Map | null = null
let miniChart: echarts.ECharts | null = null
let playTimer: ReturnType<typeof setInterval> | null = null
let resizeHandler: (() => void) | null = null
let dragging = false

function updateResponsiveLayout() {
  const width = window.innerWidth
  const height = window.innerHeight
  /* <=1366px 或 <=700px 自动启用紧凑尺寸，减少固定 px 造成的纵向溢出。 */
  autoCompactMode.value = width <= 1366 || height <= 700
  /* <=1100px 默认折叠右侧面板，给中间地图保留最小可视宽度。 */
  if (width <= 1100) rightCollapsed.value = true
  nextTick(() => {
    map?.resize()
    miniChart?.resize()
  })
}

// 地图相关
function zoomIn() { if (map) map.zoomIn() }
function zoomOut() { if (map) map.zoomOut() }
function resetView() { if (map) map.flyTo({ center: [116.4, 39.9], zoom: 10 }) }

// 时间轴拖动
function startDrag(ev: MouseEvent) {
  dragging = true
  const moveHandler = (e: MouseEvent) => {
    const slider = document.querySelector('.slider-container') as HTMLElement
    if (!slider) return
    const rect = slider.getBoundingClientRect()
    let p = ((e.clientX - rect.left) / rect.width) * 100
    p = Math.max(0, Math.min(100, p))
    timelineProgress.value = p
  }
  const upHandler = () => {
    dragging = false
    document.removeEventListener('mousemove', moveHandler)
    document.removeEventListener('mouseup', upHandler)
  }
  document.addEventListener('mousemove', moveHandler)
  document.addEventListener('mouseup', upHandler)
}

function playTimeline() {
  playing.value = !playing.value
  if (playing.value) {
    playTimer = setInterval(() => {
      timelineProgress.value = (timelineProgress.value + 0.5) % 101
    }, 100)
  } else if (playTimer) clearInterval(playTimer)
}

function resetTimeline() {
  timelineProgress.value = 0
  playing.value = false
  if (playTimer) clearInterval(playTimer)
}

async function startSimulation() {
  simulating.value = true
  try {
    const result = await simulateAPI.start({ model: simForm.model, time: simForm.time.toISOString(), duration: simForm.duration, scene_id: 'scene-001' })
    simResult.value = result || { area: '12.5', radius: '3.2', speed: '2.5', direction: '东北', risk: '高' }
  } catch (e) {
    simResult.value = { area: '12.5', radius: '3.2', speed: '2.5', direction: '东北', risk: '高' }
  }
  simulating.value = false
}

// 数据加载
async function loadData() {
  try {
    const stat = await fireAPI.getStat()
    statData.value = stat || {}
    if (stat?.weather) {
      weatherIcon.value = stat.weather === 'sunny' ? '☀️' : stat.weather === 'rainy' ? '🌧️' : '☁️'
    }
  } catch (e) {}
  initMiniTrend()
}

function initMiniTrend() {
  if (!miniTrendRef.value) return
  miniChart = echarts.init(miniTrendRef.value)
  miniChart.setOption({
    grid: { top: 10, bottom: 10, left: 0, right: 0 },
    xAxis: { type: 'category', data: ['8:00','10:00','12:00','14:00','16:00'], show: false },
    yAxis: { type: 'value', show: false },
    series: [{
      type: 'line',
      smooth: true,
      data: [2, 5, 8, 12, 15],
      symbol: 'none',
      lineStyle: { color: '#f59e0b', width: 2 },
      areaStyle: { color: 'rgba(245,158,11,0.1)' }
    }]
  })
}

function initMap() {
  if (!mapRef.value) return
  mapboxgl.accessToken = 'pk.eyJ1IjoiZXhhbXBsZSIsInAiOiJ0ZXN0In0.test'
  map = new mapboxgl.Map({
    container: mapRef.value,
    style: 'mapbox://styles/mapbox/dark-v11',
    center: [116.4, 39.9],
    zoom: 10,
    attributionControl: false
  })
}

// 键盘快捷键
function handleKeydown(e: KeyboardEvent) {
  if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement || e.target instanceof HTMLTextAreaElement) return
  if (e.code === 'KeyL') leftCollapsed.value = !leftCollapsed.value
  if (e.code === 'KeyR') rightCollapsed.value = !rightCollapsed.value
  if (e.code === 'KeyC') manualCompactMode.value = !manualCompactMode.value
  if (e.code === 'Space') {
    e.preventDefault()
    playTimeline()
  }
}

onMounted(() => {
  updateResponsiveLayout()
  initMap()
  loadData()
  resizeHandler = updateResponsiveLayout
  window.addEventListener('resize', resizeHandler)
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  miniChart?.dispose()
  if (playTimer) clearInterval(playTimer)
  map?.remove()
  if (resizeHandler) window.removeEventListener('resize', resizeHandler)
  window.removeEventListener('keydown', handleKeydown)
})
</script>

<style scoped>
.fire-predict-container {
  /* 继承 App 主区域高度，避免 AppHeader + 页面 100vh 叠加产生浏览器滚动条。 */
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: linear-gradient(180deg, #0a1628 0%, #0d1421 100%);
  display: flex;
  flex-direction: column;
  color: #e2e8f0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}

/* 顶部状态条 */
.top-status-bar {
  /* 顶部栏使用 clamp，在 600-700px 高屏幕下自动压缩。 */
  height: clamp(48px, 8vh, 64px);
  flex: 0 0 clamp(48px, 8vh, 64px);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: clamp(6px, 0.85vw, 16px);
  padding: 0 clamp(10px, 1.7vw, 32px);
  background: linear-gradient(180deg, rgba(20,28,40,0.95) 0%, rgba(20,28,40,0.85) 100%);
  border-bottom: 1px solid rgba(255,255,255,0.06);
  backdrop-filter: blur(10px);
}

.capsule-item {
  height: clamp(32px, 5.2vh, 40px);
  min-width: 0;
  width: clamp(96px, 10vw, 120px);
  /* 胶囊宽度和 padding 随视口收缩，防止顶部栏横向溢出。 */
  padding: 0 clamp(8px, 0.85vw, 16px);
  border-radius: 999px;
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(255,255,255,0.12);
  box-shadow: 0 0 12px rgba(255,255,255,0.04), inset 0 0 20px rgba(255,255,255,0.02);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  backdrop-filter: blur(8px);
}

.capsule-value {
  font-size: clamp(16px, 1.15vw, 22px);
  font-weight: 700;
  background: linear-gradient(90deg, #fff 0%, #a5f3fc 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.capsule-unit {
  font-size: clamp(9px, 0.65vw, 12px);
  color: #94a3b8;
}

.capsule-icon {
  font-size: clamp(12px, 0.85vw, 16px);
}

.capsule-text {
  font-size: clamp(11px, 0.75vw, 14px);
  font-weight: 500;
}

.capsule-item.risk {
  border-color: rgba(248,113,113,0.4);
  background: rgba(248,113,113,0.1);
}

.capsule-item.risk.中 {
  border-color: rgba(251,191,36,0.4);
  background: rgba(251,191,36,0.1);
}
.capsule-item.risk.低 {
  border-color: rgba(52,211,153,0.4);
  background: rgba(52,211,153,0.1);
}

.risk-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #ef4444;
  box-shadow: 0 0 12px rgba(239,68,68,0.6);
}
.capsule-item.risk.中 .risk-dot { background: #f59e0b; box-shadow: 0 0 12px rgba(245,158,11,0.6); }
.capsule-item.risk.低 .risk-dot { background: #22c55e; box-shadow: 0 0 12px rgba(34,197,94,0.6); }

/* 主内容区 */
.main-content {
  flex: 1;
  display: flex;
  min-height: 0;
  min-width: 0;
  overflow: hidden;
}

/* 侧边面板通用 */
.side-panel {
  /* 固定 320px 改为 clamp，防止小屏横向溢出。 */
  width: clamp(200px, 18vw, 320px);
  flex: 0 0 clamp(200px, 18vw, 320px);
  min-height: 0;
  display: flex;
  flex-direction: column;
  position: relative;
  transition: width 0.2s ease;
  padding: clamp(6px, 1vh, 12px);
  gap: clamp(6px, 1vh, 12px);
  overflow: hidden;
}

.side-panel.collapsed {
  /* 折叠宽度使用 clamp，保持按钮和图标可见且不挤压中心区域。 */
  width: clamp(48px, 6vw, 60px);
  flex-basis: clamp(48px, 6vw, 60px);
  padding: clamp(6px, 1vh, 12px) clamp(4px, 0.45vw, 8px);
}

.collapse-btn {
  position: absolute;
  top: 50%;
  z-index: 10;
  width: clamp(18px, 1.4vw, 24px);
  height: clamp(36px, 6vh, 48px);
  border-radius: 0 8px 8px 0;
  background: rgba(20,28,40,0.9);
  border: 1px solid rgba(255,255,255,0.08);
  color: #94a3b8;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  backdrop-filter: blur(6px);
}

.collapse-btn:hover {
  color: #e2e8f0;
  background: rgba(30,40,55,0.95);
}

.side-panel.left .collapse-btn { right: 0; transform: translateY(-50%); border-radius: 0 8px 8px 0; }
.side-panel.right .collapse-btn { left: 0; transform: translateY(-50%); border-radius: 8px 0 0 8px; }

/* 玻璃卡片 */
.glass-card {
  background: rgba(20,28,40,0.7);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 16px;
  /* 卡片 padding 使用 clamp，低屏幕下减少纵向累计高度。 */
  padding: clamp(8px, 1.2vh, 16px);
  box-shadow: 0 4px 24px rgba(0,0,0,0.25);
  backdrop-filter: blur(10px);
  transition: all 0.2s ease;
  min-height: 0;
  overflow: hidden;
}

.side-panel > .glass-card {
  flex: 1 1 0;
  display: flex;
  flex-direction: column;
}

.glass-card:hover {
  border-color: rgba(96,165,250,0.25);
  box-shadow: 0 4px 30px rgba(96,165,250,0.08);
}

.card-title {
  font-size: clamp(10px, 0.72vw, 13px);
  font-weight: 600;
  color: #cbd5e1;
  margin-bottom: clamp(6px, 1vh, 12px);
  letter-spacing: 0.5px;
}

/* 环境网格 */
.env-grid {
  display: grid;
  grid-template-columns: repeat(2,1fr);
  gap: clamp(5px, 0.8vh, 10px);
  min-height: 0;
}

.env-item {
  display: flex;
  align-items: center;
  gap: clamp(4px, 0.5vw, 8px);
  background: rgba(255,255,255,0.04);
  padding: clamp(5px, 0.8vh, 8px) clamp(6px, 0.6vw, 10px);
  border-radius: 10px;
}

.env-icon { font-size: clamp(12px, 0.85vw, 16px); }
.env-val { font-size: clamp(10px, 0.7vw, 13px); font-weight: 600; color: #e2e8f0; }

/* 预测数据 */
.pred-grid {
  display: flex;
  gap: clamp(5px, 0.8vh, 10px);
  margin-bottom: clamp(6px, 1vh, 12px);
}

.pred-item {
  flex: 1;
  background: rgba(255,255,255,0.04);
  padding: clamp(6px, 0.9vh, 10px);
  border-radius: 10px;
  text-align: center;
}

.pred-label { display: block; font-size: clamp(9px, 0.6vw, 11px); color: #64748b; margin-bottom: 4px; }
.pred-value { display: block; font-size: clamp(12px, 0.85vw, 16px); font-weight: 700; color: #f59e0b; }

.mini-trend { width: 100%; height: clamp(32px, 6vh, 50px); min-height: 0; }

/* 模拟控制 */
.sim-controls {
  display: flex;
  flex-direction: column;
  gap: clamp(5px, 0.8vh, 8px);
}

.sim-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.sim-label { font-size: 12px; color: #64748b; }
.sim-val { font-size: 13px; font-weight: 600; }

/* 折叠图标 */
.collapsed-icons {
  display: flex;
  flex-direction: column;
  gap: clamp(8px, 1.6vh, 16px);
  align-items: center;
  padding-top: clamp(14px, 3vh, 24px);
}

.ico-item {
  width: clamp(32px, 4.8vh, 36px);
  height: clamp(32px, 4.8vh, 36px);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  background: rgba(255,255,255,0.05);
  cursor: pointer;
  transition: all 0.2s ease;
}
.ico-item:hover {
  background: rgba(96,165,250,0.15);
  transform: translateY(-2px);
}
.ico-item.active {
  background: rgba(96,165,250,0.2);
  border: 1px solid rgba(96,165,250,0.3);
}

/* 中央地图 */
.map-area {
  flex: 1;
  position: relative;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.map-container {
  width: 100%;
  height: 100%;
}

.map-float-controls {
  position: absolute;
  top: clamp(8px, 2vw, 16px);
  right: clamp(8px, 2vw, 16px);
  display: flex;
  flex-direction: column;
  gap: clamp(4px, 0.65vh, 8px);
  z-index: 10;
  background: rgba(20,28,40,0.7);
  padding: clamp(5px, 0.8vh, 8px);
  border-radius: 14px;
  border: 1px solid rgba(255,255,255,0.08);
  backdrop-filter: blur(8px);
}

.float-btn {
  width: clamp(30px, 4.8vh, 36px);
  height: clamp(30px, 4.8vh, 36px);
  border-radius: 10px;
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(255,255,255,0.1);
  color: #e2e8f0;
  font-size: 18px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.float-btn:hover {
  background: rgba(96,165,250,0.2);
  transform: scale(1.05);
}

.float-btn:active {
  transform: scale(0.98);
}

.dir-indicator {
  width: clamp(30px, 4.8vh, 36px);
  height: clamp(30px, 4.8vh, 36px);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  color: #60a5fa;
  font-weight: bold;
  border: 1px solid rgba(96,165,250,0.3);
  background: rgba(96,165,250,0.1);
}

/* 右侧标签页 */
.tabs {
  display: flex;
  gap: 4px;
  background: rgba(255,255,255,0.04);
  padding: 4px;
  border-radius: 12px;
  margin-bottom: clamp(6px, 1vh, 12px);
  flex: 0 0 auto;
}

.tab-item {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: clamp(3px, 0.4vw, 6px);
  padding: clamp(5px, 0.8vh, 8px) clamp(5px, 0.6vw, 10px);
  border-radius: 10px;
  font-size: clamp(10px, 0.68vw, 13px);
  color: #94a3b8;
  cursor: pointer;
  transition: all 0.2s ease;
}

.tab-item:hover { color: #e2e8f0; }
.tab-item.active {
  background: rgba(96,165,250,0.2);
  color: #60a5fa;
  font-weight: 600;
}

.tab-content {
  flex: 1;
  background: rgba(20,28,40,0.7);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 16px;
  padding: clamp(8px, 1.2vh, 14px);
  box-shadow: 0 4px 24px rgba(0,0,0,0.25);
  backdrop-filter: blur(10px);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.tab-inner {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

/* 图层按钮网格 */
.layer-grid {
  display: grid;
  grid-template-columns: repeat(2,1fr);
  gap: clamp(4px, 0.7vh, 8px);
  margin-bottom: clamp(6px, 1vh, 12px);
}

.layer-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: clamp(6px, 0.9vh, 10px);
  border-radius: 12px;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.06);
  color: #94a3b8;
  font-size: clamp(10px, 0.65vw, 12px);
  cursor: pointer;
  transition: all 0.2s ease;
}

.layer-btn:hover {
  background: rgba(96,165,250,0.1);
  color: #cbd5e1;
}

.layer-btn.on {
  background: rgba(96,165,250,0.18);
  border-color: rgba(96,165,250,0.4);
  color: #60a5fa;
}

.ly-icon { font-size: 18px; }

.more-link {
  border: none;
  background: none;
  color: #60a5fa;
  font-size: 12px;
  cursor: pointer;
  padding: 4px 0;
  text-align: left;
}
.more-link:hover { text-decoration: underline; }

/* 历史列表 */
.history-list {
  display: flex;
  flex-direction: column;
  gap: clamp(3px, 0.6vh, 6px);
  margin-bottom: clamp(6px, 1vh, 12px);
  min-height: 0;
  overflow: hidden;
}

.history-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: clamp(5px, 0.75vh, 8px) clamp(6px, 0.6vw, 10px);
  border-radius: 10px;
  background: rgba(255,255,255,0.03);
  border-bottom: 1px solid rgba(255,255,255,0.04);
}

.h-time { font-size: 12px; color: #64748b; width: 45px; }
.h-area { font-size: 13px; font-weight: 600; }

/* Agent摘要 */
.agent-summary {
  font-size: clamp(10px, 0.7vw, 13px);
  color: #94a3b8;
  line-height: 1.55;
  margin-bottom: 8px;
}

/* 底部控制条 */
.bottom-control-bar {
  /* 底部控制条使用 clamp，低屏幕下压缩到 52px。 */
  height: clamp(52px, 8vh, 80px);
  flex: 0 0 clamp(52px, 8vh, 80px);
  background: linear-gradient(0deg, rgba(20,28,40,0.95) 0%, rgba(20,28,40,0.85) 100%);
  border-top: 1px solid rgba(255,255,255,0.06);
  display: flex;
  align-items: center;
  padding: 0 clamp(10px, 1.3vw, 24px);
  gap: clamp(8px, 1.25vw, 24px);
  backdrop-filter: blur(10px);
}

.bc-left {
  display: flex;
  gap: clamp(6px, 0.8vw, 12px);
}

.bc-btn {
  width: clamp(32px, 5.2vh, 48px);
  height: clamp(32px, 5.2vh, 48px);
  border-radius: 50%;
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(255,255,255,0.12);
  color: #e2e8f0;
  font-size: 18px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.bc-btn:hover {
  background: rgba(96,165,250,0.2);
  transform: scale(1.05);
}
.bc-btn:active { transform: scale(0.98); }
.bc-btn.on {
  background: rgba(96,165,250,0.25);
  border-color: rgba(96,165,250,0.5);
}

.bc-center {
  flex: 1;
  display: flex;
  align-items: center;
}

.slider-container {
  width: 100%;
  height: clamp(28px, 5vh, 40px);
  position: relative;
}

.slider-track {
  position: absolute;
  top: 50%;
  left: 0;
  right: 0;
  height: 6px;
  border-radius: 3px;
  background: linear-gradient(90deg, rgba(255,255,255,0.08), rgba(255,255,255,0.15));
  transform: translateY(-50%);
}

.slider-thumb {
  position: absolute;
  top: 50%;
  width: clamp(14px, 2vh, 18px);
  height: clamp(14px, 2vh, 18px);
  border-radius: 50%;
  background: #60a5fa;
  box-shadow: 0 0 12px rgba(96,165,250,0.6), 0 0 30px rgba(96,165,250,0.3);
  transform: translate(-50%,-50%);
  cursor: grab;
  transition: box-shadow 0.2s ease;
}
.slider-thumb:active { cursor: grabbing; }

.slider-tooltip {
  position: absolute;
  top: -26px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(20,28,40,0.9);
  border: 1px solid rgba(96,165,250,0.3);
  color: #e2e8f0;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 12px;
  white-space: nowrap;
}

.slider-marks {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
}

.mark {
  position: absolute;
  top: clamp(22px, 3.6vh, 28px);
  transform: translateX(-50%);
  font-size: 11px;
  color: #64748b;
}

.bc-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
}

.area-display {
  font-size: clamp(13px, 0.95vw, 18px);
  font-weight: 700;
  color: #f59e0b;
}
.summary-display {
  font-size: clamp(10px, 0.65vw, 12px);
  color: #64748b;
}

/* 抽屉过渡 */
.drawer-enter-active, .drawer-leave-active {
  transition: all 0.2s ease;
}
.drawer-enter-from, .drawer-leave-to {
  opacity: 0;
}
.drawer-enter-from .drawer-content, .drawer-leave-to .drawer-content {
  transform: translateX(100%);
}

.drawer-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.4);
  display: flex;
  justify-content: flex-end;
  z-index: 100;
}

.drawer-content {
  width: clamp(280px, 32vw, 320px);
  background: rgba(20,28,40,0.95);
  border-left: 1px solid rgba(255,255,255,0.08);
  backdrop-filter: blur(12px);
  display: flex;
  flex-direction: column;
  transition: transform 0.2s ease;
}

.drawer-header {
  padding: clamp(10px, 1.2vh, 16px);
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid rgba(255,255,255,0.06);
  font-weight: 600;
}

.close-drawer {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  border: none;
  background: rgba(255,255,255,0.06);
  color: #94a3b8;
  cursor: pointer;
}

.drawer-body {
  flex: 1;
  padding: clamp(8px, 1.2vh, 16px);
  /* 抽屉保持 overflow:hidden，内容通过紧凑间距和隐藏次要文本适配。 */
  overflow: hidden;
  min-height: 0;
}

.drawer-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: clamp(7px, 1vh, 12px) 0;
  border-bottom: 1px solid rgba(255,255,255,0.04);
  font-size: 13px;
}

.agent-full {
  line-height: 1.7;
  color: #94a3b8;
}

.suggestions-title {
  margin-top: 16px;
  margin-bottom: 8px;
  color: #cbd5e1;
}

.agent-full ul {
  margin: 0;
  padding-left: 18px;
}

/* 历史模态框 */
.full-history {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.full-history-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-radius: 8px;
  background: rgba(255,255,255,0.03);
}

.fh-time { width: 60px; color: #64748b; }
.fh-area { font-weight: 600; }

.compact .top-status-bar {
  height: clamp(46px, 7vh, 52px);
  flex-basis: clamp(46px, 7vh, 52px);
  padding: 0 clamp(8px, 1.2vw, 16px);
  gap: 8px;
}

.compact .capsule-item {
  height: 32px;
  width: clamp(88px, 10vw, 110px);
  padding: 0 10px;
}

.compact .capsule-value {
  font-size: 17px;
}

.compact .side-panel {
  /* 紧凑模式作为小屏默认值：面板宽度、padding、gap 同步压缩。 */
  width: clamp(200px, 18vw, 260px);
  flex-basis: clamp(200px, 18vw, 260px);
  padding: 6px;
  gap: 6px;
}

.compact .side-panel.collapsed {
  width: clamp(48px, 6vw, 52px);
  flex-basis: clamp(48px, 6vw, 52px);
  padding: 6px 4px;
}

.compact .glass-card,
.compact .tab-content {
  padding: 8px;
  border-radius: 14px;
}

.compact .card-title {
  font-size: 10px;
  margin-bottom: 6px;
}

.compact .env-item,
.compact .pred-item,
.compact .layer-btn,
.compact .history-item {
  padding: 5px 7px;
}

.compact .mini-trend {
  height: 34px;
}

.compact .bottom-control-bar {
  height: clamp(50px, 7.5vh, 64px);
  flex-basis: clamp(50px, 7.5vh, 64px);
}

.compact .bc-btn {
  width: 34px;
  height: 34px;
}

@media (max-width: 1366px) {
  .fire-predict-container {
    font-size: 12px;
  }

  .top-status-bar {
    height: clamp(46px, 7vh, 52px);
    flex-basis: clamp(46px, 7vh, 52px);
    padding: 0 12px;
    gap: 8px;
  }

  .side-panel {
    width: clamp(200px, 18vw, 260px);
    flex-basis: clamp(200px, 18vw, 260px);
    padding: 6px;
    gap: 6px;
  }

  .glass-card,
  .tab-content {
    padding: 8px;
    border-radius: 14px;
  }

  .card-title {
    font-size: 10px;
    margin-bottom: 6px;
  }

  .mini-trend {
    height: 34px;
  }

  .bottom-control-bar {
    height: clamp(50px, 7.5vh, 64px);
    flex-basis: clamp(50px, 7.5vh, 64px);
  }
}

@media (max-width: 1100px) {
  .side-panel.right {
    /* <=1100px 时右侧面板由脚本默认折叠，CSS 同步限制占宽。 */
    width: clamp(48px, 5.5vw, 52px);
    flex-basis: clamp(48px, 5.5vw, 52px);
  }

  .side-panel.right:not(.collapsed) {
    position: absolute;
    right: 0;
    top: 0;
    bottom: clamp(52px, 8vh, 80px);
    z-index: 30;
    width: min(260px, 32vw);
    flex-basis: min(260px, 32vw);
    background: rgba(10,15,26,0.92);
  }

  .capsule-item:nth-child(4),
  .summary-display {
    display: none;
  }
}

@media (max-width: 800px) {
  .main-content {
    /* 窄屏垂直堆叠，所有区块宽度 100%，避免横向滚动。 */
    flex-direction: column;
  }

  .side-panel,
  .compact .side-panel,
  .side-panel.right,
  .side-panel.right:not(.collapsed) {
    position: relative;
    width: 100%;
    max-width: 100%;
    flex: 0 0 clamp(92px, 22vh, 140px);
  }

  .side-panel.collapsed,
  .compact .side-panel.collapsed {
    width: 100%;
    flex-basis: clamp(42px, 7vh, 52px);
  }

  .map-area {
    flex: 1 1 auto;
  }

  .top-status-bar {
    justify-content: flex-start;
  }

  .capsule-item {
    flex: 1 1 0;
    width: auto;
  }

  .capsule-unit,
  .tab-text,
  .summary-display {
    display: none;
  }

  .bottom-control-bar {
    gap: 8px;
  }

  .bc-right {
    min-width: 60px;
  }
}

@media (max-height: 700px) {
  .top-status-bar {
    height: 46px;
    flex-basis: 46px;
  }

  .bottom-control-bar {
    height: 50px;
    flex-basis: 50px;
  }

  .side-panel {
    padding: 5px;
    gap: 5px;
  }

  .glass-card,
  .tab-content {
    padding: 6px;
  }

  .env-item,
  .pred-item,
  .layer-btn,
  .history-item {
    padding: 5px 7px;
  }

  .pred-label,
  .more-link,
  .slider-tooltip,
  .slider-marks,
  .summary-display {
    /* 低高度时隐藏次要标签/刻度，保证核心信息不需要内部滚动。 */
    display: none;
  }

  .mini-trend {
    height: 28px;
  }

  .agent-summary {
    line-height: 1.4;
  }

  .drawer-header {
    padding: 10px 12px;
  }
}
</style>
