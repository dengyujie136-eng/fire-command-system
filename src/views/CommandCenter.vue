<template>
  <div class="command-container" :class="{ compact: compactMode }" @keydown="handleKeydown" tabindex="0">
    <div class="top-bar">
      <div class="capsule capsule-fires" @click="showFiresDetail = true">
        <span class="cap-icon">🔥</span>
        <div class="cap-data">
          <span class="cap-val">3</span>
          <span class="cap-unit">起火点</span>
        </div>
        <span class="cap-pulse"></span>
      </div>
      <div class="capsule capsule-uav" @click="showUavDetail = true">
        <span class="cap-icon">🛸</span>
        <div class="cap-data">
          <span class="cap-val">8</span>
          <span class="cap-unit">架在线</span>
        </div>
        <span class="cap-sub">2 架执行任务</span>
      </div>
      <div class="capsule capsule-resource">
        <span class="cap-icon">📦</span>
        <div class="cap-data">
          <span class="cap-val">12</span>
          <span class="cap-unit">个</span>
        </div>
        <span class="cap-sub">资源点</span>
      </div>
      <div class="capsule capsule-personnel">
        <span class="cap-icon">👥</span>
        <div class="cap-data">
          <span class="cap-val">320</span>
          <span class="cap-unit">人</span>
        </div>
        <span class="cap-sub">已部署 280 人</span>
      </div>
      <div class="capsule capsule-env">
        <span class="cap-icon">☀️</span>
        <div class="cap-data">
          <span class="cap-val">26℃</span>
          <span class="cap-unit">晴</span>
        </div>
        <span class="cap-sub">湿度 45%</span>
      </div>
      <div class="top-right">
        <span v-if="hasNewAlert" class="alert-dot" title="新告警">⚠️</span>
        <div class="update-tag">
          <span class="ut-text">数据更新：{{ lastUpdate }}</span>
          <button class="ut-refresh" @click="refreshData" title="刷新数据">↻</button>
        </div>
      </div>
    </div>

    <div class="main-content">
      <div class="side-panel left" :class="{ collapsed: leftCollapsed }">
        <button class="collapse-btn" @click="leftCollapsed = !leftCollapsed" :title="leftCollapsed ? '展开面板' : '收起面板'">
          <span class="arrow">{{ leftCollapsed ? '→' : '←' }}</span>
        </button>

        <template v-if="!leftCollapsed">
          <div class="glass-card">
            <div class="card-title">关键指标</div>
            <div class="kpi-grid">
              <div class="kpi-cell" @click="focusMapArea">
                <span class="kc-icon">📐</span>
                <span class="kc-val">850</span>
                <span class="kc-unit">公顷</span>
                <span class="kc-label">控制面积</span>
                <div class="kc-bar"><div class="kc-fill" style="width: 72%"></div></div>
              </div>
              <div class="kpi-cell">
                <span class="kc-icon">👤</span>
                <span class="kc-val">320</span>
                <span class="kc-unit">人</span>
                <span class="kc-label">投入人员</span>
                <span class="kc-trend up">↑ 8%</span>
              </div>
              <div class="kpi-cell">
                <span class="kc-icon">🚒</span>
                <span class="kc-val">45</span>
                <span class="kc-unit">辆</span>
                <span class="kc-label">调度车辆</span>
                <span class="kc-trend stable">→</span>
              </div>
              <div class="kpi-cell">
                <span class="kc-icon">🏃</span>
                <span class="kc-val">1,200</span>
                <span class="kc-unit">人</span>
                <span class="kc-label">疏散人数</span>
                <span class="kc-trend up">↑ 5%</span>
              </div>
            </div>
          </div>

          <div class="glass-card">
            <div class="card-title">当前任务调度</div>
            <div class="task-cards">
              <div class="task-card" @click="focusTaskOnMap('火场A')">
                <div class="tc-header">
                  <span class="tc-name">火场A灭火</span>
                  <span class="tc-status running">执行中</span>
                </div>
                <div class="tc-progress">
                  <div class="tc-bar"><div class="tc-fill" style="width: 65%"></div></div>
                  <span class="tc-pct">65%</span>
                </div>
                <div class="tc-actions">
                  <button class="tc-btn" title="暂停">⏸</button>
                  <button class="tc-btn" title="通讯">📞</button>
                  <button class="tc-detail" @click.stop="showTaskDetail = true">查看详情</button>
                </div>
              </div>
              <div class="task-card">
                <div class="tc-header">
                  <span class="tc-name">人员疏散R</span>
                  <span class="tc-status pending">等待中</span>
                </div>
                <div class="tc-info">调度中 · 预计 15 分钟</div>
                <div class="tc-actions">
                  <button class="tc-btn" title="通讯">📞</button>
                  <button class="tc-detail" @click="showTaskDetail = true">查看详情</button>
                </div>
              </div>
            </div>
            <button class="detail-link" @click="showAllTasks = true">全部任务</button>
          </div>

          <div class="glass-card">
            <div class="card-title">快速操作</div>
            <button class="action-btn primary" @click="showCreateTask = true">
              <span>📋</span> 创建调度任务
            </button>
            <div class="action-row">
              <button class="action-btn" @click="emergencyCall">
                <span>🚨</span> 紧急广播
              </button>
              <button class="action-btn" @click="sendCommand">
                <span>📨</span> 发送指令
              </button>
            </div>
          </div>
        </template>

        <template v-else>
          <div class="collapsed-icons">
            <div class="ico-item" title="关键指标" @click="leftCollapsed = false">📊</div>
            <div class="ico-item" title="任务调度" @click="showAllTasks = true">📋</div>
            <div class="ico-item" title="创建任务" @click="showCreateTask = true">➕</div>
          </div>
        </template>
      </div>

      <div class="center-area">
        <div ref="mapRef" class="map-container"></div>
        <div class="map-layer-controls">
          <button class="ml-btn" :class="{ active: mapLayers.fire }" @click="toggleLayer('fire')" title="火情点">
            🔥 火情
          </button>
          <button class="ml-btn" :class="{ active: mapLayers.uav }" @click="toggleLayer('uav')" title="无人机">
            🛸 无人机
          </button>
          <button class="ml-btn" :class="{ active: mapLayers.resource }" @click="toggleLayer('resource')" title="资源点">
            📦 资源
          </button>
          <button class="ml-btn" :class="{ active: mapLayers.personnel }" @click="toggleLayer('personnel')" title="人员">
            👥 人员
          </button>
        </div>
        <div class="map-legend">
          <div class="ml-item"><span class="ml-dot" style="background:#ef4444"></span>火情点</div>
          <div class="ml-item"><span class="ml-dot" style="background:#3b82f6"></span>无人机</div>
          <div class="ml-item"><span class="ml-dot" style="background:#22c55e"></span>资源点</div>
          <div class="ml-item"><span class="ml-dot" style="background:#f59e0b"></span>人员</div>
          <div class="ml-item"><span class="ml-area"></span>控制区域</div>
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
            <transition name="tab-fade" mode="out-in">
              <div v-if="activeTab === 'video'" key="video" class="tab-inner">
                <div class="video-grid">
                  <div class="video-card" v-for="v in videoCameras" :key="v.id" @click="showVideoFull(v)">
                    <div class="vc-preview">
                      <span class="vc-icon">📹</span>
                      <span class="vc-status online">●</span>
                    </div>
                    <div class="vc-info">
                      <span class="vc-name">{{ v.name }}</span>
                      <span class="vc-rate">控制率 {{ v.controlRate }}%</span>
                    </div>
                  </div>
                </div>
                <button class="detail-link" @click="showAllCameras = true">查看全部摄像头</button>
              </div>

              <div v-else-if="activeTab === 'personnel'" key="personnel" class="tab-inner">
                <div class="personnel-list">
                  <div v-for="p in personnelList" :key="p.id" class="personnel-item">
                    <span class="pl-dot" :class="p.status"></span>
                    <div class="pl-info">
                      <span class="pl-name">{{ p.name }}</span>
                      <span class="pl-loc">{{ p.location }}</span>
                    </div>
                    <span class="pl-status" :class="p.status">{{ p.status === 'deployed' ? '已部署' : '待命中' }}</span>
                    <button class="pl-comm" title="通讯">📞</button>
                  </div>
                </div>
                <button class="detail-link" @click="showAllPersonnel = true">查看全部队伍</button>
              </div>

              <div v-else key="env" class="tab-inner">
                <div class="env-grid">
                  <div class="env-cell">
                    <span class="ev-icon">🌡️</span>
                    <span class="ev-val">26℃</span>
                    <span class="ev-label">温度</span>
                  </div>
                  <div class="env-cell">
                    <span class="ev-icon">💧</span>
                    <span class="ev-val">45%</span>
                    <span class="ev-label">湿度</span>
                  </div>
                  <div class="env-cell">
                    <span class="ev-icon">🌫️</span>
                    <span class="ev-val">35</span>
                    <span class="ev-label">PM2.5 μg/m³</span>
                  </div>
                </div>
                <div class="comm-preview">
                  <div class="comm-title">最新通讯</div>
                  <div v-for="c in commRecords" :key="c.id" class="comm-item">
                    <span class="ci-time">{{ c.time }}</span>
                    <span class="ci-msg">{{ c.msg }}</span>
                  </div>
                </div>
                <button class="detail-link" @click="showCommHistory = true">查看全部通讯</button>
              </div>
            </transition>
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

    <div class="bottom-bar">
      <div class="bb-left">
        <button class="bb-btn emergency" @click="emergencyCall">
          <span class="bb-icon">🚨</span> 紧急呼叫
        </button>
        <button class="bb-btn" @click="broadcastNotify">
          <span class="bb-icon">📢</span> 广播通知
        </button>
      </div>
      <div class="bb-center">
        <span class="bb-sync">数据同步：{{ lastUpdate }}</span>
      </div>
      <div class="bb-right">
        <button class="bb-btn compact-toggle" :class="{ active: compactMode }" @click="compactMode = !compactMode" title="紧凑模式">
          <span class="bb-icon">⊞</span> 紧凑
        </button>
        <button class="bb-btn" @click="refreshData">
          <span class="bb-icon">🔄</span> 刷新
        </button>
        <button class="bb-btn" @click="exportReport">
          <span class="bb-icon">📥</span> 导出态势
        </button>
      </div>
    </div>

    <transition name="toast">
      <div v-if="showToast" class="toast-notification">
        <span class="toast-icon">✓</span>
        <span class="toast-text">{{ toastMessage }}</span>
      </div>
    </transition>

    <transition name="drawer">
      <div v-if="showAllTasks" class="drawer-overlay" @click="showAllTasks = false">
        <div class="drawer-content" @click.stop>
          <div class="drawer-header">
            全部任务调度
            <button class="close-drawer" @click="showAllTasks = false">✕</button>
          </div>
          <div class="drawer-body">
            <div v-for="t in allTasks" :key="t.id" class="drawer-task-item">
              <div class="dti-header">
                <span class="dti-name">{{ t.name }}</span>
                <span class="dti-status" :class="t.statusClass">{{ t.status }}</span>
              </div>
              <div v-if="t.progress !== undefined" class="dti-progress">
                <div class="dti-bar"><div class="dti-fill" :style="{ width: t.progress + '%' }"></div></div>
                <span class="dti-pct">{{ t.progress }}%</span>
              </div>
              <div class="dti-meta">
                <span>{{ t.location }}</span>
                <span>{{ t.time }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </transition>

    <transition name="drawer">
      <div v-if="showAllCameras" class="drawer-overlay" @click="showAllCameras = false">
        <div class="drawer-content" @click.stop>
          <div class="drawer-header">
            全部摄像头
            <button class="close-drawer" @click="showAllCameras = false">✕</button>
          </div>
          <div class="drawer-body">
            <div class="camera-grid">
              <div v-for="v in allCameras" :key="v.id" class="camera-card" @click="showVideoFull(v)">
                <div class="cc-preview">
                  <span class="cc-icon">📹</span>
                  <span class="cc-status online">●</span>
                </div>
                <div class="cc-info">
                  <span class="cc-name">{{ v.name }}</span>
                  <span class="cc-rate">控制率 {{ v.controlRate }}%</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </transition>

    <transition name="drawer">
      <div v-if="showCommHistory" class="drawer-overlay" @click="showCommHistory = false">
        <div class="drawer-content" @click.stop>
          <div class="drawer-header">
            通讯记录历史
            <button class="close-drawer" @click="showCommHistory = false">✕</button>
          </div>
          <div class="drawer-body">
            <div v-for="c in commHistory" :key="c.id" class="comm-history-item">
              <span class="chi-time">{{ c.time }}</span>
              <div class="chi-bubble">
                <span class="chi-sender">{{ c.sender }}</span>
                <span class="chi-msg">{{ c.msg }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </transition>

    <transition name="drawer">
      <div v-if="showCreateTask" class="drawer-overlay" @click="showCreateTask = false">
        <div class="drawer-content" @click.stop>
          <div class="drawer-header">
            创建调度任务
            <button class="close-drawer" @click="showCreateTask = false">✕</button>
          </div>
          <div class="drawer-body">
            <div class="form-group">
              <label class="fg-label">任务名称</label>
              <input v-model="newTask.name" class="fg-input" placeholder="请输入任务名称" />
            </div>
            <div class="form-group">
              <label class="fg-label">任务类型</label>
              <select v-model="newTask.type" class="fg-select">
                <option value="fire">灭火</option>
                <option value="evacuate">疏散</option>
                <option value="supply">物资运输</option>
                <option value="rescue">救援</option>
              </select>
            </div>
            <div class="form-group">
              <label class="fg-label">目标位置</label>
              <input v-model="newTask.location" class="fg-input" placeholder="请输入目标位置" />
            </div>
            <div class="form-group">
              <label class="fg-label">优先级</label>
              <select v-model="newTask.priority" class="fg-select">
                <option value="high">高</option>
                <option value="medium">中</option>
                <option value="low">低</option>
              </select>
            </div>
            <button class="fg-submit" @click="submitTask">提交任务</button>
          </div>
        </div>
      </div>
    </transition>

    <transition name="drawer">
      <div v-if="showTaskDetail" class="drawer-overlay" @click="showTaskDetail = false">
        <div class="drawer-content" @click.stop>
          <div class="drawer-header">
            任务详情
            <button class="close-drawer" @click="showTaskDetail = false">✕</button>
          </div>
          <div class="drawer-body">
            <div class="td-section">
              <h4>火场A灭火</h4>
              <p>状态：<span class="td-running">执行中</span></p>
              <p>进度：65%</p>
              <p>位置：北部林区（116.42°E, 39.95°N）</p>
              <p>投入人员：120 人</p>
              <p>调度车辆：18 辆</p>
              <p>预计完成：16:30</p>
            </div>
          </div>
        </div>
      </div>
    </transition>

    <transition name="drawer">
      <div v-if="showFiresDetail" class="drawer-overlay" @click="showFiresDetail = false">
        <div class="drawer-content" @click.stop>
          <div class="drawer-header">
            火情详情
            <button class="close-drawer" @click="showFiresDetail = false">✕</button>
          </div>
          <div class="drawer-body">
            <div v-for="f in firesDetail" :key="f.name" class="da-item">
              <span class="da-name">{{ f.name }}</span>
              <div class="da-bar-area">
                <div class="da-bar" :style="{ width: (f.area / 500 * 100) + '%' }"></div>
              </div>
              <span class="da-val">{{ f.area }} hm²</span>
            </div>
          </div>
        </div>
      </div>
    </transition>

    <transition name="drawer">
      <div v-if="showUavDetail" class="drawer-overlay" @click="showUavDetail = false">
        <div class="drawer-content" @click.stop>
          <div class="drawer-header">
            无人机详情
            <button class="close-drawer" @click="showUavDetail = false">✕</button>
          </div>
          <div class="drawer-body">
            <div v-for="u in uavDetail" :key="u.id" class="da-item">
              <span class="da-name">{{ u.id }}</span>
              <span class="da-status" :class="u.status">{{ u.status === 'active' ? '执行中' : '待命' }}</span>
              <span class="da-val">{{ u.location }}</span>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { fireAPI, commandAPI, dispatchAPI, agentAPI } from '../api/modules'
import { onAlertMessage } from '../services/websocket'
import * as echarts from 'echarts'
import mapboxgl from 'mapbox-gl'

const mapRef = ref<HTMLDivElement>()

const leftCollapsed = ref(false)
const rightCollapsed = ref(false)
const activeTab = ref('video')
const autoCompactMode = ref(false)
const manualCompactMode = ref(false)
/* 自动紧凑与手动紧凑叠加：小屏强制 compact，底部按钮仍可手动切换。 */
const compactMode = computed({
  get: () => autoCompactMode.value || manualCompactMode.value,
  set: (value: boolean) => {
    manualCompactMode.value = value
  }
})
const showToast = ref(false)
const toastMessage = ref('')
const lastUpdate = ref('14:38')
const hasNewAlert = ref(false)

const showAllTasks = ref(false)
const showAllCameras = ref(false)
const showCommHistory = ref(false)
const showCreateTask = ref(false)
const showTaskDetail = ref(false)
const showFiresDetail = ref(false)
const showUavDetail = ref(false)

const mapLayers = reactive({
  fire: true,
  uav: true,
  resource: true,
  personnel: true
})

const newTask = reactive({
  name: '',
  type: 'fire',
  location: '',
  priority: 'high'
})

const tabs = [
  { id: 'video', label: '监控', icon: '📹' },
  { id: 'personnel', label: '部署', icon: '👥' },
  { id: 'env', label: '环境', icon: '🌡️' }
]

const videoCameras = ref([
  { id: 1, name: '摄像头 1', controlRate: 72 },
  { id: 2, name: '摄像头 2', controlRate: 85 }
])

const allCameras = ref([
  { id: 1, name: '摄像头 1', controlRate: 72 },
  { id: 2, name: '摄像头 2', controlRate: 85 },
  { id: 3, name: '摄像头 3', controlRate: 60 },
  { id: 4, name: '摄像头 4', controlRate: 78 }
])

const personnelList = ref([
  { id: 1, name: '消防一队', location: '火场A', status: 'deployed' },
  { id: 2, name: '救援二队', location: '营地', status: 'standby' },
  { id: 3, name: '医疗组', location: '医院', status: 'deployed' },
  { id: 4, name: '抢险三队', location: '火场B', status: 'deployed' },
  { id: 5, name: '后勤保障', location: '基地', status: 'standby' }
])

const commRecords = ref([
  { id: 1, time: '14:30', msg: '指挥部：启动一级响应' },
  { id: 2, time: '14:35', msg: '消防一队：已到达现场' }
])

const commHistory = ref([
  { id: 1, time: '14:30', sender: '指挥部', msg: '启动一级响应' },
  { id: 2, time: '14:35', sender: '消防一队', msg: '已到达现场' },
  { id: 3, time: '14:40', sender: '无人机', msg: '开始侦察' },
  { id: 4, time: '14:42', sender: '医疗组', msg: '已就位' },
  { id: 5, time: '14:45', sender: '指挥部', msg: '注意火势蔓延' }
])

const allTasks = ref([
  { id: 1, name: '火场A灭火', status: '执行中', statusClass: 'running', progress: 65, location: '北部林区', time: '14:00' },
  { id: 2, name: '人员疏散R', status: '等待中', statusClass: 'pending', progress: undefined, location: 'R区', time: '14:15' },
  { id: 3, name: '物资运输C', status: '待执行', statusClass: 'waiting', progress: undefined, location: 'C区', time: '14:20' },
  { id: 4, name: '无人机侦察', status: '已完成', statusClass: 'done', progress: 100, location: '全区域', time: '14:10' }
])

const firesDetail = ref([
  { name: '火场A', area: 480 },
  { name: '火场B', area: 320 },
  { name: '火场C', area: 250 }
])

const uavDetail = ref([
  { id: 'UAV-01', status: 'active', location: '火场A上空' },
  { id: 'UAV-02', status: 'active', location: '火场B上空' },
  { id: 'UAV-03', status: 'standby', location: '基地' },
  { id: 'UAV-04', status: 'standby', location: '基地' },
  { id: 'UAV-05', status: 'standby', location: '基地' },
  { id: 'UAV-06', status: 'standby', location: '基地' },
  { id: 'UAV-07', status: 'standby', location: '基地' },
  { id: 'UAV-08', status: 'standby', location: '基地' }
])

let map: mapboxgl.Map | null = null
let resizeHandler: (() => void) | null = null

function updateResponsiveLayout() {
  const width = window.innerWidth
  const height = window.innerHeight
  /* <=1366px 或 <=700px 自动启用 compact，降低固定设计稿尺寸造成的纵向溢出风险。 */
  autoCompactMode.value = width <= 1366 || height <= 700
  /* <=1100px 默认折叠右侧面板，给地图主区域保留完整宽度。 */
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

function emergencyCall() {
  toast('紧急呼叫已发送')
  hasNewAlert.value = true
  setTimeout(() => { hasNewAlert.value = false }, 5000)
}

function broadcastNotify() {
  toast('广播通知已发送')
}

function sendCommand() {
  toast('指令已发送')
}

function refreshData() {
  lastUpdate.value = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  toast('数据已刷新')
}

function exportReport() {
  toast('态势报告导出中...')
}

function focusMapArea() {
  if (map) {
    map.flyTo({ center: [116.42, 39.95], zoom: 12 })
    toast('地图已聚焦控制区域')
  }
}

function focusTaskOnMap(area: string) {
  if (map) {
    map.flyTo({ center: [116.42, 39.95], zoom: 13 })
    toast(`地图已聚焦${area}`)
  }
}

function showVideoFull(v: any) {
  toast(`${v.name} 视频流加载中...`)
}

function submitTask() {
  if (!newTask.name.trim()) {
    toast('请输入任务名称')
    return
  }
  allTasks.value.unshift({
    id: Date.now(),
    name: newTask.name,
    status: '待执行',
    statusClass: 'waiting',
    progress: undefined,
    location: newTask.location || '未指定',
    time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  })
  showCreateTask.value = false
  newTask.name = ''
  newTask.location = ''
  toast('调度任务已创建')
}

function handleKeydown(e: KeyboardEvent) {
  if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement || e.target instanceof HTMLTextAreaElement) return
  switch (e.key.toLowerCase()) {
    case 'l': leftCollapsed.value = !leftCollapsed.value; break
    case 'r': rightCollapsed.value = !rightCollapsed.value; break
    case 'm': if (map) { map.flyTo({ center: [116.4, 39.9], zoom: 10 }); toast('地图已复位') }; break
    case 'c': showCreateTask.value = true; break
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
}

async function loadData() {
  try {
    const [stat, cmdOverview] = await Promise.all([
      fireAPI.getStat().catch(() => ({})),
      commandAPI.getOverview().catch(() => ({}))
    ])
  } catch (e) {}
}

watch([leftCollapsed, rightCollapsed], () => {
  nextTick(() => {
    setTimeout(() => map?.resize(), 250)
  })
})

onMounted(() => {
  updateResponsiveLayout()
  resizeHandler = updateResponsiveLayout
  window.addEventListener('resize', resizeHandler)
  initMap()
  loadData()
  lastUpdate.value = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  onAlertMessage((data: any) => {
    hasNewAlert.value = true
    commRecords.value.unshift({ id: Date.now(), time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }), msg: data?.message || '新告警' })
    setTimeout(() => { hasNewAlert.value = false }, 8000)
  })
})

onUnmounted(() => {
  if (resizeHandler) window.removeEventListener('resize', resizeHandler)
  map?.remove()
})
</script>

<style scoped>
.command-container {
  /* 使用父级 100% 替代 100vw/100vh，避免视口计算误差产生浏览器主滚动条。 */
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
  /* 顶部栏高度使用 clamp，小高度屏幕自动压缩，释放中间主区高度。 */
  height: clamp(48px, 8vh, 64px);
  flex: 0 0 clamp(48px, 8vh, 64px);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: clamp(6px, 0.9vw, 14px);
  padding: 0 clamp(10px, 1.7vw, 32px);
  background: rgba(20, 28, 40, 0.9);
  border-bottom: 1px solid rgba(255,255,255,0.06);
  backdrop-filter: blur(16px);
}

.capsule {
  display: flex;
  align-items: center;
  /* 胶囊 padding 与字号可压缩，防止顶栏在窄屏横向溢出。 */
  padding: clamp(5px, 0.8vh, 8px) clamp(8px, 0.85vw, 16px);
  border-radius: 40px;
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(255,255,255,0.12);
  backdrop-filter: blur(10px);
  gap: clamp(4px, 0.6vw, 8px);
  cursor: pointer;
  transition: border-color 0.2s;
  position: relative;
}

.capsule:hover { border-color: rgba(255,255,255,0.25); }
.capsule:active { transform: scale(0.97); }

.capsule-fires { border-color: rgba(239,68,68,0.3); background: rgba(239,68,68,0.06); }

.cap-icon { font-size: clamp(13px, 0.9vw, 16px); }
.cap-data { display: flex; align-items: baseline; gap: 3px; }

.cap-val {
  font-size: clamp(16px, 1.15vw, 22px);
  font-weight: 700;
  line-height: 1;
}

.capsule-fires .cap-val {
  background: linear-gradient(90deg, #fff, #fca5a5);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.capsule-uav .cap-val {
  background: linear-gradient(90deg, #fff, #67e8f9);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.capsule-resource .cap-val {
  background: linear-gradient(90deg, #fff, #86efac);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.capsule-personnel .cap-val {
  background: linear-gradient(90deg, #fff, #fde68a);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.capsule-env .cap-val {
  background: linear-gradient(90deg, #fff, #a5b4fc);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.cap-unit { font-size: clamp(10px, 0.7vw, 12px); color: #94a3b8; }
.cap-sub { font-size: clamp(9px, 0.62vw, 10px); color: #64748b; }

.cap-pulse {
  position: absolute;
  top: 6px;
  right: 10px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ef4444;
  animation: pulse 1.5s ease-in-out infinite;
}

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

.update-tag {
  display: flex;
  align-items: center;
  gap: 6px;
}

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
  /* 将固定 320px 改为 clamp，侧栏随视口收缩，防止横向溢出。 */
  width: clamp(200px, 18vw, 320px);
  flex: 0 0 clamp(200px, 18vw, 320px);
  display: flex;
  flex-direction: column;
  position: relative;
  transition: width 0.2s ease, flex-basis 0.2s ease;
  padding: clamp(6px, 1vh, 12px);
  gap: clamp(6px, 0.9vh, 10px);
  overflow: hidden;
  min-height: 0;
}

.side-panel.collapsed {
  /* 折叠宽度同样使用 clamp，避免折叠态按钮撑出布局。 */
  width: clamp(48px, 6vw, 60px);
  flex-basis: clamp(48px, 6vw, 60px);
  padding: clamp(6px, 1vh, 12px) clamp(5px, 0.6vw, 8px);
}

.collapse-btn {
  position: absolute;
  top: 50%;
  z-index: 10;
  width: 24px;
  height: 48px;
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
  /* 卡片 padding 自适应压缩，避免多卡片在 600px 高度内累积溢出。 */
  padding: clamp(8px, 1.1vh, 14px);
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
  margin-bottom: clamp(6px, 0.9vh, 12px);
  letter-spacing: 0.5px;
}

.kpi-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: clamp(5px, 0.8vh, 10px);
  min-height: 0;
  overflow: hidden;
}

.kpi-cell {
  padding: clamp(5px, 0.8vh, 10px);
  border-radius: 14px;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.04);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  cursor: pointer;
  transition: all 0.2s;
}

.kpi-cell:hover { background: rgba(96,165,250,0.08); border-color: rgba(96,165,250,0.2); }

.kc-icon { font-size: clamp(13px, 1vw, 18px); }
.kc-val { font-size: clamp(14px, 1.05vw, 20px); font-weight: 700; color: #e2e8f0; }
.kc-unit { font-size: 10px; color: #64748b; }
.kc-label { font-size: 10px; color: #94a3b8; margin-top: 2px; }

.kc-bar {
  width: 80%;
  height: 3px;
  background: rgba(255,255,255,0.08);
  border-radius: 2px;
  overflow: hidden;
  margin-top: 4px;
}

.kc-fill {
  height: 100%;
  background: linear-gradient(90deg, #22c55e, #3b82f6);
  border-radius: 2px;
}

.kc-trend { font-size: 10px; font-weight: 600; }
.kc-trend.up { color: #ef4444; }
.kc-trend.stable { color: #94a3b8; }

.task-cards {
  display: flex;
  flex-direction: column;
  gap: clamp(5px, 0.8vh, 10px);
  margin-bottom: clamp(4px, 0.7vh, 8px);
  min-height: 0;
  overflow: hidden;
}

.task-card {
  padding: clamp(5px, 0.8vh, 10px);
  border-radius: 14px;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06);
  cursor: pointer;
  transition: all 0.2s;
}

.task-card:hover { border-color: rgba(96,165,250,0.2); background: rgba(96,165,250,0.05); }

.tc-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: clamp(3px, 0.6vh, 6px);
}

.tc-name { font-size: clamp(10px, 0.72vw, 13px); font-weight: 500; }

.tc-status {
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 20px;
  font-weight: 600;
}

.tc-status.running { background: rgba(245,158,11,0.15); color: #fbbf24; }
.tc-status.pending { background: rgba(148,163,184,0.15); color: #94a3b8; }

.tc-progress {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: clamp(4px, 0.7vh, 8px);
}

.tc-bar {
  flex: 1;
  height: 4px;
  background: rgba(255,255,255,0.08);
  border-radius: 2px;
  overflow: hidden;
}

.tc-fill {
  height: 100%;
  background: linear-gradient(90deg, #f59e0b, #ef4444);
  border-radius: 2px;
}

.tc-pct { font-size: 11px; color: #94a3b8; font-weight: 600; }

.tc-info { font-size: clamp(9px, 0.62vw, 11px); color: #64748b; margin-bottom: clamp(4px, 0.7vh, 8px); }

.tc-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.tc-btn {
  width: 28px;
  height: 28px;
  border-radius: 8px;
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

.tc-btn:hover { background: rgba(96,165,250,0.15); color: #e2e8f0; }

.tc-detail {
  margin-left: auto;
  border: none;
  background: none;
  color: #60a5fa;
  font-size: 11px;
  cursor: pointer;
}

.tc-detail:hover { text-decoration: underline; }

.action-btn {
  width: 100%;
  padding: clamp(6px, 0.9vh, 10px);
  border-radius: 14px;
  border: 1px solid rgba(255,255,255,0.1);
  background: rgba(255,255,255,0.06);
  color: #cbd5e1;
  font-size: clamp(10px, 0.72vw, 13px);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: all 0.2s;
  margin-bottom: clamp(4px, 0.7vh, 8px);
}

.action-btn:hover { background: rgba(96,165,250,0.15); color: #e2e8f0; }
.action-btn:active { transform: scale(0.97); }

.action-btn.primary {
  background: linear-gradient(90deg, rgba(59,130,246,0.2), rgba(99,102,241,0.2));
  border-color: rgba(96,165,250,0.3);
  font-weight: 600;
}

.action-row {
  display: flex;
  gap: 8px;
}

.action-row .action-btn {
  flex: 1;
  margin-bottom: 0;
  font-size: 12px;
}

.detail-link {
  border: none;
  background: none;
  color: #60a5fa;
  font-size: clamp(10px, 0.7vw, 12px);
  cursor: pointer;
  padding: 4px 0;
  text-align: left;
  width: 100%;
}

.detail-link:hover { text-decoration: underline; }

.collapsed-icons {
  display: flex;
  flex-direction: column;
  gap: clamp(8px, 1.6vh, 16px);
  align-items: center;
  padding-top: clamp(12px, 3vh, 24px);
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
  position: relative;
  margin: clamp(6px, 1vh, 12px) 0;
  border-radius: 20px;
  overflow: hidden;
  border: 1px solid rgba(255,255,255,0.08);
  min-width: 0;
  min-height: 0;
}

.map-container {
  width: 100%;
  height: 100%;
}

.map-layer-controls {
  position: absolute;
  /* 地图控件使用 clamp 偏移，避免绝对定位元素在小屏贴边溢出。 */
  top: clamp(8px, 2vw, 16px);
  left: clamp(8px, 2vw, 16px);
  display: flex;
  flex-direction: column;
  gap: 4px;
  z-index: 10;
}

.ml-btn {
  padding: clamp(5px, 0.8vh, 8px) clamp(8px, 0.8vw, 14px);
  border-radius: 10px;
  border: 1px solid rgba(255,255,255,0.1);
  background: rgba(20,28,40,0.85);
  color: #94a3b8;
  font-size: clamp(10px, 0.65vw, 11px);
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
  padding: clamp(7px, 1vh, 10px) clamp(9px, 0.8vw, 14px);
  border-radius: 12px;
  background: rgba(20,28,40,0.85);
  border: 1px solid rgba(255,255,255,0.08);
  backdrop-filter: blur(8px);
  z-index: 10;
  font-size: 11px;
  color: #94a3b8;
}

.ml-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.ml-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.ml-area {
  width: 12px;
  height: 8px;
  border-radius: 2px;
  background: rgba(34,197,94,0.3);
  border: 1px solid rgba(34,197,94,0.5);
}

.tabs {
  display: flex;
  gap: 4px;
  background: rgba(255,255,255,0.04);
  padding: 4px;
  border-radius: 12px;
  margin-bottom: clamp(5px, 0.9vh, 10px);
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
  min-height: 0;
  background: rgba(20,28,40,0.7);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 20px;
  padding: clamp(8px, 1.1vh, 14px);
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
  gap: clamp(5px, 0.9vh, 10px);
}

.video-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: clamp(5px, 0.8vh, 10px);
  min-height: 0;
  overflow: hidden;
}

.video-card {
  border-radius: 14px;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06);
  overflow: hidden;
  cursor: pointer;
  transition: all 0.2s;
}

.video-card:hover { border-color: rgba(96,165,250,0.2); }

.vc-preview {
  height: clamp(58px, 13vh, 100px);
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0,0,0,0.2);
  position: relative;
}

.vc-icon { font-size: 28px; opacity: 0.6; }

.vc-status {
  position: absolute;
  top: 6px;
  right: 6px;
  font-size: 8px;
}

.vc-status.online { color: #34d399; }

.vc-info {
  padding: clamp(4px, 0.7vh, 8px);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.vc-name { font-size: 11px; color: #cbd5e1; }
.vc-rate { font-size: 10px; color: #64748b; }

.personnel-list {
  display: flex;
  flex-direction: column;
  gap: clamp(4px, 0.7vh, 6px);
  margin-bottom: clamp(4px, 0.7vh, 6px);
  min-height: 0;
  overflow: hidden;
}

.personnel-item {
  display: flex;
  align-items: center;
  gap: clamp(5px, 0.55vw, 8px);
  padding: clamp(5px, 0.8vh, 8px) clamp(6px, 0.6vw, 10px);
  border-radius: 10px;
  background: rgba(255,255,255,0.03);
  transition: all 0.2s;
}

.personnel-item:hover { background: rgba(96,165,250,0.05); }

.pl-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.pl-dot.deployed { background: #34d399; }
.pl-dot.standby { background: #64748b; }

.pl-info {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.pl-name { font-size: 12px; color: #cbd5e1; }
.pl-loc { font-size: 10px; color: #64748b; }

.pl-status {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 10px;
}

.pl-status.deployed { background: rgba(52,211,153,0.12); color: #34d399; }
.pl-status.standby { background: rgba(100,116,139,0.12); color: #94a3b8; }

.pl-comm {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  border: 1px solid rgba(255,255,255,0.08);
  background: rgba(255,255,255,0.04);
  color: #94a3b8;
  cursor: pointer;
  font-size: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.pl-comm:hover { background: rgba(96,165,250,0.15); color: #e2e8f0; }

.env-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: clamp(4px, 0.7vh, 8px);
}

.env-cell {
  padding: clamp(5px, 0.8vh, 10px);
  border-radius: 12px;
  background: rgba(255,255,255,0.03);
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.ev-icon { font-size: clamp(12px, 0.9vw, 16px); }
.ev-val { font-size: clamp(12px, 0.9vw, 16px); font-weight: 700; color: #e2e8f0; }
.ev-label { font-size: 9px; color: #64748b; }

.comm-preview {
  margin-top: clamp(2px, 0.5vh, 4px);
  min-height: 0;
  overflow: hidden;
}

.comm-title {
  font-size: 11px;
  color: #64748b;
  margin-bottom: 6px;
}

.comm-item {
  display: flex;
  gap: clamp(4px, 0.6vw, 8px);
  padding: clamp(4px, 0.7vh, 6px) clamp(5px, 0.6vw, 8px);
  border-radius: 8px;
  background: rgba(255,255,255,0.03);
  margin-bottom: 4px;
  font-size: 11px;
}

.ci-time { color: #64748b; white-space: nowrap; flex-shrink: 0; }
.ci-msg { color: #94a3b8; }

.bottom-bar {
  /* 底部栏使用 clamp，小高度屏幕压缩到 48px，避免主内容被挤出。 */
  height: clamp(48px, 7vh, 60px);
  flex: 0 0 clamp(48px, 7vh, 60px);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 clamp(10px, 1.7vw, 32px);
  background: rgba(20, 28, 40, 0.9);
  border-top: 1px solid rgba(255,255,255,0.06);
  backdrop-filter: blur(16px);
}

.bb-left, .bb-center, .bb-right { display: flex; align-items: center; gap: clamp(6px, 0.8vw, 12px); min-width: 0; }

.bb-btn {
  padding: clamp(6px, 0.9vh, 8px) clamp(9px, 0.85vw, 16px);
  border-radius: 10px;
  border: 1px solid rgba(255,255,255,0.1);
  background: rgba(255,255,255,0.06);
  color: #cbd5e1;
  font-size: clamp(10px, 0.7vw, 12px);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: all 0.2s;
  backdrop-filter: blur(6px);
}

.bb-btn:hover { background: rgba(96,165,250,0.15); color: #e2e8f0; }
.bb-btn:active { transform: scale(0.96); }

.bb-btn.emergency {
  background: rgba(239,68,68,0.15);
  border-color: rgba(239,68,68,0.3);
  color: #f87171;
}

.bb-btn.emergency:hover { background: rgba(239,68,68,0.25); }

.bb-btn.compact-toggle.active { background: rgba(96,165,250,0.2); border-color: rgba(96,165,250,0.4); color: #60a5fa; }

.bb-icon { font-size: 12px; }

.bb-sync { font-size: 11px; color: #64748b; }

.toast-notification {
  position: fixed;
  top: clamp(56px, 9vh, 80px);
  right: clamp(12px, 1.7vw, 32px);
  display: flex;
  align-items: center;
  gap: 10px;
  padding: clamp(8px, 1vh, 12px) clamp(12px, 1vw, 20px);
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

.tab-fade-enter-active { transition: opacity 0.15s ease; }
.tab-fade-leave-active { transition: opacity 0.1s ease; }
.tab-fade-enter-from, .tab-fade-leave-to { opacity: 0; }

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

.close-drawer:hover { background: rgba(239,68,68,0.15); color: #f87171; }

.drawer-body {
  flex: 1;
  padding: clamp(8px, 1.2vh, 16px);
  /* 抽屉不再使用 overflow-y:auto，内容通过紧凑间距与隐藏次要信息适配视口。 */
  overflow: hidden;
  min-height: 0;
}

.drawer-task-item {
  padding: clamp(6px, 0.9vh, 10px);
  border-radius: 10px;
  background: rgba(255,255,255,0.03);
  margin-bottom: clamp(4px, 0.7vh, 8px);
}

.dti-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.dti-name { font-size: 13px; font-weight: 500; }

.dti-status {
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 20px;
  font-weight: 600;
}

.dti-status.running { background: rgba(245,158,11,0.15); color: #fbbf24; }
.dti-status.pending { background: rgba(148,163,184,0.15); color: #94a3b8; }
.dti-status.waiting { background: rgba(100,116,139,0.12); color: #94a3b8; }
.dti-status.done { background: rgba(34,197,94,0.12); color: #4ade80; }

.dti-progress {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.dti-bar {
  flex: 1;
  height: 4px;
  background: rgba(255,255,255,0.08);
  border-radius: 2px;
  overflow: hidden;
}

.dti-fill {
  height: 100%;
  background: linear-gradient(90deg, #f59e0b, #ef4444);
  border-radius: 2px;
}

.dti-pct { font-size: 11px; color: #94a3b8; }

.dti-meta {
  display: flex;
  gap: 12px;
  font-size: 10px;
  color: #64748b;
}

.camera-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: clamp(5px, 0.8vh, 10px);
  min-height: 0;
  overflow: hidden;
}

.camera-card {
  border-radius: 14px;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06);
  overflow: hidden;
  cursor: pointer;
  transition: all 0.2s;
}

.camera-card:hover { border-color: rgba(96,165,250,0.2); }

.cc-preview {
  height: clamp(56px, 12vh, 80px);
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0,0,0,0.2);
  position: relative;
}

.cc-icon { font-size: 24px; opacity: 0.6; }

.cc-status {
  position: absolute;
  top: 4px;
  right: 4px;
  font-size: 8px;
}

.cc-status.online { color: #34d399; }

.cc-info {
  padding: 6px;
  display: flex;
  flex-direction: column;
}

.cc-name { font-size: 11px; color: #cbd5e1; }
.cc-rate { font-size: 10px; color: #64748b; }

.comm-history-item {
  display: flex;
  gap: clamp(5px, 0.6vw, 10px);
  padding: clamp(5px, 0.8vh, 8px);
  margin-bottom: clamp(4px, 0.7vh, 8px);
}

.chi-time {
  font-size: 11px;
  color: #64748b;
  white-space: nowrap;
  padding-top: 2px;
}

.chi-bubble {
  flex: 1;
  padding: 8px 12px;
  border-radius: 12px;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.06);
}

.chi-sender {
  display: block;
  font-size: 10px;
  color: #60a5fa;
  margin-bottom: 2px;
}

.chi-msg { font-size: 12px; color: #cbd5e1; }

.form-group {
  margin-bottom: clamp(8px, 1.1vh, 14px);
}

.fg-label {
  display: block;
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 6px;
}

.fg-input, .fg-select {
  width: 100%;
  padding: clamp(7px, 1vh, 10px) clamp(8px, 0.8vw, 12px);
  border-radius: 10px;
  border: 1px solid rgba(255,255,255,0.1);
  background: rgba(255,255,255,0.06);
  color: #e2e8f0;
  font-size: 13px;
  outline: none;
  transition: border-color 0.2s;
}

.fg-input:focus, .fg-select:focus { border-color: rgba(96,165,250,0.5); }

.fg-select option { background: #1a2332; color: #e2e8f0; }

.fg-submit {
  width: 100%;
  padding: clamp(8px, 1vh, 12px);
  border-radius: 12px;
  border: none;
  background: linear-gradient(90deg, #3b82f6, #6366f1);
  color: white;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s;
  margin-top: 8px;
}

.fg-submit:hover { transform: scale(0.98); }
.fg-submit:active { transform: scale(0.95); }

.td-section {
  line-height: 1.45;
}

.td-section h4 {
  font-size: clamp(13px, 0.9vw, 16px);
  font-weight: 600;
  color: #e2e8f0;
  margin-bottom: clamp(6px, 1vh, 12px);
}

.td-section p {
  font-size: 13px;
  color: #94a3b8;
}

.td-running { color: #fbbf24; font-weight: 600; }

.da-item {
  display: flex;
  align-items: center;
  gap: clamp(5px, 0.55vw, 10px);
  padding: clamp(6px, 0.9vh, 10px);
  border-radius: 10px;
  background: rgba(255,255,255,0.03);
  margin-bottom: clamp(4px, 0.7vh, 8px);
}

.da-name { width: clamp(48px, 4vw, 60px); font-size: clamp(10px, 0.7vw, 12px); color: #cbd5e1; }

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

.da-val { width: clamp(60px, 5.2vw, 80px); font-size: clamp(10px, 0.7vw, 12px); color: #94a3b8; text-align: right; }

.da-status {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 10px;
}

.da-status.active { background: rgba(52,211,153,0.12); color: #34d399; }
.da-status.standby { background: rgba(100,116,139,0.12); color: #94a3b8; }

.drawer-enter-active, .drawer-leave-active { transition: opacity 0.2s ease; }
.drawer-enter-from, .drawer-leave-to { opacity: 0; }
.drawer-enter-from .drawer-content, .drawer-leave-to .drawer-content { transform: translateX(100%); }

/* 紧凑模式：面板/卡片/标题按规范压缩，确保侧栏内容无需内部滚动。 */
.compact .side-panel {
  width: clamp(190px, 17vw, 260px);
  flex-basis: clamp(190px, 17vw, 260px);
  padding: 6px;
  gap: 6px;
}

.compact .side-panel.collapsed {
  width: clamp(44px, 5vw, 52px);
  flex-basis: clamp(44px, 5vw, 52px);
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

.compact .kpi-cell,
.compact .task-card,
.compact .personnel-item,
.compact .env-cell,
.compact .drawer-task-item,
.compact .da-item {
  padding: 5px 7px;
}

.compact .kc-val,
.compact .cap-val {
  font-size: clamp(15px, 1vw, 18px);
}

.compact .top-bar {
  height: clamp(44px, 6.5vh, 52px);
  flex-basis: clamp(44px, 6.5vh, 52px);
  padding: 0 clamp(6px, 0.8vw, 12px);
  gap: clamp(4px, 0.6vw, 8px);
}

.compact .bottom-bar {
  height: 48px;
  flex-basis: 48px;
  padding: 0 clamp(6px, 0.8vw, 12px);
}

.compact .capsule {
  padding: 5px 8px;
}

.compact .cap-sub,
.compact .tc-info,
.compact .kc-trend,
.compact .detail-link,
.compact .vc-rate,
.compact .pl-loc,
.compact .comm-title,
.compact .ci-msg,
.compact .dti-meta {
  display: none;
}

.compact .vc-preview {
  height: clamp(50px, 11vh, 70px);
}

/* <=1366px 自动套用 compact 同款尺寸，小屏无需点击紧凑按钮也不会溢出。 */
@media (max-width: 1366px) {
  .top-bar {
    height: clamp(44px, 6.5vh, 52px);
    flex-basis: clamp(44px, 6.5vh, 52px);
    padding: 0 clamp(6px, 0.8vw, 12px);
    gap: clamp(4px, 0.6vw, 8px);
  }

  .bottom-bar {
    height: 48px;
    flex-basis: 48px;
    padding: 0 clamp(6px, 0.8vw, 12px);
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

  .kpi-cell,
  .task-card,
  .personnel-item,
  .env-cell,
  .drawer-task-item,
  .da-item {
    padding: 5px 7px;
  }

  .cap-sub,
  .tc-info,
  .kc-trend,
  .detail-link,
  .vc-rate,
  .pl-loc,
  .comm-title,
  .ci-msg,
  .dti-meta {
    display: none;
  }

  .vc-preview {
    height: clamp(50px, 11vh, 70px);
  }
}

/* <=1100px 右侧面板默认让位，展开时作为浮层覆盖地图，不增加布局总宽度。 */
@media (max-width: 1100px) {
  .capsule-env,
  .top-right,
  .tab-text,
  .bb-center {
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
    bottom: 48px;
    z-index: 30;
    width: min(260px, 34vw);
    flex-basis: min(260px, 34vw);
    background: rgba(7, 14, 28, 0.94);
  }

  .bb-btn {
    padding: 6px 9px;
  }
}

/* <=800px 改为纵向堆叠，侧栏宽度 100%，彻底避免横向挤压。 */
@media (max-width: 800px) {
  .top-bar {
    flex-wrap: wrap;
    align-content: center;
  }

  .capsule {
    flex: 1 1 0;
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
    flex: 0 0 clamp(90px, 20vh, 136px);
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
    margin: 0;
    min-height: 0;
  }

  .bottom-bar {
    gap: 6px;
  }

  .bb-left,
  .bb-right {
    flex: 1 1 0;
  }

  .bb-btn span:not(.bb-icon),
  .bb-btn:not(.compact-toggle):nth-child(n + 3),
  .map-legend .ml-item:nth-child(n + 4),
  .video-card:nth-child(n + 2),
  .personnel-item:nth-child(n + 4),
  .comm-item:nth-child(n + 2) {
    display: none;
  }
}

/* <=700px 高度进一步压缩顶/底栏和次要文本，保证 600px 高度无内部滚动。 */
@media (max-height: 700px) {
  .top-bar {
    height: 44px;
    flex-basis: 44px;
  }

  .bottom-bar {
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

  .kpi-cell,
  .task-card,
  .personnel-item,
  .env-cell,
  .drawer-task-item,
  .da-item {
    padding: 5px 7px;
  }

  .task-cards,
  .video-grid,
  .personnel-list,
  .tab-inner {
    gap: 4px;
  }

  .cap-sub,
  .tc-info,
  .kc-trend,
  .detail-link,
  .vc-rate,
  .pl-loc,
  .comm-title,
  .ci-msg,
  .dti-meta,
  .bb-sync {
    display: none;
  }

  .vc-preview,
  .cc-preview {
    height: clamp(44px, 10vh, 64px);
  }

  .drawer-body {
    padding: 6px;
  }
}
</style>
