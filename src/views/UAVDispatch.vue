<template>
  <div class="uav-container" :class="{ compact: compactMode }" @keydown="handleKeydown" tabindex="0">
    <!-- 顶部状态条 -->
    <div class="top-bar">
      <div class="capsule capsule-left">
        <span class="cap-big">{{ uavStats.online }}</span>
        <span class="cap-unit">在线</span>
        <span class="cap-sub">执行 {{ uavStats.mission }} / 待命 {{ uavStats.standby }}</span>
      </div>
      <div class="capsule capsule-center">
        <span class="cap-big">8</span>
        <span class="cap-unit">km²</span>
        <span class="cap-trend">↑</span>
      </div>
      <div class="capsule capsule-alert" :class="{ pulsing: hasActiveAlert }" @click="showAlertDrawer = true">
        <span class="alert-dot"></span>
        <span class="cap-alert-text">{{ topAlert }}</span>
      </div>
    </div>

    <!-- 主内容区 -->
    <div class="main-content">
      <!-- 左侧面板 -->
      <div class="side-panel left" :class="{ collapsed: leftCollapsed }">
        <button class="collapse-btn" @click="leftCollapsed = !leftCollapsed" :title="leftCollapsed ? '展开面板' : '收起面板'">
          <span class="arrow">{{ leftCollapsed ? '→' : '←' }}</span>
        </button>

        <template v-if="!leftCollapsed">
          <!-- 卡片A - 进行中的任务 -->
          <div class="glass-card">
            <div class="card-title">进行中的任务</div>
            <div class="task-list">
              <div v-for="task in missionList" :key="task.id" class="task-item">
                <div class="task-row">
                  <span class="task-name">{{ task.name }}</span>
                  <div class="task-actions">
                    <button class="icon-btn" :title="task.status === 'running' ? '暂停' : '继续'" @click="toggleTask(task)">
                      {{ task.status === 'running' ? '⏸' : '▶' }}
                    </button>
                    <button class="icon-btn" title="详情" @click="openTaskDetail(task)">📋</button>
                  </div>
                </div>
                <div class="task-progress-row">
                  <div class="task-progress-bar">
                    <div class="task-progress-fill" :style="{ width: task.progress + '%' }"></div>
                  </div>
                  <span class="task-percent">{{ task.progress }}%</span>
                </div>
                <div class="task-meta">
                  <span :class="task.status">{{ task.status === 'running' ? '执行中' : '等待' }}</span>
                  <span v-if="task.status === 'running'">预计 {{ task.eta }}min 完成</span>
                  <span v-else>{{ task.startTime }} 启动</span>
                </div>
              </div>
            </div>
            <button class="new-task-btn" @click="showNewTaskForm = true">+ 新建任务</button>
          </div>

          <!-- 卡片B - 无人机列表 -->
          <div class="glass-card">
            <div class="card-title">无人机列表</div>
            <div class="uav-list">
              <div 
                v-for="uav in topUavs" 
                :key="uav.id" 
                class="uav-item"
                :class="{ selected: selectedUav?.id === uav.id, warning: uav.battery <= 20 }"
                @click="selectUav(uav)"
              >
                <div class="uav-row">
                  <span class="uav-name">{{ uav.name }}</span>
                  <span class="uav-battery" :class="batteryClass(uav.battery)">
                    {{ uav.battery }}%
                  </span>
                </div>
                <div class="uav-commands">
                  <button class="cmd-btn" title="返航" @click.stop="sendCmd('return', uav)">🏠</button>
                  <button class="cmd-btn" title="悬停" @click.stop="sendCmd('hover', uav)">⏸</button>
                  <button class="cmd-btn" title="拍照" @click.stop="sendCmd('photo', uav)">📷</button>
                  <button class="cmd-btn" title="降落" @click.stop="sendCmd('land', uav)">⬇️</button>
                </div>
              </div>
            </div>
            <button class="more-link" @click="showUavDrawer = true">查看全部无人机</button>
          </div>

          <!-- 卡片C - 状态分布 -->
          <div class="glass-card">
            <div class="card-title">状态分布</div>
            <div class="status-ring">
              <svg viewBox="0 0 100 100" class="ring-svg">
                <circle cx="50" cy="50" r="40" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="10"/>
                <circle cx="50" cy="50" r="40" fill="none" stroke="#22c55e" stroke-width="10" stroke-linecap="round"
                  :stroke-dasharray="`${statusDist.mission * 2.51} 251`" stroke-dashoffset="0"/>
                <circle cx="50" cy="50" r="40" fill="none" stroke="#3b82f6" stroke-width="10" stroke-linecap="round"
                  :stroke-dasharray="`${statusDist.standby * 2.51} 251`" :stroke-dashoffset="`${-statusDist.mission * 2.51}`"/>
                <circle cx="50" cy="50" r="40" fill="none" stroke="#64748b" stroke-width="10" stroke-linecap="round"
                  :stroke-dasharray="`${statusDist.offline * 2.51} 251`" :stroke-dashoffset="`${-(statusDist.mission + statusDist.standby) * 2.51}`"/>
              </svg>
              <div class="ring-center">
                <span class="ring-total">{{ uavStats.online }}</span>
                <span class="ring-label">在线</span>
              </div>
            </div>
            <div class="status-legend">
              <div class="legend-item" @click="highlightStatus('mission')">
                <span class="legend-dot green"></span>
                <span class="legend-text">执行中 {{ statusDist.mission }}</span>
              </div>
              <div class="legend-item" @click="highlightStatus('standby')">
                <span class="legend-dot blue"></span>
                <span class="legend-text">待命 {{ statusDist.standby }}</span>
              </div>
              <div class="legend-item" @click="highlightStatus('offline')">
                <span class="legend-dot gray"></span>
                <span class="legend-text">离线 {{ statusDist.offline }}</span>
              </div>
            </div>
          </div>
        </template>

        <template v-else>
          <div class="collapsed-icons">
            <div class="ico-item" title="任务控制">📋</div>
            <div class="ico-item" title="无人机列表" @click="showUavDrawer = true">✈️</div>
            <div class="ico-item" title="状态分布">📊</div>
          </div>
        </template>
      </div>

      <!-- 中央主区域 -->
      <div class="center-area">
        <div ref="mapRef" class="map-container"></div>
        
        <!-- 地图悬浮控件 -->
        <div class="map-controls-left">
          <button class="map-ctrl-btn" :class="{ active: showTracks }" @click="showTracks = !showTracks" title="显示轨迹">轨迹</button>
          <button class="map-ctrl-btn" :class="{ active: showCoverageArea }" @click="showCoverageArea = !showCoverageArea" title="显示覆盖范围">覆盖</button>
          <button class="map-ctrl-btn" @click="focusAllUavs" title="聚焦所有无人机">聚焦</button>
        </div>
        <div class="map-controls-right">
          <button class="map-ctrl-btn" @click="zoomIn" title="放大">+</button>
          <button class="map-ctrl-btn" @click="zoomOut" title="缩小">−</button>
          <button class="map-ctrl-btn" @click="resetView" title="重置视图">⌂</button>
        </div>

        <!-- 可拖拽视频悬浮窗 -->
        <div 
          v-if="showVideo"
          class="video-window"
          :style="{ left: videoPos.x + 'px', top: videoPos.y + 'px' }"
          @mousedown="startDrag"
        >
          <div class="video-header">
            <div class="video-select" @click.stop="showVideoSelect = !showVideoSelect">
              {{ selectedUav ? selectedUav.name : 'UAV-01' }} 视角 ▾
            </div>
            <div class="video-header-btns">
              <button class="vid-btn" title="截图" @click.stop="screenshot">📷</button>
              <button class="vid-btn" title="录制" @click.stop="toggleRecord">⏺</button>
              <button class="vid-btn" title="全屏" @click.stop="toggleFullscreen">⛶</button>
              <button class="vid-btn" title="关闭" @click.stop="showVideo = false">✕</button>
            </div>
          </div>
          <div class="video-body">
            <div class="video-placeholder">
              <span class="video-icon">📹</span>
              <span class="video-text">实时视频流</span>
            </div>
          </div>
          <transition name="fade">
            <div v-if="showVideoSelect" class="video-dropdown">
              <div 
                v-for="uav in topUavs" 
                :key="uav.id" 
                class="video-option"
                @click.stop="selectVideoUav(uav)"
              >
                {{ uav.name }}
              </div>
            </div>
          </transition>
        </div>
      </div>

      <!-- 右侧面板 -->
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
            <!-- 概览标签页 -->
            <div v-if="activeTab === 'overview'" class="tab-inner">
              <div class="overview-section">
                <div class="overview-label">飞行轨迹</div>
                <div class="overview-thumb trajectory" @click="showTracks = true; focusAllUavs()">
                  <div class="thumb-visual trajectory-visual"></div>
                </div>
              </div>
              <div class="overview-section">
                <div class="overview-label">覆盖范围</div>
                <div class="overview-thumb coverage">
                  <div class="thumb-visual coverage-visual"></div>
                </div>
              </div>
              <div class="env-data">
                <div class="env-item">
                  <span class="env-icon">🌡️</span>
                  <span class="env-value">24°C</span>
                </div>
                <div class="env-item">
                  <span class="env-icon">☀️</span>
                  <span class="env-value">晴</span>
                </div>
                <div class="env-item">
                  <span class="env-icon">🌬️</span>
                  <span class="env-value">3.2 m/s</span>
                </div>
              </div>
            </div>

            <!-- 时间轴与甘特图标签页 -->
            <div v-if="activeTab === 'timeline'" class="tab-inner">
              <div class="timeline-slider">
                <div class="timeline-track">
                  <div class="timeline-range" style="left: 0%; width: 100%;">
                    <div class="timeline-now" :style="{ left: timelineNow + '%' }"></div>
                  </div>
                </div>
                <div class="timeline-labels">
                  <span>09:00</span>
                  <span>10:00</span>
                  <span>11:00</span>
                  <span>12:00</span>
                </div>
              </div>
              <div class="gantt-chart">
                <div v-for="task in ganttTasks" :key="task.id" class="gantt-row">
                  <span class="gantt-label">{{ task.name }}</span>
                  <div class="gantt-bar-area">
                    <div 
                      class="gantt-bar" 
                      :style="{ left: task.start + '%', width: task.width + '%', background: task.color }"
                    ></div>
                  </div>
                </div>
              </div>
              <button class="more-link" @click="showGanttDrawer = true">编辑计划</button>
            </div>

            <!-- 告警与日志标签页 -->
            <div v-if="activeTab === 'alerts'" class="tab-inner">
              <div class="alert-list">
                <div v-for="alert in activeAlerts" :key="alert.id" class="alert-card" :class="alert.level">
                  <div class="alert-row">
                    <span class="alert-icon">{{ alert.level === 'critical' ? '🔴' : '🟡' }}</span>
                    <span class="alert-msg">{{ alert.msg }}</span>
                  </div>
                  <div class="alert-actions">
                    <button class="alert-btn" @click="ackAlert(alert)">确认</button>
                    <button class="alert-btn" @click="dismissAlert(alert)">忽略</button>
                  </div>
                </div>
              </div>
              <div class="alert-history">
                <div class="history-title">历史告警</div>
                <div v-for="h in alertHistory" :key="h.id" class="history-item">
                  <span class="history-msg">{{ h.msg }}</span>
                  <span class="history-time">{{ h.time }}</span>
                </div>
              </div>
              <button class="more-link" @click="showAlertDrawer = true">查看全部告警</button>
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
              @click="activeTab = tab.id"
            >
              {{ tab.icon }}
            </div>
          </div>
        </template>
      </div>
    </div>

    <!-- 新建任务悬浮表单 -->
    <transition name="fade">
      <div v-if="showNewTaskForm" class="modal-overlay" @click="showNewTaskForm = false">
        <div class="modal-content" @click.stop>
          <div class="modal-header">
            新建任务
            <button class="close-btn" @click="showNewTaskForm = false">✕</button>
          </div>
          <div class="modal-body">
            <div class="form-group">
              <label>任务名称</label>
              <input type="text" v-model="newTask.name" placeholder="输入任务名称" class="form-input" />
            </div>
            <div class="form-group">
              <label>任务类型</label>
              <select v-model="newTask.type" class="form-input">
                <option value="scout">侦察</option>
                <option value="monitor">监测</option>
                <option value="support">灭火辅助</option>
              </select>
            </div>
            <div class="form-group">
              <label>预计时长 (min)</label>
              <input type="number" v-model="newTask.duration" class="form-input" />
            </div>
            <button class="submit-btn" @click="createTask">创建任务</button>
          </div>
        </div>
      </div>
    </transition>

    <!-- 全部无人机抽屉 -->
    <transition name="drawer">
      <div v-if="showUavDrawer" class="drawer-overlay" @click="showUavDrawer = false">
        <div class="drawer-content" @click.stop>
          <div class="drawer-header">
            全部无人机
            <button class="close-drawer" @click="showUavDrawer = false">✕</button>
          </div>
          <div class="drawer-body">
            <input type="text" v-model="uavSearch" placeholder="搜索无人机..." class="search-input" />
            <div v-for="uav in filteredUavs" :key="uav.id" class="drawer-uav-item" @click="selectUav(uav); showUavDrawer = false">
              <span class="duav-icon">{{ uav.status === 'offline' ? '⚫' : uav.status === 'mission' ? '🟢' : '🔵' }}</span>
              <div class="duav-info">
                <span class="duav-name">{{ uav.name }}</span>
                <span class="duav-status">{{ uavStatusText(uav.status) }} · 电量 {{ uav.battery }}%</span>
              </div>
              <span class="duav-battery" :class="batteryClass(uav.battery)">{{ uav.battery }}%</span>
            </div>
          </div>
        </div>
      </div>
    </transition>

    <!-- 告警详情抽屉 -->
    <transition name="drawer">
      <div v-if="showAlertDrawer" class="drawer-overlay" @click="showAlertDrawer = false">
        <div class="drawer-content" @click.stop>
          <div class="drawer-header">
            告警详情
            <button class="close-drawer" @click="showAlertDrawer = false">✕</button>
          </div>
          <div class="drawer-body">
            <div v-for="alert in allAlerts" :key="alert.id" class="drawer-alert-item" :class="alert.level">
              <span class="da-icon">{{ alert.level === 'critical' ? '🔴' : '🟡' }}</span>
              <div class="da-info">
                <span class="da-msg">{{ alert.msg }}</span>
                <span class="da-time">{{ alert.time }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </transition>

    <!-- 甘特图编辑抽屉 -->
    <transition name="drawer">
      <div v-if="showGanttDrawer" class="drawer-overlay" @click="showGanttDrawer = false">
        <div class="drawer-content" @click.stop>
          <div class="drawer-header">
            任务计划编辑
            <button class="close-drawer" @click="showGanttDrawer = false">✕</button>
          </div>
          <div class="drawer-body">
            <div v-for="task in missionList" :key="task.id" class="gantt-edit-item">
              <span class="ge-name">{{ task.name }}</span>
              <div class="ge-row">
                <label>开始时间</label>
                <input type="time" :value="task.startTime" class="form-input small" />
              </div>
              <div class="ge-row">
                <label>持续时长</label>
                <input type="number" :value="task.duration" class="form-input small" />
                <span class="ge-unit">min</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, nextTick, onMounted, onUnmounted } from 'vue'
import { fireAPI, uavAPI } from '../api/modules'
import mapboxgl from 'mapbox-gl'

const mapRef = ref<HTMLDivElement>()

const leftCollapsed = ref(false)
const rightCollapsed = ref(false)
const autoCompactMode = ref(false)
const manualCompactMode = ref(false)
/* 自动紧凑与手动紧凑叠加：小屏强制 compact，键盘 C 保留人工切换能力。 */
const compactMode = computed(() => autoCompactMode.value || manualCompactMode.value)
const activeTab = ref('overview')
const showVideo = ref(true)
const showTracks = ref(true)
const showCoverageArea = ref(true)
const showVideoSelect = ref(false)
const showNewTaskForm = ref(false)
const showUavDrawer = ref(false)
const showAlertDrawer = ref(false)
const showGanttDrawer = ref(false)
const uavSearch = ref('')
const selectedUav = ref<any>(null)
const isRecording = ref(false)
const isDragging = ref(false)
const dragOffset = reactive({ x: 0, y: 0 })
const videoPos = reactive({ x: 0, y: 0 })
const timelineNow = ref(35)

const uavStats = reactive({ online: 12, mission: 8, standby: 4 })
const statusDist = reactive({ mission: 8, standby: 4, offline: 2 })

const topAlert = ref('UAV-03 电量低')
const hasActiveAlert = ref(true)

const uavList = ref<any[]>([
  { id: 'UAV-01', name: '侦察机 1', status: 'mission', battery: 85, lat: 39.91, lng: 116.40 },
  { id: 'UAV-02', name: '监测机 2', status: 'mission', battery: 45, lat: 39.92, lng: 116.42 },
  { id: 'UAV-03', name: '灭火机 3', status: 'mission', battery: 18, lat: 39.90, lng: 116.38 },
  { id: 'UAV-05', name: '侦察机 5', status: 'online', battery: 72, lat: 39.89, lng: 116.39 },
  { id: 'UAV-06', name: '运输机 6', status: 'online', battery: 90, lat: 39.93, lng: 116.41 },
  { id: 'UAV-07', name: '通信机 7', status: 'mission', battery: 32, lat: 39.88, lng: 116.37 },
  { id: 'UAV-08', name: '侦察机 8', status: 'online', battery: 65, lat: 39.94, lng: 116.43 },
  { id: 'UAV-09', name: '监测机 9', status: 'offline', battery: 0, lat: 39.87, lng: 116.36 },
  { id: 'UAV-10', name: '灭火机 10', status: 'mission', battery: 55, lat: 39.95, lng: 116.44 }
])

const topUavs = computed(() => uavList.value.slice(0, 4))
const filteredUavs = computed(() => {
  if (!uavSearch.value) return uavList.value
  return uavList.value.filter((u: any) => u.name.includes(uavSearch.value) || u.id.includes(uavSearch.value))
})

const missionList = ref([
  { id: 1, name: '侦察任务 A', status: 'running', progress: 65, duration: 30, eta: 18, startTime: '09:00', coverage: 5.2 },
  { id: 2, name: '监测任务 B', status: 'pending', progress: 0, duration: 45, eta: 0, startTime: '10:30', coverage: 8.0 }
])

const newTask = reactive({ name: '', type: 'scout', duration: 30 })

const tabs = [
  { id: 'overview', label: '概览', icon: '🗺️' },
  { id: 'timeline', label: '时间轴', icon: '⏱️' },
  { id: 'alerts', label: '告警', icon: '🔔' }
]

const ganttTasks = [
  { id: 1, name: '侦察A', start: 0, width: 50, color: '#22c55e' },
  { id: 2, name: '监测B', start: 30, width: 40, color: '#3b82f6' }
]

const activeAlerts = ref([
  { id: 1, level: 'critical', msg: 'UAV-03 电量低于 20%', time: '10:15' },
  { id: 2, level: 'warning', msg: 'UAV-07 信号弱', time: '10:12' }
])

const alertHistory = ref([
  { id: 3, msg: 'UAV-02 温度过高（已恢复）', time: '09:45' },
  { id: 4, msg: 'UAV-04 离线', time: '09:30' },
  { id: 5, msg: 'UAV-01 GPS信号丢失（已恢复）', time: '09:15' }
])

const allAlerts = computed(() => [...activeAlerts.value, ...alertHistory.value])

let map: mapboxgl.Map | null = null
let resizeHandler: (() => void) | null = null

function clampVideoPosition() {
  const centerArea = document.querySelector('.center-area') as HTMLElement | null
  if (!centerArea) return
  const videoWidth = Math.min(320, Math.max(220, centerArea.clientWidth * 0.34))
  const videoHeight = videoWidth * 0.66 + 40
  videoPos.x = Math.max(8, Math.min(videoPos.x, centerArea.clientWidth - videoWidth - 8))
  videoPos.y = Math.max(8, Math.min(videoPos.y, centerArea.clientHeight - videoHeight - 8))
}

function updateResponsiveLayout() {
  const width = window.innerWidth
  const height = window.innerHeight
  /* <=1366px 或 <=700px 自动启用紧凑尺寸，减少固定 px 造成的纵向溢出。 */
  autoCompactMode.value = width <= 1366 || height <= 700
  /* <=1100px 默认折叠右侧面板，给地图和视频窗保留可视宽度。 */
  if (width <= 1100) rightCollapsed.value = true
  nextTick(() => {
    map?.resize()
    clampVideoPosition()
  })
}

function uavStatusText(status: string) {
  return status === 'online' ? '待命' : status === 'mission' ? '执行中' : '离线'
}

function batteryClass(level: number) {
  if (level > 50) return 'good'
  if (level > 20) return 'warn'
  return 'critical'
}

function selectUav(uav: any) {
  selectedUav.value = uav
  if (map) map.flyTo({ center: [uav.lng, uav.lat], zoom: 13 })
  activeTab.value = 'overview'
}

function sendCmd(cmd: string, uav: any) {
  uavAPI.control({ uav_id: uav.id, command: cmd }).catch(() => {
    console.log('Command sent (mock):', cmd, 'to', uav.name)
  })
}

function toggleTask(task: any) {
  task.status = task.status === 'running' ? 'paused' : 'running'
}

function openTaskDetail(task: any) {
  showGanttDrawer.value = true
}

function createTask() {
  if (!newTask.name) return
  missionList.value.push({
    id: Date.now(),
    name: newTask.name,
    status: 'pending',
    progress: 0,
    duration: newTask.duration,
    eta: 0,
    startTime: '--:--',
    coverage: 0
  })
  showNewTaskForm.value = false
  newTask.name = ''
  newTask.type = 'scout'
  newTask.duration = 30
}

function highlightStatus(status: string) {
  console.log('Highlight status:', status)
}

function ackAlert(alert: any) {
  activeAlerts.value = activeAlerts.value.filter((a: any) => a.id !== alert.id)
}

function dismissAlert(alert: any) {
  activeAlerts.value = activeAlerts.value.filter((a: any) => a.id !== alert.id)
}

function selectVideoUav(uav: any) {
  selectedUav.value = uav
  showVideoSelect.value = false
}

function screenshot() { console.log('Screenshot') }
function toggleRecord() { isRecording.value = !isRecording.value }
function toggleFullscreen() { console.log('Toggle video fullscreen') }

function zoomIn() { if (map) map.zoomIn() }
function zoomOut() { if (map) map.zoomOut() }
function resetView() { if (map) map.flyTo({ center: [116.4, 39.9], zoom: 11 }) }
function focusAllUavs() { resetView() }

function startDrag(e: MouseEvent) {
  isDragging.value = true
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  dragOffset.x = e.clientX - rect.left
  dragOffset.y = e.clientY - rect.top
  const onMouseMove = (ev: MouseEvent) => {
    if (!isDragging.value) return
    videoPos.x = ev.clientX - dragOffset.x
    videoPos.y = ev.clientY - dragOffset.y
    clampVideoPosition()
  }
  const onMouseUp = () => {
    isDragging.value = false
    document.removeEventListener('mousemove', onMouseMove)
    document.removeEventListener('mouseup', onMouseUp)
  }
  document.addEventListener('mousemove', onMouseMove)
  document.addEventListener('mouseup', onMouseUp)
}

function handleKeydown(e: KeyboardEvent) {
  if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement) return
  switch (e.key.toLowerCase()) {
    case 'l': leftCollapsed.value = !leftCollapsed.value; break
    case 'r': rightCollapsed.value = !rightCollapsed.value; break
    case 'c': manualCompactMode.value = !manualCompactMode.value; break
    case 'f': focusAllUavs(); break
    case 'v': showVideo.value = !showVideo.value; break
  }
}

async function loadData() {
  try {
    const uavs = await uavAPI.getList().catch(() => [])
    if (uavs.length) uavList.value = uavs
    uavStats.online = uavList.value.filter((u: any) => u.status !== 'offline').length
    uavStats.mission = uavList.value.filter((u: any) => u.status === 'mission').length
    uavStats.standby = uavList.value.filter((u: any) => u.status === 'online').length
    statusDist.mission = uavStats.mission
    statusDist.standby = uavStats.standby
    statusDist.offline = uavList.value.length - uavStats.online
  } catch (e) {
    console.error('Failed to load data:', e)
  }
}

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
}

onMounted(() => {
  updateResponsiveLayout()
  initMap()
  loadData()
  const centerArea = document.querySelector('.center-area')
  if (centerArea) {
    videoPos.x = centerArea.clientWidth - 340
    videoPos.y = centerArea.clientHeight - 290
  }
  clampVideoPosition()
  resizeHandler = updateResponsiveLayout
  window.addEventListener('resize', resizeHandler)
})

onUnmounted(() => {
  if (resizeHandler) window.removeEventListener('resize', resizeHandler)
  map?.remove()
})
</script>

<style scoped>
.uav-container {
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

.capsule-left {
  gap: clamp(3px, 0.65vh, 8px);
  min-width: 0;
  width: clamp(150px, 16vw, 200px);
  flex-direction: column;
  align-items: flex-start;
  padding: clamp(6px, 0.8vh, 10px) clamp(8px, 1vw, 20px);
}

.capsule-center {
  gap: 6px;
  min-width: 0;
  width: clamp(96px, 10vw, 120px);
  justify-content: center;
}

.capsule-alert {
  gap: 10px;
  min-width: 0;
  width: clamp(150px, 17vw, 200px);
  justify-content: center;
  cursor: pointer;
  border-color: rgba(239,68,68,0.3);
  background: rgba(239,68,68,0.08);
}

.capsule-alert.pulsing {
  animation: alertPulse 2s ease-in-out infinite;
}

@keyframes alertPulse {
  0%, 100% { border-color: rgba(239,68,68,0.3); }
  50% { border-color: rgba(239,68,68,0.7); }
}

.cap-big {
  font-size: clamp(18px, 1.45vw, 28px);
  font-weight: 700;
  background: linear-gradient(90deg, #fff, #67e8f9);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  line-height: 1;
}

.cap-unit { font-size: clamp(10px, 0.7vw, 13px); color: #94a3b8; }
.cap-sub { font-size: clamp(9px, 0.6vw, 11px); color: #64748b; }
.cap-trend { color: #22c55e; font-size: clamp(11px, 0.75vw, 14px); font-weight: bold; }

.alert-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #ef4444;
  animation: dotBlink 1.5s ease-in-out infinite;
}

@keyframes dotBlink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.cap-alert-text { font-size: clamp(10px, 0.7vw, 13px); color: #fca5a5; }

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

.collapse-btn:hover { color: #e2e8f0; background: rgba(30,40,55,0.95); }
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

/* 任务列表 */
.task-list {
  display: flex;
  flex-direction: column;
  gap: clamp(4px, 0.75vh, 10px);
  margin-bottom: clamp(4px, 0.8vh, 12px);
  min-height: 0;
  overflow: hidden;
}

.task-item {
  padding: clamp(6px, 0.9vh, 10px);
  background: rgba(255,255,255,0.03);
  border-radius: 12px;
}

.task-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: clamp(4px, 0.7vh, 8px);
}

.task-name { font-size: clamp(10px, 0.7vw, 13px); font-weight: 500; }

.task-actions {
  display: flex;
  gap: 4px;
}

.icon-btn {
  width: clamp(24px, 3.6vh, 28px);
  height: clamp(24px, 3.6vh, 28px);
  border-radius: 8px;
  border: none;
  background: rgba(255,255,255,0.06);
  cursor: pointer;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.icon-btn:hover { background: rgba(96,165,250,0.2); transform: scale(0.96); }

.task-progress-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.task-progress-bar {
  flex: 1;
  height: 4px;
  background: rgba(255,255,255,0.1);
  border-radius: 2px;
  overflow: hidden;
}

.task-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6, #22c55e);
  border-radius: 2px;
  transition: width 0.3s ease;
}

.task-percent { font-size: 12px; font-weight: 600; color: #60a5fa; }

.task-meta {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: #64748b;
}

.task-meta.running { color: #22c55e; }
.task-meta.pending { color: #64748b; }

.new-task-btn {
  width: 100%;
  padding: clamp(6px, 0.9vh, 10px);
  border-radius: 12px;
  border: 1px dashed rgba(96,165,250,0.3);
  background: rgba(96,165,250,0.06);
  color: #60a5fa;
  font-size: clamp(10px, 0.7vw, 13px);
  cursor: pointer;
  transition: all 0.2s ease;
}

.new-task-btn:hover { background: rgba(96,165,250,0.15); border-color: rgba(96,165,250,0.5); }

/* 无人机列表 */
.uav-list {
  display: flex;
  flex-direction: column;
  gap: clamp(4px, 0.7vh, 8px);
  margin-bottom: clamp(4px, 0.8vh, 12px);
  min-height: 0;
  overflow: hidden;
}

.uav-item {
  padding: clamp(6px, 0.9vh, 10px);
  background: rgba(255,255,255,0.03);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
  border: 1px solid transparent;
}

.uav-item:hover { background: rgba(96,165,250,0.08); }
.uav-item.selected { border-color: rgba(96,165,250,0.4); background: rgba(96,165,250,0.1); }
.uav-item.warning { border-color: rgba(239,68,68,0.3); }

.uav-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: clamp(4px, 0.7vh, 8px);
}

.uav-name { font-size: clamp(10px, 0.7vw, 13px); font-weight: 500; }

.uav-battery {
  font-size: 12px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
}

.uav-battery.good { color: #22c55e; background: rgba(34,197,94,0.1); }
.uav-battery.warn { color: #f59e0b; background: rgba(245,158,11,0.1); }
.uav-battery.critical { color: #ef4444; background: rgba(239,68,68,0.1); }

.uav-commands {
  display: flex;
  gap: 6px;
}

.cmd-btn {
  width: clamp(26px, 4vh, 32px);
  height: clamp(26px, 4vh, 32px);
  border-radius: 10px;
  border: 1px solid rgba(255,255,255,0.06);
  background: rgba(255,255,255,0.04);
  cursor: pointer;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.cmd-btn:hover { background: rgba(96,165,250,0.15); transform: scale(0.96); }

/* 状态分布 */
.status-ring {
  position: relative;
  width: clamp(62px, 10vh, 100px);
  height: clamp(62px, 10vh, 100px);
  margin: 0 auto clamp(6px, 1vh, 12px);
}

.ring-svg { width: 100%; height: 100%; transform: rotate(-90deg); }

.ring-center {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
}

.ring-total {
  display: block;
  font-size: 20px;
  font-weight: 700;
  background: linear-gradient(90deg, #fff, #67e8f9);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.ring-label { font-size: 10px; color: #64748b; }

.status-legend {
  display: flex;
  justify-content: center;
  gap: clamp(6px, 0.85vw, 16px);
  flex-wrap: wrap;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  transition: opacity 0.2s;
}

.legend-item:hover { opacity: 0.8; }

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.legend-dot.green { background: #22c55e; }
.legend-dot.blue { background: #3b82f6; }
.legend-dot.gray { background: #64748b; }
.legend-text { font-size: 11px; color: #94a3b8; }

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

.ico-item:hover { background: rgba(96,165,250,0.15); transform: translateY(-2px); }
.ico-item.active { background: rgba(96,165,250,0.2); border: 1px solid rgba(96,165,250,0.3); }

/* 中央区域 */
.center-area {
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

.map-controls-left {
  position: absolute;
  top: clamp(8px, 2vw, 16px);
  left: clamp(8px, 2vw, 16px);
  display: flex;
  flex-direction: column;
  gap: 8px;
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

/* 视频悬浮窗 */
.video-window {
  position: absolute;
  /* 视频窗随地图区域收缩，并由脚本钳制在中心区域内，防止横纵向溢出。 */
  width: clamp(220px, 34%, 320px);
  border-radius: 16px;
  background: rgba(20,28,40,0.9);
  border: 1px solid rgba(255,255,255,0.1);
  backdrop-filter: blur(12px);
  box-shadow: 0 8px 32px rgba(0,0,0,0.4);
  z-index: 20;
  overflow: hidden;
}

.video-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: clamp(5px, 0.8vh, 8px) clamp(7px, 0.8vw, 12px);
  background: rgba(255,255,255,0.04);
  cursor: move;
  user-select: none;
}

.video-select {
  font-size: 12px;
  font-weight: 500;
  color: #cbd5e1;
  cursor: pointer;
}

.video-header-btns {
  display: flex;
  gap: 4px;
}

.vid-btn {
  width: clamp(20px, 3.2vh, 24px);
  height: clamp(20px, 3.2vh, 24px);
  border-radius: 6px;
  border: none;
  background: rgba(255,255,255,0.06);
  color: #94a3b8;
  cursor: pointer;
  font-size: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.vid-btn:hover { background: rgba(96,165,250,0.2); }

.video-body {
  height: clamp(120px, 24vh, 200px);
  background: rgba(0,0,0,0.3);
}

.video-placeholder {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.video-icon { font-size: clamp(20px, 1.7vw, 32px); }
.video-text { font-size: 12px; color: #64748b; }

.video-dropdown {
  position: absolute;
  top: 36px;
  left: 12px;
  background: rgba(20,28,40,0.95);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 10px;
  padding: 4px;
  min-width: 160px;
  z-index: 30;
}

.video-option {
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 12px;
  cursor: pointer;
  transition: background 0.15s;
}

.video-option:hover { background: rgba(96,165,250,0.15); }

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
  gap: clamp(6px, 1vh, 16px);
}

/* 概览标签页 */
.overview-section {
  display: flex;
  flex-direction: column;
  gap: clamp(4px, 0.7vh, 8px);
}

.overview-label { font-size: 12px; color: #64748b; }

.overview-thumb {
  height: clamp(48px, 12vh, 80px);
  border-radius: 12px;
  background: rgba(255,255,255,0.04);
  overflow: hidden;
  cursor: pointer;
  transition: all 0.2s ease;
}

.overview-thumb:hover { background: rgba(96,165,250,0.08); transform: scale(1.01); }

.thumb-visual {
  width: 100%;
  height: 100%;
  position: relative;
}

.trajectory-visual {
  background: 
    radial-gradient(circle at 30% 40%, rgba(96,165,250,0.3) 0%, transparent 50%),
    radial-gradient(circle at 70% 60%, rgba(96,165,250,0.2) 0%, transparent 40%);
}

.trajectory-visual::after {
  content: '';
  position: absolute;
  top: 30%;
  left: 20%;
  width: 60%;
  height: 40%;
  border: 2px dashed rgba(96,165,250,0.4);
  border-radius: 50%;
}

.coverage-visual {
  background: 
    radial-gradient(circle at 50% 50%, rgba(34,197,94,0.2) 0%, transparent 60%),
    radial-gradient(circle at 40% 45%, rgba(59,130,246,0.15) 0%, transparent 40%),
    radial-gradient(circle at 60% 55%, rgba(59,130,246,0.15) 0%, transparent 40%);
}

.env-data {
  display: flex;
  justify-content: space-around;
  padding: clamp(6px, 1vh, 12px);
  background: rgba(255,255,255,0.03);
  border-radius: 12px;
}

.env-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}

.env-icon { font-size: 16px; }
.env-value { color: #cbd5e1; }

/* 时间轴标签页 */
.timeline-slider {
  margin-bottom: clamp(6px, 1vh, 16px);
}

.timeline-track {
  position: relative;
  height: 6px;
  background: rgba(255,255,255,0.1);
  border-radius: 3px;
  margin-bottom: 8px;
}

.timeline-range {
  position: absolute;
  top: 0;
  height: 100%;
  background: rgba(96,165,250,0.2);
  border-radius: 3px;
}

.timeline-now {
  position: absolute;
  top: -4px;
  width: 3px;
  height: 14px;
  background: #ef4444;
  border-radius: 2px;
}

.timeline-labels {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  color: #64748b;
}

.gantt-chart {
  display: flex;
  flex-direction: column;
  gap: clamp(6px, 1vh, 12px);
}

.gantt-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.gantt-label {
  width: clamp(42px, 3vw, 50px);
  font-size: 11px;
  color: #94a3b8;
}

.gantt-bar-area {
  flex: 1;
  height: clamp(18px, 3vh, 24px);
  background: rgba(255,255,255,0.04);
  border-radius: 6px;
  position: relative;
}

.gantt-bar {
  position: absolute;
  top: 2px;
  height: calc(100% - 4px);
  border-radius: 6px;
  opacity: 0.8;
  transition: opacity 0.2s;
}

.gantt-bar:hover { opacity: 1; }

/* 告警标签页 */
.alert-list {
  display: flex;
  flex-direction: column;
  gap: clamp(5px, 0.8vh, 10px);
  margin-bottom: clamp(6px, 1vh, 16px);
  min-height: 0;
  overflow: hidden;
}

.alert-card {
  padding: clamp(7px, 1vh, 12px);
  border-radius: 12px;
  background: rgba(255,255,255,0.03);
}

.alert-card.critical {
  background: rgba(239,68,68,0.1);
  border: 1px solid rgba(239,68,68,0.2);
}

.alert-card.warning {
  background: rgba(245,158,11,0.08);
  border: 1px solid rgba(245,158,11,0.2);
}

.alert-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: clamp(4px, 0.7vh, 8px);
}

.alert-icon { font-size: 12px; }
.alert-msg { font-size: 12px; flex: 1; }

.alert-actions {
  display: flex;
  gap: 8px;
}

.alert-btn {
  padding: 4px 12px;
  border-radius: 6px;
  border: 1px solid rgba(255,255,255,0.1);
  background: rgba(255,255,255,0.04);
  color: #94a3b8;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.alert-btn:hover { background: rgba(96,165,250,0.15); }

.alert-history {
  border-top: 1px solid rgba(255,255,255,0.06);
  padding-top: clamp(6px, 1vh, 12px);
}

.history-title { font-size: 12px; color: #64748b; margin-bottom: 8px; }

.history-item {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  border-bottom: 1px solid rgba(255,255,255,0.03);
  font-size: 11px;
}

.history-msg { color: #94a3b8; }
.history-time { color: #475569; }

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

/* 模态框 */
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
  width: clamp(300px, 34vw, 400px);
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
}

.modal-body {
  padding: 20px;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 6px;
}

.form-input {
  width: 100%;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid rgba(255,255,255,0.1);
  background: rgba(255,255,255,0.04);
  color: #e2e8f0;
  font-size: 13px;
  outline: none;
  transition: border-color 0.2s;
}

.form-input:focus { border-color: rgba(96,165,250,0.5); }
.form-input.small { width: 80px; }

.submit-btn {
  width: 100%;
  padding: 12px;
  border-radius: 12px;
  border: none;
  background: linear-gradient(90deg, #3b82f6, #6366f1);
  color: white;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s;
}

.submit-btn:hover { transform: scale(0.98); }

/* 抽屉 */
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

.search-input {
  width: 100%;
  padding: clamp(7px, 1vh, 10px) clamp(8px, 0.8vw, 12px);
  border-radius: 10px;
  border: 1px solid rgba(255,255,255,0.1);
  background: rgba(255,255,255,0.04);
  color: #e2e8f0;
  font-size: 13px;
  outline: none;
  margin-bottom: clamp(6px, 1vh, 12px);
}

.search-input:focus { border-color: rgba(96,165,250,0.5); }

.drawer-uav-item {
  display: flex;
  align-items: center;
  gap: clamp(6px, 0.7vw, 12px);
  padding: clamp(7px, 1vh, 12px);
  border-radius: 12px;
  background: rgba(255,255,255,0.03);
  margin-bottom: clamp(4px, 0.8vh, 8px);
  cursor: pointer;
  transition: background 0.15s;
}

.drawer-uav-item:hover { background: rgba(96,165,250,0.1); }

.duav-icon { font-size: 16px; }
.duav-info { flex: 1; }
.duav-name { display: block; font-size: 13px; font-weight: 500; }
.duav-status { display: block; font-size: 11px; color: #64748b; }

.duav-battery {
  font-size: 12px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
}

.duav-battery.good { color: #22c55e; background: rgba(34,197,94,0.1); }
.duav-battery.warn { color: #f59e0b; background: rgba(245,158,11,0.1); }
.duav-battery.critical { color: #ef4444; background: rgba(239,68,68,0.1); }

.drawer-alert-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: clamp(7px, 1vh, 12px);
  border-radius: 12px;
  background: rgba(255,255,255,0.03);
  margin-bottom: clamp(4px, 0.8vh, 8px);
}

.drawer-alert-item.critical { background: rgba(239,68,68,0.08); }
.drawer-alert-item.warning { background: rgba(245,158,11,0.06); }

.da-icon { font-size: 12px; margin-top: 2px; }
.da-info { flex: 1; }
.da-msg { display: block; font-size: 12px; }
.da-time { display: block; font-size: 10px; color: #475569; margin-top: 4px; }

.gantt-edit-item {
  padding: clamp(7px, 1vh, 12px);
  background: rgba(255,255,255,0.03);
  border-radius: 12px;
  margin-bottom: clamp(5px, 0.8vh, 10px);
}

.ge-name { display: block; font-size: 13px; font-weight: 500; margin-bottom: 10px; }

.ge-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.ge-row label { font-size: 12px; color: #64748b; width: 60px; }
.ge-unit { font-size: 11px; color: #64748b; }

/* 动画 */
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

.drawer-enter-active, .drawer-leave-active { transition: all 0.2s ease; }
.drawer-enter-from, .drawer-leave-to { opacity: 0; }
.drawer-enter-from .drawer-content, .drawer-leave-to .drawer-content { transform: translateX(100%); }

.compact .top-bar {
  height: clamp(46px, 7vh, 52px);
  flex-basis: clamp(46px, 7vh, 52px);
  padding: 0 clamp(8px, 1.2vw, 16px);
  gap: 8px;
}

.compact .capsule {
  padding: 6px 10px;
}

.compact .cap-big {
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

.compact .task-item,
.compact .uav-item,
.compact .alert-card {
  padding: 5px 7px;
}

.compact .status-ring {
  width: 62px;
  height: 62px;
}

.compact .video-window {
  width: clamp(220px, 30%, 280px);
}

.compact .video-body {
  height: clamp(100px, 20vh, 150px);
}

.compact .cap-sub,
.compact .video-text {
  /* 小屏隐藏次要说明，避免容器文字溢出。 */
  display: none;
}

@media (max-width: 1366px) {
  .uav-container {
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

  .status-ring {
    width: 62px;
    height: 62px;
  }

  .video-window {
    width: clamp(220px, 30%, 280px);
  }

  .video-body {
    height: clamp(100px, 20vh, 150px);
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
    top: clamp(48px, 8vh, 64px);
    bottom: 0;
    z-index: 30;
    width: min(260px, 32vw);
    flex-basis: min(260px, 32vw);
    background: rgba(10,15,26,0.92);
  }

  .capsule-alert {
    width: clamp(120px, 16vw, 160px);
  }

  .cap-sub,
  .tab-text {
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
    top: auto;
    bottom: auto;
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
  }

  .top-bar {
    justify-content: flex-start;
  }

  .capsule {
    flex: 1 1 0;
    min-width: 0;
    width: auto;
  }

  .capsule-center,
  .cap-unit,
  .cap-sub {
    display: none;
  }

  .video-window {
    width: min(260px, 62vw);
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

  .task-item,
  .uav-item,
  .alert-card,
  .drawer-uav-item,
  .drawer-alert-item,
  .gantt-edit-item {
    padding: 5px 7px;
  }

  .status-ring {
    width: 54px;
    height: 54px;
  }

  .status-legend,
  .more-link,
  .video-text,
  .timeline-labels,
  .alert-history,
  .duav-status,
  .da-time {
    /* 低高度时隐藏次要说明/历史，确保核心信息不需要内部滚动。 */
    display: none;
  }

  .overview-thumb {
    height: 42px;
  }

  .video-body {
    height: 90px;
  }

  .drawer-header {
    padding: 10px 12px;
  }
}
</style>
