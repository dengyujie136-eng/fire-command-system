<template>
  <div class="fusion-container" :class="{ compact: compactMode }">
    <!-- 顶部状态条 -->
    <div class="top-bar">
      <div class="capsule left">
        <span class="cap-value">{{ fusionResult.fire_estimation }}</span>
        <span class="cap-unit">m²</span>
      </div>
      <div class="capsule center">
        <div class="cap-row">
          <span class="cap-label">CPU</span>
          <div class="cap-progress"><div class="cap-progress-fill" :style="{ width: sysInfo.cpu + '%' }"></div></div>
          <span class="cap-num">{{ sysInfo.cpu }}%</span>
        </div>
        <div class="cap-row">
          <span class="cap-label">内存</span>
          <div class="cap-progress"><div class="cap-progress-fill" :style="{ width: sysInfo.memory + '%' }"></div></div>
          <span class="cap-num">{{ sysInfo.memory }}%</span>
        </div>
      </div>
      <div class="capsule right">
        <div class="cap-row">
          <span class="cap-label">总数据</span>
          <span class="cap-value-sm">{{ dataStats.volume }}</span>
        </div>
        <div class="cap-row">
          <span class="cap-label">覆盖率</span>
          <span class="cap-value-sm">{{ dataStats.coverage }}%</span>
        </div>
      </div>
      <button class="more-btn" @click="showMoreInfo = !showMoreInfo" title="更多信息">
        <span>⋮</span>
      </button>
      <transition name="fade">
        <div v-if="showMoreInfo" class="more-info-popup">
          <div class="more-item">
            <span class="more-icon">🔥</span>
            <span class="more-label">活跃火源</span>
            <span class="more-value">{{ fireStat.active }}</span>
          </div>
          <div class="more-item">
            <span class="more-icon">✈️</span>
            <span class="more-label">在线无人机</span>
            <span class="more-value">{{ uavStat.online }}</span>
          </div>
        </div>
      </transition>
    </div>

    <!-- 主内容区 -->
    <div class="main-content">
      <!-- 左侧面板 -->
      <div class="side-panel left" :class="{ collapsed: leftCollapsed }">
        <button class="collapse-btn" @click="leftCollapsed = !leftCollapsed" :title="leftCollapsed ? '展开面板' : '收起面板'">
          {{ leftCollapsed ? '→' : '←' }}
        </button>

        <template v-if="!leftCollapsed">
          <!-- 卡片A - 数据源控制 -->
          <div class="glass-card">
            <div class="card-title">数据源控制</div>
            <div class="source-buttons">
              <button 
                v-for="src in sourceTypes" 
                :key="src.id"
                class="source-btn"
                :class="{ on: sources[src.id] }"
                @click="sources[src.id] = !sources[src.id]"
              >
                <span class="src-icon">{{ src.icon }}</span>
                <span class="src-label">{{ src.label }}</span>
              </button>
            </div>
            <div class="confidence-control">
              <div class="conf-header">
                <span class="conf-label">融合置信度</span>
                <span class="conf-value">{{ fusionResult.confidence }}%</span>
              </div>
              <input 
                type="range" 
                v-model="fusionResult.confidence" 
                min="0" 
                max="100" 
                class="conf-slider"
                @input="onConfidenceChange"
              />
            </div>
          </div>

          <!-- 卡片B - 数据源列表 -->
          <div class="glass-card">
            <div class="card-title">活跃数据源</div>
            <div class="source-list">
              <div v-for="src in activeSources" :key="src.name" class="source-item">
                <span class="src-type">{{ src.type }}</span>
                <span class="src-name">{{ src.name }}</span>
                <span class="src-status" :class="src.status">{{ src.status === 'online' ? '●' : '○' }}</span>
              </div>
            </div>
            <button class="more-link" @click="showSourceDrawer = true">查看全部数据源</button>
          </div>

          <!-- 卡片C - 融合流程 -->
          <div class="glass-card">
            <div class="card-title">融合流程</div>
            <div class="process-steps">
              <div 
                v-for="(step, idx) in processSteps" 
                :key="idx" 
                class="step"
                :class="{ active: currentStep === idx }"
              >
                <div class="step-dot"></div>
                <span class="step-label">{{ step }}</span>
              </div>
            </div>
            <div class="process-progress">
              <div class="progress-bar">
                <div class="progress-fill" :style="{ width: processProgress + '%' }"></div>
              </div>
              <span class="progress-text">{{ processProgress }}%</span>
            </div>
          </div>
        </template>

        <!-- 折叠状态 -->
        <template v-else>
          <div class="collapsed-icons">
            <div class="ico-item" title="数据源控制" @click="sources.satellite = !sources.satellite">📡</div>
            <div class="ico-item" title="数据源列表" @click="showSourceDrawer = true">📋</div>
            <div class="ico-item" title="融合流程">⚙️</div>
          </div>
        </template>
      </div>

      <!-- 中央主区域 -->
      <div class="center-area">
        <div class="map-section">
          <div ref="mapRef" class="map-container"></div>
          <div class="map-float-controls">
            <div class="legend-group">
              <div class="legend-item"><span class="legend-dot fire"></span>火点</div>
              <div class="legend-item"><span class="legend-dot uav"></span>无人机</div>
              <div class="legend-item"><span class="legend-dot sensor"></span>传感器</div>
            </div>
            <div class="zoom-group">
              <button class="zoom-btn" @click="zoomIn">+</button>
              <button class="zoom-btn" @click="zoomOut">−</button>
              <button class="zoom-btn" @click="resetView">⌂</button>
            </div>
          </div>
        </div>
        <div class="preview-section">
          <div class="preview-grid">
            <div 
              v-for="preview in previews" 
              :key="preview.id" 
              class="preview-card"
              @click="showPreviewModal(preview)"
            >
              <div class="preview-icon">{{ preview.icon }}</div>
              <div class="preview-title">{{ preview.title }}</div>
              <div class="preview-hint">点击放大</div>
            </div>
          </div>
          <button class="fire-resource-btn" @click="showFireResourceDrawer = true">
            <span>🔥</span>
            <span>火点无人机资源</span>
          </button>
        </div>
      </div>

      <!-- 右侧面板 -->
      <div class="side-panel right" :class="{ collapsed: rightCollapsed }">
        <button class="collapse-btn" @click="rightCollapsed = !rightCollapsed" :title="rightCollapsed ? '展开面板' : '收起面板'">
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
              {{ tab.icon }}
              <span class="tab-text">{{ tab.label }}</span>
            </div>
          </div>

          <div class="tab-content">
            <!-- 数据质量 -->
            <div v-if="activeTab === 'quality'" class="tab-inner">
              <div class="quality-metrics">
                <div class="quality-item">
                  <div class="quality-ring">
                    <svg viewBox="0 0 100 100" class="ring-svg">
                      <circle cx="50" cy="50" r="42" fill="none" stroke="rgba(255,255,255,0.1)" stroke-width="8"/>
                      <circle cx="50" cy="50" r="42" fill="none" stroke="#34d399" stroke-width="8" stroke-linecap="round" :stroke-dasharray="`${qualityData.completeness * 2.64} 264`"/>
                    </svg>
                    <span class="ring-value">{{ qualityData.completeness }}%</span>
                  </div>
                  <span class="quality-label">完整性</span>
                </div>
                <div class="quality-item">
                  <div class="quality-ring">
                    <svg viewBox="0 0 100 100" class="ring-svg">
                      <circle cx="50" cy="50" r="42" fill="none" stroke="rgba(255,255,255,0.1)" stroke-width="8"/>
                      <circle cx="50" cy="50" r="42" fill="none" stroke="#60a5fa" stroke-width="8" stroke-linecap="round" :stroke-dasharray="`${qualityData.accuracy * 2.64} 264`"/>
                    </svg>
                    <span class="ring-value">{{ qualityData.accuracy }}%</span>
                  </div>
                  <span class="quality-label">准确性</span>
                </div>
              </div>
              <div class="preview-thumbs">
                <div 
                  v-for="preview in previews" 
                  :key="preview.id" 
                  class="thumb-item"
                  @click="showPreviewModal(preview)"
                >
                  <div class="thumb-icon">{{ preview.icon }}</div>
                  <span class="thumb-title">{{ preview.title }}</span>
                </div>
              </div>
            </div>

            <!-- 相关性分析 -->
            <div v-if="activeTab === 'correlation'" class="tab-inner">
              <div class="correlation-items">
                <div v-for="item in correlationData" :key="item.label" class="corr-item">
                  <div class="corr-header">
                    <span class="corr-icon">{{ item.icon }}</span>
                    <span class="corr-label">{{ item.label }}</span>
                    <span class="corr-value">{{ item.value }} {{ item.unit }}</span>
                    <span class="corr-trend" :class="item.trend">{{ item.trend === 'up' ? '↑' : '↓' }}</span>
                  </div>
                  <div ref="miniChartRef" class="mini-chart">
                    <svg viewBox="0 0 100 30" preserveAspectRatio="none">
                      <defs>
                        <linearGradient :id="'grad-' + item.label" x1="0%" y1="0%" x2="0%" y2="100%">
                          <stop offset="0%" :stop-color="item.color" stop-opacity="0.3"/>
                          <stop offset="100%" :stop-color="item.color" stop-opacity="0"/>
                        </linearGradient>
                      </defs>
                      <path :d="getMiniChartPath(item.data)" :fill="'url(#grad-' + item.label + ')'" />
                      <path :d="getMiniChartPath(item.data)" fill="none" :stroke="item.color" stroke-width="2" />
                    </svg>
                  </div>
                </div>
              </div>
              <button class="more-link" @click="showCorrelationDrawer = true">高级分析</button>
            </div>

            <!-- 数据统计 -->
            <div v-if="activeTab === 'statistics'" class="tab-inner">
              <div class="stats-main">
                <span class="stats-label">记录数</span>
                <span class="stats-value">{{ dataStats.records }}</span>
              </div>
              <div class="stats-dist">
                <div class="dist-title">数据源分布</div>
                <div class="dist-bars">
                  <div v-for="dist in dataDistribution" :key="dist.name" class="dist-bar-item">
                    <span class="dist-label">{{ dist.name }}</span>
                    <div class="dist-bar">
                      <div class="dist-bar-fill" :style="{ width: dist.percent + '%', background: dist.color }"></div>
                    </div>
                    <span class="dist-percent">{{ dist.percent }}%</span>
                  </div>
                </div>
              </div>
              <button class="more-link" @click="showDistributionMap = !showDistributionMap">在地图上显示分布</button>
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
              @click="activeTab = tab.id"
            >
              {{ tab.icon }}
            </div>
          </div>
        </template>
      </div>
    </div>

    <!-- 数据源抽屉 -->
    <transition name="drawer">
      <div v-if="showSourceDrawer" class="drawer-overlay" @click="showSourceDrawer = false">
        <div class="drawer-content" @click.stop>
          <div class="drawer-header">
            全部数据源
            <button class="close-drawer" @click="showSourceDrawer = false">✕</button>
          </div>
          <div class="drawer-body source-list-full">
            <div v-for="src in sourceList" :key="src.name" class="drawer-source-item">
              <span class="drawer-src-icon">{{ getSourceIcon(src.type) }}</span>
              <div class="drawer-src-info">
                <span class="drawer-src-name">{{ src.name }}</span>
                <span class="drawer-src-type">{{ src.type }}</span>
              </div>
              <span class="drawer-src-status" :class="src.status">{{ src.status === 'online' ? '在线' : '离线' }}</span>
            </div>
          </div>
        </div>
      </div>
    </transition>

    <!-- 相关性分析抽屉 -->
    <transition name="drawer">
      <div v-if="showCorrelationDrawer" class="drawer-overlay" @click="showCorrelationDrawer = false">
        <div class="drawer-content" @click.stop>
          <div class="drawer-header">
            相关性矩阵分析
            <button class="close-drawer" @click="showCorrelationDrawer = false">✕</button>
          </div>
          <div class="drawer-body">
            <div ref="correlationHeatmapRef" class="correlation-heatmap" style="height: 250px;"></div>
          </div>
        </div>
      </div>
    </transition>

    <!-- 火点资源抽屉 -->
    <transition name="drawer">
      <div v-if="showFireResourceDrawer" class="drawer-overlay" @click="showFireResourceDrawer = false">
        <div class="drawer-content" @click.stop>
          <div class="drawer-header">
            火点无人机资源清单
            <button class="close-drawer" @click="showFireResourceDrawer = false">✕</button>
          </div>
          <div class="drawer-body">
            <div v-for="resource in fireResources" :key="resource.id" class="fire-resource-item">
              <span class="fire-res-icon">{{ resource.icon }}</span>
              <div class="fire-res-info">
                <span class="fire-res-name">{{ resource.name }}</span>
                <span class="fire-res-pos">位置: {{ resource.position }}</span>
              </div>
              <el-tag :type="resource.status === 'available' ? 'success' : 'warning'" size="small">
                {{ resource.status === 'available' ? '可用' : '任务中' }}
              </el-tag>
            </div>
          </div>
        </div>
      </div>
    </transition>

    <!-- 预览模态框 -->
    <el-dialog v-model="showPreview" title="数据预览" width="60%" :close-on-click-modal="true">
      <div v-if="selectedPreview" class="preview-modal-content">
        <div class="preview-modal-icon">{{ selectedPreview.icon }}</div>
        <h3>{{ selectedPreview.title }}</h3>
        <p>{{ selectedPreview.description }}</p>
        <div class="preview-modal-preview">{{ selectedPreview.preview }}</div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, nextTick, onMounted, onUnmounted } from 'vue'
import { fireAPI, sensorAPI, uavAPI, systemAPI } from '../api/modules'
import * as echarts from 'echarts'
import mapboxgl from 'mapbox-gl'

const mapRef = ref<HTMLDivElement>()
const correlationHeatmapRef = ref<HTMLDivElement>()

// 状态
const leftCollapsed = ref(false)
const rightCollapsed = ref(false)
const autoCompactMode = ref(false)
const manualCompactMode = ref(false)
/* 自动紧凑与手动紧凑叠加：小屏强制 compact，键盘 C 保留人工切换能力。 */
const compactMode = computed(() => autoCompactMode.value || manualCompactMode.value)
const activeTab = ref('quality')
const showMoreInfo = ref(false)
const showSourceDrawer = ref(false)
const showCorrelationDrawer = ref(false)
const showFireResourceDrawer = ref(false)
const showPreview = ref(false)
const selectedPreview = ref<any>(null)
const showDistributionMap = ref(false)

// 数据
const sources = reactive({ satellite: true, uav: true, sensor: true })
const sourceTypes = [
  { id: 'satellite', label: '卫星', icon: '🛰️' },
  { id: 'uav', label: '无人机', icon: '✈️' },
  { id: 'sensor', label: '传感器', icon: '📡' }
]
const statData = ref<any>({})
const fireStat = ref({ active: 5 })
const uavStat = ref({ online: 8 })
const sensorStat = ref({ active: 25 })
const sourceList = ref<any[]>([])
const fusionResult = ref({ confidence: 85, fire_estimation: 1250 })
const dataStats = ref({ volume: '12.5 GB', records: '1,240,000', coverage: 94 })
const sysInfo = reactive({ cpu: 45, memory: 62 })
const processSteps = ['采集', '配准', '融合', '输出']
const currentStep = ref(2)
const processProgress = ref(78)

const qualityData = reactive({ completeness: 98, accuracy: 95 })

const correlationData = [
  { label: 'PM2.5', value: 45, unit: 'μg/m³', icon: '💨', trend: 'up', color: '#f59e0b', data: [30, 35, 40, 38, 42, 45] },
  { label: '风速', value: 3.2, unit: 'm/s', icon: '🌬️', trend: 'down', color: '#60a5fa', data: [4.5, 4.0, 3.8, 3.5, 3.3, 3.2] },
  { label: '湿度', value: 42, unit: '%', icon: '💧', trend: 'up', color: '#34d399', data: [38, 39, 40, 41, 42, 42] }
]

const dataDistribution = [
  { name: '卫星', percent: 52, color: '#60a5fa' },
  { name: '无人机', percent: 30, color: '#f59e0b' },
  { name: '传感器', percent: 18, color: '#34d399' }
]

const previews = [
  { id: 1, icon: '🔥', title: '热红外', description: '红外热成像数据预览', preview: '热红外图像数据展示区域' },
  { id: 2, icon: '📷', title: '可见光', description: '可见光图像数据预览', preview: '可见光图像数据展示区域' },
  { id: 3, icon: '🗺️', title: '卫星', description: '卫星遥感数据预览', preview: '卫星图像数据展示区域' },
  { id: 4, icon: '📊', title: '气象', description: '气象数据预览', preview: '气象数据可视化展示' }
]

const fireResources = [
  { id: 1, icon: '✈️', name: '无人机-01', position: '北纬39.9°, 东经116.4°', status: 'available' },
  { id: 2, icon: '✈️', name: '无人机-02', position: '北纬39.8°, 东经116.5°', status: 'tasking' },
  { id: 3, icon: '🚁', name: '直升机-01', position: '北纬40.0°, 东经116.3°', status: 'available' }
]

const tabs = [
  { id: 'quality', label: '数据质量', icon: '📊' },
  { id: 'correlation', label: '相关性', icon: '🔗' },
  { id: 'statistics', label: '统计', icon: '📈' }
]

// 计算活跃数据源（前3个）
const activeSources = ref<any[]>([
  { type: '卫星', name: 'Sentinel-2', status: 'online' },
  { type: '无人机', name: 'DJI Mavic 3', status: 'online' },
  { type: '传感器', name: '地面气象站', status: 'online' }
])

let map: mapboxgl.Map | null = null
let heatmapChart: echarts.ECharts | null = null
let resizeHandler: (() => void) | null = null

function updateResponsiveLayout() {
  const width = window.innerWidth
  const height = window.innerHeight
  /* <=1366px 或 <=700px 自动启用紧凑尺寸，减少固定 px 造成的纵向溢出。 */
  autoCompactMode.value = width <= 1366 || height <= 700
  /* <=1100px 默认折叠右侧面板，给中心地图和预览区保留可视宽度。 */
  if (width <= 1100) rightCollapsed.value = true
  nextTick(() => {
    map?.resize()
    heatmapChart?.resize()
  })
}

function handleKeydown(e: KeyboardEvent) {
  if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement || e.target instanceof HTMLTextAreaElement) return
  switch (e.key.toLowerCase()) {
    case 'l': leftCollapsed.value = !leftCollapsed.value; break
    case 'r': rightCollapsed.value = !rightCollapsed.value; break
    case 'c': manualCompactMode.value = !manualCompactMode.value; break
  }
}

function getSourceIcon(type: string) {
  const icons: Record<string, string> = { '卫星': '🛰️', '无人机': '✈️', '传感器': '📡' }
  return icons[type] || '📦'
}

function getMiniChartPath(data: number[]) {
  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1
  const width = 100
  const height = 30
  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * width
    const y = height - ((v - min) / range) * height
    return `${x},${y}`
  })
  return `M ${points.join(' L ')} L ${width},${height} L 0,${height} Z`
}

function showPreviewModal(preview: any) {
  selectedPreview.value = preview
  showPreview.value = true
}

function onConfidenceChange() {
  // 融合置信度变化时的处理
}

// 地图相关
function zoomIn() { if (map) map.zoomIn() }
function zoomOut() { if (map) map.zoomOut() }
function resetView() { if (map) map.flyTo({ center: [116.4, 39.9], zoom: 10 }) }

async function loadData() {
  try {
    const [sensors, uavs, sysStatus] = await Promise.all([
      sensorAPI.getList().catch(() => []),
      uavAPI.getList().catch(() => []),
      systemAPI.getStatus().catch(() => ({ cpu: 45, memory: 62 }))
    ])
    sourceList.value = sensors.map((s: any) => ({ ...s, type: '传感器' })).concat(uavs.slice(0, 5).map((u: any) => ({ ...u, type: '无人机' })))
    uavStat.value = { online: uavs.filter((u: any) => u.status === 'online').length }
    sensorStat.value = { active: sensors.filter((s: any) => s.status === 'online').length }
    if (sysStatus) {
      sysInfo.cpu = sysStatus.cpu || 45
      sysInfo.memory = sysStatus.memory || 62
    }
  } catch (e) {
    console.error('Failed to load data:', e)
  }
}

function initHeatmapChart() {
  if (!correlationHeatmapRef.value) return
  heatmapChart = echarts.init(correlationHeatmapRef.value)
  const labels = ['温度', '湿度', '风速', 'PM2.5', '气压', '能见度']
  const data: number[][] = []
  for (let i = 0; i < labels.length; i++) {
    for (let j = 0; j < labels.length; j++) {
      data.push([i, j, i === j ? 100 : Math.floor(Math.random() * 60 + 30)])
    }
  }
  heatmapChart.setOption({
    tooltip: { position: 'top' },
    grid: { top: 30, bottom: 30, left: 60, right: 10 },
    xAxis: { type: 'category', data: labels, axisLabel: { color: '#94a3b8', fontSize: 12 } },
    yAxis: { type: 'category', data: labels, axisLabel: { color: '#94a3b8', fontSize: 12 } },
    visualMap: { min: 0, max: 100, calculable: true, orient: 'horizontal', left: 'center', bottom: 5, inRange: { color: ['#1e3a5f', '#3b82f6', '#f59e0b'] }, textStyle: { color: '#94a3b8' } },
    series: [{ type: 'heatmap', data, label: { show: true, color: '#fff', fontSize: 10 }, emphasis: { itemStyle: { shadowBlur: 10 } } }]
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

onMounted(() => {
  updateResponsiveLayout()
  initMap()
  loadData()
  resizeHandler = updateResponsiveLayout
  window.addEventListener('resize', resizeHandler)
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  if (resizeHandler) window.removeEventListener('resize', resizeHandler)
  window.removeEventListener('keydown', handleKeydown)
  heatmapChart?.dispose()
  map?.remove()
})
</script>

<style scoped>
.fusion-container {
  /* 继承 App 主区域高度，避免 AppHeader + 页面 100vh 叠加产生浏览器滚动条。 */
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: linear-gradient(180deg, #0A0F1A 0%, #162035 100%);
  display: flex;
  flex-direction: column;
  color: #e2e8f0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}

/* 顶部状态条 */
.top-bar {
  /* 顶部栏使用 clamp，在低高度屏幕中自动压缩。 */
  height: clamp(48px, 8vh, 64px);
  flex: 0 0 clamp(48px, 8vh, 64px);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: clamp(8px, 1vw, 20px);
  padding: 0 clamp(10px, 1.7vw, 32px);
  background: rgba(20, 28, 40, 0.9);
  border-bottom: 1px solid rgba(255,255,255,0.06);
  backdrop-filter: blur(16px);
  position: relative;
}

.capsule {
  display: flex;
  align-items: center;
  /* 胶囊 padding 随视口收缩，防止顶部区域横向溢出。 */
  padding: clamp(5px, 0.75vh, 8px) clamp(8px, 1vw, 20px);
  border-radius: 40px;
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(255,255,255,0.12);
  backdrop-filter: blur(10px);
}

.capsule.left {
  gap: 6px;
  min-width: 0;
  width: clamp(112px, 12vw, 140px);
  justify-content: center;
}
.capsule.center {
  flex-direction: column;
  gap: 4px;
  min-width: 0;
  width: clamp(136px, 16vw, 180px);
}
.capsule.right {
  flex-direction: column;
  gap: 4px;
  min-width: 0;
  width: clamp(120px, 14vw, 160px);
}

.cap-value {
  font-size: clamp(18px, 1.45vw, 28px);
  font-weight: 700;
  background: linear-gradient(90deg, #fff, #67e8f9);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.cap-unit { font-size: clamp(9px, 0.65vw, 12px); color: #94a3b8; }

.cap-row {
  display: flex;
  align-items: center;
  gap: clamp(4px, 0.5vw, 8px);
  width: 100%;
}

.cap-label { font-size: clamp(9px, 0.6vw, 11px); color: #64748b; width: clamp(24px, 2vw, 30px); }
.cap-value-sm { font-size: clamp(11px, 0.75vw, 14px); font-weight: 600; }
.cap-num { font-size: clamp(10px, 0.7vw, 12px); font-weight: 600; color: #60a5fa; }

.cap-progress {
  flex: 1;
  height: 4px;
  background: rgba(255,255,255,0.1);
  border-radius: 2px;
  overflow: hidden;
}

.cap-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6, #6366f1);
  border-radius: 2px;
  transition: width 0.3s ease;
}

.more-btn {
  position: absolute;
  right: clamp(10px, 1.7vw, 32px);
  width: clamp(30px, 4.8vh, 36px);
  height: clamp(30px, 4.8vh, 36px);
  border-radius: 50%;
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(255,255,255,0.1);
  color: #94a3b8;
  font-size: 18px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.more-btn:hover {
  background: rgba(96,165,250,0.2);
  color: #60a5fa;
}

.more-info-popup {
  position: absolute;
  right: clamp(10px, 1.7vw, 32px);
  top: clamp(52px, 8.8vh, 70px);
  background: rgba(20,28,40,0.95);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 12px;
  padding: 12px;
  min-width: clamp(160px, 16vw, 200px);
  backdrop-filter: blur(12px);
  z-index: 100;
}

.more-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid rgba(255,255,255,0.04);
}

.more-item:last-child { border-bottom: none; }
.more-icon { font-size: 16px; }
.more-label { flex: 1; font-size: 13px; color: #94a3b8; }
.more-value { font-size: 14px; font-weight: 600; }

/* 主内容区 */
.main-content {
  flex: 1;
  display: flex;
  min-height: 0;
  min-width: 0;
  overflow: hidden;
}

/* 侧边面板 */
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
  border-radius: 20px;
  /* 卡片 padding 使用 clamp，低屏幕下减少纵向累计高度。 */
  padding: clamp(8px, 1.2vh, 16px);
  box-shadow: 0 8px 32px rgba(0,0,0,0.3);
  backdrop-filter: blur(16px);
  min-height: 0;
  overflow: hidden;
}

.side-panel > .glass-card {
  flex: 1 1 0;
  display: flex;
  flex-direction: column;
}

.card-title {
  font-size: clamp(10px, 0.72vw, 13px);
  font-weight: 600;
  color: #cbd5e1;
  margin-bottom: clamp(6px, 1vh, 14px);
  letter-spacing: 0.5px;
}

/* 数据源控制 */
.source-buttons {
  display: grid;
  grid-template-columns: 1fr;
  gap: clamp(4px, 0.75vh, 8px);
  margin-bottom: clamp(6px, 1vh, 16px);
}

.source-btn {
  display: flex;
  align-items: center;
  gap: clamp(5px, 0.55vw, 10px);
  padding: clamp(6px, 0.9vh, 10px) clamp(7px, 0.7vw, 12px);
  border-radius: 14px;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.06);
  color: #94a3b8;
  font-size: clamp(10px, 0.7vw, 13px);
  cursor: pointer;
  transition: all 0.2s ease;
}

.source-btn:hover {
  background: rgba(96,165,250,0.1);
  color: #cbd5e1;
}

.source-btn.on {
  background: rgba(96,165,250,0.18);
  border-color: rgba(96,165,250,0.4);
  color: #60a5fa;
}

.src-icon { font-size: 18px; }

/* 置信度控制 */
.confidence-control {
  padding-top: clamp(6px, 0.9vh, 12px);
  border-top: 1px solid rgba(255,255,255,0.06);
}

.conf-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: clamp(4px, 0.7vh, 8px);
}

.conf-label { font-size: 12px; color: #64748b; }
.conf-value { font-size: 14px; font-weight: 700; color: #f59e0b; }

.conf-slider {
  width: 100%;
  height: 6px;
  -webkit-appearance: none;
  appearance: none;
  background: rgba(255,255,255,0.1);
  border-radius: 3px;
  outline: none;
}

.conf-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #f59e0b;
  cursor: pointer;
  box-shadow: 0 0 12px rgba(245,158,11,0.5);
}

/* 数据源列表 */
.source-list {
  display: flex;
  flex-direction: column;
  gap: clamp(3px, 0.6vh, 6px);
  margin-bottom: clamp(4px, 0.8vh, 12px);
  min-height: 0;
  overflow: hidden;
}

.source-item {
  display: flex;
  align-items: center;
  gap: clamp(5px, 0.55vw, 10px);
  padding: clamp(5px, 0.7vh, 8px) clamp(6px, 0.6vw, 10px);
  border-radius: 10px;
  background: rgba(255,255,255,0.03);
}

.src-type {
  font-size: 10px;
  color: #64748b;
  background: rgba(96,165,250,0.1);
  padding: 2px 6px;
  border-radius: 4px;
}

.src-name { flex: 1; font-size: 12px; }
.src-status { font-size: 10px; }
.src-status.online { color: #22c55e; }
.src-status.offline { color: #64748b; }

/* 融合流程 */
.process-steps {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: clamp(6px, 1vh, 16px);
}

.step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.step-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: rgba(255,255,255,0.2);
  transition: all 0.2s ease;
}

.step.active .step-dot {
  background: #60a5fa;
  box-shadow: 0 0 12px rgba(96,165,250,0.6);
}

.step-label { font-size: 11px; color: #64748b; }
.step.active .step-label { color: #e2e8f0; }

.process-progress {
  display: flex;
  align-items: center;
  gap: 10px;
}

.progress-bar {
  flex: 1;
  height: 4px;
  background: rgba(255,255,255,0.1);
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6, #10b981);
  border-radius: 2px;
  transition: width 0.3s ease;
}

.progress-text { font-size: 12px; color: #60a5fa; font-weight: 600; }

/* 折叠图标 */
.collapsed-icons {
  display: flex;
  flex-direction: column;
  gap: clamp(8px, 1.6vh, 16px);
  align-items: center;
  padding-top: clamp(14px, 3vh, 24px);
}

.ico-item {
  width: clamp(32px, 4.8vh, 40px);
  height: clamp(32px, 4.8vh, 40px);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  background: rgba(255,255,255,0.05);
  cursor: pointer;
  font-size: 18px;
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

/* 中央区域 */
.center-area {
  flex: 1;
  display: flex;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.map-section {
  flex: 0.7;
  position: relative;
  min-width: 0;
  min-height: 0;
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
  gap: 12px;
  z-index: 10;
}

.legend-group {
  background: rgba(20,28,40,0.8);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 12px;
  padding: clamp(6px, 0.8vh, 10px) clamp(8px, 0.8vw, 12px);
  backdrop-filter: blur(8px);
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  margin-bottom: 4px;
}

.legend-item:last-child { margin-bottom: 0; }

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.legend-dot.fire { background: #ef4444; }
.legend-dot.uav { background: #3b82f6; }
.legend-dot.sensor { background: #22c55e; }

.zoom-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.zoom-btn {
  width: clamp(30px, 4.8vh, 36px);
  height: clamp(30px, 4.8vh, 36px);
  border-radius: 10px;
  background: rgba(20,28,40,0.8);
  border: 1px solid rgba(255,255,255,0.08);
  color: #e2e8f0;
  font-size: 16px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.zoom-btn:hover {
  background: rgba(96,165,250,0.2);
  transform: scale(1.05);
}

/* 预览区域 */
.preview-section {
  flex: 0.3;
  display: flex;
  flex-direction: column;
  padding: clamp(6px, 1vh, 12px);
  gap: clamp(6px, 1vh, 12px);
  background: rgba(20,28,40,0.5);
  border-left: 1px solid rgba(255,255,255,0.04);
}

.preview-grid {
  display: grid;
  grid-template-columns: repeat(2,1fr);
  gap: clamp(5px, 0.8vh, 10px);
  min-height: 0;
}

.preview-card {
  aspect-ratio: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.preview-card:hover {
  background: rgba(96,165,250,0.1);
  border-color: rgba(96,165,250,0.3);
  transform: translateY(-2px);
}

.preview-icon { font-size: clamp(18px, 1.5vw, 28px); }
.preview-title { font-size: clamp(10px, 0.68vw, 12px); font-weight: 500; }
.preview-hint { font-size: clamp(8px, 0.58vw, 10px); color: #64748b; }

.fire-resource-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: clamp(4px, 0.5vw, 8px);
  padding: clamp(7px, 1vh, 12px);
  background: rgba(239,68,68,0.1);
  border: 1px solid rgba(239,68,68,0.3);
  border-radius: 12px;
  color: #f87171;
  font-size: clamp(10px, 0.7vw, 13px);
  cursor: pointer;
  transition: all 0.2s ease;
}

.fire-resource-btn:hover {
  background: rgba(239,68,68,0.2);
  transform: scale(1.02);
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
  border-radius: 20px;
  padding: clamp(8px, 1.2vh, 16px);
  box-shadow: 0 8px 32px rgba(0,0,0,0.3);
  backdrop-filter: blur(16px);
  overflow: hidden;
}

.tab-inner {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

/* 数据质量 */
.quality-metrics {
  display: flex;
  justify-content: center;
  gap: clamp(12px, 1.25vw, 24px);
  margin-bottom: clamp(8px, 1.2vh, 20px);
}

.quality-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.quality-ring {
  position: relative;
  width: clamp(54px, 8vh, 80px);
  height: clamp(54px, 8vh, 80px);
}

.ring-svg { width: 100%; height: 100%; transform: rotate(-90deg); }

.ring-value {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: clamp(11px, 0.85vw, 16px);
  font-weight: 700;
  color: #e2e8f0;
}

.quality-label { font-size: 12px; color: #64748b; }

.preview-thumbs {
  display: grid;
  grid-template-columns: repeat(2,1fr);
  gap: clamp(4px, 0.65vh, 8px);
  min-height: 0;
}

.thumb-item {
  aspect-ratio: 3/2;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: clamp(2px, 0.45vh, 4px);
  background: rgba(255,255,255,0.04);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.thumb-item:hover {
  background: rgba(96,165,250,0.1);
  transform: scale(1.02);
}

.thumb-icon { font-size: clamp(14px, 1vw, 20px); }
.thumb-title { font-size: clamp(9px, 0.6vw, 11px); }

/* 相关性分析 */
.correlation-items {
  display: flex;
  flex-direction: column;
  gap: clamp(6px, 1vh, 16px);
  min-height: 0;
  overflow: hidden;
}

.corr-item {
  padding: clamp(6px, 1vh, 12px);
  background: rgba(255,255,255,0.04);
  border-radius: 12px;
}

.corr-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: clamp(4px, 0.7vh, 8px);
}

.corr-icon { font-size: 16px; }
.corr-label { flex: 1; font-size: 12px; }
.corr-value { font-size: 14px; font-weight: 600; }
.corr-trend {
  font-size: 14px;
  font-weight: bold;
}
.corr-trend.up { color: #ef4444; }
.corr-trend.down { color: #22c55e; }

.mini-chart {
  width: 100%;
  height: 30px;
}

/* 数据统计 */
.stats-main {
  text-align: center;
  margin-bottom: clamp(8px, 1.2vh, 20px);
  padding: clamp(8px, 1.2vh, 16px);
  background: rgba(255,255,255,0.04);
  border-radius: 12px;
}

.stats-label { display: block; font-size: 12px; color: #64748b; margin-bottom: 4px; }
.stats-value {
  font-size: clamp(18px, 1.45vw, 28px);
  font-weight: 700;
  background: linear-gradient(90deg, #fff, #67e8f9);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.stats-dist {
  flex: 1;
}

.dist-title { font-size: 12px; color: #64748b; margin-bottom: 12px; }

.dist-bars {
  display: flex;
  flex-direction: column;
  gap: clamp(5px, 0.8vh, 10px);
}

.dist-bar-item {
  display: flex;
  align-items: center;
  gap: 10px;
}

.dist-label { width: 50px; font-size: 12px; }
.dist-bar {
  flex: 1;
  height: 6px;
  background: rgba(255,255,255,0.1);
  border-radius: 3px;
  overflow: hidden;
}

.dist-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s ease;
}

.dist-percent { width: 35px; font-size: 12px; text-align: right; }

/* 通用链接 */
.more-link {
  border: none;
  background: none;
  color: #60a5fa;
  font-size: 12px;
  cursor: pointer;
  padding: clamp(4px, 0.75vh, 8px) 0;
  text-align: left;
}

.more-link:hover { text-decoration: underline; }

/* 抽屉样式 */
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
  width: clamp(280px, 32vw, 360px);
  height: 100%;
  background: rgba(20,28,40,0.95);
  border-left: 1px solid rgba(255,255,255,0.08);
  backdrop-filter: blur(12px);
  display: flex;
  flex-direction: column;
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
  /* 抽屉不再使用 overflow-y:auto，内容通过紧凑间距和隐藏次要信息适配。 */
  overflow: hidden;
  min-height: 0;
}

.drawer-source-item {
  display: flex;
  align-items: center;
  gap: clamp(6px, 0.7vw, 12px);
  padding: clamp(7px, 1vh, 12px);
  border-radius: 12px;
  background: rgba(255,255,255,0.03);
  margin-bottom: clamp(4px, 0.8vh, 8px);
}

.drawer-src-icon { font-size: 20px; }

.drawer-src-info {
  flex: 1;
}

.drawer-src-name {
  display: block;
  font-size: 13px;
  font-weight: 500;
}

.drawer-src-type {
  display: block;
  font-size: 11px;
  color: #64748b;
}

.drawer-src-status {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
}

.drawer-src-status.online {
  background: rgba(34,197,94,0.15);
  color: #22c55e;
}

.drawer-src-status.offline {
  background: rgba(100,116,139,0.15);
  color: #64748b;
}

.fire-resource-item {
  display: flex;
  align-items: center;
  gap: clamp(6px, 0.7vw, 12px);
  padding: clamp(7px, 1vh, 12px);
  border-radius: 12px;
  background: rgba(255,255,255,0.03);
  margin-bottom: clamp(4px, 0.8vh, 8px);
}

.fire-res-icon { font-size: 20px; }

.fire-res-info { flex: 1; }

.fire-res-name {
  display: block;
  font-size: 13px;
  font-weight: 500;
}

.fire-res-pos {
  display: block;
  font-size: 11px;
  color: #64748b;
}

.correlation-heatmap {
  width: 100%;
}

/* 预览模态框 */
.preview-modal-content {
  text-align: center;
  padding: 20px;
}

.preview-modal-icon { font-size: 48px; margin-bottom: 16px; }

.preview-modal-preview {
  margin-top: 16px;
  padding: 20px;
  background: rgba(255,255,255,0.04);
  border-radius: 12px;
  color: #94a3b8;
}

/* 淡入动画 */
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from, .fade-leave-to {
  opacity: 0;
}

.compact .top-bar {
  height: clamp(46px, 7vh, 52px);
  flex-basis: clamp(46px, 7vh, 52px);
  gap: 8px;
  padding: 0 clamp(8px, 1.2vw, 16px);
}

.compact .capsule {
  padding: 6px 10px;
}

.compact .cap-value {
  font-size: 18px;
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

.compact .source-btn,
.compact .source-item,
.compact .corr-item {
  padding: 5px 7px;
}

.compact .source-buttons,
.compact .source-list,
.compact .correlation-items {
  gap: 5px;
}

.compact .quality-ring {
  width: 56px;
  height: 56px;
}

.compact .preview-hint,
.compact .thumb-title {
  /* 小屏隐藏次要提示文字，避免预览卡片内部溢出。 */
  display: none;
}

@media (max-width: 1366px) {
  .fusion-container {
    font-size: 12px;
  }

  .top-bar {
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

  .quality-ring {
    width: 56px;
    height: 56px;
  }

  .preview-hint {
    display: none;
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
    bottom: 0;
    z-index: 30;
    width: min(260px, 32vw);
    flex-basis: min(260px, 32vw);
    background: rgba(10,15,26,0.92);
  }

  .capsule.right {
    display: none;
  }

  .preview-section {
    flex: 0.26;
  }

  .map-section {
    flex: 0.74;
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

  .center-area {
    flex: 1 1 auto;
    flex-direction: column;
  }

  .map-section {
    flex: 1 1 auto;
  }

  .preview-section {
    flex: 0 0 clamp(78px, 16vh, 112px);
    border-left: none;
    border-top: 1px solid rgba(255,255,255,0.04);
  }

  .preview-grid,
  .preview-thumbs {
    grid-template-columns: repeat(4, 1fr);
  }

  .preview-title,
  .fire-resource-btn span:last-child,
  .cap-unit,
  .cap-label {
    display: none;
  }

  .capsule {
    flex: 1 1 0;
  }
}

@media (max-height: 700px) {
  .top-bar {
    height: 46px;
    flex-basis: 46px;
  }

  .side-panel {
    padding: 5px;
    gap: 5px;
  }

  .glass-card,
  .tab-content {
    padding: 6px;
  }

  .source-btn,
  .source-item,
  .corr-item,
  .drawer-source-item,
  .fire-resource-item {
    padding: 5px 7px;
  }

  .preview-hint,
  .thumb-title,
  .more-link,
  .quality-label {
    /* 低高度时隐藏次要入口/说明，确保核心卡片不需要内部滚动。 */
    display: none;
  }

  .quality-ring {
    width: 50px;
    height: 50px;
  }

  .mini-chart {
    height: 24px;
  }

  .drawer-header {
    padding: 10px 12px;
  }
}
</style>
