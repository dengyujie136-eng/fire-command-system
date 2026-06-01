<template>
  <div class="assess-container" :class="{ compact: compactMode }" @keydown="handleKeydown" tabindex="0">
    <div class="top-bar">
      <div class="capsule capsule-burned" @click="showBurnedDetail = true">
        <span class="cap-icon">🔥</span>
        <div class="cap-data">
          <span class="cap-val">1250</span>
          <span class="cap-unit">hm²</span>
        </div>
        <span class="cap-trend up">↑</span>
      </div>
      <div class="capsule capsule-loss" @click="showLossDetail = true">
        <span class="cap-icon">💰</span>
        <div class="cap-data">
          <span class="cap-val">3200</span>
          <span class="cap-unit">万元</span>
        </div>
      </div>
      <div class="capsule capsule-people">
        <span class="cap-icon">👥</span>
        <div class="cap-data">
          <span class="cap-val">12.5k</span>
          <span class="cap-unit">人</span>
        </div>
      </div>
      <div class="capsule capsule-weather">
        <span class="cap-icon">☀️</span>
        <div class="cap-data">
          <span class="cap-val">26℃</span>
          <span class="cap-unit">晴</span>
        </div>
        <span class="cap-humidity">湿度 45%</span>
      </div>
      <div class="update-tag">
        <span class="ut-text">最后更新：刚刚</span>
        <button class="ut-refresh" @click="refreshData" title="刷新数据">↻</button>
      </div>
    </div>

    <div class="main-content">
      <div class="side-panel left" :class="{ collapsed: leftCollapsed }">
        <button class="collapse-btn" @click="leftCollapsed = !leftCollapsed" :title="leftCollapsed ? '展开面板' : '收起面板'">
          <span class="arrow">{{ leftCollapsed ? '→' : '←' }}</span>
        </button>

        <template v-if="!leftCollapsed">
          <div class="glass-card clickable" @click="highlightTrendPeak">
            <div class="card-title">评估等级</div>
            <div class="grade-row">
              <div class="grade-badge severe">严重</div>
              <div class="grade-score">
                <span class="gs-val">7.2</span>
                <span class="gs-max">/10</span>
              </div>
            </div>
            <div class="severity-bar">
              <div class="sb-fill" style="width: 72%"></div>
            </div>
            <div class="severity-label">灾害严重程度 72%</div>
            <div class="grade-summary">本次火灾影响范围较大</div>
          </div>

          <div class="glass-card">
            <div class="card-title">地表覆盖影响</div>
            <div class="impact-items">
              <div class="impact-item">
                <div class="ii-header">
                  <span class="ii-label">生态影响</span>
                  <span class="ii-pct">72%</span>
                </div>
                <div class="ii-bar">
                  <div class="ii-fill eco" style="width: 72%"></div>
                </div>
                <span class="ii-desc">中度影响</span>
              </div>
              <div class="impact-item">
                <div class="ii-header">
                  <span class="ii-label">经济影响</span>
                  <span class="ii-pct">65%</span>
                </div>
                <div class="ii-bar">
                  <div class="ii-fill econ" style="width: 65%"></div>
                </div>
                <span class="ii-desc">中度影响</span>
              </div>
            </div>
            <button class="detail-link" @click="showEcoDetail = true">生态因子详情</button>
          </div>

          <div class="glass-card">
            <div class="card-title">影响趋势</div>
            <div ref="miniTrendRef" class="mini-chart"></div>
            <div class="trend-change">相比昨日 <span class="up">+12%</span></div>
            <button class="detail-link" @click="showTrendDrawer = true">详细趋势</button>
          </div>
        </template>

        <template v-else>
          <div class="collapsed-icons">
            <div class="ico-item" title="评估等级" @click="leftCollapsed = false">⚠️</div>
            <div class="ico-item" title="地表覆盖" @click="showEcoDetail = true">🌍</div>
            <div class="ico-item" title="影响趋势" @click="showTrendDrawer = true">📈</div>
          </div>
        </template>
      </div>

      <div class="center-area">
        <div class="chart-panel left-chart">
          <div class="chart-header">
            <span class="ch-title">过火面积趋势</span>
            <div class="ch-legend">
              <span class="legend-dot red"></span>过火面积
            </div>
          </div>
          <div ref="trendChartRef" class="chart-body"></div>
        </div>
        <div class="chart-panel right-chart">
          <div class="chart-header">
            <span class="ch-title">历史对比</span>
            <div class="ch-legend">
              <span class="legend-dot blue"></span>本年
              <span class="legend-dot indigo"></span>去年
              <span class="legend-dot gray"></span>平均
            </div>
          </div>
          <div ref="compareChartRef" class="chart-body"></div>
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
              <div v-if="activeTab === 'report'" key="report" class="tab-inner">
                <div class="score-ring">
                  <svg viewBox="0 0 100 100" class="ring-svg">
                    <circle cx="50" cy="50" r="40" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="8"/>
                    <circle cx="50" cy="50" r="40" fill="none" stroke="#ef4444" stroke-width="8"
                      stroke-linecap="round" :stroke-dasharray="`${7.2 * 25.1} 251`" stroke-dashoffset="0"/>
                  </svg>
                  <div class="ring-center">
                    <span class="ring-val">7.2</span>
                    <span class="ring-label">评估得分</span>
                  </div>
                </div>
                <div class="report-text">
                  {{ reportText }}
                </div>
                <button class="detail-link" @click="showReportDrawer = true">展开全文</button>
              </div>

              <div v-else-if="activeTab === 'loss'" key="loss" class="tab-inner">
                <div class="loss-items">
                  <div class="loss-item">
                    <div class="li-header">
                      <span class="li-icon">🌾</span>
                      <span class="li-label">农业损失</span>
                      <span class="li-val">800 万元</span>
                    </div>
                    <div class="li-bar">
                      <div class="li-fill agriculture" style="width: 40%"></div>
                    </div>
                    <div class="li-ring-row">
                      <svg viewBox="0 0 60 60" class="mini-ring">
                        <circle cx="30" cy="30" r="22" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="5"/>
                        <circle cx="30" cy="30" r="22" fill="none" stroke="#f59e0b" stroke-width="5"
                          stroke-linecap="round" :stroke-dasharray="`${0.4 * 138.2} 138.2`" stroke-dashoffset="0"/>
                      </svg>
                      <span class="li-pct">占比 40%</span>
                    </div>
                  </div>
                  <div class="loss-item">
                    <div class="li-header">
                      <span class="li-icon">🌲</span>
                      <span class="li-label">林业损失</span>
                      <span class="li-val">1200 万元</span>
                    </div>
                    <div class="li-bar">
                      <div class="li-fill forest" style="width: 60%"></div>
                    </div>
                    <div class="li-ring-row">
                      <svg viewBox="0 0 60 60" class="mini-ring">
                        <circle cx="30" cy="30" r="22" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="5"/>
                        <circle cx="30" cy="30" r="22" fill="none" stroke="#22c55e" stroke-width="5"
                          stroke-linecap="round" :stroke-dasharray="`${0.6 * 138.2} 138.2`" stroke-dashoffset="0"/>
                      </svg>
                      <span class="li-pct">占比 60%</span>
                    </div>
                  </div>
                  <div class="loss-item other">
                    <div class="li-header">
                      <span class="li-icon">🏗️</span>
                      <span class="li-label">其他损失</span>
                      <span class="li-val">1200 万元</span>
                    </div>
                  </div>
                </div>
                <button class="detail-link" @click="showLossDrawer = true">分类明细</button>
              </div>

              <div v-else key="measures" class="tab-inner">
                <div class="measure-list">
                  <div v-for="m in measures" :key="m.id" class="measure-item">
                    <div class="mi-header">
                      <span class="mi-priority" :class="m.priority">{{ m.priorityLabel }}</span>
                      <span class="mi-title">{{ m.title }}</span>
                    </div>
                    <div class="mi-status-row">
                      <button class="mi-status-btn" :class="m.statusClass" @click="cycleStatus(m)">
                        {{ m.statusText }}
                      </button>
                    </div>
                  </div>
                </div>
                <div class="measure-sections">
                  <div class="ms-group">
                    <div class="ms-title" @click="showShortTerm = !showShortTerm">
                      短期措施 <span class="ms-arrow">{{ showShortTerm ? '▾' : '▸' }}</span>
                    </div>
                    <div v-if="showShortTerm" class="ms-items">
                      <div v-for="s in shortTermMeasures" :key="s" class="ms-item">{{ s }}</div>
                    </div>
                  </div>
                  <div class="ms-group">
                    <div class="ms-title" @click="showLongTerm = !showLongTerm">
                      长期措施 <span class="ms-arrow">{{ showLongTerm ? '▾' : '▸' }}</span>
                    </div>
                    <div v-if="showLongTerm" class="ms-items">
                      <div v-for="s in longTermMeasures" :key="s" class="ms-item">{{ s }}</div>
                    </div>
                  </div>
                </div>
                <button class="generate-btn" @click="generateTaskList">生成任务清单</button>
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
        <button class="bb-btn export" @click="exportReport">
          <span class="bb-icon">📥</span> 导出评估报告
        </button>
      </div>
      <div class="bb-center">
        <button class="bb-btn" @click="printPreview">
          <span class="bb-icon">🖨️</span> 打印预览
        </button>
        <button class="bb-btn" @click="shareReport">
          <span class="bb-icon">🔗</span> 分享
        </button>
      </div>
      <div class="bb-right">
        <button class="bb-btn compact-toggle" :class="{ active: compactMode }" @click="compactMode = !compactMode" title="紧凑模式">
          <span class="bb-icon">⊞</span> 紧凑
        </button>
        <select v-model="timeRange" class="time-select" @change="onTimeRangeChange">
          <option value="24h">最近 24 小时</option>
          <option value="7d">最近 7 天</option>
          <option value="30d">最近 30 天</option>
        </select>
      </div>
    </div>

    <transition name="toast">
      <div v-if="showToast" class="toast-notification">
        <span class="toast-icon">✓</span>
        <span class="toast-text">{{ toastMessage }}</span>
      </div>
    </transition>

    <transition name="drawer">
      <div v-if="showBurnedDetail" class="drawer-overlay" @click="showBurnedDetail = false">
        <div class="drawer-content" @click.stop>
          <div class="drawer-header">
            过火面积详情
            <button class="close-drawer" @click="showBurnedDetail = false">✕</button>
          </div>
          <div class="drawer-body">
            <div v-for="area in burnedAreas" :key="area.name" class="da-item">
              <span class="da-name">{{ area.name }}</span>
              <div class="da-bar-area">
                <div class="da-bar" :style="{ width: (area.value / 500 * 100) + '%' }"></div>
              </div>
              <span class="da-val">{{ area.value }} hm²</span>
            </div>
          </div>
        </div>
      </div>
    </transition>

    <transition name="drawer">
      <div v-if="showLossDetail" class="drawer-overlay" @click="showLossDetail = false">
        <div class="drawer-content" @click.stop>
          <div class="drawer-header">
            经济损失详情
            <button class="close-drawer" @click="showLossDetail = false">✕</button>
          </div>
          <div class="drawer-body">
            <div v-for="item in lossDetailItems" :key="item.name" class="da-item">
              <span class="da-name">{{ item.name }}</span>
              <span class="da-val">{{ item.value }} 万元</span>
            </div>
          </div>
        </div>
      </div>
    </transition>

    <transition name="drawer">
      <div v-if="showEcoDetail" class="drawer-overlay" @click="showEcoDetail = false">
        <div class="drawer-content" @click.stop>
          <div class="drawer-header">
            生态影响因子分析
            <button class="close-drawer" @click="showEcoDetail = false">✕</button>
          </div>
          <div class="drawer-body">
            <div v-for="f in ecoFactors" :key="f.name" class="eco-item">
              <div class="eco-header">
                <span class="eco-name">{{ f.name }}</span>
                <span class="eco-pct" :class="f.level">{{ f.value }}%</span>
              </div>
              <div class="eco-bar">
                <div class="eco-fill" :class="f.level" :style="{ width: f.value + '%' }"></div>
              </div>
              <span class="eco-desc">{{ f.desc }}</span>
            </div>
          </div>
        </div>
      </div>
    </transition>

    <transition name="drawer">
      <div v-if="showTrendDrawer" class="drawer-overlay" @click="showTrendDrawer = false">
        <div class="drawer-content wide" @click.stop>
          <div class="drawer-header">
            影响趋势详细数据
            <button class="close-drawer" @click="showTrendDrawer = false">✕</button>
          </div>
          <div class="drawer-body">
            <div ref="detailTrendChartRef" class="detail-chart"></div>
          </div>
        </div>
      </div>
    </transition>

    <transition name="drawer">
      <div v-if="showReportDrawer" class="drawer-overlay" @click="showReportDrawer = false">
        <div class="drawer-content" @click.stop>
          <div class="drawer-header">
            完整评估报告
            <button class="close-drawer" @click="showReportDrawer = false">✕</button>
          </div>
          <div class="drawer-body report-drawer-body">
            <h3 class="rd-title">综合灾情评估报告</h3>
            <div class="rd-section">
              <h4>一、火灾概况</h4>
              <p>本次火灾始于 2026 年 5 月 28 日，过火面积达 1250 公顷，持续 72 小时后基本控制。火场主要位于北部林区，涉及 3 个乡镇、12 个行政村。</p>
            </div>
            <div class="rd-section">
              <h4>二、损失评估</h4>
              <p>直接经济损失约 3200 万元，其中林业损失 1200 万元，农业损失 800 万元，基础设施损失 600 万元，建筑损失 600 万元。受影响人口 12500 人，转移安置 3200 人。</p>
            </div>
            <div class="rd-section">
              <h4>三、生态影响</h4>
              <p>生态环境受到中度影响，植被覆盖率下降 15%，野生动物栖息地受损面积约 800 公顷。预计 3-6 个月可基本恢复，但部分区域需 1-2 年完成生态修复。</p>
            </div>
            <div class="rd-section">
              <h4>四、建议措施</h4>
              <p>1. 加强生态恢复监测，建立长期跟踪机制<br/>2. 推进受灾群众安置，确保基本生活保障<br/>3. 修复受损基础设施，恢复交通和通信<br/>4. 开展灾后心理疏导，关注受灾群众心理健康</p>
            </div>
          </div>
        </div>
      </div>
    </transition>

    <transition name="drawer">
      <div v-if="showLossDrawer" class="drawer-overlay" @click="showLossDrawer = false">
        <div class="drawer-content" @click.stop>
          <div class="drawer-header">
            损失分类明细
            <button class="close-drawer" @click="showLossDrawer = false">✕</button>
          </div>
          <div class="drawer-body">
            <div v-for="item in lossCategories" :key="item.name" class="lc-item">
              <span class="lc-icon">{{ item.icon }}</span>
              <div class="lc-info">
                <span class="lc-name">{{ item.name }}</span>
                <span class="lc-detail">{{ item.detail }}</span>
              </div>
              <span class="lc-val">{{ item.value }} 万元</span>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { fireAPI, agentAPI } from '../api/modules'
import * as echarts from 'echarts'

const miniTrendRef = ref<HTMLDivElement>()
const trendChartRef = ref<HTMLDivElement>()
const compareChartRef = ref<HTMLDivElement>()
const detailTrendChartRef = ref<HTMLDivElement>()

const leftCollapsed = ref(false)
const rightCollapsed = ref(false)
const activeTab = ref('report')
const timeRange = ref('24h')
const showShortTerm = ref(false)
const showLongTerm = ref(false)
const showToast = ref(false)
const toastMessage = ref('')
const showBurnedDetail = ref(false)
const showLossDetail = ref(false)
const showEcoDetail = ref(false)
const showTrendDrawer = ref(false)
const showReportDrawer = ref(false)
const showLossDrawer = ref(false)
const trendHighlight = ref(false)
const autoCompactMode = ref(false)
const manualCompactMode = ref(false)
/* 自动紧凑与手动紧凑叠加：小屏强制 compact，底部按钮继续保留手动切换。 */
const compactMode = computed({
  get: () => autoCompactMode.value || manualCompactMode.value,
  set: (value: boolean) => {
    manualCompactMode.value = value
  }
})

const reportText = ref('本次火灾影响范围较大，过火面积达1250公顷，直接经济损失约3200万元。生态环境受到中度影响，预计3-6个月可基本恢复。')

const tabs = [
  { id: 'report', label: '报告', icon: '📄' },
  { id: 'loss', label: '损失', icon: '💰' },
  { id: 'measures', label: '措施', icon: '🛡️' }
]

const measures = ref([
  { id: 1, title: '加强生态恢复监测', priority: 'high', priorityLabel: '高', status: 'pending', statusText: '未开始', statusClass: 'pending' },
  { id: 2, title: '推进受灾群众安置', priority: 'high', priorityLabel: '高', status: 'running', statusText: '进行中', statusClass: 'running' }
])

const shortTermMeasures = ref([
  '设置临时安置点',
  '清理火场残留物',
  '恢复供电供水',
  '开展安全隐患排查'
])

const longTermMeasures = ref([
  '植被恢复与造林',
  '水土保持工程',
  '野生动物栖息地修复',
  '建立灾害预警系统'
])

const burnedAreas = ref([
  { name: 'A区', value: 480 },
  { name: 'B区', value: 320 },
  { name: 'C区', value: 250 },
  { name: 'D区', value: 200 }
])

const lossDetailItems = ref([
  { name: '林业损失', value: 1200 },
  { name: '农业损失', value: 800 },
  { name: '基础设施', value: 600 },
  { name: '建筑损失', value: 600 }
])

const ecoFactors = ref([
  { name: '植被损失率', value: 45, level: 'high', desc: '大量林木被烧毁' },
  { name: '土壤退化', value: 30, level: 'medium', desc: '表层土壤有机质流失' },
  { name: '水体污染', value: 20, level: 'low', desc: '灭火用水导致轻微污染' },
  { name: '栖息地破坏', value: 55, level: 'high', desc: '野生动物栖息地大面积受损' }
])

const lossCategories = ref([
  { name: '林木资源', icon: '🌲', value: 1200, detail: '成材林 800 + 幼林 400' },
  { name: '农作物', icon: '🌾', value: 800, detail: '小麦 300 + 玉米 500' },
  { name: '道路桥梁', icon: '🛤️', value: 350, detail: '省道 200 + 乡村路 150' },
  { name: '电力设施', icon: '⚡', value: 250, detail: '输电线路 150 + 变压器 100' },
  { name: '通信设施', icon: '📡', value: 150, detail: '基站 100 + 光缆 50' },
  { name: '居民房屋', icon: '🏠', value: 450, detail: '全毁 30 栋 + 半毁 55 栋' }
])

let miniTrendChart: echarts.ECharts | null = null
let trendChart: echarts.ECharts | null = null
let compareChart: echarts.ECharts | null = null
let detailTrendChart: echarts.ECharts | null = null

function updateResponsiveLayout() {
  const width = window.innerWidth
  const height = window.innerHeight
  /* <=1366px 或 <=700px 自动启用 compact，减少固定设计稿尺寸造成的纵向溢出。 */
  autoCompactMode.value = width <= 1366 || height <= 700
  /* <=1100px 默认折叠右侧面板，给中央图表区留出完整宽度。 */
  if (width <= 1100) rightCollapsed.value = true
  nextTick(() => resizeCharts())
}

function cycleStatus(m: any) {
  const states = [
    { status: 'pending', statusText: '未开始', statusClass: 'pending' },
    { status: 'running', statusText: '进行中', statusClass: 'running' },
    { status: 'done', statusText: '已完成', statusClass: 'done' }
  ]
  const idx = states.findIndex(s => s.status === m.status)
  const next = states[(idx + 1) % states.length]
  Object.assign(m, next)
}

function generateTaskList() {
  toastMessage.value = '任务清单已生成'
  showToast.value = true
  setTimeout(() => { showToast.value = false }, 2500)
}

function exportReport() {
  toastMessage.value = '评估报告导出中...'
  showToast.value = true
  setTimeout(() => { showToast.value = false }, 2500)
}

function printPreview() {
  toastMessage.value = '正在准备打印预览'
  showToast.value = true
  setTimeout(() => { showToast.value = false }, 2500)
}

function shareReport() {
  toastMessage.value = '分享链接已复制'
  showToast.value = true
  setTimeout(() => { showToast.value = false }, 2500)
}

function refreshData() {
  toastMessage.value = '数据已刷新'
  showToast.value = true
  setTimeout(() => { showToast.value = false }, 2000)
}

function onTimeRangeChange() {
  updateTrendChart()
}

function initMiniTrend() {
  if (!miniTrendRef.value) return
  miniTrendChart = echarts.init(miniTrendRef.value)
  miniTrendChart.setOption({
    grid: { top: 5, bottom: 5, left: 5, right: 5 },
    xAxis: { type: 'category', show: false, data: ['W1', 'W2', 'W3', 'W4', 'W5', 'W6'] },
    yAxis: { type: 'value', show: false },
    series: [{
      type: 'line',
      data: [80, 75, 70, 65, 58, 52],
      smooth: true,
      lineStyle: { color: '#f59e0b', width: 2 },
      areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(245,158,11,0.3)' }, { offset: 1, color: 'rgba(245,158,11,0.02)' }] } },
      symbol: 'none'
    }]
  })
}

function initTrendChart() {
  if (!trendChartRef.value) return
  trendChart = echarts.init(trendChartRef.value)
  updateTrendChart()
}

function updateTrendChart() {
  if (!trendChart) return
  const dataMap: Record<string, number[]> = {
    '24h': [50, 120, 280, 450, 620, 780, 950, 1100, 1250],
    '7d': [200, 350, 500, 680, 850, 1000, 1150, 1250],
    '30d': [100, 200, 350, 500, 680, 850, 1000, 1150, 1250]
  }
  const labelMap: Record<string, string[]> = {
    '24h': ['06:00', '08:00', '10:00', '12:00', '14:00', '16:00', '18:00', '20:00', '22:00'],
    '7d': ['5/25', '5/26', '5/27', '5/28', '5/29', '5/30', '5/31', '6/1'],
    '30d': ['5/1', '5/5', '5/9', '5/13', '5/17', '5/21', '5/25', '5/29', '5/31']
  }
  trendChart.setOption({
    animation: true,
    animationDuration: 1200,
    animationEasing: 'cubicOut',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(20,28,40,0.9)',
      borderColor: 'rgba(255,255,255,0.1)',
      textStyle: { color: '#e2e8f0', fontSize: 12 }
    },
    grid: { top: 30, bottom: 30, left: 50, right: 20 },
    xAxis: {
      type: 'category',
      data: labelMap[timeRange.value] || labelMap['24h'],
      axisLabel: { color: '#64748b', fontSize: 10 },
      axisLine: { lineStyle: { color: 'rgba(255,255,255,0.08)' } },
      axisTick: { show: false }
    },
    yAxis: {
      type: 'value',
      name: 'hm²',
      nameTextStyle: { color: '#64748b', fontSize: 10 },
      axisLabel: { color: '#64748b', fontSize: 10 },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.04)' } },
      axisLine: { show: false },
      axisTick: { show: false }
    },
    series: [{
      type: 'line',
      data: dataMap[timeRange.value] || dataMap['24h'],
      smooth: true,
      lineStyle: { color: '#ef4444', width: 2.5 },
      areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(239,68,68,0.25)' }, { offset: 1, color: 'rgba(239,68,68,0.02)' }] } },
      symbol: 'circle',
      symbolSize: 4,
      itemStyle: { color: '#ef4444' }
    }]
  })
}

function initCompareChart() {
  if (!compareChartRef.value) return
  compareChart = echarts.init(compareChartRef.value)
  compareChart.setOption({
    animation: true,
    animationDuration: 1000,
    animationEasing: 'cubicOut',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(20,28,40,0.9)',
      borderColor: 'rgba(255,255,255,0.1)',
      textStyle: { color: '#e2e8f0', fontSize: 12 }
    },
    grid: { top: 30, bottom: 30, left: 50, right: 20 },
    xAxis: {
      type: 'category',
      data: ['1月', '3月', '5月', '7月', '9月', '11月'],
      axisLabel: { color: '#64748b', fontSize: 10 },
      axisLine: { lineStyle: { color: 'rgba(255,255,255,0.08)' } },
      axisTick: { show: false }
    },
    yAxis: {
      type: 'value',
      name: 'hm²',
      nameTextStyle: { color: '#64748b', fontSize: 10 },
      axisLabel: { color: '#64748b', fontSize: 10 },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.04)' } },
      axisLine: { show: false },
      axisTick: { show: false }
    },
    series: [
      { name: '本年', type: 'bar', data: [5, 8, 12, 15, 9, 6], itemStyle: { color: '#3b82f6', borderRadius: [4, 4, 0, 0] }, barWidth: 12 },
      { name: '去年', type: 'bar', data: [4, 6, 10, 12, 7, 5], itemStyle: { color: '#6366f1', borderRadius: [4, 4, 0, 0] }, barWidth: 12 },
      { name: '平均', type: 'bar', data: [3, 5, 8, 10, 6, 4], itemStyle: { color: 'rgba(148,163,184,0.3)', borderRadius: [4, 4, 0, 0] }, barWidth: 12 }
    ]
  })
}

function initDetailTrendChart() {
  if (!detailTrendChartRef.value) return
  detailTrendChart = echarts.init(detailTrendChartRef.value)
  detailTrendChart.setOption({
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(20,28,40,0.9)',
      borderColor: 'rgba(255,255,255,0.1)',
      textStyle: { color: '#e2e8f0', fontSize: 12 }
    },
    legend: { data: ['生态影响', '经济影响', '社会影响'], textStyle: { color: '#94a3b8', fontSize: 11 }, top: 0 },
    grid: { top: 40, bottom: 30, left: 50, right: 20 },
    xAxis: {
      type: 'category',
      data: ['W1', 'W2', 'W3', 'W4', 'W5', 'W6', 'W7', 'W8'],
      axisLabel: { color: '#64748b', fontSize: 10 },
      axisLine: { lineStyle: { color: 'rgba(255,255,255,0.08)' } },
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
      { name: '生态影响', type: 'line', data: [80, 75, 70, 65, 58, 52, 48, 45], smooth: true, lineStyle: { color: '#22c55e', width: 2 }, symbol: 'circle', symbolSize: 4 },
      { name: '经济影响', type: 'line', data: [90, 85, 80, 72, 68, 62, 58, 55], smooth: true, lineStyle: { color: '#f59e0b', width: 2 }, symbol: 'circle', symbolSize: 4 },
      { name: '社会影响', type: 'line', data: [60, 55, 50, 48, 45, 42, 40, 38], smooth: true, lineStyle: { color: '#3b82f6', width: 2 }, symbol: 'circle', symbolSize: 4 }
    ]
  })
}

function handleKeydown(e: KeyboardEvent) {
  if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement) return
  switch (e.key.toLowerCase()) {
    case 'l': leftCollapsed.value = !leftCollapsed.value; break
    case 'r': rightCollapsed.value = !rightCollapsed.value; break
    case '1': activeTab.value = 'report'; break
    case '2': activeTab.value = 'loss'; break
    case '3': activeTab.value = 'measures'; break
    case 'e': exportReport(); break
  }
}

function resizeCharts() {
  trendChart?.resize()
  compareChart?.resize()
  miniTrendChart?.resize()
}

function highlightTrendPeak() {
  trendHighlight.value = !trendHighlight.value
  if (!trendChart) return
  if (trendHighlight.value) {
    trendChart.setOption({
      series: [{
        markPoint: {
          data: [{ type: 'max', name: '峰值' }],
          symbol: 'pin',
          symbolSize: 40,
          itemStyle: { color: '#ef4444' },
          label: { color: '#fff', fontSize: 10 }
        }
      }]
    })
  } else {
    trendChart.setOption({
      series: [{ markPoint: { data: [] } }]
    })
  }
}

function handleWindowResize() {
  updateResponsiveLayout()
}

watch([leftCollapsed, rightCollapsed], () => {
  nextTick(() => {
    setTimeout(() => resizeCharts(), 250)
  })
})

async function loadData() {
  try {
    const stat = await fireAPI.getStat().catch(() => ({}))
  } catch (e) {}
}

watch(showTrendDrawer, (v) => {
  if (v) {
    nextTick(() => initDetailTrendChart())
  }
})

onMounted(() => {
  updateResponsiveLayout()
  initMiniTrend()
  initTrendChart()
  initCompareChart()
  loadData()
  window.addEventListener('resize', handleWindowResize)
})

onUnmounted(() => {
  miniTrendChart?.dispose()
  trendChart?.dispose()
  compareChart?.dispose()
  detailTrendChart?.dispose()
  window.removeEventListener('resize', handleWindowResize)
})
</script>

<style scoped>
.assess-container {
  /* 使用父级 100% 替代 100vw/100vh，避免浏览器视口计算差异产生主滚动条。 */
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
  /* 顶栏高度使用 clamp，小高度屏幕自动压缩，释放主内容高度。 */
  height: clamp(48px, 8vh, 64px);
  flex: 0 0 clamp(48px, 8vh, 64px);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: clamp(6px, 1vw, 16px);
  padding: 0 clamp(10px, 1.7vw, 32px);
  background: rgba(20, 28, 40, 0.9);
  border-bottom: 1px solid rgba(255,255,255,0.06);
  backdrop-filter: blur(16px);
}

.capsule {
  display: flex;
  align-items: center;
  /* 胶囊使用自适应 padding，防止顶栏横向溢出。 */
  padding: clamp(5px, 0.8vh, 8px) clamp(9px, 0.95vw, 18px);
  border-radius: 40px;
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(255,255,255,0.12);
  backdrop-filter: blur(10px);
  gap: clamp(4px, 0.6vw, 10px);
  cursor: pointer;
  transition: border-color 0.2s;
}

.capsule:hover { border-color: rgba(255,255,255,0.25); }
.capsule:active { transform: scale(0.97); }

.capsule-burned { border-color: rgba(239,68,68,0.3); background: rgba(239,68,68,0.06); }
.capsule-loss { border-color: rgba(245,158,11,0.2); }

.cap-icon { font-size: clamp(13px, 0.9vw, 16px); }
.cap-data { display: flex; align-items: baseline; gap: 3px; }

.cap-val {
  font-size: clamp(16px, 1.15vw, 22px);
  font-weight: 700;
  line-height: 1;
}

.capsule-burned .cap-val {
  background: linear-gradient(90deg, #fff, #fca5a5);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.capsule-loss .cap-val {
  background: linear-gradient(90deg, #fff, #fde68a);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.capsule-people .cap-val {
  background: linear-gradient(90deg, #fff, #67e8f9);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.capsule-weather .cap-val {
  background: linear-gradient(90deg, #fff, #a5b4fc);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.cap-unit { font-size: clamp(10px, 0.7vw, 12px); color: #94a3b8; }
.cap-trend { font-size: clamp(10px, 0.7vw, 12px); font-weight: 600; }
.cap-trend.up { color: #ef4444; }
.cap-trend.down { color: #22c55e; }
.cap-humidity { font-size: 10px; color: #64748b; }

.update-tag {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
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
  gap: clamp(6px, 1vh, 12px);
  overflow: hidden;
  min-height: 0;
}

.side-panel.collapsed {
  /* 折叠宽度同样使用 clamp，避免折叠态撑出视口。 */
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
  /* 卡片 padding 自适应压缩，减少多卡片纵向累积高度。 */
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

.glass-card.clickable { cursor: pointer; }
.glass-card.clickable:hover { border-color: rgba(96,165,250,0.3); background: rgba(20,28,40,0.85); }

.card-title {
  font-size: clamp(10px, 0.72vw, 13px);
  font-weight: 600;
  color: #cbd5e1;
  margin-bottom: clamp(6px, 1vh, 14px);
  letter-spacing: 0.5px;
}

.grade-row {
  display: flex;
  align-items: center;
  gap: clamp(8px, 0.9vw, 16px);
  margin-bottom: clamp(6px, 1vh, 12px);
}

.grade-badge {
  padding: clamp(5px, 0.8vh, 8px) clamp(10px, 1vw, 20px);
  border-radius: 12px;
  font-size: clamp(11px, 0.9vw, 16px);
  font-weight: 700;
}

.grade-badge.severe { background: rgba(239,68,68,0.2); color: #f87171; border: 1px solid rgba(239,68,68,0.3); }
.grade-badge.moderate { background: rgba(245,158,11,0.2); color: #fbbf24; border: 1px solid rgba(245,158,11,0.3); }
.grade-badge.light { background: rgba(34,197,94,0.2); color: #4ade80; border: 1px solid rgba(34,197,94,0.3); }

.grade-score { display: flex; align-items: baseline; gap: 2px; }

.gs-val {
  font-size: clamp(20px, 1.7vw, 32px);
  font-weight: 700;
  background: linear-gradient(90deg, #fff, #fca5a5);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.gs-max { font-size: 14px; color: #64748b; }

.severity-bar {
  height: 6px;
  background: rgba(255,255,255,0.08);
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 6px;
}

.sb-fill {
  height: 100%;
  background: linear-gradient(90deg, #f59e0b, #ef4444);
  border-radius: 3px;
}

.severity-label { font-size: clamp(9px, 0.62vw, 11px); color: #64748b; margin-bottom: clamp(4px, 0.7vh, 8px); }
.grade-summary { font-size: clamp(10px, 0.7vw, 12px); color: #94a3b8; }

.impact-items {
  display: flex;
  flex-direction: column;
  gap: clamp(6px, 1vh, 14px);
  margin-bottom: clamp(5px, 0.8vh, 10px);
  min-height: 0;
  overflow: hidden;
}

.impact-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.ii-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.ii-label { font-size: clamp(10px, 0.7vw, 12px); color: #cbd5e1; }
.ii-pct { font-size: clamp(11px, 0.8vw, 14px); font-weight: 700; }

.ii-bar {
  height: 6px;
  background: rgba(255,255,255,0.08);
  border-radius: 3px;
  overflow: hidden;
}

.ii-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s ease;
}

.ii-fill.eco { background: linear-gradient(90deg, #22c55e, #f59e0b); }
.ii-fill.econ { background: linear-gradient(90deg, #3b82f6, #f59e0b); }

.ii-desc { font-size: clamp(9px, 0.6vw, 10px); color: #64748b; }

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

.mini-chart { width: 100%; height: clamp(52px, 10vh, 80px); }

.trend-change { font-size: clamp(10px, 0.7vw, 12px); color: #94a3b8; margin-top: clamp(3px, 0.5vh, 6px); margin-bottom: clamp(3px, 0.5vh, 6px); }
.trend-change .up { color: #ef4444; font-weight: 600; }
.trend-change .down { color: #22c55e; font-weight: 600; }

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
  display: flex;
  gap: clamp(6px, 1vw, 12px);
  padding: clamp(6px, 1vh, 12px) 0;
  min-width: 0;
  min-height: 0;
}

.chart-panel {
  flex: 1;
  background: rgba(20,28,40,0.7);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 20px;
  backdrop-filter: blur(16px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
  min-height: 0;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: clamp(7px, 1vh, 12px) clamp(9px, 0.9vw, 16px);
  border-bottom: 1px solid rgba(255,255,255,0.06);
}

.ch-title { font-size: 13px; font-weight: 600; color: #cbd5e1; }

.ch-legend {
  display: flex;
  gap: clamp(6px, 0.8vw, 12px);
  font-size: clamp(9px, 0.62vw, 11px);
  color: #94a3b8;
  align-items: center;
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
  margin-right: 4px;
}

.legend-dot.red { background: #ef4444; }
.legend-dot.blue { background: #3b82f6; }
.legend-dot.indigo { background: #6366f1; }
.legend-dot.gray { background: rgba(148,163,184,0.5); }

.chart-body { flex: 1; min-height: 0; }

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
  min-height: 0;
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

.score-ring {
  position: relative;
  width: clamp(56px, 10vh, 100px);
  height: clamp(56px, 10vh, 100px);
  margin: 0 auto clamp(4px, 0.8vh, 8px);
}

.ring-svg { width: 100%; height: 100%; transform: rotate(-90deg); }

.ring-center {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.ring-val {
  font-size: clamp(15px, 1.2vw, 24px);
  font-weight: 700;
  background: linear-gradient(90deg, #fff, #fca5a5);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.ring-label { font-size: 10px; color: #64748b; }

.report-text {
  font-size: clamp(10px, 0.7vw, 12px);
  color: #94a3b8;
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.loss-items {
  display: flex;
  flex-direction: column;
  gap: clamp(5px, 0.9vh, 12px);
  margin-bottom: clamp(5px, 0.8vh, 10px);
  min-height: 0;
  overflow: hidden;
}

.loss-item {
  padding: clamp(6px, 0.9vh, 10px);
  border-radius: 12px;
  background: rgba(255,255,255,0.03);
}

.loss-item.other {
  background: rgba(255,255,255,0.02);
  padding: clamp(5px, 0.8vh, 8px) clamp(6px, 0.6vw, 10px);
}

.li-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: clamp(3px, 0.6vh, 6px);
}

.li-icon { font-size: 14px; }
.li-label { font-size: clamp(10px, 0.7vw, 12px); color: #cbd5e1; flex: 1; }
.li-val { font-size: clamp(10px, 0.75vw, 13px); font-weight: 600; color: #fde68a; }

.li-bar {
  height: 4px;
  background: rgba(255,255,255,0.08);
  border-radius: 2px;
  overflow: hidden;
  margin-bottom: 6px;
}

.li-fill {
  height: 100%;
  border-radius: 2px;
}

.li-fill.agriculture { background: linear-gradient(90deg, #f59e0b, #eab308); }
.li-fill.forest { background: linear-gradient(90deg, #22c55e, #16a34a); }

.li-ring-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.mini-ring { width: clamp(26px, 5vh, 36px); height: clamp(26px, 5vh, 36px); }
.li-pct { font-size: 11px; color: #94a3b8; }

.measure-list {
  display: flex;
  flex-direction: column;
  gap: clamp(5px, 0.8vh, 10px);
  margin-bottom: clamp(5px, 0.8vh, 10px);
  min-height: 0;
  overflow: hidden;
}

.measure-item {
  padding: clamp(6px, 0.9vh, 10px);
  border-radius: 12px;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06);
}

.mi-header {
  display: flex;
  align-items: center;
  gap: clamp(5px, 0.6vw, 8px);
  margin-bottom: clamp(4px, 0.7vh, 8px);
}

.mi-priority {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 20px;
}

.mi-priority.high { color: #f87171; background: rgba(239,68,68,0.12); }
.mi-priority.medium { color: #fbbf24; background: rgba(245,158,11,0.12); }
.mi-priority.low { color: #94a3b8; background: rgba(100,116,139,0.12); }

.mi-title { font-size: clamp(10px, 0.72vw, 13px); font-weight: 500; }

.mi-status-row { display: flex; justify-content: flex-end; }

.mi-status-btn {
  padding: 4px 12px;
  border-radius: 6px;
  border: 1px solid rgba(255,255,255,0.1);
  background: rgba(255,255,255,0.04);
  color: #94a3b8;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.2s;
}

.mi-status-btn.pending { color: #94a3b8; }
.mi-status-btn.running { color: #60a5fa; border-color: rgba(59,130,246,0.3); }
.mi-status-btn.done { color: #4ade80; border-color: rgba(34,197,94,0.3); }

.mi-status-btn:hover { background: rgba(96,165,250,0.15); }

.measure-sections {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: clamp(5px, 0.8vh, 10px);
  min-height: 0;
  overflow: hidden;
}

.ms-group { }

.ms-title {
  font-size: 12px;
  color: #64748b;
  cursor: pointer;
  padding: 4px 0;
  display: flex;
  align-items: center;
  gap: 4px;
}

.ms-title:hover { color: #94a3b8; }
.ms-arrow { font-size: 10px; }

.ms-items {
  padding-left: 12px;
  margin-top: 4px;
}

.ms-item {
  font-size: 11px;
  color: #94a3b8;
  padding: 3px 0;
}

.generate-btn {
  width: 100%;
  padding: clamp(7px, 1vh, 10px);
  border-radius: 12px;
  border: none;
  background: linear-gradient(90deg, #3b82f6, #6366f1);
  color: white;
  font-size: clamp(11px, 0.75vw, 13px);
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s;
}

.generate-btn:hover { transform: scale(0.98); }
.generate-btn:active { transform: scale(0.95); }

.bottom-bar {
  /* 底栏使用 clamp，在低高度屏幕压缩到 48px，减少纵向占用。 */
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

.bb-btn.export {
  background: linear-gradient(90deg, rgba(59,130,246,0.2), rgba(99,102,241,0.2));
  border-color: rgba(96,165,250,0.3);
}

.bb-icon { font-size: 12px; }

.time-select {
  padding: clamp(6px, 0.9vh, 8px) clamp(8px, 0.75vw, 12px);
  border-radius: 10px;
  border: 1px solid rgba(255,255,255,0.1);
  background: rgba(255,255,255,0.06);
  color: #e2e8f0;
  font-size: clamp(10px, 0.7vw, 12px);
  outline: none;
  cursor: pointer;
}

.time-select:focus { border-color: rgba(96,165,250,0.5); }

.time-select option { background: #1a2332; color: #e2e8f0; }

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

.drawer-content.wide { width: clamp(320px, 48vw, 560px); }

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
  /* 抽屉不再使用 overflow-y:auto，长文本/列表通过压缩和隐藏低优先级段落适配。 */
  overflow: hidden;
  min-height: 0;
}

.detail-chart { width: 100%; height: clamp(180px, 48vh, 300px); }

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

.eco-item {
  padding: clamp(6px, 0.9vh, 10px);
  border-radius: 10px;
  background: rgba(255,255,255,0.03);
  margin-bottom: clamp(4px, 0.7vh, 8px);
}

.eco-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.eco-name { font-size: 12px; color: #cbd5e1; }

.eco-pct { font-size: 13px; font-weight: 600; }
.eco-pct.high { color: #f87171; }
.eco-pct.medium { color: #fbbf24; }
.eco-pct.low { color: #4ade80; }

.eco-bar {
  height: 4px;
  background: rgba(255,255,255,0.08);
  border-radius: 2px;
  overflow: hidden;
  margin-bottom: 4px;
}

.eco-fill {
  height: 100%;
  border-radius: 2px;
}

.eco-fill.high { background: linear-gradient(90deg, #ef4444, #f59e0b); }
.eco-fill.medium { background: linear-gradient(90deg, #f59e0b, #eab308); }
.eco-fill.low { background: linear-gradient(90deg, #22c55e, #4ade80); }

.eco-desc { font-size: 10px; color: #64748b; }

.lc-item {
  display: flex;
  align-items: center;
  gap: clamp(5px, 0.55vw, 10px);
  padding: clamp(6px, 0.9vh, 10px);
  border-radius: 10px;
  background: rgba(255,255,255,0.03);
  margin-bottom: clamp(4px, 0.7vh, 8px);
}

.lc-icon { font-size: 14px; }
.lc-info { flex: 1; display: flex; flex-direction: column; }
.lc-name { font-size: 12px; font-weight: 500; color: #cbd5e1; }
.lc-detail { font-size: 10px; color: #64748b; }
.lc-val { font-size: 13px; font-weight: 600; color: #fde68a; }

.report-drawer-body { line-height: 1.4; }

.rd-title {
  font-size: clamp(14px, 1vw, 18px);
  font-weight: 700;
  color: #e2e8f0;
  margin-bottom: clamp(8px, 1.2vh, 16px);
}

.rd-section { margin-bottom: clamp(8px, 1.2vh, 16px); }

.rd-section h4 {
  font-size: 14px;
  font-weight: 600;
  color: #60a5fa;
  margin-bottom: 8px;
}

.rd-section p {
  font-size: clamp(10px, 0.7vw, 12px);
  color: #94a3b8;
  line-height: 1.45;
}

.drawer-enter-active, .drawer-leave-active { transition: opacity 0.2s ease; }
.drawer-enter-from, .drawer-leave-to { opacity: 0; }
.drawer-enter-from .drawer-content, .drawer-leave-to .drawer-content { transform: translateX(100%); }

/* 紧凑模式：将面板/卡片/标题压缩到规范小屏值，避免面板内部滚动。 */
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

.compact .grade-badge {
  padding: 5px 10px;
  font-size: 11px;
}

.compact .gs-val,
.compact .cap-val {
  font-size: clamp(15px, 1vw, 18px);
}

.compact .mini-chart {
  height: clamp(46px, 9vh, 60px);
}

.compact .center-area {
  flex-direction: column;
  gap: 8px;
}

.compact .chart-panel {
  border-radius: 14px;
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

.compact .cap-humidity,
.compact .cap-trend,
.compact .grade-summary,
.compact .severity-label,
.compact .ii-desc,
.compact .trend-change,
.compact .detail-link,
.compact .report-text,
.compact .li-ring-row,
.compact .measure-sections,
.compact .eco-desc,
.compact .lc-detail,
.compact .rd-section:nth-of-type(n + 3) {
  display: none;
}

/* <=1366px 自动套用 compact 同款尺寸，小屏不依赖手动切换也不会溢出。 */
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

  .grade-badge,
  .loss-item,
  .measure-item,
  .eco-item,
  .lc-item,
  .da-item {
    padding: 5px 7px;
  }

  .cap-humidity,
  .cap-trend,
  .grade-summary,
  .severity-label,
  .ii-desc,
  .trend-change,
  .detail-link,
  .report-text,
  .li-ring-row,
  .measure-sections,
  .eco-desc,
  .lc-detail,
  .rd-section:nth-of-type(n + 3) {
    display: none;
  }

  .center-area {
    flex-direction: column;
    gap: 8px;
  }
}

/* <=1100px 右侧面板默认让位，展开时作为浮层，不撑宽主布局。 */
@media (max-width: 1100px) {
  .capsule-weather,
  .update-tag,
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
    min-height: 0;
    padding: 0;
  }

  .bb-left,
  .bb-right {
    flex: 1 1 0;
  }

  .bb-btn span:not(.bb-icon),
  .bb-btn:nth-child(n + 2),
  .time-select,
  .chart-panel.right-chart,
  .loss-item:nth-child(n + 3),
  .measure-item:nth-child(n + 2) {
    display: none;
  }
}

/* <=700px 高度进一步压缩，隐藏低优先级文字，保证 600px 高度无内部滚动。 */
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

  .grade-badge,
  .loss-item,
  .measure-item,
  .eco-item,
  .lc-item,
  .da-item {
    padding: 5px 7px;
  }

  .center-area,
  .loss-items,
  .measure-list,
  .impact-items,
  .tab-inner {
    gap: 4px;
  }

  .cap-humidity,
  .cap-trend,
  .grade-summary,
  .severity-label,
  .ii-desc,
  .trend-change,
  .detail-link,
  .report-text,
  .li-ring-row,
  .measure-sections,
  .eco-desc,
  .lc-detail,
  .rd-section:nth-of-type(n + 3) {
    display: none;
  }

  .mini-chart {
    height: 44px;
  }

  .score-ring {
    width: 48px;
    height: 48px;
  }

  .detail-chart {
    height: clamp(140px, 42vh, 240px);
  }

  .drawer-body {
    padding: 6px;
  }
}

.bb-btn.compact-toggle.active { background: rgba(96,165,250,0.2); border-color: rgba(96,165,250,0.4); color: #60a5fa; }
</style>
