<template>
  <div class="monitor-container" :class="{ compact: compactMode }" @keydown="handleKeydown" tabindex="0">
    <div class="top-bar">
      <div class="capsule capsule-temp" @click="showTempDetail = true">
        <span class="cap-icon">🌡️</span>
        <div class="cap-data">
          <span class="cap-val">687</span>
          <span class="cap-unit">℃</span>
        </div>
        <span class="cap-label">火线温度</span>
      </div>
      <div class="capsule capsule-area" @click="showAreaDetail = true">
        <span class="cap-icon">📐</span>
        <div class="cap-data">
          <span class="cap-val">12.3</span>
          <span class="cap-unit">km²</span>
        </div>
        <span class="cap-label">过火面积</span>
      </div>
      <div class="capsule capsule-risk" :class="riskClass">
        <span class="cap-icon">⚠️</span>
        <div class="cap-data">
          <span class="cap-dot" :class="riskClass"></span>
          <span class="cap-val-sm">{{ riskLabel }}</span>
        </div>
        <span class="cap-label">火势风险</span>
      </div>
      <div class="capsule capsule-alert-time">
        <span class="cap-icon">🕐</span>
        <div class="cap-data">
          <span class="cap-val-sm">{{ latestAlertTime }}</span>
        </div>
        <span class="cap-label">最新预警</span>
      </div>
      <div class="top-right">
        <span v-if="hasNewAlert" class="alert-dot" title="新告警" @click="showAllAlerts = true">⚠️</span>
        <div class="update-tag">
          <span class="ut-text">更新：{{ lastUpdate }}</span>
          <button class="ut-refresh" @click="refreshData" title="刷新">↻</button>
        </div>
      </div>
    </div>

    <div class="main-content">
      <div class="side-panel left" :class="{ collapsed: leftCollapsed }">
        <button class="collapse-btn" @click="leftCollapsed = !leftCollapsed" :title="leftCollapsed ? '展开面板' : '收起面板'">
          <span class="arrow">{{ leftCollapsed ? '→' : '←' }}</span>
        </button>

        <template v-if="!leftCollapsed">
          <div class="glass-card weather-card" :class="{ 'pm-warn': pm25Warn }">
            <div class="card-title">实时气象观测</div>
            <div class="weather-grid">
              <div class="wg-cell">
                <span class="wg-icon">🌡️</span>
                <span class="wg-val">28℃</span>
                <span class="wg-sub">体感 26℃</span>
                <span class="wg-trend down">↓ 2℃</span>
              </div>
              <div class="wg-cell">
                <span class="wg-icon">💨</span>
                <span class="wg-val">3.4</span>
                <span class="wg-sub">m/s 西北</span>
                <span class="wg-compass">↖</span>
              </div>
              <div class="wg-cell">
                <span class="wg-icon">🌫️</span>
                <span class="wg-val">65</span>
                <span class="wg-sub">PM2.5 良</span>
                <span class="wg-trend up">↑ 8</span>
              </div>
            </div>
            <div class="weather-alert">
              <span class="wa-tag">⚠ 大风黄色预警</span>
            </div>
          </div>

          <div class="glass-card tabbed-card">
            <div class="tabs-row">
              <div
                v-for="lt in leftTabs"
                :key="lt.id"
                class="tr-item"
                :class="{ active: leftActiveTab === lt.id }"
                @click="leftActiveTab = lt.id"
              >{{ lt.label }}</div>
            </div>
            <div class="tab-body">
              <div v-if="leftActiveTab === 'fireline'" class="fireline-list">
                <div v-for="fl in firelineData" :key="fl.id" class="fl-item">
                  <span class="fl-icon">🔥</span>
                  <div class="fl-info">
                    <span class="fl-name">{{ fl.name }}</span>
                    <span class="fl-dir">{{ fl.direction }}</span>
                  </div>
                  <span class="fl-temp">{{ fl.temp }}℃</span>
                </div>
              </div>
              <div v-else-if="leftActiveTab === 'heatmap'" class="heatmap-view">
                <div class="hm-scale">
                  <div class="hm-bar"></div>
                  <div class="hm-labels">
                    <span>低温</span><span>中温</span><span>高温</span>
                  </div>
                </div>
                <div class="hm-legend-item">当前热力覆盖：<span class="hm-val">850 hm²</span></div>
              </div>
              <div v-else class="env-extra">
                <div class="ee-row">
                  <span class="ee-label">湿度</span><span class="ee-val">45%</span>
                </div>
                <div class="ee-row">
                  <span class="ee-label">降水概率</span><span class="ee-val">12%</span>
                </div>
                <div class="ee-row">
                  <span class="ee-label">能见度</span><span class="ee-val">8.2 km</span>
                </div>
                <div class="ee-row">
                  <span class="ee-label">气压</span><span class="ee-val">1013 hPa</span>
                </div>
              </div>
            </div>
          </div>

          <div class="glass-card">
            <div class="card-title-row">
              <span class="card-title">资源部署摘要</span>
              <button class="card-detail-btn" @click="showResourceDetail = true">详情</button>
            </div>
            <div class="resource-grid">
              <div class="rg-cell">
                <span class="rg-icon">🚒</span>
                <span class="rg-val">12</span>
                <span class="rg-label">消防队伍</span>
              </div>
              <div class="rg-cell">
                <span class="rg-icon">🚁</span>
                <span class="rg-val">5</span>
                <span class="rg-label">直升机</span>
              </div>
              <div class="rg-cell">
                <span class="rg-icon">🛸</span>
                <span class="rg-val">8</span>
                <span class="rg-label">无人机</span>
              </div>
              <div class="rg-cell">
                <span class="rg-icon">🚛</span>
                <span class="rg-val">20</span>
                <span class="rg-label">水车</span>
              </div>
            </div>
          </div>
        </template>

        <template v-else>
          <div class="collapsed-icons">
            <div class="ico-item" title="气象观测" @click="leftCollapsed = false">🌡️</div>
            <div class="ico-item" title="火线态势" @click="leftCollapsed = false; leftActiveTab = 'fireline'">🔥</div>
            <div class="ico-item" title="资源部署" @click="showResourceDetail = true">🚒</div>
          </div>
        </template>
      </div>

      <div class="center-area">
        <div ref="mapRef" class="map-container"></div>
        <div class="map-overlay-top">
          <div class="map-layer-controls">
            <button class="ml-btn" :class="{ active: mapLayers.fire }" @click="toggleLayer('fire')">🔥 火线</button>
            <button class="ml-btn" :class="{ active: mapLayers.heatmap }" @click="toggleLayer('heatmap')">🌡️ 热力</button>
            <button class="ml-btn" :class="{ active: mapLayers.resource }" @click="toggleLayer('resource')">📦 资源</button>
          </div>
        </div>
        <div class="map-legend">
          <div class="ml-item"><span class="ml-dot" style="background:#ef4444"></span>高危火点</div>
          <div class="ml-item"><span class="ml-dot" style="background:#f59e0b"></span>中危火点</div>
          <div class="ml-item"><span class="ml-dot" style="background:#84cc16"></span>低危火点</div>
          <div class="ml-item"><span class="ml-line"></span>火线蔓延</div>
        </div>
      </div>

      <div class="side-panel right" :class="{ collapsed: rightCollapsed }">
        <button class="collapse-btn" @click="rightCollapsed = !rightCollapsed" :title="rightCollapsed ? '展开面板' : '收起面板'">
          <span class="arrow">{{ rightCollapsed ? '←' : '→' }}</span>
        </button>

        <template v-if="!rightCollapsed">
          <div class="glass-card">
            <div class="card-title">高危火情列表</div>
            <div class="fire-list">
              <div v-if="fireList.length === 0" class="empty-state">
                <span class="es-icon">✅</span>
                <span class="es-text">暂无活跃高危火情</span>
              </div>
              <div
                v-for="(f, idx) in fireList"
                :key="f.id"
                class="fire-list-item"
                :class="{ 'top-risk': idx === 0 && f.level === 'high' }"
                @click="focusFireOnMap(f)"
              >
                <div class="fli-header">
                  <span class="fli-id">{{ f.id }}</span>
                  <span class="fli-loc">{{ f.location }}</span>
                </div>
                <div class="fli-meta">
                  <span class="fli-temp">{{ f.temperature }}℃</span>
                  <span class="fli-area">{{ f.area }} hm²</span>
                  <span class="fli-confidence">{{ f.confidence }}%</span>
                </div>
                <div class="fli-time">
                  <span>{{ f.firstTime }}</span>
                  <span class="fli-update">{{ f.lastUpdate }}</span>
                </div>
              </div>
            </div>
          </div>

          <div class="glass-card alert-card">
            <div class="card-title-row">
              <span class="card-title">实时告警</span>
              <span v-if="newAlertCount > 0" class="alert-badge">{{ newAlertCount }}</span>
            </div>
            <div
              class="alert-stream"
              @mouseenter="pauseAlertScroll = true"
              @mouseleave="pauseAlertScroll = false"
            >
              <div ref="alertScrollRef" class="alert-scroll-inner">
                <div v-for="a in displayAlerts" :key="a.id" class="alert-item" :class="a.level">
                  <span class="ai-time">{{ a.time }}</span>
                  <span class="ai-msg">{{ a.message }}</span>
                  <span v-if="a.level === 'high'" class="ai-tag">高</span>
                </div>
              </div>
            </div>
            <button class="detail-link" @click="showAllAlerts = true">查看更多</button>
          </div>

          <div class="glass-card">
            <div class="card-title">视频监控</div>
            <div class="video-wall">
              <div
                v-for="cam in cameras"
                :key="cam.id"
                class="video-thumb"
                @click="openVideo(cam)"
                @mouseenter="cam.hovered = true"
                @mouseleave="cam.hovered = false"
              >
                <div class="vt-preview">
                  <span class="vt-icon">📹</span>
                  <div v-if="cam.hovered" class="vt-hint">点击查看实时画面</div>
                </div>
                <div class="vt-info">
                  <span class="vt-name">{{ cam.name }}</span>
                  <span class="vt-status" :class="cam.status">{{ cam.status === 'online' ? '正常' : '离线' }}</span>
                </div>
              </div>
            </div>
            <button class="detail-link" @click="showAllCameras = true">全部监控</button>
          </div>
        </template>

        <template v-else>
          <div class="collapsed-icons">
            <div class="ico-item" :class="{ 'alert-active': fireList.length > 0 }" title="高危火情" @click="rightCollapsed = false">🔥</div>
            <div class="ico-item" :class="{ 'alert-active': newAlertCount > 0 }" title="实时告警" @click="showAllAlerts = true">⚠️</div>
            <div class="ico-item" title="视频监控" @click="rightCollapsed = false">📹</div>
          </div>
        </template>
      </div>
    </div>

    <div class="bottom-bar">
      <div class="tl-controls">
        <button class="tl-btn" :class="{ active: isPlaying }" @click="togglePlay" :title="isPlaying ? '暂停' : '播放'">
          {{ isPlaying ? '⏸' : '▶' }}
        </button>
        <button class="tl-btn" @click="resetTimeline" title="重置">⟲</button>
      </div>
      <div class="tl-slider-track">
        <div class="tl-time-bubble" :style="{ left: sliderPercent + '%' }">{{ currentTimeDisplay }}</div>
        <input
          type="range"
          class="tl-slider"
          :min="0"
          :max="timeSteps.length - 1"
          :value="currentStep"
          @input="onSliderInput"
        />
        <div class="tl-marks">
          <span v-for="(t, i) in timeMarks" :key="i" class="tl-mark" :style="{ left: (i / (timeMarks.length - 1) * 100) + '%' }">{{ t }}</span>
        </div>
      </div>
      <div class="tl-summary">
        <span>过火面积：<span class="tls-val">12.3 km²</span></span>
        <span class="tls-divider">|</span>
        <span>活跃火点：<span class="tls-val">7 处</span></span>
      </div>
    </div>

    <transition name="toast">
      <div v-if="showToast" class="toast-notification">
        <span class="toast-icon">✓</span>
        <span class="toast-text">{{ toastMessage }}</span>
      </div>
    </transition>

    <transition name="drawer">
      <div v-if="showAllAlerts" class="drawer-overlay" @click="showAllAlerts = false">
        <div class="drawer-content" @click.stop>
          <div class="drawer-header">
            历史告警
            <button class="close-drawer" @click="showAllAlerts = false">✕</button>
          </div>
          <div class="drawer-body">
            <div v-for="a in allAlerts" :key="a.id" class="da-alert-item" :class="a.level">
              <span class="da-time">{{ a.time }}</span>
              <div class="da-bubble">
                <span class="da-msg">{{ a.message }}</span>
              </div>
              <span v-if="a.level === 'high'" class="da-tag">高</span>
            </div>
          </div>
        </div>
      </div>
    </transition>

    <transition name="drawer">
      <div v-if="showAllCameras" class="drawer-overlay" @click="showAllCameras = false">
        <div class="drawer-content" @click.stop>
          <div class="drawer-header">
            全部监控
            <button class="close-drawer" @click="showAllCameras = false">✕</button>
          </div>
          <div class="drawer-body">
            <div class="camera-grid-drawer">
              <div v-for="cam in allCameras" :key="cam.id" class="cam-drawer-card" @click="openVideo(cam)">
                <div class="cdc-preview">
                  <span class="cdc-icon">📹</span>
                </div>
                <div class="cdc-info">
                  <span class="cdc-name">{{ cam.name }}</span>
                  <span class="cdc-status" :class="cam.status">{{ cam.status === 'online' ? '正常' : '离线' }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </transition>

    <transition name="drawer">
      <div v-if="showResourceDetail" class="drawer-overlay" @click="showResourceDetail = false">
        <div class="drawer-content" @click.stop>
          <div class="drawer-header">
            资源清单
            <button class="close-drawer" @click="showResourceDetail = false">✕</button>
          </div>
          <div class="drawer-body">
            <div v-for="r in resourceList" :key="r.name" class="res-drawer-item">
              <span class="rd-icon">{{ r.icon }}</span>
              <div class="rd-info">
                <span class="rd-name">{{ r.name }}</span>
                <span class="rd-detail">{{ r.detail }}</span>
              </div>
              <span class="rd-val">{{ r.value }}</span>
            </div>
          </div>
        </div>
      </div>
    </transition>

    <transition name="drawer">
      <div v-if="showTempDetail" class="drawer-overlay" @click="showTempDetail = false">
        <div class="drawer-content" @click.stop>
          <div class="drawer-header">
            火线温度详情
            <button class="close-drawer" @click="showTempDetail = false">✕</button>
          </div>
          <div class="drawer-body">
            <div v-for="tp in tempDetail" :key="tp.name" class="da-item">
              <span class="da-name">{{ tp.name }}</span>
              <div class="da-bar-area">
                <div class="da-bar" :style="{ width: (tp.temp / 800 * 100) + '%' }"></div>
              </div>
              <span class="da-val">{{ tp.temp }}℃</span>
            </div>
          </div>
        </div>
      </div>
    </transition>

    <transition name="drawer">
      <div v-if="showAreaDetail" class="drawer-overlay" @click="showAreaDetail = false">
        <div class="drawer-content" @click.stop>
          <div class="drawer-header">
            过火面积详情
            <button class="close-drawer" @click="showAreaDetail = false">✕</button>
          </div>
          <div class="drawer-body">
            <div v-for="a in areaDetail" :key="a.name" class="da-item">
              <span class="da-name">{{ a.name }}</span>
              <div class="da-bar-area">
                <div class="da-bar" :style="{ width: (a.area / 6 * 100) + '%' }"></div>
              </div>
              <span class="da-val">{{ a.area }} km²</span>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { fireAPI, resourceAPI } from '../api/modules'
import { onAlertMessage } from '../services/websocket'
import * as echarts from 'echarts'
import mapboxgl from 'mapbox-gl'

const mapRef = ref<HTMLDivElement>()
const alertScrollRef = ref<HTMLDivElement>()

const leftCollapsed = ref(false)
const rightCollapsed = ref(false)
const leftActiveTab = ref('fireline')
const autoCompactMode = ref(false)
const manualCompactMode = ref(false)
/* 自动紧凑和手动紧凑叠加：小屏强制紧凑，键盘 C 仍可手动切换紧凑模式。 */
const compactMode = computed(() => autoCompactMode.value || manualCompactMode.value)
const showToast = ref(false)
const toastMessage = ref('')
const lastUpdate = ref('14:38')
const hasNewAlert = ref(false)
const newAlertCount = ref(0)
const pauseAlertScroll = ref(false)
const pm25Warn = ref(false)

const showAllAlerts = ref(false)
const showAllCameras = ref(false)
const showResourceDetail = ref(false)
const showTempDetail = ref(false)
const showAreaDetail = ref(false)

const isPlaying = ref(false)
const currentStep = ref(6)
const timeSteps = ['10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00']
const timeMarks = ['12:00', '14:00', '16:00', '18:00']

const riskClass = computed(() => {
  const area = 12.3
  if (area > 15) return 'high'
  if (area > 8) return 'medium'
  return 'low'
})

const riskLabel = computed(() => {
  if (riskClass.value === 'high') return '高风险'
  if (riskClass.value === 'medium') return '中风险'
  return '低风险'
})

const latestAlertTime = ref('15:23:08')
const sliderPercent = computed(() => currentStep.value / (timeSteps.length - 1) * 100)
const currentTimeDisplay = computed(() => timeSteps[currentStep.value] || '16:00')

const mapLayers = reactive({
  fire: true,
  heatmap: false,
  resource: false
})

const leftTabs = [
  { id: 'fireline', label: '火线态势' },
  { id: 'heatmap', label: '热力分布' },
  { id: 'env', label: '环境监测' }
]

const firelineData = ref([
  { id: 'A', name: '火线 A', direction: '→ 东南蔓延', temp: 687 },
  { id: 'B', name: '火线 B', direction: '↗ 东北蔓延', temp: 542 },
  { id: 'C', name: '火线 C', direction: '↓ 南向蔓延', temp: 398 }
])

const fireList = ref([
  { id: 'F-103', location: '石门山北坡', temperature: 687, area: 4.8, confidence: 95, level: 'high', firstTime: '14:20', lastUpdate: '15:23', lng: 116.42, lat: 39.95 },
  { id: 'F-102', location: '青松岭西侧', temperature: 542, area: 3.2, confidence: 88, level: 'high', firstTime: '13:50', lastUpdate: '15:18', lng: 116.38, lat: 39.92 },
  { id: 'F-101', location: '白桦林南坡', temperature: 398, area: 2.1, confidence: 82, level: 'medium', firstTime: '13:15', lastUpdate: '15:10', lng: 116.45, lat: 39.88 },
  { id: 'F-100', location: '鹰嘴崖东侧', temperature: 276, area: 1.2, confidence: 76, level: 'medium', firstTime: '12:40', lastUpdate: '15:05', lng: 116.35, lat: 39.97 },
  { id: 'F-099', location: '松涛谷', temperature: 185, area: 0.8, confidence: 91, level: 'low', firstTime: '12:10', lastUpdate: '14:55', lng: 116.50, lat: 39.90 }
])

const cameras = ref([
  { id: 1, name: '西北角塔', status: 'online', hovered: false },
  { id: 2, name: '南坡路口', status: 'online', hovered: false },
  { id: 3, name: '东侧瞭望', status: 'offline', hovered: false }
])

const allCameras = ref([
  { id: 1, name: '西北角塔', status: 'online' },
  { id: 2, name: '南坡路口', status: 'online' },
  { id: 3, name: '东侧瞭望', status: 'offline' },
  { id: 4, name: '北山监测', status: 'online' },
  { id: 5, name: '河谷监控', status: 'online' },
  { id: 6, name: '营地周边', status: 'offline' }
])

const displayAlerts = ref([
  { id: 1, time: '15:32:21', message: '【石门山】红外异常升温，建议增援', level: 'high' },
  { id: 2, time: '15:28:15', message: '【青松岭】火势蔓延加速，风向突变', level: 'high' },
  { id: 3, time: '15:20:08', message: '【白桦林】火线已控制，持续监测中', level: 'medium' },
  { id: 4, time: '15:15:42', message: '【鹰嘴崖】新增火点，已派遣无人机侦察', level: 'medium' },
  { id: 5, time: '15:10:03', message: '【松涛谷】火势稳定，无扩大趋势', level: 'low' }
])

const allAlerts = ref([
  { id: 1, time: '15:32:21', message: '【石门山】红外异常升温，建议增援', level: 'high' },
  { id: 2, time: '15:28:15', message: '【青松岭】火势蔓延加速，风向突变', level: 'high' },
  { id: 3, time: '15:20:08', message: '【白桦林】火线已控制，持续监测中', level: 'medium' },
  { id: 4, time: '15:15:42', message: '【鹰嘴崖】新增火点，已派遣无人机侦察', level: 'medium' },
  { id: 5, time: '15:10:03', message: '【松涛谷】火势稳定，无扩大趋势', level: 'low' },
  { id: 6, time: '15:05:30', message: '【石门山】烟雾浓度上升，注意防护', level: 'medium' },
  { id: 7, time: '14:58:12', message: '【青松岭】首批消防力量抵达', level: 'low' },
  { id: 8, time: '14:50:45', message: '【指挥部】启动二级响应预案', level: 'high' }
])

const resourceList = ref([
  { icon: '🚒', name: '消防一队', detail: '火场A · 已部署', value: '32人' },
  { icon: '🚒', name: '消防二队', detail: '火场B · 已部署', value: '28人' },
  { icon: '🚒', name: '消防三队', detail: '待命中', value: '25人' },
  { icon: '🚁', name: '直升机H1', detail: '火场A · 侦察中', value: '1架' },
  { icon: '🚁', name: '直升机H2', detail: '待命中', value: '1架' },
  { icon: '🛸', name: '无人机U1-U8', detail: '2架执行 · 6架待命', value: '8架' },
  { icon: '🚛', name: '水车编队', detail: '已部署15辆', value: '20辆' }
])

const tempDetail = ref([
  { name: '火场A', temp: 687 },
  { name: '火场B', temp: 542 },
  { name: '火场C', temp: 398 }
])

const areaDetail = ref([
  { name: '石门山', area: 4.8 },
  { name: '青松岭', area: 3.2 },
  { name: '白桦林', area: 2.1 },
  { name: '鹰嘴崖', area: 1.2 },
  { name: '松涛谷', area: 0.8 }
])

let map: mapboxgl.Map | null = null
let playInterval: ReturnType<typeof setInterval> | null = null
let resizeHandler: (() => void) | null = null

function updateResponsiveLayout() {
  const width = window.innerWidth
  const height = window.innerHeight
  /* 宽度 <=1366 或高度 <=700 自动启用紧凑尺寸，防止面板内容纵向溢出。 */
  autoCompactMode.value = width <= 1366 || height <= 700
  /* 宽度 <=1100 时右侧面板默认折叠，给中心地图保留最小可视宽度。 */
  if (width <= 1100) rightCollapsed.value = true
  nextTick(() => map?.resize())
}

function toast(msg: string, duration = 2500) {
  toastMessage.value = msg
  showToast.value = true
  setTimeout(() => { showToast.value = false }, duration)
}

function toggleLayer(layer: string) {
  const key = layer as keyof typeof mapLayers
  mapLayers[key] = !mapLayers[key]
}

function focusFireOnMap(f: any) {
  if (map) {
    map.flyTo({ center: [f.lng, f.lat], zoom: 12 })
    toast(`已聚焦 ${f.location}`)
  }
}

function openVideo(cam: any) {
  toast(`${cam.name} 视频流加载中...`)
}

function refreshData() {
  lastUpdate.value = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  toast('数据已刷新')
}

function togglePlay() {
  if (isPlaying.value) {
    isPlaying.value = false
    if (playInterval) { clearInterval(playInterval); playInterval = null }
  } else {
    isPlaying.value = true
    playInterval = setInterval(() => {
      if (currentStep.value < timeSteps.length - 1) {
        currentStep.value++
      } else {
        isPlaying.value = false
        if (playInterval) { clearInterval(playInterval); playInterval = null }
      }
    }, 800)
  }
}

function resetTimeline() {
  isPlaying.value = false
  if (playInterval) { clearInterval(playInterval); playInterval = null }
  currentStep.value = timeSteps.length - 1
  toast('时间轴已重置为最新')
}

function onSliderInput(e: Event) {
  const target = e.target as HTMLInputElement
  currentStep.value = parseInt(target.value)
}

function handleKeydown(e: KeyboardEvent) {
  if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement || e.target instanceof HTMLTextAreaElement) return
  switch (e.key.toLowerCase()) {
    case 'l': leftCollapsed.value = !leftCollapsed.value; break
    case 'r': rightCollapsed.value = !rightCollapsed.value; break
    case 'c': manualCompactMode.value = !manualCompactMode.value; break
    case 'm': if (map) { map.flyTo({ center: [116.4, 39.9], zoom: 10 }); toast('地图已复位') }; break
  }
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
  map.addControl(new mapboxgl.NavigationControl(), 'top-right')

  map.on('load', () => {
    map!.addSource('fire-points', {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: fireList.value.map(f => ({
        type: 'Feature',
        properties: { level: f.level },
        geometry: { type: 'Point', coordinates: [f.lng, f.lat] }
      })) }
    })
    map!.addLayer({
      id: 'fire-circles',
      type: 'circle',
      source: 'fire-points',
      paint: {
        'circle-radius': ['match', ['get', 'level'], 'high', 12, 'medium', 8, 6],
        'circle-color': ['match', ['get', 'level'], 'high', '#ef4444', 'medium', '#f59e0b', '#84cc16'],
        'circle-opacity': 0.8,
        'circle-stroke-width': 2,
        'circle-stroke-color': '#fff'
      }
    })
  })
}

async function loadData() {
  try {
    const [fires, stat] = await Promise.all([
      fireAPI.getList().catch(() => []),
      fireAPI.getStat().catch(() => ({}))
    ])
    if (fires && fires.length) fireList.value = fires
  } catch (e) {}
}

watch([leftCollapsed, rightCollapsed], () => {
  nextTick(() => {
    setTimeout(() => map?.resize(), 250)
  })
})

onMounted(() => {
  updateResponsiveLayout()
  initMap()
  loadData()
  lastUpdate.value = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  onAlertMessage((data: any) => {
    hasNewAlert.value = true
    newAlertCount.value++
    const newAlert = {
      id: Date.now(),
      time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      message: data?.message || '新告警',
      level: data?.level || 'medium'
    }
    displayAlerts.value.unshift(newAlert)
    allAlerts.value.unshift(newAlert)
    latestAlertTime.value = newAlert.time
    setTimeout(() => { hasNewAlert.value = false }, 8000)
    setTimeout(() => { newAlertCount.value = Math.max(0, newAlertCount.value - 1) }, 5000)
  })
  resizeHandler = updateResponsiveLayout
  window.addEventListener('resize', resizeHandler)
})

onUnmounted(() => {
  if (playInterval) clearInterval(playInterval)
  if (resizeHandler) window.removeEventListener('resize', resizeHandler)
  map?.remove()
})
</script>

<style scoped>
.monitor-container {
  /* 改为继承 App 主区域高度，避免 AppHeader + 100vh 叠加产生页面滚动条。 */
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: linear-gradient(180deg, #0A0F1A 0%, #162035 100%);
  display: flex;
  flex-direction: column;
  color: #e2e8f0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  outline: none;
}

.top-bar {
  /* 顶部状态栏使用 clamp，在 600-700px 高屏幕下自动压缩。 */
  height: clamp(48px, 8vh, 64px);
  flex: 0 0 clamp(48px, 8vh, 64px);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: clamp(6px, 0.8vw, 14px);
  padding: 0 clamp(10px, 1.7vw, 32px);
  background: rgba(20, 28, 40, 0.9);
  border-bottom: 1px solid rgba(255,255,255,0.06);
  backdrop-filter: blur(16px);
}

.capsule {
  display: flex;
  align-items: center;
  /* 胶囊横向间距随视口收缩，防止顶部栏横向溢出。 */
  padding: clamp(5px, 0.75vh, 8px) clamp(8px, 0.85vw, 16px);
  border-radius: 40px;
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(255,255,255,0.12);
  backdrop-filter: blur(10px);
  gap: clamp(4px, 0.45vw, 8px);
  cursor: pointer;
  transition: border-color 0.2s;
  position: relative;
}

.capsule:hover { border-color: rgba(255,255,255,0.25); }
.capsule:active { transform: scale(0.97); }

.capsule-temp { border-color: rgba(239,68,68,0.3); background: rgba(239,68,68,0.06); }
.capsule-area { border-color: rgba(245,158,11,0.3); background: rgba(245,158,11,0.05); }
.capsule-risk.high { border-color: rgba(239,68,68,0.4); background: rgba(239,68,68,0.08); }
.capsule-risk.medium { border-color: rgba(245,158,11,0.3); background: rgba(245,158,11,0.05); }
.capsule-risk.low { border-color: rgba(34,197,94,0.3); background: rgba(34,197,94,0.05); }
.capsule-alert-time { border-color: rgba(99,102,241,0.3); background: rgba(99,102,241,0.05); }

.cap-icon { font-size: clamp(12px, 0.85vw, 16px); }
.cap-data { display: flex; align-items: baseline; gap: 3px; }

.cap-val {
  font-size: clamp(16px, 1.25vw, 24px);
  font-weight: 700;
  line-height: 1;
}

.capsule-temp .cap-val {
  background: linear-gradient(90deg, #fca5a5, #ef4444);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.capsule-area .cap-val {
  background: linear-gradient(90deg, #fcd34d, #f59e0b);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.cap-val-sm { font-size: clamp(12px, 0.85vw, 16px); font-weight: 700; }

.cap-unit { font-size: clamp(9px, 0.65vw, 12px); color: #94a3b8; }
.cap-label { font-size: clamp(9px, 0.58vw, 10px); color: #64748b; }

.cap-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.cap-dot.high { background: #ef4444; animation: pulse 1.5s ease-in-out infinite; }
.cap-dot.medium { background: #f59e0b; }
.cap-dot.low { background: #22c55e; }

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(1.5); }
}

.top-right {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-left: auto;
}

.alert-dot {
  font-size: 16px;
  animation: pulse 1s ease-in-out infinite;
  cursor: pointer;
}

.update-tag { display: flex; align-items: center; gap: 6px; }
.ut-text { font-size: 11px; color: #64748b; }

.ut-refresh {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  border: 1px solid rgba(255,255,255,0.08);
  background: rgba(255,255,255,0.04);
  color: #94a3b8;
  cursor: pointer;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.ut-refresh:hover { background: rgba(96,165,250,0.15); color: #e2e8f0; }

.main-content {
  flex: 1;
  display: flex;
  min-height: 0;
  min-width: 0;
  overflow: hidden;
}

.side-panel {
  /* 将固定 320px 改为 clamp(200px,18vw,320px)，防止窄屏横向溢出。 */
  width: clamp(200px, 18vw, 320px);
  flex: 0 0 clamp(200px, 18vw, 320px);
  min-height: 0;
  display: flex;
  flex-direction: column;
  position: relative;
  transition: width 0.2s ease;
  padding: clamp(6px, 0.9vh, 10px);
  gap: clamp(5px, 0.9vh, 10px);
  overflow: hidden;
}

.side-panel.collapsed {
  /* 折叠宽度也使用 clamp，避免小屏仍占用过多主区域宽度。 */
  width: clamp(48px, 6vw, 60px);
  flex-basis: clamp(48px, 6vw, 60px);
  padding: clamp(5px, 0.9vh, 10px) clamp(4px, 0.45vw, 8px);
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
  /* 卡片 padding 随高度收缩，减少小屏纵向累计高度。 */
  padding: clamp(7px, 1.1vh, 12px);
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

.side-panel > .weather-card {
  flex: 0.9 1 0;
}

.side-panel > .tabbed-card {
  flex: 1 1 0;
}

.glass-card:hover { border-color: rgba(255,255,255,0.15); }

.weather-card.pm-warn { border-color: rgba(239,68,68,0.3); }

.card-title {
  font-size: clamp(10px, 0.68vw, 12px);
  font-weight: 600;
  color: #cbd5e1;
  margin-bottom: clamp(5px, 0.8vh, 10px);
  letter-spacing: 0.5px;
}

.card-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: clamp(5px, 0.8vh, 10px);
}

.card-title-row .card-title { margin-bottom: 0; }

.card-detail-btn {
  border: none;
  background: rgba(96,165,250,0.15);
  color: #60a5fa;
  font-size: 10px;
  padding: 4px 10px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.card-detail-btn:hover { background: rgba(96,165,250,0.25); }

.weather-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: clamp(4px, 0.7vh, 8px);
  margin-bottom: clamp(4px, 0.7vh, 8px);
}

.wg-cell {
  padding: clamp(4px, 0.75vh, 8px);
  border-radius: 12px;
  background: rgba(255,255,255,0.03);
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.wg-icon { font-size: clamp(12px, 0.9vw, 16px); }
.wg-val { font-size: clamp(13px, 0.95vw, 18px); font-weight: 700; color: #e2e8f0; }
.wg-sub { font-size: 9px; color: #64748b; }
.wg-trend { font-size: 9px; font-weight: 600; }
.wg-trend.up { color: #ef4444; }
.wg-trend.down { color: #22c55e; }
.wg-compass { font-size: 14px; color: #60a5fa; }

.weather-alert {
  padding: 6px 10px;
  border-radius: 8px;
  background: rgba(245,158,11,0.1);
  border: 1px solid rgba(245,158,11,0.2);
  text-align: center;
}

.wa-tag { font-size: 10px; color: #fbbf24; font-weight: 600; }

.tabs-row {
  display: flex;
  gap: 4px;
  background: rgba(255,255,255,0.04);
  padding: 4px;
  border-radius: 10px;
  margin-bottom: clamp(5px, 0.8vh, 10px);
}

.tr-item {
  flex: 1;
  text-align: center;
  padding: 6px 4px;
  border-radius: 8px;
  font-size: 11px;
  color: #94a3b8;
  cursor: pointer;
  transition: all 0.2s;
}

.tr-item:hover { color: #e2e8f0; }
.tr-item.active { background: rgba(96,165,250,0.2); color: #60a5fa; font-weight: 600; }

.tab-body {
  /* 去掉固定最小高度，允许标签内容在低屏幕中收缩。 */
  min-height: 0;
  flex: 1;
  overflow: hidden;
}

.fireline-list { display: flex; flex-direction: column; gap: 6px; }

.fl-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 8px;
  background: rgba(255,255,255,0.03);
}

.fl-icon { font-size: 14px; }
.fl-info { flex: 1; display: flex; flex-direction: column; }
.fl-name { font-size: 11px; color: #cbd5e1; }
.fl-dir { font-size: 9px; color: #64748b; }
.fl-temp { font-size: 12px; font-weight: 600; color: #f87171; }

.hm-scale { margin-bottom: 8px; }

.hm-bar {
  height: 8px;
  border-radius: 4px;
  background: linear-gradient(90deg, #3b82f6, #f59e0b, #ef4444);
}

.hm-labels { display: flex; justify-content: space-between; font-size: 9px; color: #64748b; margin-top: 2px; }

.hm-legend-item { font-size: 11px; color: #94a3b8; }
.hm-val { color: #f59e0b; font-weight: 600; }

.env-extra { display: flex; flex-direction: column; gap: 6px; }

.ee-row {
  display: flex;
  justify-content: space-between;
  padding: 4px 8px;
  border-radius: 6px;
  background: rgba(255,255,255,0.03);
  font-size: 11px;
}

.ee-label { color: #94a3b8; }
.ee-val { color: #cbd5e1; font-weight: 600; }

.resource-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: clamp(4px, 0.7vh, 8px);
  flex: 1;
  min-height: 0;
}

.rg-cell {
  padding: clamp(4px, 0.7vh, 8px);
  border-radius: 12px;
  background: rgba(255,255,255,0.03);
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.rg-icon { font-size: 18px; }
.rg-val { font-size: 18px; font-weight: 700; color: #e2e8f0; }
.rg-label { font-size: 10px; color: #64748b; }

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
.ico-item.alert-active { border: 1px solid rgba(239,68,68,0.4); background: rgba(239,68,68,0.1); }

.center-area {
  flex: 1;
  position: relative;
  margin: clamp(6px, 0.9vh, 10px) 0;
  border-radius: 20px;
  overflow: hidden;
  border: 1px solid rgba(255,255,255,0.08);
  min-width: 0;
  min-height: 0;
}

.map-container { width: 100%; height: 100%; }

.map-overlay-top { position: absolute; top: 12px; left: 12px; z-index: 10; }
.map-overlay-top {
  /* 地图控件偏移用 clamp，确保不会贴边或越界。 */
  top: clamp(8px, 2vw, 16px);
  left: clamp(8px, 2vw, 16px);
}

.map-layer-controls { display: flex; flex-direction: column; gap: 4px; }

.ml-btn {
  padding: 7px 12px;
  border-radius: 10px;
  border: 1px solid rgba(255,255,255,0.1);
  background: rgba(20,28,40,0.85);
  color: #94a3b8;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.2s;
  backdrop-filter: blur(8px);
  text-align: left;
}

.ml-btn:hover { color: #e2e8f0; }
.ml-btn.active { background: rgba(96,165,250,0.2); border-color: rgba(96,165,250,0.4); color: #60a5fa; }

.map-legend {
  position: absolute;
  bottom: clamp(8px, 2vw, 16px);
  right: clamp(8px, 2vw, 16px);
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: clamp(6px, 0.8vh, 10px) clamp(8px, 0.8vw, 14px);
  border-radius: 12px;
  background: rgba(20,28,40,0.85);
  border: 1px solid rgba(255,255,255,0.08);
  backdrop-filter: blur(8px);
  z-index: 10;
  font-size: 11px;
  color: #94a3b8;
}

.ml-item { display: flex; align-items: center; gap: 6px; }

.ml-dot { width: 8px; height: 8px; border-radius: 50%; }

.ml-line { width: 12px; height: 2px; background: rgba(239,68,68,0.6); border-radius: 1px; }

.fire-list {
  display: flex;
  flex-direction: column;
  gap: clamp(3px, 0.55vh, 6px);
  min-height: 0;
  overflow: hidden;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 20px;
  gap: 8px;
}

.es-icon { font-size: 24px; }
.es-text { font-size: 12px; color: #64748b; }

.fire-list-item {
  padding: clamp(5px, 0.75vh, 8px) clamp(6px, 0.7vw, 10px);
  border-radius: 10px;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.04);
  cursor: pointer;
  transition: all 0.2s;
}

.fire-list-item:hover { background: rgba(96,165,250,0.08); border-color: rgba(96,165,250,0.2); }
.fire-list-item.top-risk { border-left: 3px solid #ef4444; }

.fli-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
}

.fli-id { font-size: 11px; font-weight: 600; color: #60a5fa; }
.fli-loc { font-size: 11px; color: #cbd5e1; }

.fli-meta {
  display: flex;
  gap: 10px;
  margin-bottom: 4px;
}

.fli-temp { font-size: 12px; font-weight: 600; color: #f87171; }
.fli-area { font-size: 11px; color: #94a3b8; }
.fli-confidence { font-size: 10px; color: #64748b; }

.fli-time {
  display: flex;
  justify-content: space-between;
  font-size: 9px;
  color: #64748b;
}

.fli-update { color: #60a5fa; }

.alert-card { position: relative; }

.alert-badge {
  position: absolute;
  top: 10px;
  right: 12px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #ef4444;
  color: white;
  font-size: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  animation: pulse 1.5s ease-in-out infinite;
}

.alert-stream {
  /* 固定 120px 改为视口相关高度，低屏幕下自动压缩且不出现内部滚动条。 */
  height: clamp(74px, 14vh, 120px);
  overflow: hidden;
  margin-bottom: 6px;
}

.alert-scroll-inner {
  animation: autoScroll 15s linear infinite;
}

.alert-stream:hover .alert-scroll-inner { animation-play-state: paused; }

@keyframes autoScroll {
  0% { transform: translateY(0); }
  100% { transform: translateY(-50%); }
}

.alert-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 8px;
  border-radius: 6px;
  margin-bottom: 3px;
  font-size: 10px;
  background: rgba(255,255,255,0.03);
}

.alert-item.high { background: rgba(239,68,68,0.08); border-left: 2px solid #ef4444; }
.alert-item.medium { border-left: 2px solid #f59e0b; }
.alert-item.low { border-left: 2px solid #84cc16; }

.ai-time { color: #64748b; white-space: nowrap; flex-shrink: 0; }
.ai-msg {
  flex: 1;
  color: #94a3b8;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

.ai-tag {
  padding: 1px 5px;
  border-radius: 4px;
  background: #ef4444;
  color: white;
  font-size: 8px;
  font-weight: 700;
  flex-shrink: 0;
}

.detail-link {
  border: none;
  background: none;
  color: #60a5fa;
  font-size: 11px;
  cursor: pointer;
  padding: 4px 0;
  text-align: left;
  width: 100%;
}

.detail-link:hover { text-decoration: underline; }

.video-wall {
  display: flex;
  gap: clamp(4px, 0.55vw, 8px);
  margin-bottom: clamp(3px, 0.55vh, 6px);
  min-height: 0;
}

.video-thumb {
  flex: 1;
  border-radius: 10px;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06);
  overflow: hidden;
  cursor: pointer;
  transition: all 0.2s;
}

.video-thumb:hover { transform: scale(1.03); border-color: rgba(96,165,250,0.3); }

.vt-preview {
  aspect-ratio: 16/9;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0,0,0,0.3);
  position: relative;
}

.vt-icon { font-size: 20px; opacity: 0.5; }

.vt-hint {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0,0,0,0.6);
  font-size: 10px;
  color: #60a5fa;
}

.vt-info {
  padding: 5px 6px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.vt-name { font-size: 9px; color: #cbd5e1; }

.vt-status {
  font-size: 8px;
  padding: 1px 5px;
  border-radius: 6px;
}

.vt-status.online { background: rgba(34,197,94,0.12); color: #4ade80; }
.vt-status.offline { background: rgba(239,68,68,0.12); color: #f87171; }

.bottom-bar {
  /* 底部时间轴使用 clamp，在小高度屏幕中压缩到 52px。 */
  height: clamp(52px, 8vh, 80px);
  flex: 0 0 clamp(52px, 8vh, 80px);
  display: flex;
  align-items: center;
  gap: clamp(8px, 0.85vw, 16px);
  padding: 0 clamp(10px, 1.7vw, 32px);
  background: rgba(20,28,40,0.9);
  border-top: 1px solid rgba(255,255,255,0.06);
  backdrop-filter: blur(16px);
}

.tl-controls {
  display: flex;
  gap: 8px;
}

.tl-btn {
  width: clamp(30px, 4.8vh, 40px);
  height: clamp(30px, 4.8vh, 40px);
  border-radius: 50%;
  border: 1px solid rgba(255,255,255,0.12);
  background: rgba(255,255,255,0.06);
  color: #cbd5e1;
  font-size: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.tl-btn:hover { background: rgba(96,165,250,0.15); color: #e2e8f0; }
.tl-btn:active { transform: scale(0.92); }
.tl-btn.active { background: rgba(96,165,250,0.2); border-color: rgba(96,165,250,0.4); color: #60a5fa; }

.tl-slider-track {
  flex: 1;
  position: relative;
  padding: 20px 0 0 0;
}

.tl-time-bubble {
  position: absolute;
  top: 0;
  transform: translateX(-50%);
  padding: 3px 10px;
  border-radius: 8px;
  background: rgba(96,165,250,0.2);
  border: 1px solid rgba(96,165,250,0.3);
  font-size: 10px;
  color: #60a5fa;
  white-space: nowrap;
  backdrop-filter: blur(6px);
  z-index: 2;
}

.tl-slider {
  width: 100%;
  height: 4px;
  -webkit-appearance: none;
  appearance: none;
  background: rgba(255,255,255,0.08);
  border-radius: 2px;
  outline: none;
  cursor: pointer;
}

.tl-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #60a5fa;
  border: 2px solid rgba(255,255,255,0.3);
  box-shadow: 0 0 12px rgba(96,165,250,0.5);
  cursor: pointer;
}

.tl-marks {
  display: flex;
  justify-content: space-between;
  position: relative;
  margin-top: 4px;
  padding: 0 8px;
}

.tl-mark {
  font-size: 9px;
  color: #64748b;
  position: absolute;
  transform: translateX(-50%);
}

.tl-summary {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #94a3b8;
  white-space: nowrap;
}

.tls-val { color: #e2e8f0; font-weight: 600; }
.tls-divider { color: #334155; }

.toast-notification {
  position: fixed;
  top: 80px;
  right: 32px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 20px;
  border-radius: 14px;
  background: rgba(20,28,40,0.9);
  border: 1px solid rgba(96,165,250,0.3);
  backdrop-filter: blur(12px);
  box-shadow: 0 8px 32px rgba(0,0,0,0.4);
  z-index: 300;
}

.toast-icon { color: #22c55e; font-size: 16px; font-weight: 700; }
.toast-text { font-size: 13px; color: #cbd5e1; }

.toast-enter-active { transition: all 0.3s ease; }
.toast-leave-active { transition: all 0.3s ease; }
.toast-enter-from { opacity: 0; transform: translateX(40px); }
.toast-leave-to { opacity: 0; transform: translateX(40px); }

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
  transition: transform 0.25s ease;
}

.drawer-header {
  padding: 16px;
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

.close-drawer:hover { background: rgba(239,68,68,0.15); color: #f87171; }

.drawer-body {
  flex: 1;
  padding: clamp(8px, 1.2vh, 16px);
  /* 禁止抽屉内部纵向滚动，内容通过更小间距和网格压缩展示。 */
  overflow: hidden;
  min-height: 0;
}

.da-alert-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  margin-bottom: 6px;
  font-size: 11px;
  background: rgba(255,255,255,0.03);
}

.da-alert-item.high { background: rgba(239,68,68,0.08); }

.da-time { color: #64748b; white-space: nowrap; font-size: 10px; }
.da-bubble { flex: 1; }
.da-msg { color: #94a3b8; }

.da-tag {
  padding: 2px 6px;
  border-radius: 4px;
  background: #ef4444;
  color: white;
  font-size: 9px;
  font-weight: 700;
}

.camera-grid-drawer {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.cam-drawer-card {
  border-radius: 12px;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06);
  overflow: hidden;
  cursor: pointer;
  transition: all 0.2s;
}

.cam-drawer-card:hover { border-color: rgba(96,165,250,0.2); }

.cdc-preview {
  aspect-ratio: 16/9;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0,0,0,0.3);
}

.cdc-icon { font-size: 24px; opacity: 0.5; }

.cdc-info {
  padding: 6px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.cdc-name { font-size: 11px; color: #cbd5e1; }

.cdc-status {
  font-size: 9px;
  padding: 1px 5px;
  border-radius: 6px;
}

.cdc-status.online { background: rgba(34,197,94,0.12); color: #4ade80; }
.cdc-status.offline { background: rgba(239,68,68,0.12); color: #f87171; }

.res-drawer-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  border-radius: 10px;
  background: rgba(255,255,255,0.03);
  margin-bottom: 6px;
}

.rd-icon { font-size: 20px; }
.rd-info { flex: 1; display: flex; flex-direction: column; }
.rd-name { font-size: 13px; color: #cbd5e1; }
.rd-detail { font-size: 10px; color: #64748b; }
.rd-val { font-size: 14px; font-weight: 600; color: #e2e8f0; }

.da-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  border-radius: 10px;
  background: rgba(255,255,255,0.03);
  margin-bottom: 8px;
}

.da-name { width: 60px; font-size: 12px; color: #cbd5e1; }

.da-bar-area {
  flex: 1;
  height: 6px;
  background: rgba(255,255,255,0.06);
  border-radius: 3px;
  overflow: hidden;
}

.da-bar {
  height: 100%;
  background: linear-gradient(90deg, #ef4444, #f59e0b);
  border-radius: 3px;
}

.da-val { width: 80px; font-size: 12px; color: #94a3b8; text-align: right; }

.drawer-enter-active, .drawer-leave-active { transition: opacity 0.2s ease; }
.drawer-enter-from, .drawer-leave-to { opacity: 0; }
.drawer-enter-from .drawer-content, .drawer-leave-to .drawer-content { transform: translateX(100%); }

.compact .side-panel {
  /* 紧凑模式作为小屏默认值：压缩面板宽度和间距，避免横纵向溢出。 */
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
.compact .glass-card { padding: 8px; border-radius: 14px; }
.compact .card-title { font-size: 10px; margin-bottom: 6px; }
.compact .card-title-row { margin-bottom: 6px; }
.compact .wg-cell,
.compact .rg-cell { padding: 5px; border-radius: 10px; }
.compact .wg-val,
.compact .rg-val { font-size: 14px; }
.compact .top-bar {
  height: clamp(46px, 7vh, 52px);
  flex-basis: clamp(46px, 7vh, 52px);
  padding: 0 clamp(8px, 1.2vw, 16px);
  gap: 8px;
}
.compact .bottom-bar {
  height: clamp(50px, 7.5vh, 64px);
  flex-basis: clamp(50px, 7.5vh, 64px);
  padding: 0 clamp(8px, 1.2vw, 16px);
}
.compact .capsule { padding: 6px 10px; }
.compact .cap-val { font-size: 18px; }
.compact .cap-val-sm { font-size: 13px; }
.compact .tl-btn { width: 32px; height: 32px; font-size: 14px; }
.compact .tl-slider-track { padding-top: 16px; }
.compact .alert-stream { height: clamp(66px, 12vh, 92px); }
.compact .fire-list-item { padding: 5px 7px; }
.compact .fli-header,
.compact .fli-meta { margin-bottom: 2px; }
.compact .video-thumb:nth-child(3) {
  /* 小屏中隐藏第三个视频预览，把空间留给主要监控内容；全部监控仍可通过抽屉查看。 */
  display: none;
}

@media (max-width: 1366px) {
  .monitor-container {
    font-size: 12px;
  }

  .side-panel {
    width: clamp(200px, 18vw, 260px);
    flex-basis: clamp(200px, 18vw, 260px);
    padding: 6px;
    gap: 6px;
  }

  .glass-card {
    padding: 8px;
    border-radius: 14px;
  }

  .card-title {
    font-size: 10px;
    margin-bottom: 6px;
  }

  .top-bar {
    height: clamp(46px, 7vh, 52px);
    flex-basis: clamp(46px, 7vh, 52px);
    padding: 0 12px;
    gap: 8px;
  }

  .bottom-bar {
    height: clamp(50px, 7.5vh, 64px);
    flex-basis: clamp(50px, 7.5vh, 64px);
    padding: 0 12px;
  }

  .capsule {
    padding: 6px 10px;
  }

  .cap-val {
    font-size: 18px;
  }

  .cap-val-sm {
    font-size: 13px;
  }

  .video-thumb:nth-child(3) {
    display: none;
  }
}

@media (max-width: 1100px) {
  .side-panel.right {
    /* <=1100px 时右栏默认由脚本折叠，同时 CSS 限制其占宽。 */
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

  .top-right .ut-text {
    display: none;
  }

  .tl-summary {
    font-size: 10px;
  }
}

@media (max-width: 800px) {
  .main-content {
    /* 极窄 PC/小窗口下垂直排列，所有区块宽度 100%，无横向滚动。 */
    flex-direction: column;
  }

  .side-panel,
  .compact .side-panel,
  .side-panel.right,
  .side-panel.right:not(.collapsed) {
    position: relative;
    width: 100%;
    flex: 0 0 clamp(96px, 22vh, 140px);
    max-width: 100%;
  }

  .side-panel.collapsed,
  .compact .side-panel.collapsed {
    flex-basis: clamp(42px, 7vh, 52px);
    width: 100%;
  }

  .center-area {
    flex: 1 1 auto;
    margin: 0 6px;
  }

  .top-bar {
    justify-content: flex-start;
  }

  .capsule {
    flex: 1 1 0;
    min-width: 0;
  }

  .cap-label {
    display: none;
  }

  .bottom-bar {
    gap: 8px;
  }

  .tl-summary {
    display: none;
  }
}

@media (max-height: 700px) {
  .top-bar {
    height: 46px;
    flex-basis: 46px;
  }

  .bottom-bar {
    height: 50px;
    flex-basis: 50px;
  }

  .side-panel {
    padding: 5px;
    gap: 5px;
  }

  .glass-card {
    padding: 6px;
  }

  .weather-alert,
  .detail-link,
  .tl-marks {
    /* 低高度时隐藏次要提示/刻度，保证核心面板无滚动完整可见。 */
    display: none;
  }

  .alert-stream {
    height: 62px;
  }

  .video-thumb .vt-info {
    padding: 3px 5px;
  }

  .drawer-header {
    padding: 10px 12px;
  }
}
</style>
