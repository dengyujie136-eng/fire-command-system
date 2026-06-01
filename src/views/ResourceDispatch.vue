<template>
  <div class="dispatch-container" :class="{ compact: compactMode }" @keydown="handleKeydown" tabindex="0">
    <div class="top-bar">
      <div class="capsule capsule-env">
        <span class="cap-icon">☀️</span>
        <span class="cap-temp">26℃</span>
        <span class="cap-weather">晴</span>
        <span class="cap-humidity">湿度 45%</span>
      </div>
      <div class="capsule capsule-resource">
        <span class="cap-res-label">资源总量</span>
        <span class="cap-res-val">{{ resourceStats.total }}</span>
        <span class="cap-res-unit">件</span>
        <span class="cap-res-sub">可用 {{ resourceStats.available }} / 运输中 {{ resourceStats.inTransit }}</span>
      </div>
      <div class="capsule capsule-alert" :class="{ pulsing: hasActiveAlert }" @click="showAlertDrawer = true">
        <span class="alert-dot"></span>
        <span class="cap-alert-text">{{ topAlert }}</span>
        <span class="cap-alert-more">▸</span>
      </div>
    </div>

    <div class="main-content">
      <div class="side-panel left" :class="{ collapsed: leftCollapsed }">
        <button class="collapse-btn" @click="leftCollapsed = !leftCollapsed" :title="leftCollapsed ? '展开面板' : '收起面板'">
          <span class="arrow">{{ leftCollapsed ? '→' : '←' }}</span>
        </button>

        <template v-if="!leftCollapsed">
          <div class="glass-card">
            <div class="card-title">资源概览</div>
            <div class="overview-metrics">
              <div class="metric-item">
                <span class="metric-icon">📍</span>
                <div class="metric-info">
                  <span class="metric-val">{{ overviewStats.resourcePoints }}</span>
                  <span class="metric-label">资源点</span>
                </div>
              </div>
              <div class="metric-item">
                <span class="metric-icon">🛤️</span>
                <div class="metric-info">
                  <span class="metric-val">{{ overviewStats.routeLength }}</span>
                  <span class="metric-label">路线 km</span>
                </div>
              </div>
              <div class="metric-item">
                <span class="metric-icon">👷</span>
                <div class="metric-info">
                  <span class="metric-val">{{ overviewStats.personnel }}</span>
                  <span class="metric-label">人员</span>
                </div>
              </div>
            </div>
            <button class="detail-link" @click="focusAllResources">资源点分布</button>
          </div>

          <div class="glass-card">
            <div class="card-title">关键库存</div>
            <div class="inventory-list">
              <div
                v-for="item in topInventory"
                :key="item.name"
                class="inv-item"
                :class="{ warning: item.available / item.total < 0.5 }"
              >
                <div class="inv-row">
                  <span class="inv-name">{{ item.name }}</span>
                  <span class="inv-nums" :class="{ low: item.available / item.total < 0.5 }">
                    {{ item.available }}/{{ item.total }} {{ item.unit }}
                  </span>
                </div>
                <div class="inv-bar">
                  <div class="inv-bar-fill" :style="{ width: (item.available / item.total * 100) + '%' }" :class="item.available / item.total < 0.5 ? 'warn' : 'ok'"></div>
                </div>
              </div>
            </div>
            <button class="detail-link" @click="showInventoryDrawer = true">查看全部库存</button>
          </div>

          <div class="glass-card">
            <div class="card-title">快速调度</div>
            <div class="dispatch-form">
              <div class="form-row">
                <label class="form-label">目标地点</label>
                <input type="text" v-model="dispatchForm.target" placeholder="A区物资补充" class="form-input" ref="targetInputRef" />
              </div>
              <div class="form-row">
                <label class="form-label">数量</label>
                <div class="number-input">
                  <button class="num-btn" @click="dispatchForm.quantity = Math.max(1, dispatchForm.quantity - 10)">−</button>
                  <input type="number" v-model.number="dispatchForm.quantity" class="num-val" min="1" />
                  <button class="num-btn" @click="dispatchForm.quantity += 10">+</button>
                </div>
              </div>
              <div class="form-row">
                <label class="form-label">物资类型</label>
                <select v-model="dispatchForm.type" class="form-input">
                  <option value="hose">消防水管</option>
                  <option value="extinguisher">灭火器</option>
                  <option value="suit">防护服</option>
                </select>
              </div>
              <button class="submit-btn" :class="{ flash: submitFlash }" @click="submitDispatch">
                提交调度
              </button>
              <div v-if="lastDispatchStatus" class="dispatch-status" :class="lastDispatchStatus">
                {{ lastDispatchStatus === 'success' ? '✓ 调度成功' : '✗ 调度失败' }}
              </div>
            </div>
          </div>
        </template>

        <template v-else>
          <div class="collapsed-icons">
            <div class="ico-item" title="资源概览" @click="leftCollapsed = false">📊</div>
            <div class="ico-item" title="库存" @click="showInventoryDrawer = true">📦</div>
            <div class="ico-item" title="调度" @click="leftCollapsed = false; nextTick(() => targetInputRef?.focus())">🚀</div>
          </div>
        </template>
      </div>

      <div class="center-area">
        <div class="map-section">
          <div ref="mapRef" class="map-container"></div>

          <div class="map-controls-left">
            <button class="map-ctrl-btn" :class="{ active: showResourcePoints }" @click="showResourcePoints = !showResourcePoints" title="资源点">资源点</button>
            <button class="map-ctrl-btn" :class="{ active: showRoutes }" @click="showRoutes = !showRoutes" title="路线">路线</button>
            <button class="map-ctrl-btn" :class="{ active: showHeatmap }" @click="showHeatmap = !showHeatmap" title="热力图">热力</button>
          </div>
          <div class="map-controls-right">
            <button class="map-ctrl-btn" @click="zoomIn" title="放大">+</button>
            <button class="map-ctrl-btn" @click="zoomOut" title="缩小">−</button>
            <button class="map-ctrl-btn" @click="resetMapView" title="重置视角">⌂</button>
          </div>
        </div>

        <div class="trend-section">
          <div class="trend-header">
            <span class="trend-title">库存趋势（6h）</span>
          </div>
          <div ref="trendChartRef" class="trend-chart"></div>
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
              <span v-if="tab.id === 'alerts' && hasActiveAlert" class="tab-badge"></span>
            </div>
          </div>

          <div class="tab-content">
            <div v-if="activeTab === 'personnel'" class="tab-inner">
              <div class="personnel-list">
                <div v-for="p in topPersonnel" :key="p.name" class="person-item">
                  <span class="person-dot" :class="p.status === 'deployed' ? 'green' : 'gray'"></span>
                  <div class="person-info">
                    <span class="person-name">{{ p.name }}</span>
                    <span class="person-role">{{ p.role }}</span>
                  </div>
                  <span class="person-status" :class="p.status">{{ p.status === 'deployed' ? '已部署' : '待命' }}</span>
                  <button class="contact-btn" title="联系" @click="contactPerson(p)">📞</button>
                </div>
              </div>
              <button class="detail-link" @click="showPersonnelDrawer = true">查看全部人员</button>
            </div>

            <div v-if="activeTab === 'tasks'" class="tab-inner">
              <div class="task-list">
                <div v-for="task in recentTasks" :key="task.id" class="task-card" :class="task.statusClass">
                  <div class="tc-header">
                    <span class="tc-name">{{ task.name }}</span>
                    <span class="tc-status-badge" :class="task.statusClass">{{ task.statusText }}</span>
                  </div>
                  <div v-if="task.status === 'running'" class="tc-progress">
                    <div class="tc-progress-bar">
                      <div class="tc-progress-fill" :style="{ width: task.progress + '%' }"></div>
                    </div>
                    <span class="tc-percent">{{ task.progress }}%</span>
                  </div>
                  <div v-if="task.suggestion" class="tc-suggest">💡 {{ task.suggestion }}</div>
                  <div v-if="task.status === 'pending'" class="tc-action">
                    <button class="tc-btn" @click="activateTask(task)">可立即调动</button>
                  </div>
                </div>
              </div>
              <button class="detail-link" @click="showHistoryDrawer = true">历史任务</button>
            </div>

            <div v-if="activeTab === 'alerts'" class="tab-inner">
              <div class="alert-list">
                <div v-for="alert in activeAlerts" :key="alert.id" class="alert-card" :class="alert.level">
                  <div class="ac-row">
                    <span class="ac-icon">{{ alert.level === 'critical' ? '🔴' : '🟡' }}</span>
                    <span class="ac-msg">{{ alert.msg }}</span>
                  </div>
                  <button class="ac-btn" @click="handleAlert(alert)">{{ alert.actionText }}</button>
                </div>
              </div>
              <div class="suggest-section">
                <div class="ss-title">调度建议</div>
                <div v-for="s in suggestions" :key="s" class="ss-item">💡 {{ s }}</div>
              </div>
              <button class="detail-link" @click="showSuggestDrawer = true">全部建议</button>
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
              <span v-if="tab.id === 'alerts' && hasActiveAlert" class="ico-badge"></span>
            </div>
          </div>
        </template>
      </div>
    </div>

    <transition name="toast">
      <div v-if="showToast" class="toast-notification">
        <span class="toast-icon">✓</span>
        <span class="toast-text">{{ toastMessage }}</span>
      </div>
    </transition>

    <transition name="drawer">
      <div v-if="showInventoryDrawer" class="drawer-overlay" @click="showInventoryDrawer = false">
        <div class="drawer-content" @click.stop>
          <div class="drawer-header">
            完整库存
            <button class="close-drawer" @click="showInventoryDrawer = false">✕</button>
          </div>
          <div class="drawer-body">
            <input type="text" v-model="inventorySearch" placeholder="搜索物资..." class="search-input" />
            <div class="inv-drawer-list">
              <div v-for="item in filteredInventory" :key="item.name" class="inv-drawer-item">
                <span class="idi-name">{{ item.name }}</span>
                <div class="idi-bar-area">
                  <div class="idi-bar" :style="{ width: (item.available / item.total * 100) + '%' }" :class="item.available / item.total < 0.5 ? 'warn' : 'ok'"></div>
                </div>
                <span class="idi-nums">{{ item.available }}/{{ item.total }} {{ item.unit }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </transition>

    <transition name="drawer">
      <div v-if="showPersonnelDrawer" class="drawer-overlay" @click="showPersonnelDrawer = false">
        <div class="drawer-content" @click.stop>
          <div class="drawer-header">
            全部人员
            <button class="close-drawer" @click="showPersonnelDrawer = false">✕</button>
          </div>
          <div class="drawer-body">
            <div class="filter-row">
              <button
                v-for="f in personnelFilters"
                :key="f.value"
                class="filter-btn"
                :class="{ active: personnelFilter === f.value }"
                @click="personnelFilter = f.value"
              >{{ f.label }}</button>
            </div>
            <div class="personnel-drawer-list">
              <div v-for="p in filteredPersonnel" :key="p.name" class="pd-item">
                <span class="pd-dot" :class="p.status === 'deployed' ? 'green' : 'gray'"></span>
                <div class="pd-info">
                  <span class="pd-name">{{ p.name }}</span>
                  <span class="pd-role">{{ p.role }}</span>
                </div>
                <span class="pd-status" :class="p.status">{{ p.status === 'deployed' ? '已部署' : '待命' }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </transition>

    <transition name="drawer">
      <div v-if="showHistoryDrawer" class="drawer-overlay" @click="showHistoryDrawer = false">
        <div class="drawer-content" @click.stop>
          <div class="drawer-header">
            历史任务
            <button class="close-drawer" @click="showHistoryDrawer = false">✕</button>
          </div>
          <div class="drawer-body">
            <div v-for="task in historyTasks" :key="task.id" class="ht-item">
              <span class="ht-status" :class="task.statusClass">{{ task.statusText }}</span>
              <div class="ht-info">
                <span class="ht-name">{{ task.name }}</span>
                <span class="ht-time">{{ task.time }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </transition>

    <transition name="drawer">
      <div v-if="showSuggestDrawer" class="drawer-overlay" @click="showSuggestDrawer = false">
        <div class="drawer-content" @click.stop>
          <div class="drawer-header">
            AI 调度建议报告
            <button class="close-drawer" @click="showSuggestDrawer = false">✕</button>
          </div>
          <div class="drawer-body">
            <div v-for="s in fullSuggestions" :key="s.title" class="fs-item">
              <div class="fs-title">{{ s.title }}</div>
              <div class="fs-desc">{{ s.desc }}</div>
              <div class="fs-priority" :class="s.priority">优先级：{{ s.priorityLabel }}</div>
            </div>
          </div>
        </div>
      </div>
    </transition>

    <transition name="drawer">
      <div v-if="showAlertDrawer" class="drawer-overlay" @click="showAlertDrawer = false">
        <div class="drawer-content" @click.stop>
          <div class="drawer-header">
            告警详情
            <button class="close-drawer" @click="showAlertDrawer = false">✕</button>
          </div>
          <div class="drawer-body">
            <div v-for="alert in allAlerts" :key="alert.id" class="da-item" :class="alert.level">
              <span class="da-icon">{{ alert.level === 'critical' ? '🔴' : '🟡' }}</span>
              <div class="da-info">
                <span class="da-msg">{{ alert.msg }}</span>
                <span class="da-detail">{{ alert.detail }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { fireAPI, resourceAPI, personnelAPI, dispatchAPI } from '../api/modules'
import * as echarts from 'echarts'
import mapboxgl from 'mapbox-gl'

const mapRef = ref<HTMLDivElement>()
const trendChartRef = ref<HTMLDivElement>()
const targetInputRef = ref<HTMLInputElement>()

const leftCollapsed = ref(false)
const rightCollapsed = ref(false)
const autoCompactMode = ref(false)
const manualCompactMode = ref(false)
/* 自动紧凑与手动紧凑叠加：小屏/低高屏默认压缩尺寸，键盘 C 可手动切换。 */
const compactMode = computed(() => autoCompactMode.value || manualCompactMode.value)
const activeTab = ref('personnel')
const showResourcePoints = ref(true)
const showRoutes = ref(true)
const showHeatmap = ref(false)
const showInventoryDrawer = ref(false)
const showPersonnelDrawer = ref(false)
const showHistoryDrawer = ref(false)
const showSuggestDrawer = ref(false)
const showAlertDrawer = ref(false)
const showToast = ref(false)
const toastMessage = ref('')
const submitFlash = ref(false)
const lastDispatchStatus = ref<'success' | 'error' | null>(null)
const inventorySearch = ref('')
const personnelFilter = ref('all')

const resourceStats = reactive({ total: 1250, available: 980, inTransit: 270 })
const overviewStats = reactive({ resourcePoints: 12, routeLength: 45, personnel: 8 })
const topAlert = ref('防护服库存不足')
const hasActiveAlert = ref(true)

const topInventory = ref([
  { name: '消防水管', total: 500, available: 380, unit: 'm' },
  { name: '灭火器', total: 200, available: 165, unit: '个' },
  { name: '防护服', total: 300, available: 120, unit: '套' }
])

const fullInventory = ref([
  { name: '消防水管', total: 500, available: 380, unit: 'm' },
  { name: '灭火器', total: 200, available: 165, unit: '个' },
  { name: '防护服', total: 300, available: 120, unit: '套' },
  { name: '急救包', total: 150, available: 120, unit: '个' },
  { name: '饮用水', total: 2000, available: 1500, unit: 'L' },
  { name: '对讲机', total: 80, available: 65, unit: '台' },
  { name: '消防斧', total: 60, available: 48, unit: '把' }
])

const filteredInventory = computed(() => {
  if (!inventorySearch.value) return fullInventory.value
  return fullInventory.value.filter(i => i.name.includes(inventorySearch.value))
})

const dispatchForm = reactive({ type: 'suit', target: 'A区物资补充', quantity: 50 })

const tabs = [
  { id: 'personnel', label: '人员', icon: '👷' },
  { id: 'tasks', label: '任务', icon: '📋' },
  { id: 'alerts', label: '告警', icon: '🔔' }
]

const topPersonnel = ref([
  { name: '张三', role: '指挥员', status: 'deployed' },
  { name: '李四', role: '消防员', status: 'deployed' },
  { name: '王五', role: '医疗员', status: 'standby' },
  { name: '赵六', role: '驾驶员', status: 'deployed' }
])

const allPersonnel = ref([
  { name: '张三', role: '指挥员', status: 'deployed' },
  { name: '李四', role: '消防员', status: 'deployed' },
  { name: '王五', role: '医疗员', status: 'standby' },
  { name: '赵六', role: '驾驶员', status: 'deployed' },
  { name: '孙七', role: '消防员', status: 'deployed' },
  { name: '周八', role: '通信员', status: 'standby' },
  { name: '吴九', role: '医疗员', status: 'deployed' },
  { name: '郑十', role: '驾驶员', status: 'standby' }
])

const personnelFilters = [
  { label: '全部', value: 'all' },
  { label: '已部署', value: 'deployed' },
  { label: '待命', value: 'standby' }
]

const filteredPersonnel = computed(() => {
  if (personnelFilter.value === 'all') return allPersonnel.value
  return allPersonnel.value.filter(p => p.status === personnelFilter.value)
})

const recentTasks = ref([
  { id: 1, name: 'A区物资补充', status: 'running', statusClass: 'running', statusText: '执行中', progress: 65, suggestion: '建议优先调拨A区防护装备' },
  { id: 2, name: 'B区人员调配', status: 'done', statusClass: 'done', statusText: '已完成', progress: 100, suggestion: null },
  { id: 3, name: 'C区待命', status: 'pending', statusClass: 'pending', statusText: '等待中', progress: 0, suggestion: null }
])

const historyTasks = ref([
  { id: 10, name: 'D区消防水管运输', status: 'done', statusClass: 'done', statusText: '已完成', time: '09:30' },
  { id: 11, name: 'E区急救包补给', status: 'done', statusClass: 'done', statusText: '已完成', time: '08:45' },
  { id: 12, name: 'F区人员撤离', status: 'done', statusClass: 'done', statusText: '已完成', time: '07:20' }
])

const activeAlerts = ref([
  { id: 1, level: 'critical', msg: '防护服库存不足', detail: '当前可用 120 套，低于安全阈值 150 套', actionText: '查看详情' },
  { id: 2, level: 'warning', msg: '饮用水消耗过快', detail: '近 2 小时消耗 500L，超出预期 30%', actionText: '补给建议' }
])

const allAlerts = computed(() => [
  ...activeAlerts.value,
  { id: 3, level: 'warning', msg: '灭火器即将过期', detail: '15 个灭火器将于下周到期', actionText: '更换' }
])

const suggestions = ref([
  '建议优先调拨A区防护装备',
  'B区饮用水库存充足，可支援其他区域'
])

const fullSuggestions = ref([
  { title: 'A区防护装备调拨', desc: '当前A区防护服库存仅剩 120 套，低于安全阈值。建议从B区仓库紧急调拨 80 套防护服至A区，预计运输时间 25 分钟。', priority: 'high', priorityLabel: '高' },
  { title: 'B区饮用水支援', desc: 'B区饮用水库存 800L，远超当前需求。建议调拨 300L 至C区和D区，缓解区域消耗不均问题。', priority: 'medium', priorityLabel: '中' },
  { title: '灭火器更换计划', desc: '15 个灭火器将于下周到期，建议提前安排更换，避免影响消防能力。', priority: 'low', priorityLabel: '低' }
])

let map: mapboxgl.Map | null = null
let trendChart: echarts.ECharts | null = null
let resizeHandler: (() => void) | null = null

function updateResponsiveLayout() {
  const width = window.innerWidth
  const height = window.innerHeight
  /* <=1366px 或 <=700px 自动启用 compact，减少固定设计稿尺寸造成的纵向溢出。 */
  autoCompactMode.value = width <= 1366 || height <= 700
  /* <=1100px 默认折叠右侧信息面板，让地图和趋势图区保持完整可见。 */
  if (width <= 1100) rightCollapsed.value = true
  nextTick(() => {
    map?.resize()
    trendChart?.resize()
  })
}

function focusAllResources() {
  resetMapView()
}

function contactPerson(p: any) {
  console.log('Contact:', p.name)
}

function activateTask(task: any) {
  task.status = 'running'
  task.statusClass = 'running'
  task.statusText = '执行中'
  task.progress = 10
}

function handleAlert(alert: any) {
  if (alert.level === 'critical') {
    dispatchForm.target = 'A区物资补充'
    dispatchForm.type = 'suit'
    dispatchForm.quantity = 80
    leftCollapsed.value = false
    nextTick(() => targetInputRef.value?.focus())
  }
}

async function submitDispatch() {
  submitFlash.value = true
  try {
    await dispatchAPI.create({
      type: dispatchForm.type,
      target: dispatchForm.target,
      quantity: dispatchForm.quantity
    }).catch(() => {})
    lastDispatchStatus.value = 'success'
    toastMessage.value = '调度指令已下达'
  } catch (e) {
    lastDispatchStatus.value = 'error'
    toastMessage.value = '调度失败，请重试'
  }
  showToast.value = true
  setTimeout(() => { showToast.value = false }, 2500)
  setTimeout(() => { submitFlash.value = false }, 600)
  setTimeout(() => { lastDispatchStatus.value = null }, 3000)
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
    drawResourcePoints()
    drawRoutes()
  })
  map.on('click', (e: mapboxgl.MapMouseEvent) => {
    console.log('Map clicked:', e.lngLat)
  })
}

function drawResourcePoints() {
  if (!map) return
  const points = [
    { lng: 116.38, lat: 39.92, name: 'A区仓库', type: 'resource' },
    { lng: 116.42, lat: 39.93, name: 'B区仓库', type: 'resource' },
    { lng: 116.40, lat: 39.90, name: 'C区仓库', type: 'resource' },
    { lng: 116.44, lat: 39.91, name: 'D区仓库', type: 'resource' },
    { lng: 116.39, lat: 39.88, name: 'A区指挥部', type: 'target' },
    { lng: 116.43, lat: 39.89, name: 'B区指挥部', type: 'target' }
  ]
  points.forEach(p => {
    const el = document.createElement('div')
    el.className = 'map-marker'
    el.style.cssText = p.type === 'resource'
      ? 'width:24px;height:24px;background:rgba(34,197,94,0.8);border-radius:50%;border:2px solid #22c55e;cursor:pointer;'
      : 'width:24px;height:24px;background:rgba(239,68,68,0.8);border-radius:4px;border:2px solid #ef4444;cursor:pointer;'
    new mapboxgl.Marker({ element: el })
      .setLngLat([p.lng, p.lat])
      .setPopup(new mapboxgl.Popup({ offset: 12, className: 'custom-popup' }).setText(p.name))
      .addTo(map!)
  })
}

function drawRoutes() {
  if (!map) return
  const routes = [
    { id: 'route-a', coords: [[116.38, 39.92], [116.39, 39.91], [116.39, 39.88]] },
    { id: 'route-b', coords: [[116.42, 39.93], [116.43, 39.91], [116.43, 39.89]] },
    { id: 'route-c', coords: [[116.40, 39.90], [116.41, 39.89], [116.39, 39.88]] }
  ]
  routes.forEach(r => {
    map!.addSource(r.id, {
      type: 'geojson',
      data: { type: 'Feature', geometry: { type: 'LineString', coordinates: r.coords } }
    })
    map!.addLayer({
      id: r.id,
      type: 'line',
      source: r.id,
      paint: { 'line-color': '#3b82f6', 'line-width': 2, 'line-dasharray': [4, 2], 'line-opacity': 0.7 }
    })
  })
}

function initTrendChart() {
  if (!trendChartRef.value) return
  trendChart = echarts.init(trendChartRef.value)
  trendChart.setOption({
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(20,28,40,0.9)',
      borderColor: 'rgba(255,255,255,0.1)',
      textStyle: { color: '#e2e8f0', fontSize: 11 }
    },
    grid: { top: 10, bottom: 20, left: 40, right: 16 },
    xAxis: {
      type: 'category',
      data: ['06:00', '07:00', '08:00', '09:00', '10:00', '11:00'],
      axisLabel: { color: '#64748b', fontSize: 10 },
      axisLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
      axisTick: { show: false }
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#64748b', fontSize: 10 },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.04)' } },
      axisLine: { show: false },
      axisTick: { show: false }
    },
    series: [
      {
        name: '消防水管',
        type: 'line',
        data: [420, 400, 390, 385, 380, 380],
        smooth: true,
        lineStyle: { color: '#3b82f6', width: 1.5 },
        symbol: 'none'
      },
      {
        name: '防护服',
        type: 'line',
        data: [250, 220, 200, 170, 140, 120],
        smooth: true,
        lineStyle: { color: '#f59e0b', width: 1.5 },
        symbol: 'none'
      },
      {
        name: '灭火器',
        type: 'line',
        data: [180, 175, 170, 168, 166, 165],
        smooth: true,
        lineStyle: { color: '#22c55e', width: 1.5 },
        symbol: 'none'
      }
    ]
  })
}

function handleKeydown(e: KeyboardEvent) {
  if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement) return
  switch (e.key.toLowerCase()) {
    case 'l': leftCollapsed.value = !leftCollapsed.value; break
    case 'r': rightCollapsed.value = !rightCollapsed.value; break
    case 'c': manualCompactMode.value = !manualCompactMode.value; break
    case 's': leftCollapsed.value = false; nextTick(() => targetInputRef.value?.focus()); break
    case 'h': console.log('Help: L=左面板 R=右面板 S=调度 H=帮助'); break
  }
}

async function loadData() {
  try {
    const [stat, resources, personnel] = await Promise.all([
      fireAPI.getStat().catch(() => ({})),
      resourceAPI.getList().catch(() => []),
      personnelAPI.getList().catch(() => [])
    ])
    if (resources.length) {
      fullInventory.value = resources
      topInventory.value = resources.slice(0, 3)
      resourceStats.total = resources.reduce((sum: number, r: any) => sum + (r.total || 0), 0)
      resourceStats.available = resources.reduce((sum: number, r: any) => sum + (r.available || 0), 0)
      resourceStats.inTransit = resourceStats.total - resourceStats.available
    }
    if (personnel.length) {
      allPersonnel.value = personnel
      topPersonnel.value = personnel.slice(0, 4)
    }
  } catch (e) {
    console.error('Failed to load data:', e)
  }
}

onMounted(() => {
  updateResponsiveLayout()
  resizeHandler = updateResponsiveLayout
  window.addEventListener('resize', resizeHandler)
  initMap()
  initTrendChart()
  loadData()
})

onUnmounted(() => {
  if (resizeHandler) window.removeEventListener('resize', resizeHandler)
  trendChart?.dispose()
  map?.remove()
})
</script>

<style scoped>
.dispatch-container {
  /* 使用父级 100% 而不是 100vw/100vh，避免浏览器视口计算差异带来主滚动条。 */
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
  /* 顶栏高度改为 clamp，小高度屏幕自动压缩，释放中间区域高度。 */
  height: clamp(48px, 8vh, 64px);
  flex: 0 0 clamp(48px, 8vh, 64px);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: clamp(8px, 1.1vw, 20px);
  padding: 0 clamp(12px, 1.7vw, 32px);
  background: rgba(20, 28, 40, 0.9);
  border-bottom: 1px solid rgba(255,255,255,0.06);
  backdrop-filter: blur(16px);
}

.capsule {
  display: flex;
  align-items: center;
  /* 胶囊横向 padding 自适应，防止顶栏在 1024px 宽度下撑出页面。 */
  padding: clamp(5px, 0.8vh, 8px) clamp(10px, 1vw, 20px);
  border-radius: 40px;
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(255,255,255,0.12);
  backdrop-filter: blur(10px);
}

.capsule-env { gap: clamp(4px, 0.6vw, 8px); min-width: 0; }
.cap-icon { font-size: clamp(14px, 1vw, 18px); }
.cap-temp {
  font-size: clamp(16px, 1.2vw, 22px);
  font-weight: 700;
  background: linear-gradient(90deg, #fff, #67e8f9);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
.cap-weather { font-size: clamp(10px, 0.75vw, 13px); color: #cbd5e1; }
.cap-humidity { font-size: clamp(9px, 0.65vw, 11px); color: #64748b; margin-left: 4px; }

.capsule-resource {
  gap: 6px;
  min-width: 0;
  flex-direction: column;
  align-items: flex-start;
  padding: clamp(5px, 0.8vh, 10px) clamp(10px, 1vw, 20px);
}
.cap-res-label { font-size: clamp(9px, 0.65vw, 11px); color: #64748b; }
.cap-res-val {
  font-size: clamp(17px, 1.45vw, 28px);
  font-weight: 700;
  background: linear-gradient(90deg, #fff, #67e8f9);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  line-height: 1;
}
.cap-res-unit { font-size: clamp(10px, 0.75vw, 13px); color: #94a3b8; margin-left: 2px; }
.cap-res-sub { font-size: clamp(9px, 0.65vw, 11px); color: #64748b; }

.capsule-alert {
  gap: 10px;
  min-width: 0;
  justify-content: center;
  cursor: pointer;
  border-color: rgba(245,158,11,0.3);
  background: rgba(245,158,11,0.08);
}
.capsule-alert.pulsing { animation: alertPulse 2s ease-in-out infinite; }

@keyframes alertPulse {
  0%, 100% { border-color: rgba(245,158,11,0.3); }
  50% { border-color: rgba(245,158,11,0.7); }
}

.alert-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #f59e0b;
  animation: dotBlink 1.5s ease-in-out infinite;
}

@keyframes dotBlink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.cap-alert-text { font-size: clamp(10px, 0.8vw, 13px); color: #fde68a; white-space: normal; }
.cap-alert-more { font-size: 12px; color: #60a5fa; }

.main-content {
  flex: 1;
  display: flex;
  min-height: 0;
  min-width: 0;
  overflow: hidden;
}

.side-panel {
  /* 将固定 320px 改为 clamp，侧栏在窄屏收缩，防止横向溢出。 */
  width: clamp(200px, 18vw, 320px);
  flex: 0 0 clamp(200px, 18vw, 320px);
  display: flex;
  flex-direction: column;
  position: relative;
  transition: width 0.2s ease, flex-basis 0.2s ease;
  padding: clamp(6px, 1vh, 12px);
  gap: clamp(6px, 1vh, 12px);
  min-height: 0;
  overflow: hidden;
}

.side-panel.collapsed {
  /* 折叠宽度也使用 clamp，保证控件不把页面撑宽。 */
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
  /* 卡片 padding 自适应压缩，减少纵向累积高度。 */
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

.overview-metrics {
  display: flex;
  gap: clamp(4px, 0.65vw, 12px);
  margin-bottom: clamp(4px, 0.8vh, 10px);
  min-height: 0;
}

.metric-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: clamp(3px, 0.5vh, 6px);
  padding: clamp(5px, 0.8vh, 10px) clamp(4px, 0.5vw, 6px);
  border-radius: 12px;
  background: rgba(255,255,255,0.03);
}

.metric-icon { font-size: clamp(13px, 1vw, 18px); }
.metric-info { display: flex; flex-direction: column; align-items: center; }
.metric-val {
  font-size: clamp(14px, 1.05vw, 20px);
  font-weight: 700;
  background: linear-gradient(90deg, #fff, #67e8f9);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
.metric-label { font-size: 10px; color: #64748b; }

.detail-link {
  border: none;
  background: none;
  color: #60a5fa;
  font-size: clamp(10px, 0.7vw, 12px);
  cursor: pointer;
  padding: 4px 0;
  text-align: left;
}

.detail-link:hover { text-decoration: underline; }

.inventory-list {
  display: flex;
  flex-direction: column;
  gap: clamp(4px, 0.8vh, 10px);
  margin-bottom: clamp(4px, 0.8vh, 10px);
  min-height: 0;
  overflow: hidden;
}

.inv-item {
  padding: clamp(5px, 0.8vh, 10px);
  border-radius: 12px;
  background: rgba(255,255,255,0.03);
  transition: border-color 0.2s;
}

.inv-item.warning { border: 1px solid rgba(245,158,11,0.2); }

.inv-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: clamp(3px, 0.5vh, 6px);
}

.inv-name { font-size: clamp(10px, 0.72vw, 13px); font-weight: 500; }
.inv-nums { font-size: clamp(10px, 0.7vw, 12px); font-weight: 600; color: #cbd5e1; }
.inv-nums.low { color: #f59e0b; }

.inv-bar {
  height: 4px;
  background: rgba(255,255,255,0.08);
  border-radius: 2px;
  overflow: hidden;
}

.inv-bar-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.3s ease;
}

.inv-bar-fill.ok { background: linear-gradient(90deg, #3b82f6, #22c55e); }
.inv-bar-fill.warn { background: linear-gradient(90deg, #f59e0b, #ef4444); }

.dispatch-form {
  display: flex;
  flex-direction: column;
  gap: clamp(5px, 0.8vh, 10px);
  min-height: 0;
}

.form-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.form-label { font-size: 11px; color: #64748b; }

.form-input {
  width: 100%;
  padding: clamp(6px, 0.8vh, 8px) clamp(8px, 0.7vw, 10px);
  border-radius: 10px;
  border: 1px solid rgba(255,255,255,0.1);
  background: rgba(255,255,255,0.04);
  color: #e2e8f0;
  font-size: 12px;
  outline: none;
  transition: border-color 0.2s;
}

.form-input:focus { border-color: rgba(96,165,250,0.5); }

.number-input {
  display: flex;
  align-items: center;
  gap: 0;
  border-radius: 10px;
  border: 1px solid rgba(255,255,255,0.1);
  background: rgba(255,255,255,0.04);
  overflow: hidden;
}

.num-btn {
  width: clamp(28px, 2.2vw, 36px);
  height: clamp(26px, 4vh, 32px);
  border: none;
  background: rgba(255,255,255,0.06);
  color: #94a3b8;
  cursor: pointer;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s;
}

.num-btn:hover { background: rgba(96,165,250,0.15); }

.num-val {
  width: 60px;
  text-align: center;
  border: none;
  background: transparent;
  color: #e2e8f0;
  font-size: 14px;
  font-weight: 600;
  outline: none;
  -moz-appearance: textfield;
}

.num-val::-webkit-inner-spin-button,
.num-val::-webkit-outer-spin-button { -webkit-appearance: none; }

.submit-btn {
  width: 100%;
  padding: clamp(7px, 1vh, 12px);
  border-radius: 12px;
  border: none;
  background: linear-gradient(90deg, #3b82f6, #6366f1);
  color: white;
  font-size: clamp(11px, 0.8vw, 14px);
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s;
}

.submit-btn:hover { transform: scale(0.98); }
.submit-btn.flash { animation: submitFlash 0.6s ease; }

@keyframes submitFlash {
  0% { box-shadow: 0 0 0 rgba(96,165,250,0); }
  50% { box-shadow: 0 0 24px rgba(96,165,250,0.6); }
  100% { box-shadow: 0 0 0 rgba(96,165,250,0); }
}

.dispatch-status {
  font-size: 12px;
  padding: 4px 0;
}

.dispatch-status.success { color: #22c55e; }
.dispatch-status.error { color: #ef4444; }

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
  position: relative;
}

.ico-item:hover { background: rgba(96,165,250,0.15); transform: translateY(-2px); }
.ico-item.active { background: rgba(96,165,250,0.2); border: 1px solid rgba(96,165,250,0.3); }

.ico-badge {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #f59e0b;
}

.center-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.map-section {
  flex: 8;
  position: relative;
  min-height: 0;
  min-width: 0;
  overflow: hidden;
}

.map-container { width: 100%; height: 100%; }

.map-controls-left {
  position: absolute;
  /* 地图控件偏移使用 clamp，避免绝对定位控件贴边溢出。 */
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

.trend-section {
  flex: 0 0 clamp(86px, 20vh, 180px);
  background: rgba(20,28,40,0.7);
  border-top: 1px solid rgba(255,255,255,0.06);
  backdrop-filter: blur(12px);
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.trend-header {
  padding: clamp(4px, 0.7vh, 6px) clamp(8px, 0.8vw, 12px);
  background: rgba(255,255,255,0.03);
}

.trend-title { font-size: 12px; color: #94a3b8; font-weight: 500; }

.trend-chart { flex: 1; min-height: 0; }

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
  position: relative;
}

.tab-item:hover { color: #e2e8f0; }
.tab-item.active { background: rgba(96,165,250,0.2); color: #60a5fa; font-weight: 600; }

.tab-badge {
  position: absolute;
  top: 4px;
  right: 12px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #f59e0b;
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
  gap: clamp(6px, 1vh, 12px);
}

.personnel-list {
  display: flex;
  flex-direction: column;
  gap: clamp(4px, 0.8vh, 8px);
  min-height: 0;
  overflow: hidden;
}

.person-item {
  display: flex;
  align-items: center;
  gap: clamp(5px, 0.55vw, 10px);
  padding: clamp(5px, 0.8vh, 10px);
  border-radius: 12px;
  background: rgba(255,255,255,0.03);
  transition: background 0.15s;
}

.person-item:hover { background: rgba(96,165,250,0.06); }

.person-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.person-dot.green { background: #22c55e; }
.person-dot.gray { background: #64748b; }

.person-info { flex: 1; display: flex; flex-direction: column; }
.person-name { font-size: clamp(10px, 0.72vw, 13px); font-weight: 500; }
.person-role { font-size: clamp(9px, 0.62vw, 11px); color: #64748b; }

.person-status {
  font-size: clamp(9px, 0.62vw, 11px);
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 20px;
}

.person-status.deployed { color: #4ade80; background: rgba(34,197,94,0.12); }
.person-status.standby { color: #94a3b8; background: rgba(100,116,139,0.12); }

.contact-btn {
  width: clamp(22px, 3.4vh, 28px);
  height: clamp(22px, 3.4vh, 28px);
  border-radius: 8px;
  border: none;
  background: rgba(255,255,255,0.04);
  cursor: pointer;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.contact-btn:hover { background: rgba(96,165,250,0.15); }

.task-list {
  display: flex;
  flex-direction: column;
  gap: clamp(5px, 0.8vh, 10px);
  min-height: 0;
  overflow: hidden;
}

.task-card {
  padding: clamp(6px, 0.9vh, 12px);
  border-radius: 12px;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06);
}

.task-card.running { border-color: rgba(59,130,246,0.3); }
.task-card.done { border-color: rgba(34,197,94,0.2); }
.task-card.pending { border-color: rgba(100,116,139,0.2); }

.tc-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: clamp(4px, 0.7vh, 8px);
}

.tc-name { font-size: clamp(10px, 0.72vw, 13px); font-weight: 500; }

.tc-status-badge {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 20px;
}

.tc-status-badge.running { color: #60a5fa; background: rgba(59,130,246,0.12); }
.tc-status-badge.done { color: #4ade80; background: rgba(34,197,94,0.12); }
.tc-status-badge.pending { color: #94a3b8; background: rgba(100,116,139,0.12); }

.tc-progress {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.tc-progress-bar {
  flex: 1;
  height: 4px;
  background: rgba(255,255,255,0.08);
  border-radius: 2px;
  overflow: hidden;
}

.tc-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6, #22c55e);
  border-radius: 2px;
  transition: width 0.3s ease;
}

.tc-percent { font-size: 12px; font-weight: 600; color: #60a5fa; }

.tc-suggest {
  font-size: clamp(9px, 0.62vw, 11px);
  color: #94a3b8;
  padding: 4px 0;
}

.tc-action { margin-top: 6px; }

.tc-btn {
  padding: 6px 14px;
  border-radius: 8px;
  border: 1px solid rgba(59,130,246,0.3);
  background: rgba(59,130,246,0.1);
  color: #60a5fa;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.2s;
}

.tc-btn:hover { background: rgba(59,130,246,0.2); }

.alert-list {
  display: flex;
  flex-direction: column;
  gap: clamp(5px, 0.8vh, 10px);
  margin-bottom: clamp(6px, 1vh, 12px);
  min-height: 0;
  overflow: hidden;
}

.alert-card {
  padding: clamp(6px, 0.9vh, 12px);
  border-radius: 12px;
  background: rgba(255,255,255,0.03);
}

.alert-card.critical {
  background: rgba(245,158,11,0.08);
  border: 1px solid rgba(245,158,11,0.2);
}

.alert-card.warning {
  background: rgba(234,179,8,0.06);
  border: 1px solid rgba(234,179,8,0.15);
}

.ac-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.ac-icon { font-size: 12px; }
.ac-msg { font-size: 12px; flex: 1; }

.ac-btn {
  padding: 4px 12px;
  border-radius: 6px;
  border: 1px solid rgba(255,255,255,0.1);
  background: rgba(255,255,255,0.04);
  color: #94a3b8;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.2s;
}

.ac-btn:hover { background: rgba(96,165,250,0.15); }

.suggest-section {
  border-top: 1px solid rgba(255,255,255,0.06);
  padding-top: clamp(6px, 0.9vh, 10px);
  min-height: 0;
  overflow: hidden;
}

.ss-title { font-size: 12px; color: #64748b; margin-bottom: 8px; }
.ss-item { font-size: 12px; color: #94a3b8; padding: 4px 0; }

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
  /* 抽屉不再使用 overflow-y:auto，长列表通过压缩间距和隐藏低优先级明细适配视口。 */
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
  font-size: clamp(11px, 0.75vw, 13px);
  outline: none;
  margin-bottom: clamp(6px, 1vh, 12px);
}

.search-input:focus { border-color: rgba(96,165,250,0.5); }

.inv-drawer-list {
  display: flex;
  flex-direction: column;
  gap: clamp(4px, 0.8vh, 8px);
  min-height: 0;
  overflow: hidden;
}

.inv-drawer-item {
  display: flex;
  align-items: center;
  gap: clamp(5px, 0.55vw, 10px);
  padding: clamp(6px, 0.9vh, 10px);
  border-radius: 10px;
  background: rgba(255,255,255,0.03);
}

.idi-name { width: clamp(48px, 4vw, 60px); font-size: clamp(10px, 0.7vw, 12px); color: #cbd5e1; }

.idi-bar-area {
  flex: 1;
  height: 6px;
  background: rgba(255,255,255,0.06);
  border-radius: 3px;
  overflow: hidden;
}

.idi-bar {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s ease;
}

.idi-bar.ok { background: linear-gradient(90deg, #3b82f6, #22c55e); }
.idi-bar.warn { background: linear-gradient(90deg, #f59e0b, #ef4444); }

.idi-nums { width: clamp(60px, 5.2vw, 80px); font-size: clamp(10px, 0.7vw, 12px); color: #94a3b8; text-align: right; }

.filter-row {
  display: flex;
  gap: 6px;
  margin-bottom: clamp(6px, 1vh, 12px);
}

.filter-btn {
  padding: clamp(5px, 0.8vh, 6px) clamp(8px, 0.8vw, 14px);
  border-radius: 8px;
  border: 1px solid rgba(255,255,255,0.08);
  background: rgba(255,255,255,0.04);
  color: #94a3b8;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.filter-btn.active { background: rgba(96,165,250,0.2); color: #60a5fa; border-color: rgba(96,165,250,0.3); }

.personnel-drawer-list {
  display: flex;
  flex-direction: column;
  gap: clamp(4px, 0.8vh, 8px);
  min-height: 0;
  overflow: hidden;
}

.pd-item {
  display: flex;
  align-items: center;
  gap: clamp(5px, 0.55vw, 10px);
  padding: clamp(6px, 0.9vh, 10px);
  border-radius: 10px;
  background: rgba(255,255,255,0.03);
}

.pd-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.pd-dot.green { background: #22c55e; }
.pd-dot.gray { background: #64748b; }

.pd-info { flex: 1; display: flex; flex-direction: column; }
.pd-name { font-size: 13px; font-weight: 500; }
.pd-role { font-size: 11px; color: #64748b; }

.pd-status {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 20px;
}

.pd-status.deployed { color: #4ade80; background: rgba(34,197,94,0.12); }
.pd-status.standby { color: #94a3b8; background: rgba(100,116,139,0.12); }

.ht-item {
  display: flex;
  align-items: center;
  gap: clamp(6px, 0.7vw, 12px);
  padding: clamp(6px, 0.9vh, 10px);
  border-radius: 10px;
  background: rgba(255,255,255,0.03);
  margin-bottom: clamp(4px, 0.8vh, 8px);
}

.ht-status {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 20px;
}

.ht-status.done { color: #4ade80; background: rgba(34,197,94,0.12); }

.ht-info { flex: 1; display: flex; flex-direction: column; }
.ht-name { font-size: 12px; font-weight: 500; }
.ht-time { font-size: 11px; color: #64748b; }

.fs-item {
  padding: clamp(8px, 1vh, 14px);
  border-radius: 12px;
  background: rgba(255,255,255,0.03);
  margin-bottom: clamp(5px, 0.9vh, 10px);
  border: 1px solid rgba(255,255,255,0.06);
}

.fs-title { font-size: clamp(11px, 0.8vw, 14px); font-weight: 600; color: #cbd5e1; margin-bottom: clamp(4px, 0.8vh, 8px); }
.fs-desc { font-size: clamp(10px, 0.7vw, 12px); color: #94a3b8; margin-bottom: clamp(4px, 0.8vh, 8px); line-height: 1.35; }

.fs-priority {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 10px;
  border-radius: 20px;
  display: inline-block;
}

.fs-priority.high { color: #f87171; background: rgba(239,68,68,0.12); }
.fs-priority.medium { color: #fbbf24; background: rgba(245,158,11,0.12); }
.fs-priority.low { color: #94a3b8; background: rgba(100,116,139,0.12); }

.da-item {
  display: flex;
  align-items: flex-start;
  gap: clamp(5px, 0.55vw, 10px);
  padding: clamp(6px, 0.9vh, 12px);
  border-radius: 12px;
  background: rgba(255,255,255,0.03);
  margin-bottom: clamp(4px, 0.8vh, 8px);
}

.da-item.critical { background: rgba(245,158,11,0.08); }
.da-item.warning { background: rgba(234,179,8,0.06); }

.da-icon { font-size: 12px; margin-top: 2px; }
.da-info { flex: 1; }
.da-msg { display: block; font-size: 12px; font-weight: 500; }
.da-detail { display: block; font-size: 11px; color: #64748b; margin-top: 4px; }

/* 紧凑模式：按规范把面板 padding 约 12px->6px、卡片 16px->8px、标题 13px->10px，避免面板内部滚动。 */
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

.compact .metric-item,
.compact .inv-item,
.compact .person-item,
.compact .task-card,
.compact .alert-card,
.compact .fs-item,
.compact .da-item {
  padding: 5px 7px;
  border-radius: 10px;
}

.compact .inventory-list,
.compact .dispatch-form,
.compact .personnel-list,
.compact .task-list,
.compact .alert-list,
.compact .tab-inner {
  gap: 5px;
}

.compact .cap-humidity,
.compact .cap-res-sub,
.compact .person-role,
.compact .tc-suggest,
.compact .ss-item:nth-of-type(n + 2),
.compact .detail-link,
.compact .da-detail {
  display: none;
}

.compact .trend-section {
  flex-basis: clamp(72px, 17vh, 130px);
}

.compact .drawer-content {
  width: clamp(260px, 30vw, 340px);
}

/* <=1366px 自动套用 compact 同款尺寸，小屏无需手动切换也不会溢出。 */
@media (max-width: 1366px) {
  .top-bar {
    height: clamp(44px, 6.5vh, 52px);
    flex-basis: clamp(44px, 6.5vh, 52px);
    padding: 0 clamp(6px, 0.8vw, 12px);
    gap: clamp(4px, 0.6vw, 8px);
  }

  .capsule {
    min-width: 0;
    padding: 5px clamp(7px, 0.8vw, 12px);
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

  .metric-item,
  .inv-item,
  .person-item,
  .task-card,
  .alert-card,
  .fs-item,
  .da-item {
    padding: 5px 7px;
    border-radius: 10px;
  }

  .cap-humidity,
  .cap-res-sub,
  .person-role,
  .tc-suggest,
  .ss-item:nth-of-type(n + 2),
  .detail-link,
  .da-detail {
    display: none;
  }

  .trend-section {
    flex-basis: clamp(72px, 17vh, 130px);
  }
}

/* <=1100px 右侧面板默认折叠；展开时绝对定位为浮层，不占用主布局宽度。 */
@media (max-width: 1100px) {
  .capsule-alert,
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

/* <=800px 改为纵向堆叠，侧栏宽度 100%，消除横向挤压。 */
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

  .trend-section {
    flex-basis: clamp(64px, 15vh, 96px);
  }

  .overview-metrics {
    gap: 4px;
  }

  .inventory-list .inv-item:nth-child(n + 3),
  .personnel-list .person-item:nth-child(n + 4),
  .task-list .task-card:nth-child(n + 3),
  .alert-list .alert-card:nth-child(n + 2),
  .suggest-section {
    display: none;
  }
}

/* <=700px 高度继续压缩，隐藏低优先级文字，保证 600px 高度无内部滚动。 */
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

  .metric-item,
  .inv-item,
  .person-item,
  .task-card,
  .alert-card,
  .fs-item,
  .da-item {
    padding: 5px 7px;
  }

  .tabs {
    margin-bottom: 5px;
  }

  .tab-inner,
  .inventory-list,
  .dispatch-form,
  .personnel-list,
  .task-list,
  .alert-list {
    gap: 4px;
  }

  .cap-humidity,
  .cap-res-sub,
  .cap-alert-more,
  .person-role,
  .tc-suggest,
  .detail-link,
  .ss-item:nth-of-type(n + 2),
  .da-detail,
  .dispatch-status {
    display: none;
  }

  .trend-section {
    flex-basis: clamp(60px, 15vh, 100px);
  }

  .drawer-body {
    padding: 6px;
  }

  .search-input,
  .filter-row {
    margin-bottom: 5px;
  }
}

.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

.drawer-enter-active, .drawer-leave-active { transition: all 0.2s ease; }
.drawer-enter-from, .drawer-leave-to { opacity: 0; }
.drawer-enter-from .drawer-content, .drawer-leave-to .drawer-content { transform: translateX(100%); }
</style>
