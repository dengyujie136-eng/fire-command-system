<template>
  <div class="route-container" :class="{ compact: compactMode }" @keydown="handleKeydown" tabindex="0">
    <div class="top-bar">
      <div class="capsule capsule-env">
        <span class="cap-icon">☀️</span>
        <span class="cap-temp">26℃</span>
        <span class="cap-weather">晴</span>
        <span class="cap-wind">风速 12km/h</span>
      </div>
      <div class="capsule capsule-risk" :class="riskClass">
        <span class="cap-risk-dot" :class="riskClass"></span>
        <span class="cap-risk-text">{{ riskLabel }}</span>
        <span class="cap-risk-arrow">{{ riskArrow }}</span>
      </div>
      <div class="capsule capsule-suggest" @click="showSuggestDrawer = true">
        <span class="cap-suggest-text">{{ suggestText }}</span>
        <span class="cap-suggest-more">▸</span>
      </div>
      <button class="reset-btn" @click="confirmReset" title="重置规划">
        <span>↺</span>
      </button>
    </div>

    <div class="main-content">
      <div class="side-panel left" :class="{ collapsed: leftCollapsed }">
        <button class="collapse-btn" @click="leftCollapsed = !leftCollapsed" :title="leftCollapsed ? '展开面板' : '收起面板'">
          <span class="arrow">{{ leftCollapsed ? '→' : '←' }}</span>
        </button>

        <template v-if="!leftCollapsed">
          <div class="glass-card">
            <div class="card-title">路径类型</div>
            <div class="path-type-group">
              <button
                v-for="pt in pathTypes"
                :key="pt.id"
                class="path-type-btn"
                :class="[pt.id, { active: selectedPathType === pt.id }]"
                @click="selectPathType(pt.id)"
              >
                <span class="pt-icon">{{ pt.icon }}</span>
                <span class="pt-name">{{ pt.name }}</span>
                <span class="pt-desc">{{ pt.desc }}</span>
              </button>
            </div>
          </div>

          <div class="glass-card">
            <div class="card-title">起点与终点</div>
            <div class="point-input-group">
              <div class="point-row">
                <span class="point-icon start">A</span>
                <input type="text" v-model="form.start" placeholder="起点坐标或位置" class="point-input" />
                <button class="point-pick-btn" title="地图选取" @click="startPicking('start')">📍</button>
              </div>
              <button class="swap-btn" @click="swapPoints" title="交换起终点">⇅</button>
              <div class="point-row">
                <span class="point-icon end">B</span>
                <input type="text" v-model="form.end" placeholder="终点坐标或位置" class="point-input" />
                <button class="point-pick-btn" title="地图选取" @click="startPicking('end')">📍</button>
              </div>
            </div>
            <button class="clear-link" @click="clearPoints">清除所有</button>
          </div>

          <div class="glass-card">
            <div class="card-title">高程剖面</div>
            <div class="elevation-thumb">
              <svg viewBox="0 0 280 60" class="elev-svg">
                <defs>
                  <linearGradient id="elevGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" :stop-color="pathColor" stop-opacity="0.4"/>
                    <stop offset="100%" :stop-color="pathColor" stop-opacity="0.02"/>
                  </linearGradient>
                </defs>
                <path :d="elevThumbPath" fill="url(#elevGrad)" stroke="none"/>
                <path :d="elevThumbLine" fill="none" :stroke="pathColor" stroke-width="2" stroke-linecap="round"/>
              </svg>
            </div>
            <button class="detail-link" @click="showElevDrawer = true">详细剖面</button>
          </div>
        </template>

        <template v-else>
          <div class="collapsed-icons">
            <div class="ico-item" title="路径类型" @click="leftCollapsed = false">🛤️</div>
            <div class="ico-item" title="起终点" @click="leftCollapsed = false">📍</div>
            <div class="ico-item" title="高程剖面" @click="showElevDrawer = true">⛰️</div>
          </div>
        </template>
      </div>

      <div class="center-area">
        <div class="map-section">
          <div ref="mapRef" class="map-container"></div>

          <div class="map-controls-left">
            <button class="map-ctrl-btn" :class="{ active: showAllRoutes }" @click="showAllRoutes = !showAllRoutes" title="显示所有路线">全部</button>
            <button class="map-ctrl-btn" :class="{ active: !showAllRoutes }" @click="showAllRoutes = false" title="仅显示选中路线">选中</button>
            <button class="map-ctrl-btn" @click="resetMapView" title="重置视角">⌂</button>
          </div>
          <div class="map-controls-right">
            <button class="map-ctrl-btn" @click="zoomIn" title="放大">+</button>
            <button class="map-ctrl-btn" @click="zoomOut" title="缩小">−</button>
          </div>

          <div v-if="pickingMode" class="picking-hint">
            <span>点击地图选取{{ pickingTarget === 'start' ? '起点' : '终点' }}</span>
            <button class="hint-cancel" @click="cancelPicking">取消</button>
          </div>
        </div>

        <div class="elevation-section">
          <div class="elev-header">
            <span class="elev-title">高程剖面</span>
            <button class="elev-expand" @click="showElevDrawer = true" title="放大">⛶</button>
          </div>
          <div ref="elevChartRef" class="elev-chart"></div>
          <div v-if="elevHover" class="elev-tooltip" :style="{ left: elevHover.x + 'px' }">
            <span>{{ elevHover.dist }} km · {{ elevHover.elev }} m</span>
          </div>
        </div>
      </div>

      <div class="side-panel right" :class="{ collapsed: rightCollapsed }">
        <button class="collapse-btn" @click="rightCollapsed = !rightCollapsed" :title="rightCollapsed ? '展开面板' : '收起面板'">
          <span class="arrow">{{ rightCollapsed ? '←' : '→' }}</span>
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
              <span class="tab-icon">{{ tab.icon }}</span>
              <span class="tab-text">{{ tab.label }}</span>
            </div>
          </div>

          <div class="tab-content">
            <div v-if="activeTab === 'compare'" class="tab-inner">
              <div class="route-cards">
                <div
                  v-for="route in routeList"
                  :key="route.id"
                  class="route-card"
                  :class="[route.riskClass, { selected: selectedPathType === route.id }]"
                  @click="selectPathType(route.id)"
                  @mouseenter="hoverRoute = route.id"
                  @mouseleave="hoverRoute = null"
                >
                  <div class="rc-header">
                    <span class="rc-dot" :class="route.riskClass"></span>
                    <span class="rc-name">{{ route.name }}</span>
                  </div>
                  <div class="rc-stats">
                    <div class="rc-stat">
                      <span class="rc-stat-val">{{ route.distance }}</span>
                      <span class="rc-stat-unit">km</span>
                    </div>
                    <div class="rc-stat">
                      <span class="rc-stat-val">{{ route.time }}</span>
                      <span class="rc-stat-unit">min</span>
                    </div>
                    <div class="rc-stat">
                      <span class="rc-risk-badge" :class="route.riskClass">{{ route.risk }}</span>
                    </div>
                  </div>
                  <button class="rc-preview" @click.stop="previewRoute(route.id)">预览</button>
                </div>
              </div>
            </div>

            <div v-if="activeTab === 'detail'" class="tab-inner">
              <div class="weather-segments">
                <div v-for="w in routeWeather" :key="w.location" class="weather-card">
                  <span class="wc-icon">{{ w.icon }}</span>
                  <div class="wc-info">
                    <span class="wc-loc">{{ w.location }}</span>
                    <span class="wc-cond">{{ w.condition }} {{ w.temp }}</span>
                  </div>
                </div>
              </div>
              <div class="facilities-section">
                <div class="fs-title">沿途设施</div>
                <div v-for="f in facilities" :key="f.name" class="facility-item" @click="focusFacility(f)">
                  <span class="fi-icon">{{ f.icon }}</span>
                  <div class="fi-info">
                    <span class="fi-name">{{ f.name }}</span>
                    <span class="fi-dist">距离路线 {{ f.distance }} km</span>
                  </div>
                  <button class="fi-locate" title="查看位置">📍</button>
                </div>
              </div>
              <div class="radar-section">
                <span class="rs-label">雷达分析摘要</span>
                <span class="rs-text">{{ radarSummary }}</span>
                <button class="detail-link" @click="showRadarDrawer = true">详细雷达分析</button>
              </div>
            </div>

            <div v-if="activeTab === 'risk'" class="tab-inner">
              <div class="risk-overview">
                <div class="risk-ring">
                  <svg viewBox="0 0 100 100" class="ring-svg">
                    <circle cx="50" cy="50" r="40" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="8"/>
                    <circle cx="50" cy="50" r="40" fill="none" :stroke="riskRingColor" stroke-width="8"
                      stroke-linecap="round" :stroke-dasharray="`${riskPercent * 2.51} 251`" stroke-dashoffset="0"/>
                  </svg>
                  <div class="ring-center">
                    <span class="ring-val" :class="riskClass">{{ riskLabel }}</span>
                  </div>
                </div>
                <div class="risk-summary-text">{{ riskSummary }}</div>
              </div>
              <div class="risk-factors">
                <div class="rf-title">风险因素</div>
                <div v-for="f in riskFactors" :key="f" class="rf-item">
                  <span class="rf-dot" :class="riskClass"></span>
                  <span class="rf-text">{{ f }}</span>
                </div>
              </div>
              <div class="risk-actions">
                <div class="ra-suggest">{{ suggestText }}</div>
                <div class="ra-buttons">
                  <button class="ra-btn save" @click="saveRoute">保存路线</button>
                  <button class="ra-btn export" @click="exportReport">导出报告</button>
                </div>
              </div>
            </div>
          </div>
        </template>

        <template v-else>
          <div class="collapsed-icons">
            <div
              v-for="tab in tabs"
              :key="tab.id"
              class="ico-item"
              :class="{ active: activeTab === tab.id }"
              :title="tab.label"
              @click="activeTab = tab.id; rightCollapsed = false"
            >
              {{ tab.icon }}
            </div>
          </div>
        </template>
      </div>
    </div>

    <transition name="fade">
      <div v-if="showResetConfirm" class="modal-overlay" @click="showResetConfirm = false">
        <div class="modal-content" @click.stop>
          <div class="modal-header">
            确认重置
            <button class="close-btn" @click="showResetConfirm = false">✕</button>
          </div>
          <div class="modal-body">
            <p class="confirm-text">确定要清空所有规划选择吗？</p>
            <div class="confirm-actions">
              <button class="ca-btn cancel" @click="showResetConfirm = false">取消</button>
              <button class="ca-btn confirm" @click="doReset">确认重置</button>
            </div>
          </div>
        </div>
      </div>
    </transition>

    <transition name="drawer">
      <div v-if="showSuggestDrawer" class="drawer-overlay" @click="showSuggestDrawer = false">
        <div class="drawer-content" @click.stop>
          <div class="drawer-header">
            完整建议
            <button class="close-drawer" @click="showSuggestDrawer = false">✕</button>
          </div>
          <div class="drawer-body">
            <div v-for="r in recommendations" :key="r" class="suggest-item">💡 {{ r }}</div>
          </div>
        </div>
      </div>
    </transition>

    <transition name="drawer">
      <div v-if="showElevDrawer" class="drawer-overlay" @click="showElevDrawer = false">
        <div class="drawer-content wide" @click.stop>
          <div class="drawer-header">
            详细高程剖面
            <button class="close-drawer" @click="showElevDrawer = false">✕</button>
          </div>
          <div class="drawer-body">
            <div ref="elevDetailChartRef" class="elev-detail-chart"></div>
          </div>
        </div>
      </div>
    </transition>

    <transition name="drawer">
      <div v-if="showRadarDrawer" class="drawer-overlay" @click="showRadarDrawer = false">
        <div class="drawer-content" @click.stop>
          <div class="drawer-header">
            雷达分析报告
            <button class="close-drawer" @click="showRadarDrawer = false">✕</button>
          </div>
          <div class="drawer-body">
            <div ref="radarDetailChartRef" class="radar-detail-chart"></div>
            <div class="radar-data">
              <div v-for="item in radarData" :key="item.name" class="radar-row">
                <span class="rr-name">{{ item.name }}</span>
                <div class="rr-bar-area">
                  <div class="rr-bar" :style="{ width: item.value + '%' }"></div>
                </div>
                <span class="rr-val">{{ item.value }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { fireAPI, routeAPI, mapAPI } from '../api/modules'
import * as echarts from 'echarts'
import mapboxgl from 'mapbox-gl'

const mapRef = ref<HTMLDivElement>()
const elevChartRef = ref<HTMLDivElement>()
const elevDetailChartRef = ref<HTMLDivElement>()
const radarDetailChartRef = ref<HTMLDivElement>()

const leftCollapsed = ref(false)
const rightCollapsed = ref(false)
const autoCompactMode = ref(false)
const manualCompactMode = ref(false)
/* 自动紧凑与手动紧凑叠加：小屏强制 compact，键盘 X 保留人工切换能力，避免挤出视口。 */
const compactMode = computed(() => autoCompactMode.value || manualCompactMode.value)
const activeTab = ref('compare')
const selectedPathType = ref('safe')
const showAllRoutes = ref(true)
const pickingMode = ref(false)
const pickingTarget = ref<'start' | 'end'>('start')
const showResetConfirm = ref(false)
const showSuggestDrawer = ref(false)
const showElevDrawer = ref(false)
const showRadarDrawer = ref(false)
const hoverRoute = ref<string | null>(null)
const elevHover = ref<{ x: number; dist: string; elev: string } | null>(null)

const form = reactive({ start: '北区林地入口', end: '南区安全营地' })
const suggestText = ref('保持当前路线，注意观察火势变化')

const pathTypes = [
  { id: 'safe', name: '安全路径', icon: '🟢', desc: '避开火场' },
  { id: 'moderate', name: '中等路径', icon: '🟠', desc: '可能遇到烟雾' },
  { id: 'danger', name: '危险路径', icon: '🔴', desc: '最短但危险' }
]

const tabs = [
  { id: 'compare', label: '路线对比', icon: '📊' },
  { id: 'detail', label: '沿途详情', icon: '🗺️' },
  { id: 'risk', label: '风险评估', icon: '⚠️' }
]

const routeList = ref([
  { id: 'safe', name: '安全路径', distance: '12.3', time: '25', risk: '低', riskClass: 'safe' },
  { id: 'moderate', name: '中等路径', distance: '10.1', time: '18', risk: '中', riskClass: 'moderate' },
  { id: 'danger', name: '危险路径', distance: '8.7', time: '14', risk: '高', riskClass: 'danger' }
])

const routeWeather = ref([
  { location: '起点', condition: '晴', temp: '26℃', icon: '☀️' },
  { location: '中段', condition: '多云', temp: '24℃', icon: '⛅' },
  { location: '终点', condition: '阴', temp: '22℃', icon: '☁️' }
])

const facilities = ref([
  { name: '消防站 A', distance: 0.8, icon: '🚒', lat: 39.915, lng: 116.405 },
  { name: '医院 B', distance: 1.2, icon: '🏥', lat: 39.925, lng: 116.415 },
  { name: '避难所 C', distance: 0.5, icon: '🏠', lat: 39.905, lng: 116.395 }
])

const radarSummary = ref('火势稳定，风向偏西，能见度良好')
const radarData = ref([
  { name: '距离', value: 70 },
  { name: '时间', value: 80 },
  { name: '安全', value: 90 },
  { name: '可达性', value: 85 },
  { name: '成本', value: 75 }
])

const riskFactors = ref([
  '火势稳定，暂无蔓延趋势',
  '能见度良好，适合通行',
  '途径一处陡坡，需注意行进速度'
])

const recommendations = ref([
  '保持当前路线，注意观察火势变化',
  '确保通讯畅通，定时汇报位置',
  '经过陡坡段时减速慢行',
  '关注天气变化，随时准备调整路线'
])

const riskClass = computed(() => selectedPathType.value)
const riskLabel = computed(() => {
  const map: Record<string, string> = { safe: '低风险', moderate: '中等风险', danger: '高风险' }
  return map[selectedPathType.value] || '低风险'
})
const riskArrow = computed(() => {
  const map: Record<string, string> = { safe: '→', moderate: '↗', danger: '↑' }
  return map[selectedPathType.value] || '→'
})
const riskPercent = computed(() => {
  const map: Record<string, number> = { safe: 25, moderate: 55, danger: 85 }
  return map[selectedPathType.value] || 25
})
const riskRingColor = computed(() => {
  const map: Record<string, string> = { safe: '#22c55e', moderate: '#f59e0b', danger: '#ef4444' }
  return map[selectedPathType.value] || '#22c55e'
})
const riskSummary = computed(() => {
  const map: Record<string, string> = { safe: '适合通行', moderate: '需谨慎通行', danger: '不建议通行' }
  return map[selectedPathType.value] || '适合通行'
})
const pathColor = computed(() => {
  const map: Record<string, string> = { safe: '#22c55e', moderate: '#f59e0b', danger: '#ef4444' }
  return map[selectedPathType.value] || '#22c55e'
})

const elevData = [120, 135, 150, 145, 160, 155, 140, 130, 145, 165, 150, 135, 125]
const elevDist = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12.3']

const elevThumbLine = computed(() => {
  const w = 280, h = 50, pad = 5
  const max = Math.max(...elevData), min = Math.min(...elevData)
  const range = max - min || 1
  const points = elevData.map((v, i) => {
    const x = pad + (i / (elevData.length - 1)) * (w - pad * 2)
    const y = pad + (1 - (v - min) / range) * (h - pad * 2)
    return `${x},${y}`
  })
  return 'M' + points.join(' L')
})

const elevThumbPath = computed(() => {
  const w = 280, h = 50, pad = 5
  const max = Math.max(...elevData), min = Math.min(...elevData)
  const range = max - min || 1
  const points = elevData.map((v, i) => {
    const x = pad + (i / (elevData.length - 1)) * (w - pad * 2)
    const y = pad + (1 - (v - min) / range) * (h - pad * 2)
    return `${x},${y}`
  })
  return 'M' + points.join(' L') + ` L${w - pad},${h} L${pad},${h} Z`
})

let map: mapboxgl.Map | null = null
let elevChart: echarts.ECharts | null = null
let elevDetailChart: echarts.ECharts | null = null
let radarDetailChart: echarts.ECharts | null = null
let resizeHandler: (() => void) | null = null

function updateResponsiveLayout() {
  const width = window.innerWidth
  const height = window.innerHeight
  /* <=1366px 或 <=700px 自动启用紧凑尺寸，减少固定 px 造成的纵向溢出。 */
  autoCompactMode.value = width <= 1366 || height <= 700
  /* <=1100px 默认折叠右侧面板，给地图和高程剖面保留可视宽度。 */
  if (width <= 1100) rightCollapsed.value = true
  nextTick(() => {
    map?.resize()
    elevChart?.resize()
    elevDetailChart?.resize()
    radarDetailChart?.resize()
  })
}

function selectPathType(type: string) {
  selectedPathType.value = type
  updateMapRoutes()
  updateElevChart()
}

function swapPoints() {
  const tmp = form.start
  form.start = form.end
  form.end = tmp
}

function clearPoints() {
  form.start = ''
  form.end = ''
}

function startPicking(target: 'start' | 'end') {
  pickingMode.value = true
  pickingTarget.value = target
}

function cancelPicking() {
  pickingMode.value = false
}

function confirmReset() {
  showResetConfirm.value = true
}

function doReset() {
  form.start = ''
  form.end = ''
  selectedPathType.value = 'safe'
  showAllRoutes.value = true
  showResetConfirm.value = false
  resetMapView()
}

function previewRoute(id: string) {
  selectedPathType.value = id
  updateMapRoutes()
  updateElevChart()
}

function focusFacility(f: any) {
  if (map) map.flyTo({ center: [f.lng, f.lat], zoom: 14 })
}

function saveRoute() {
  routeAPI.save({ route: selectedPathType.value, start: form.start, end: form.end }).catch(() => {
    console.log('Route saved (mock)')
  })
}

function exportReport() {
  console.log('Export report (mock)')
}

function zoomIn() { if (map) map.zoomIn() }
function zoomOut() { if (map) map.zoomOut() }
function resetMapView() { if (map) map.flyTo({ center: [116.4, 39.9], zoom: 11 }) }

function initMap() {
  if (!mapRef.value) return
  mapboxgl.accessToken = 'pk.eyJ1IjoiZXhhbXBsZSIsInAiOiJ0ZXN0In0.test'
  map = new mapboxgl.Map({
    container: mapRef.value,
    style: 'mapbox://styles/mapbox/dark-v11',
    center: [116.4, 39.9],
    zoom: 11,
    attributionControl: false
  })
  map.on('load', () => {
    drawRoutesOnMap()
  })
  map.on('click', (e: mapboxgl.MapMouseEvent) => {
    if (!pickingMode.value) return
    const coord = `${e.lngLat.lat.toFixed(4)}, ${e.lngLat.lng.toFixed(4)}`
    if (pickingTarget.value === 'start') form.start = coord
    else form.end = coord
    pickingMode.value = false
  })
}

function drawRoutesOnMap() {
  if (!map) return
  const routeCoords: Record<string, [number, number][]> = {
    safe: [
      [116.38, 39.92], [116.39, 39.93], [116.40, 39.94], [116.41, 39.94],
      [116.42, 39.93], [116.43, 39.92], [116.44, 39.91]
    ],
    moderate: [
      [116.38, 39.92], [116.395, 39.93], [116.41, 39.935], [116.425, 39.93],
      [116.44, 39.91]
    ],
    danger: [
      [116.38, 39.92], [116.40, 39.94], [116.42, 39.935], [116.44, 39.91]
    ]
  }
  const colors: Record<string, string> = { safe: '#22c55e', moderate: '#f59e0b', danger: '#ef4444' }
  const dashes: Record<string, number[]> = { safe: [], moderate: [4, 2], danger: [2, 2] }

  Object.keys(routeCoords).forEach(key => {
    const id = `route-${key}`
    if (map!.getSource(id)) map!.removeLayer(id)
    if (map!.getLayer(id)) map!.removeLayer(id)

    map!.addSource(id, {
      type: 'geojson',
      data: {
        type: 'Feature',
        geometry: { type: 'LineString', coordinates: routeCoords[key] }
      }
    })
    map!.addLayer({
      id: id,
      type: 'line',
      source: id,
      paint: {
        'line-color': colors[key],
        'line-width': key === selectedPathType.value ? 5 : 2,
        'line-opacity': key === selectedPathType.value ? 1 : 0.5,
        'line-dasharray': dashes[key]
      }
    })
  })

  new mapboxgl.Marker({ color: '#22c55e' }).setLngLat([116.38, 39.92]).addTo(map!)
  new mapboxgl.Marker({ color: '#ef4444' }).setLngLat([116.44, 39.91]).addTo(map!)
}

function updateMapRoutes() {
  if (!map) return
  const widths: Record<string, number> = { safe: 2, moderate: 2, danger: 2 }
  widths[selectedPathType.value] = 5
  const opacities: Record<string, number> = { safe: 0.4, moderate: 0.4, danger: 0.4 }
  opacities[selectedPathType.value] = 1

  Object.keys(widths).forEach(key => {
    if (map!.getLayer(`route-${key}`)) {
      map!.setPaintProperty(`route-${key}`, 'line-width', widths[key])
      map!.setPaintProperty(`route-${key}`, 'line-opacity', showAllRoutes.value ? opacities[key] : (key === selectedPathType.value ? 1 : 0))
    }
  })
}

watch(showAllRoutes, () => updateMapRoutes())

function initElevChart() {
  if (!elevChartRef.value) return
  elevChart = echarts.init(elevChartRef.value)
  updateElevChart()
}

function updateElevChart() {
  if (!elevChart) return
  elevChart.setOption({
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(20,28,40,0.9)',
      borderColor: 'rgba(255,255,255,0.1)',
      textStyle: { color: '#e2e8f0', fontSize: 11 },
      formatter: (params: any) => {
        const p = params[0]
        return `${p.name} km<br/>高程: ${p.value} m`
      }
    },
    grid: { top: 10, bottom: 24, left: 40, right: 16 },
    xAxis: {
      type: 'category',
      data: elevDist,
      axisLabel: { color: '#64748b', fontSize: 10 },
      axisLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
      axisTick: { show: false }
    },
    yAxis: {
      type: 'value',
      min: 30, max: 180,
      axisLabel: { color: '#64748b', fontSize: 10 },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.04)' } },
      axisLine: { show: false },
      axisTick: { show: false }
    },
    series: [{
      type: 'line',
      data: elevData,
      smooth: true,
      lineStyle: { color: pathColor.value, width: 2 },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: pathColor.value + '40' },
          { offset: 1, color: pathColor.value + '05' }
        ])
      },
      symbol: 'circle',
      symbolSize: 4,
      itemStyle: { color: pathColor.value }
    }]
  })
}

function initElevDetailChart() {
  if (!elevDetailChartRef.value) return
  elevDetailChart = echarts.init(elevDetailChartRef.value)
  elevDetailChart.setOption({
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(20,28,40,0.9)',
      borderColor: 'rgba(255,255,255,0.1)',
      textStyle: { color: '#e2e8f0', fontSize: 12 }
    },
    grid: { top: 30, bottom: 40, left: 50, right: 30 },
    xAxis: {
      type: 'category',
      data: elevDist,
      name: '距离 (km)',
      nameTextStyle: { color: '#94a3b8', fontSize: 12 },
      axisLabel: { color: '#64748b', fontSize: 11 },
      axisLine: { lineStyle: { color: 'rgba(255,255,255,0.08)' } }
    },
    yAxis: {
      type: 'value',
      min: 30, max: 180,
      name: '高程 (m)',
      nameTextStyle: { color: '#94a3b8', fontSize: 12 },
      axisLabel: { color: '#64748b', fontSize: 11 },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.04)' } }
    },
    dataZoom: [{ type: 'inside' }],
    series: [{
      type: 'line',
      data: elevData,
      smooth: true,
      lineStyle: { color: pathColor.value, width: 3 },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: pathColor.value + '50' },
          { offset: 1, color: pathColor.value + '05' }
        ])
      },
      symbol: 'circle',
      symbolSize: 6,
      itemStyle: { color: pathColor.value }
    }]
  })
}

function initRadarDetailChart() {
  if (!radarDetailChartRef.value) return
  radarDetailChart = echarts.init(radarDetailChartRef.value)
  radarDetailChart.setOption({
    radar: {
      indicator: radarData.value.map(d => ({ name: d.name, max: 100 })),
      axisName: { color: '#94a3b8', fontSize: 11 },
      splitArea: { areaStyle: { color: ['rgba(59,130,246,0.04)', 'rgba(59,130,246,0.08)'] } },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } }
    },
    series: [{
      type: 'radar',
      data: [{ value: radarData.value.map(d => d.value), name: '路线分析' }],
      areaStyle: { color: 'rgba(59,130,246,0.25)' },
      lineStyle: { color: '#3b82f6', width: 2 },
      itemStyle: { color: '#3b82f6' }
    }]
  })
}

watch(showElevDrawer, (v) => {
  if (v) nextTick(() => initElevDetailChart())
})

watch(showRadarDrawer, (v) => {
  if (v) nextTick(() => initRadarDetailChart())
})

watch(selectedPathType, () => {
  if (elevDetailChart) {
    elevDetailChart.setOption({
      series: [{
        lineStyle: { color: pathColor.value },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: pathColor.value + '50' },
            { offset: 1, color: pathColor.value + '05' }
          ])
        },
        itemStyle: { color: pathColor.value }
      }]
    })
  }
})

function handleKeydown(e: KeyboardEvent) {
  if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement) return
  switch (e.key.toLowerCase()) {
    case 'l': leftCollapsed.value = !leftCollapsed.value; break
    case 'r': rightCollapsed.value = !rightCollapsed.value; break
    case 'x': manualCompactMode.value = !manualCompactMode.value; break
    case 's': selectPathType('safe'); break
    case 'm': selectPathType('moderate'); break
    case 'd': selectPathType('danger'); break
    case 'c': confirmReset(); break
  }
}

async function loadData() {
  try {
    const stat = await fireAPI.getStat().catch(() => null)
    if (stat) {
      if (stat.temperature) form.start = form.start
    }
    const elevResult = await mapAPI.getElevation().catch(() => null)
    if (elevResult) {
      console.log('Elevation data loaded')
    }
  } catch (e) {
    console.error('Failed to load data:', e)
  }
}

onMounted(() => {
  updateResponsiveLayout()
  initMap()
  initElevChart()
  loadData()
  resizeHandler = updateResponsiveLayout
  window.addEventListener('resize', resizeHandler)
})

onUnmounted(() => {
  if (resizeHandler) window.removeEventListener('resize', resizeHandler)
  elevChart?.dispose()
  elevDetailChart?.dispose()
  radarDetailChart?.dispose()
  map?.remove()
})
</script>

<style scoped>
.route-container {
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

.top-bar {
  /* 顶部栏使用 clamp，在 600-700px 高屏幕下自动压缩。 */
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
}

.capsule {
  display: flex;
  align-items: center;
  /* 胶囊 padding 随视口收缩，防止顶部栏横向溢出。 */
  padding: clamp(5px, 0.75vh, 8px) clamp(8px, 1vw, 20px);
  border-radius: 40px;
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(255,255,255,0.12);
  backdrop-filter: blur(10px);
}

.capsule-env {
  gap: 8px;
  min-width: 0;
  width: clamp(150px, 16vw, 200px);
}

.cap-icon { font-size: clamp(13px, 0.95vw, 18px); }

.cap-temp {
  font-size: clamp(16px, 1.15vw, 22px);
  font-weight: 700;
  background: linear-gradient(90deg, #fff, #67e8f9);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.cap-weather { font-size: clamp(10px, 0.7vw, 13px); color: #cbd5e1; }
.cap-wind { font-size: clamp(9px, 0.6vw, 11px); color: #64748b; margin-left: 4px; }

.capsule-risk {
  gap: 10px;
  min-width: 0;
  width: clamp(120px, 13vw, 160px);
  justify-content: center;
}

.capsule-risk.safe { border-color: rgba(34,197,94,0.3); background: rgba(34,197,94,0.08); }
.capsule-risk.moderate { border-color: rgba(245,158,11,0.3); background: rgba(245,158,11,0.08); }
.capsule-risk.danger { border-color: rgba(239,68,68,0.3); background: rgba(239,68,68,0.08); }

.cap-risk-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.cap-risk-dot.safe { background: #22c55e; }
.cap-risk-dot.moderate { background: #f59e0b; }
.cap-risk-dot.danger { background: #ef4444; animation: dotBlink 1.5s ease-in-out infinite; }

@keyframes dotBlink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.cap-risk-text { font-size: clamp(11px, 0.75vw, 14px); font-weight: 600; }
.capsule-risk.safe .cap-risk-text { color: #4ade80; }
.capsule-risk.moderate .cap-risk-text { color: #fbbf24; }
.capsule-risk.danger .cap-risk-text { color: #f87171; }

.cap-risk-arrow { font-size: 14px; font-weight: bold; }
.capsule-risk.safe .cap-risk-arrow { color: #22c55e; }
.capsule-risk.moderate .cap-risk-arrow { color: #f59e0b; }
.capsule-risk.danger .cap-risk-arrow { color: #ef4444; }

.capsule-suggest {
  gap: 8px;
  min-width: 0;
  width: clamp(180px, 22vw, 280px);
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;
}

.capsule-suggest:hover { background: rgba(255,255,255,0.12); }

.cap-suggest-text {
  font-size: clamp(10px, 0.7vw, 13px);
  color: #cbd5e1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: min(220px, 18vw);
}

.cap-suggest-more { font-size: 12px; color: #60a5fa; }

.reset-btn {
  width: clamp(30px, 4.8vh, 36px);
  height: clamp(30px, 4.8vh, 36px);
  border-radius: 50%;
  border: 1px solid rgba(255,255,255,0.1);
  background: rgba(255,255,255,0.06);
  color: #94a3b8;
  cursor: pointer;
  font-size: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.reset-btn:hover { background: rgba(239,68,68,0.15); color: #f87171; border-color: rgba(239,68,68,0.3); }

.main-content {
  flex: 1;
  display: flex;
  min-height: 0;
  min-width: 0;
  overflow: hidden;
}

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

.collapse-btn:hover { color: #e2e8f0; background: rgba(30,40,55,0.95); }
.side-panel.left .collapse-btn { right: 0; transform: translateY(-50%); border-radius: 0 8px 8px 0; }
.side-panel.right .collapse-btn { left: 0; transform: translateY(-50%); border-radius: 8px 0 0 8px; }

.glass-card {
  background: rgba(20,28,40,0.7);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 20px;
  /* 卡片 padding 使用 clamp，低屏幕下减少纵向累计高度。 */
  padding: clamp(8px, 1.2vh, 16px);
  box-shadow: 0 8px 32px rgba(0,0,0,0.3);
  backdrop-filter: blur(16px);
  transition: border-color 0.2s ease;
  min-height: 0;
  overflow: hidden;
}

.side-panel > .glass-card {
  flex: 1 1 0;
  display: flex;
  flex-direction: column;
}

.glass-card:hover { border-color: rgba(255,255,255,0.15); }

.card-title {
  font-size: clamp(10px, 0.72vw, 13px);
  font-weight: 600;
  color: #cbd5e1;
  margin-bottom: clamp(6px, 1vh, 14px);
  letter-spacing: 0.5px;
}

.path-type-group {
  display: flex;
  flex-direction: column;
  gap: clamp(4px, 0.75vh, 8px);
}

.path-type-btn {
  display: flex;
  align-items: center;
  gap: clamp(5px, 0.55vw, 10px);
  padding: clamp(7px, 1vh, 12px) clamp(8px, 0.8vw, 14px);
  border-radius: 14px;
  border: 1px solid rgba(255,255,255,0.06);
  background: rgba(255,255,255,0.03);
  cursor: pointer;
  transition: all 0.2s ease;
  color: #e2e8f0;
  text-align: left;
}

.path-type-btn:hover { background: rgba(255,255,255,0.06); }
.path-type-btn.safe.active { background: rgba(34,197,94,0.12); border-color: rgba(34,197,94,0.4); }
.path-type-btn.moderate.active { background: rgba(245,158,11,0.12); border-color: rgba(245,158,11,0.4); }
.path-type-btn.danger.active { background: rgba(239,68,68,0.12); border-color: rgba(239,68,68,0.4); }

.pt-icon { font-size: 16px; }
/* 路径名称使用 clamp 和相对最小宽度，避免固定 60px 在窄屏推宽左侧面板。 */
.pt-name { font-size: clamp(10px, 0.7vw, 13px); font-weight: 600; min-width: clamp(48px, 4vw, 60px); }
.pt-desc { font-size: clamp(9px, 0.6vw, 11px); color: #64748b; }

.point-input-group {
  display: flex;
  flex-direction: column;
  gap: clamp(4px, 0.75vh, 8px);
  margin-bottom: clamp(4px, 0.8vh, 10px);
}

.point-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.point-icon {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
}

.point-icon.start { background: rgba(34,197,94,0.2); color: #22c55e; }
.point-icon.end { background: rgba(239,68,68,0.2); color: #ef4444; }

.point-input {
  flex: 1;
  padding: clamp(5px, 0.8vh, 8px) clamp(6px, 0.7vw, 10px);
  border-radius: 10px;
  border: 1px solid rgba(255,255,255,0.1);
  background: rgba(255,255,255,0.04);
  color: #e2e8f0;
  font-size: 12px;
  outline: none;
  transition: border-color 0.2s;
}

.point-input:focus { border-color: rgba(96,165,250,0.5); }

.point-pick-btn {
  width: clamp(24px, 3.6vh, 28px);
  height: clamp(24px, 3.6vh, 28px);
  border-radius: 8px;
  border: 1px solid rgba(255,255,255,0.08);
  background: rgba(255,255,255,0.04);
  cursor: pointer;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.point-pick-btn:hover { background: rgba(96,165,250,0.15); }

.swap-btn {
  align-self: center;
  width: clamp(24px, 3.6vh, 28px);
  height: clamp(24px, 3.6vh, 28px);
  border-radius: 8px;
  border: 1px solid rgba(255,255,255,0.06);
  background: rgba(255,255,255,0.04);
  color: #94a3b8;
  cursor: pointer;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.swap-btn:hover { background: rgba(96,165,250,0.15); color: #60a5fa; }

.clear-link {
  border: none;
  background: none;
  color: #64748b;
  font-size: 11px;
  cursor: pointer;
  padding: 4px 0;
  text-align: left;
  transition: color 0.2s;
}

.clear-link:hover { color: #ef4444; }

.elevation-thumb {
  height: clamp(34px, 7vh, 60px);
  background: rgba(255,255,255,0.03);
  border-radius: 10px;
  overflow: hidden;
  margin-bottom: clamp(4px, 0.7vh, 8px);
}

.elev-svg { width: 100%; height: 100%; }

.detail-link {
  border: none;
  background: none;
  color: #60a5fa;
  font-size: 12px;
  cursor: pointer;
  padding: 4px 0;
  text-align: left;
}

.detail-link:hover { text-decoration: underline; }

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

.ico-item:hover { background: rgba(96,165,250,0.15); transform: translateY(-2px); }
.ico-item.active { background: rgba(96,165,250,0.2); border: 1px solid rgba(96,165,250,0.3); }

.center-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.map-section {
  flex: 7;
  position: relative;
  min-height: 0;
  min-width: 0;
  overflow: hidden;
}

.map-container {
  width: 100%;
  height: 100%;
}

.map-controls-left {
  position: absolute;
  top: clamp(8px, 2vw, 16px);
  left: clamp(8px, 2vw, 16px);
  display: flex;
  flex-direction: column;
  gap: 6px;
  z-index: 10;
}

.map-controls-right {
  position: absolute;
  top: clamp(8px, 2vw, 16px);
  right: clamp(8px, 2vw, 16px);
  display: flex;
  flex-direction: column;
  gap: 6px;
  z-index: 10;
}

.map-ctrl-btn {
  padding: clamp(5px, 0.8vh, 8px) clamp(8px, 0.8vw, 14px);
  border-radius: 10px;
  background: rgba(20,28,40,0.8);
  border: 1px solid rgba(255,255,255,0.08);
  color: #94a3b8;
  font-size: clamp(10px, 0.65vw, 12px);
  cursor: pointer;
  backdrop-filter: blur(8px);
  transition: all 0.2s ease;
}

.map-ctrl-btn:hover { background: rgba(96,165,250,0.2); color: #e2e8f0; }
.map-ctrl-btn.active { background: rgba(96,165,250,0.25); color: #60a5fa; border-color: rgba(96,165,250,0.4); }

.picking-hint {
  position: absolute;
  bottom: clamp(8px, 2vw, 16px);
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: clamp(6px, 0.8vw, 12px);
  padding: clamp(6px, 1vh, 10px) clamp(10px, 1vw, 20px);
  border-radius: 12px;
  background: rgba(59,130,246,0.15);
  border: 1px solid rgba(59,130,246,0.3);
  backdrop-filter: blur(10px);
  font-size: clamp(10px, 0.7vw, 13px);
  color: #93c5fd;
  z-index: 10;
}

.hint-cancel {
  padding: 4px 12px;
  border-radius: 8px;
  border: 1px solid rgba(255,255,255,0.1);
  background: rgba(255,255,255,0.06);
  color: #94a3b8;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.2s;
}

.hint-cancel:hover { background: rgba(239,68,68,0.15); color: #f87171; }

.elevation-section {
  flex: 0 0 clamp(96px, 24vh, 220px);
  position: relative;
  background: rgba(20,28,40,0.7);
  border-top: 1px solid rgba(255,255,255,0.06);
  backdrop-filter: blur(12px);
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.elev-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: clamp(4px, 0.7vh, 6px) clamp(8px, 0.8vw, 12px);
  background: rgba(255,255,255,0.03);
}

.elev-title { font-size: 12px; color: #94a3b8; font-weight: 500; }

.elev-expand {
  width: clamp(20px, 3.2vh, 24px);
  height: clamp(20px, 3.2vh, 24px);
  border-radius: 6px;
  border: none;
  background: rgba(255,255,255,0.06);
  color: #94a3b8;
  cursor: pointer;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.elev-expand:hover { background: rgba(96,165,250,0.2); color: #60a5fa; }

.elev-chart {
  flex: 1;
  min-height: 0;
}

.elev-tooltip {
  position: absolute;
  bottom: 8px;
  padding: 4px 10px;
  border-radius: 6px;
  background: rgba(20,28,40,0.9);
  border: 1px solid rgba(255,255,255,0.1);
  font-size: 11px;
  color: #cbd5e1;
  pointer-events: none;
  transform: translateX(-50%);
}

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
  padding: clamp(5px, 0.8vh, 8px) clamp(4px, 0.5vw, 6px);
  border-radius: 10px;
  font-size: clamp(10px, 0.65vw, 12px);
  color: #94a3b8;
  cursor: pointer;
  transition: all 0.2s ease;
}

.tab-item:hover { color: #e2e8f0; }
.tab-item.active { background: rgba(96,165,250,0.2); color: #60a5fa; font-weight: 600; }

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
  gap: clamp(6px, 1vh, 12px);
}

.route-cards {
  display: flex;
  flex-direction: column;
  gap: clamp(5px, 0.8vh, 10px);
  min-height: 0;
  overflow: hidden;
}

.route-card {
  padding: clamp(8px, 1.1vh, 14px);
  border-radius: 14px;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06);
  cursor: pointer;
  transition: all 0.2s ease;
}

.route-card:hover { background: rgba(255,255,255,0.06); }
.route-card.safe.selected { border-color: rgba(34,197,94,0.5); background: rgba(34,197,94,0.08); box-shadow: 0 0 20px rgba(34,197,94,0.15); }
.route-card.moderate.selected { border-color: rgba(245,158,11,0.5); background: rgba(245,158,11,0.08); box-shadow: 0 0 20px rgba(245,158,11,0.15); }
.route-card.danger.selected { border-color: rgba(239,68,68,0.5); background: rgba(239,68,68,0.08); box-shadow: 0 0 20px rgba(239,68,68,0.15); }

.rc-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: clamp(5px, 0.8vh, 10px);
}

.rc-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.rc-dot.safe { background: #22c55e; }
.rc-dot.moderate { background: #f59e0b; }
.rc-dot.danger { background: #ef4444; }

.rc-name { font-size: 13px; font-weight: 600; }

.rc-stats {
  display: flex;
  gap: clamp(8px, 0.9vw, 16px);
  margin-bottom: clamp(5px, 0.8vh, 10px);
}

.rc-stat {
  display: flex;
  align-items: baseline;
  gap: 2px;
}

.rc-stat-val {
  font-size: clamp(13px, 0.95vw, 18px);
  font-weight: 700;
  background: linear-gradient(90deg, #fff, #67e8f9);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.rc-stat-unit { font-size: 11px; color: #64748b; }

.rc-risk-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 10px;
  border-radius: 20px;
}

.rc-risk-badge.safe { color: #4ade80; background: rgba(34,197,94,0.15); }
.rc-risk-badge.moderate { color: #fbbf24; background: rgba(245,158,11,0.15); }
.rc-risk-badge.danger { color: #f87171; background: rgba(239,68,68,0.15); }

.rc-preview {
  padding: 6px 14px;
  border-radius: 8px;
  border: 1px solid rgba(255,255,255,0.1);
  background: rgba(255,255,255,0.04);
  color: #94a3b8;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.rc-preview:hover { background: rgba(96,165,250,0.15); color: #60a5fa; }

.weather-segments {
  display: flex;
  gap: clamp(4px, 0.7vh, 8px);
  margin-bottom: clamp(6px, 1vh, 12px);
}

.weather-card {
  flex: 1;
  display: flex;
  align-items: center;
  gap: clamp(4px, 0.55vw, 8px);
  padding: clamp(6px, 0.9vh, 10px);
  border-radius: 12px;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.06);
}

.wc-icon { font-size: 20px; }
.wc-info { display: flex; flex-direction: column; }
.wc-loc { font-size: 11px; color: #64748b; }
.wc-cond { font-size: 12px; color: #cbd5e1; }

.facilities-section {
  margin-bottom: clamp(6px, 1vh, 12px);
  min-height: 0;
  overflow: hidden;
}

.fs-title {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 8px;
}

.facility-item {
  display: flex;
  align-items: center;
  gap: clamp(5px, 0.55vw, 10px);
  padding: clamp(5px, 0.75vh, 8px) clamp(6px, 0.6vw, 10px);
  border-radius: 10px;
  background: rgba(255,255,255,0.03);
  margin-bottom: clamp(3px, 0.6vh, 6px);
  cursor: pointer;
  transition: background 0.15s;
}

.facility-item:hover { background: rgba(96,165,250,0.08); }

.fi-icon { font-size: 16px; }
.fi-info { flex: 1; display: flex; flex-direction: column; }
.fi-name { font-size: 12px; font-weight: 500; }
.fi-dist { font-size: 11px; color: #64748b; }

.fi-locate {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  border: none;
  background: rgba(255,255,255,0.04);
  cursor: pointer;
  font-size: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.fi-locate:hover { background: rgba(96,165,250,0.15); }

.radar-section {
  padding: clamp(7px, 1vh, 12px);
  border-radius: 12px;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06);
}

.rs-label { font-size: 12px; color: #64748b; display: block; margin-bottom: 6px; }
.rs-text { font-size: 12px; color: #cbd5e1; display: block; margin-bottom: 8px; }

.risk-overview {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: clamp(4px, 0.7vh, 8px);
  margin-bottom: clamp(6px, 1vh, 12px);
}

.risk-ring {
  position: relative;
  width: clamp(54px, 8vh, 80px);
  height: clamp(54px, 8vh, 80px);
}

.ring-svg { width: 100%; height: 100%; transform: rotate(-90deg); }

.ring-center {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
}

.ring-val {
  font-size: 12px;
  font-weight: 700;
}

.ring-val.safe { color: #4ade80; }
.ring-val.moderate { color: #fbbf24; }
.ring-val.danger { color: #f87171; }

.risk-summary-text {
  font-size: 13px;
  color: #cbd5e1;
}

.risk-factors {
  margin-bottom: clamp(6px, 1vh, 12px);
  min-height: 0;
  overflow: hidden;
}

.rf-title {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 8px;
}

.rf-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 6px;
}

.rf-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  margin-top: 5px;
  flex-shrink: 0;
}

.rf-dot.safe { background: #22c55e; }
.rf-dot.moderate { background: #f59e0b; }
.rf-dot.danger { background: #ef4444; }

.rf-text { font-size: 12px; color: #94a3b8; }

.risk-actions {
  padding: clamp(7px, 1vh, 12px);
  border-radius: 12px;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06);
}

.ra-suggest {
  font-size: 12px;
  color: #cbd5e1;
  margin-bottom: 10px;
}

.ra-buttons {
  display: flex;
  gap: 8px;
}

.ra-btn {
  flex: 1;
  padding: clamp(6px, 0.9vh, 10px);
  border-radius: 12px;
  border: none;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s;
}

.ra-btn:hover { transform: scale(0.98); }

.ra-btn.save {
  background: linear-gradient(90deg, #3b82f6, #6366f1);
  color: white;
}

.ra-btn.export {
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.1);
  color: #94a3b8;
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
}

.modal-content {
  width: clamp(300px, 34vw, 380px);
  background: rgba(20,28,40,0.95);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 20px;
  backdrop-filter: blur(16px);
}

.modal-header {
  padding: 16px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid rgba(255,255,255,0.06);
  font-weight: 600;
}

.close-btn {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  border: none;
  background: rgba(255,255,255,0.06);
  color: #94a3b8;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal-body {
  padding: 20px;
}

.confirm-text {
  font-size: 14px;
  color: #cbd5e1;
  margin-bottom: 20px;
  text-align: center;
}

.confirm-actions {
  display: flex;
  gap: 10px;
}

.ca-btn {
  flex: 1;
  padding: 10px;
  border-radius: 12px;
  border: none;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s;
}

.ca-btn:hover { transform: scale(0.98); }

.ca-btn.cancel {
  background: rgba(255,255,255,0.06);
  color: #94a3b8;
}

.ca-btn.confirm {
  background: linear-gradient(90deg, #ef4444, #dc2626);
  color: white;
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
  width: clamp(280px, 32vw, 380px);
  height: 100%;
  background: rgba(20,28,40,0.95);
  border-left: 1px solid rgba(255,255,255,0.08);
  backdrop-filter: blur(12px);
  display: flex;
  flex-direction: column;
}

.drawer-content.wide {
  width: clamp(320px, 48vw, 560px);
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
  display: flex;
  align-items: center;
  justify-content: center;
}

.drawer-body {
  flex: 1;
  padding: clamp(8px, 1.2vh, 16px);
  /* 抽屉不再使用 overflow-y:auto，内容通过紧凑间距和图表高度压缩适配。 */
  overflow: hidden;
  min-height: 0;
}

.suggest-item {
  padding: clamp(7px, 1vh, 12px);
  border-radius: 12px;
  background: rgba(255,255,255,0.03);
  margin-bottom: clamp(4px, 0.8vh, 8px);
  font-size: 13px;
  color: #cbd5e1;
}

.elev-detail-chart {
  width: 100%;
  height: clamp(220px, 56vh, 400px);
}

.radar-detail-chart {
  width: 100%;
  height: clamp(160px, 38vh, 300px);
  margin-bottom: clamp(8px, 1.2vh, 16px);
}

.radar-data {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.radar-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.rr-name {
  width: 50px;
  font-size: 12px;
  color: #94a3b8;
}

.rr-bar-area {
  flex: 1;
  height: 6px;
  background: rgba(255,255,255,0.06);
  border-radius: 3px;
  overflow: hidden;
}

.rr-bar {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6, #6366f1);
  border-radius: 3px;
  transition: width 0.3s ease;
}

.rr-val {
  width: 30px;
  font-size: 12px;
  color: #60a5fa;
  font-weight: 600;
  text-align: right;
}

/* 紧凑模式：把面板/卡片/按钮间距压到规范的小屏默认值，避免内部纵向滚动。 */
.compact .top-bar {
  height: clamp(44px, 6.5vh, 52px);
  flex-basis: clamp(44px, 6.5vh, 52px);
  padding: 0 clamp(6px, 0.8vw, 12px);
  gap: clamp(4px, 0.6vw, 8px);
}

.compact .side-panel {
  width: clamp(190px, 17vw, 260px);
  flex-basis: clamp(190px, 17vw, 260px);
  padding: 6px;
  gap: 6px;
}

.compact .side-panel.collapsed {
  width: clamp(44px, 5vw, 52px);
  flex-basis: clamp(44px, 5vw, 52px);
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

.compact .path-type-btn,
.compact .route-card,
.compact .weather-card,
.compact .facility-item,
.compact .risk-actions,
.compact .suggest-item {
  padding: 5px 7px;
  border-radius: 10px;
}

.compact .path-type-group,
.compact .route-cards,
.compact .tab-inner,
.compact .radar-data {
  gap: 5px;
}

.compact .pt-desc,
.compact .detail-link,
.compact .clear-link,
.compact .cap-wind,
.compact .rs-text {
  display: none;
}

.compact .elevation-section {
  flex-basis: clamp(82px, 19vh, 150px);
}

.compact .risk-ring {
  width: clamp(46px, 7vh, 64px);
  height: clamp(46px, 7vh, 64px);
}

.compact .elev-detail-chart {
  height: clamp(170px, 46vh, 300px);
}

.compact .radar-detail-chart {
  height: clamp(130px, 32vh, 220px);
}

/* <=1366px 自动套用 compact 同款尺寸，小屏不依赖手动切换也不会产生滚动条。 */
@media (max-width: 1366px) {
  .top-bar {
    height: clamp(44px, 6.5vh, 52px);
    flex-basis: clamp(44px, 6.5vh, 52px);
    padding: 0 clamp(6px, 0.8vw, 12px);
    gap: clamp(4px, 0.6vw, 8px);
  }

  .capsule {
    min-width: 0;
    padding: 0 clamp(7px, 0.8vw, 12px);
    font-size: clamp(11px, 0.85vw, 13px);
  }

  .side-panel {
    width: clamp(190px, 17vw, 260px);
    flex-basis: clamp(190px, 17vw, 260px);
    padding: 6px;
    gap: 6px;
  }

  .side-panel.collapsed {
    width: clamp(44px, 5vw, 52px);
    flex-basis: clamp(44px, 5vw, 52px);
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

  .path-type-btn,
  .route-card,
  .weather-card,
  .facility-item,
  .risk-actions,
  .suggest-item {
    padding: 5px 7px;
    border-radius: 10px;
  }

  .pt-desc,
  .detail-link,
  .clear-link,
  .cap-wind,
  .rs-text {
    display: none;
  }

  .elevation-section {
    flex-basis: clamp(82px, 19vh, 150px);
  }
}

/* <=1100px 默认右侧面板以折叠宽度让位，展开时作为浮层覆盖地图，不撑宽页面。 */
@media (max-width: 1100px) {
  .capsule-suggest,
  .tab-text {
    display: none;
  }

  .side-panel.right {
    width: clamp(44px, 5vw, 52px);
    flex-basis: clamp(44px, 5vw, 52px);
  }

  .side-panel.right:not(.collapsed) {
    position: absolute;
    right: 0;
    top: clamp(44px, 6.5vh, 52px);
    bottom: 0;
    z-index: 30;
    width: min(260px, 34vw);
    flex-basis: min(260px, 34vw);
    background: rgba(7, 14, 28, 0.94);
  }

  .map-controls-left,
  .map-controls-right {
    gap: 4px;
  }

  .map-ctrl-btn {
    padding: 5px 8px;
  }
}

/* <=800px 改成纵向排列，面板 100% 宽且固定为可压缩高度，防止横向溢出。 */
@media (max-width: 800px) {
  .top-bar {
    flex-wrap: wrap;
    align-content: center;
  }

  .capsule {
    flex: 1 1 0;
    width: auto;
    min-width: 0;
  }

  .main-content {
    flex-direction: column;
  }

  .side-panel,
  .compact .side-panel,
  .side-panel.right,
  .side-panel.right:not(.collapsed) {
    position: relative;
    top: auto;
    right: auto;
    bottom: auto;
    width: 100%;
    max-width: 100%;
    flex: 0 0 clamp(92px, 21vh, 138px);
    padding: 5px;
  }

  .side-panel.collapsed,
  .compact .side-panel.collapsed,
  .side-panel.right.collapsed {
    width: 100%;
    flex-basis: clamp(38px, 7vh, 48px);
  }

  .side-panel.left .collapse-btn,
  .side-panel.right .collapse-btn {
    top: auto;
    right: clamp(8px, 2vw, 16px);
    left: auto;
    bottom: 4px;
    transform: none;
    border-radius: 8px;
  }

  .center-area {
    flex: 1 1 auto;
    min-height: 0;
  }

  .map-section {
    flex: 1 1 auto;
  }

  .elevation-section {
    flex-basis: clamp(70px, 16vh, 104px);
  }

  .weather-segments,
  .rc-stats {
    gap: 4px;
  }

  .risk-factors,
  .facility-item:nth-of-type(n + 4) {
    display: none;
  }
}

/* <=700px 高度进一步压缩栏高、间距和次要说明，保证 600px 高度也无内部滚动。 */
@media (max-height: 700px) {
  .top-bar {
    height: 44px;
    flex-basis: 44px;
  }

  .side-panel {
    padding: 5px;
    gap: 5px;
  }

  .glass-card,
  .tab-content {
    padding: 6px;
  }

  .path-type-btn,
  .route-card,
  .weather-card,
  .facility-item,
  .suggest-item,
  .risk-actions {
    padding: 5px 7px;
  }

  .tabs {
    margin-bottom: 5px;
  }

  .tab-inner,
  .route-cards,
  .path-type-group {
    gap: 4px;
  }

  .pt-desc,
  .detail-link,
  .clear-link,
  .cap-wind,
  .cap-suggest-more,
  .rs-text,
  .risk-factors {
    display: none;
  }

  .elevation-section {
    flex-basis: clamp(68px, 17vh, 110px);
  }

  .risk-ring {
    width: 46px;
    height: 46px;
  }

  .elev-detail-chart {
    height: clamp(150px, 44vh, 260px);
  }

  .radar-detail-chart {
    height: clamp(120px, 30vh, 200px);
  }
}

.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

.drawer-enter-active, .drawer-leave-active { transition: all 0.2s ease; }
.drawer-enter-from, .drawer-leave-to { opacity: 0; }
.drawer-enter-from .drawer-content, .drawer-leave-to .drawer-content { transform: translateX(100%); }
</style>
