<template>
  <main class="predict-workbench">
    <aside class="predict-panel control-panel">
      <header class="panel-heading">
        <span>AGENT TOOL + GIS</span>
        <h1>火势推演与空间决策</h1>
        <p>动态环境时间序列驱动的智能体工具</p>
      </header>

      <section class="work-section">
        <label for="scenario">研究场景</label>
        <select id="scenario" v-model="scenarioId">
          <option v-for="item in fireEvent.scenarios" :key="item.scenario_id" :value="item.scenario_id">
            {{ item.name || item.scenario_id }}
          </option>
        </select>
        <div class="input-source">
          <span class="source-dot"></span>
          <div>
            <strong>上游模拟输入</strong>
            <small>火点可替换，风速、风向、湿度和燃料含水率按时步更新</small>
          </div>
        </div>
        <div class="coordinate-grid">
          <label>
            <span>经度</span>
            <input v-model.number="mockPoint.longitude" type="number" step="0.000001" />
          </label>
          <label>
            <span>纬度</span>
            <input v-model.number="mockPoint.latitude" type="number" step="0.000001" />
          </label>
        </div>
        <div class="section-title input-title">
          <h2>当前气象条件</h2>
          <span>{{ isRollingRun ? '续推窗口' : '当前有效窗' }}</span>
        </div>
        <div class="weather-window-head">
          <div>
            <strong>滚动气象窗口</strong>
            <small>当前气象持续生效至下一次更新时间</small>
          </div>
          <span class="weather-window-status ready">输入完整</span>
        </div>
        <div class="weather-console">
          <div class="wind-control">
            <button ref="windDialRef" type="button" class="wind-dial" aria-label="拖动设置风吹向" @pointerdown="startWindDial">
              <span class="north">北</span>
              <span class="east">东</span>
              <span class="south">南</span>
              <span class="west">西</span>
              <i class="wind-arrow" :style="{ transform: `rotate(${normalizedWindDirection}deg)` }"></i>
              <b>{{ Math.round(normalizedWindDirection) }}°</b>
              <small>{{ windDirectionLabel }} · 吹向</small>
            </button>
            <label class="dial-number">
              <span>精确风向</span>
              <input v-model.number="forecastFrames[0].wind_direction_deg" type="number" min="0" max="359" step="5" />
            </label>
          </div>
          <div class="weather-gauges">
            <label class="weather-gauge temperature-gauge">
              <span>温度</span>
              <div class="thermometer">
                <i :style="{ height: `${temperatureRatio}%` }"></i>
              </div>
              <strong>
                {{ formatNumber(environmentInput.temperatureC, 0) }}
                <small>°C</small>
              </strong>
              <input v-model.number="environmentInput.temperatureC" type="range" min="-20" max="60" step="1" />
            </label>
            <label class="weather-gauge humidity-gauge">
              <span>相对湿度</span>
              <div class="radial-gauge" :style="gaugeStyle(forecastFrames[0].humidity_percent, 0, 100, '#38bdf8')">
                <strong>
                  {{ formatNumber(forecastFrames[0].humidity_percent, 0) }}
                  <small>%</small>
                </strong>
              </div>
              <input v-model.number="forecastFrames[0].humidity_percent" type="range" min="0" max="100" step="1" />
            </label>
            <label class="weather-gauge wind-speed-gauge">
              <span>风速</span>
              <div class="radial-gauge" :style="gaugeStyle(forecastFrames[0].wind_speed_m_s, 0, 30, '#2dd4bf')">
                <strong>
                  {{ formatNumber(forecastFrames[0].wind_speed_m_s, 1) }}
                  <small>m/s</small>
                </strong>
              </div>
              <input v-model.number="forecastFrames[0].wind_speed_m_s" type="range" min="0" max="30" step="0.5" />
            </label>
          </div>
        </div>
        <div class="environment-input-grid">
          <label>
            <span>温度 °C</span>
            <input v-model.number="environmentInput.temperatureC" type="number" min="-30" max="65" step="1" />
          </label>
          <label>
            <span>湿度 %</span>
            <input v-model.number="forecastFrames[0].humidity_percent" type="number" min="0" max="100" step="1" />
          </label>
          <label>
            <span>当前风速 m/s</span>
            <input v-model.number="forecastFrames[0].wind_speed_m_s" type="number" min="0" max="60" step="0.5" />
          </label>
          <label>
            <span>当前风向（吹向）</span>
            <input v-model.number="forecastFrames[0].wind_direction_deg" type="number" min="0" max="359" step="5" />
          </label>
          <label>
            <span>燃料含水率</span>
            <input v-model.number="environmentInput.fuelMoisture" type="number" min="0.01" max="0.8" step="0.01" />
          </label>
          <label>
            <span>火险指数 FWI</span>
            <input v-model.number="environmentInput.fireWeatherIndex" type="number" min="0" max="100" step="1" />
          </label>
          <label class="weather-update-input">
            <span>距下次气象更新（分钟）</span>
            <input v-model.number="environmentInput.nextWeatherUpdateMinutes" type="number" min="1" max="1440" step="1" />
          </label>
        </div>
        <div class="forecast-timeline">
          <div class="forecast-timeline-head">
            <span>本轮有效气象</span>
            <span>T+0 至 T+{{ environmentInput.nextWeatherUpdateMinutes }} min</span>
          </div>
          <div v-for="frame in forecastFrames" :key="frame.id" class="forecast-frame current">
            <div class="forecast-frame-label">
              <strong>当前</strong>
              <small>火场实况</small>
            </div>
            <label>
              <span>风速</span>
              <input v-model.number="frame.wind_speed_m_s" type="number" min="0" max="60" step="0.5" />
            </label>
            <label>
              <span>风向</span>
              <input v-model.number="frame.wind_direction_deg" type="number" min="0" max="359" step="5" />
            </label>
            <label>
              <span>湿度</span>
              <input v-model.number="frame.humidity_percent" type="number" min="0" max="100" step="1" />
            </label>
            <label>
              <span>降水</span>
              <input v-model.number="frame.precipitation_mm_h" type="number" min="0" max="200" step="0.1" />
            </label>
          </div>
        </div>
        <div class="model-contract">
          <span class="contract-check">✓</span>
          <div>
            <strong>动态栅格模型已就绪</strong>
            <small>DEM · ESA WorldCover · 风场 · 含水率 · 降水抑制</small>
          </div>
          <b>90 m</b>
        </div>
        <button class="primary-command" :disabled="busy" @click="runWorkflow">
          {{ busy ? '正在计算...' : '按当前气象开始栅格推演' }}
        </button>
        <details class="historical-command">
          <summary>使用真实小时气象推演（可选）</summary>
          <div>
            <strong>Dixie Fire 小时气象回放</strong>
            <small>从 PostGIS 读取真实小时气象，逐小时推进火线</small>
          </div>
          <label>
            <span>时长</span>
            <select v-model.number="historicalInput.horizonHours">
              <option :value="6">6 小时</option>
              <option :value="12">12 小时</option>
              <option :value="24">24 小时</option>
            </select>
          </label>
          <button :disabled="busy" @click="runHistoricalWorkflow">开始真实气象推演</button>
          <button :disabled="busy" @click="runCalibrationWorkflow">标定 6/12/24 小时参数</button>
        </details>
        <button class="continue-command" :disabled="!canContinue" @click="continueWorkflow">
          {{ continueButtonLabel }}
        </button>
        <button class="secondary-command" :disabled="busy || !fireEvent.spatialAnalysisRun" @click="replanForBlockedRoad">
          {{ roadBlocked ? '恢复道路并重算' : '模拟道路阻断并重算' }}
        </button>
        <div v-if="fireEvent.spreadRun" class="run-lineage">
          <span>{{ runModeLabel }}</span>
          <strong>{{ currentRunWindow }}</strong>
          <small v-if="parentRunId">父运行 {{ shortRunId(parentRunId) }}</small>
          <small v-else>根运行 {{ shortRunId(fireEvent.spreadRun.run_id) }}</small>
        </div>
        <div v-if="fireEvent.spreadRun && !historicalComparison" class="checkpoint-card">
          <div>
            <span>续推检查点</span>
            <strong>T+{{ fireEvent.spreadRun.start_minute + fireEvent.spreadRun.horizon_minutes }} min</strong>
          </div>
          <div>
            <span>当前面积</span>
            <strong>{{ formatNumber(fireEvent.spreadRun.final_area_km2, 3) }} km²</strong>
          </div>
          <small>{{ canContinue ? '最终火线已锁定，更新气象后可继续' : '等待动画到达最终火线后解锁续推' }}</small>
        </div>
        <p class="operation-message" :class="{ error: hasError }">
          {{ message }}
        </p>
      </section>

      <section v-if="historicalComparison" class="historical-comparison">
        <header>
          <div>
            <span>历史对比</span>
            <strong>真实小时气象与历史范围验证</strong>
          </div>
          <b>{{ calibration ? 'Dixie 多时窗标定' : '演示模型，未校准' }}</b>
        </header>
        <div>
          <article>
            <span>模型面积</span>
            <strong>{{ formatNumber(fireEvent.spreadRun?.final_area_km2, 3) }} km²</strong>
          </article>
          <article>
            <span>同期热点凸包</span>
            <strong>{{ formatNumber(historicalComparison.nearby_hotspot_hull_km2, 3) }} km²</strong>
          </article>
          <article>
            <span>面积偏差</span>
            <strong>{{ signedPercent(historicalComparison.area_bias_vs_hotspot_hull_percent) }}</strong>
          </article>
          <article>
            <span>空间交并比</span>
            <strong>{{ formatPercent(historicalComparison.spatial_iou_percent) }}</strong>
          </article>
          <article>
            <span>模拟区命中率</span>
            <strong>{{ formatPercent(historicalComparison.simulation_precision_percent) }}</strong>
          </article>
          <article>
            <span>热点区覆盖率</span>
            <strong>{{ formatPercent(historicalComparison.hotspot_hull_recall_percent) }}</strong>
          </article>
        </div>
        <div v-if="calibration" class="temporal-validation-metrics">
          <article>
            <span>基线得分</span>
            <strong>{{ formatNumber(calibration.baseline?.score, 3) }}</strong>
          </article>
          <article>
            <span>最佳得分</span>
            <strong>{{ formatNumber(calibration.selected?.score, 3) }}</strong>
          </article>
          <article>
            <span>最差时窗得分</span>
            <strong>{{ formatNumber(calibration.selected?.worst_window_score, 3) }}</strong>
          </article>
          <article>
            <span>基础传播倍率</span>
            <strong>{{ formatNumber(calibration.selected?.parameters?.spread_rate_multiplier, 2) }}</strong>
          </article>
          <article>
            <span>风场倍率</span>
            <strong>{{ formatNumber(calibration.selected?.parameters?.wind_influence_multiplier, 2) }}</strong>
          </article>
          <article>
            <span>地形倍率</span>
            <strong>{{ formatNumber(calibration.selected?.parameters?.terrain_influence_multiplier, 2) }}</strong>
          </article>
        </div>
        <div v-if="calibration" class="calibration-windows">
          <article v-for="item in calibration.selected?.window_metrics || []" :key="item.horizon_hours">
            <strong>{{ item.horizon_hours }}h</strong>
            <span>IoU {{ formatPercent(item.spatial_iou_percent) }}</span>
            <span>面积偏差 {{ signedPercent(item.area_bias_vs_hotspot_hull_percent) }}</span>
            <b>得分 {{ formatNumber(item.score, 3) }}</b>
          </article>
        </div>
        <div v-if="temporalValidationSummary" class="temporal-validation-metrics">
          <article>
            <span>逐时有效样本</span>
            <strong>{{ temporalValidationSummary.checkpoints_with_area_metrics }}/{{ temporalValidationSummary.checkpoint_count }}</strong>
          </article>
          <article>
            <span>平均 IoU</span>
            <strong>{{ formatPercent(temporalValidationSummary.mean_spatial_iou_percent) }}</strong>
          </article>
          <article>
            <span>平均 Hausdorff</span>
            <strong>{{ formatNumber(temporalValidationSummary.mean_hausdorff_distance_km, 2) }} km</strong>
          </article>
          <article>
            <span>平均方向误差</span>
            <strong>{{ formatNumber(temporalValidationSummary.mean_direction_error_deg, 1) }}°</strong>
          </article>
          <article>
            <span>平均半径误差</span>
            <strong>{{ formatNumber(temporalValidationSummary.mean_absolute_max_radius_error_km, 2) }} km</strong>
          </article>
        </div>
        <small>输入：{{ historicalWeatherFrameLabel }}。标定同时比较 6、12、24 小时 FIRMS 凸包；它是活跃火点范围代理，不等同于实测过火边界。</small>
      </section>

      <section class="metric-grid">
        <article>
          <span>推演引擎</span>
          <strong>{{ engineLabel }}</strong>
          <small>{{ environmentSourceLabel }}</small>
        </article>
        <article>
          <span>气象有效期</span>
          <strong>{{ weatherUpdateLabel }}</strong>
          <small>{{ fireEvent.spreadSteps.length }} 个气象有效时刻</small>
        </article>
        <article>
          <span>最终过火面积</span>
          <strong>{{ formatNumber(summary.final_fire_area_km2, 3) }}</strong>
          <small>km²</small>
        </article>
        <article>
          <span>最大蔓延距离</span>
          <strong>{{ formatNumber(summary.maximum_spread_distance_km, 3) }}</strong>
          <small>km</small>
        </article>
      </section>

      <section class="work-section timeline-section">
        <div class="section-title">
          <h2>火线时间序列</h2>
          <span>{{ fireEvent.spreadSteps.length }}</span>
        </div>
        <div v-if="fireEvent.spreadSteps.length" class="timeline-list">
          <button v-for="(step, index) in fireEvent.spreadSteps" :key="step.step_id" :class="{ active: selectedStep === index }" @click="selectStep(index)">
            <span>T+{{ step.time_minute }} min</span>
            <strong>{{ formatNumber(step.area_km2, 3) }} km²</strong>
          </button>
        </div>
        <div v-if="fireEvent.spreadSteps.length" class="playback-controls">
          <div class="playback-state">
            <span>动画</span>
            <strong>{{ playbackStatusLabel }}</strong>
          </div>
          <div class="playback-actions">
            <button type="button" :title="animationPlaying ? '暂停动画' : '播放动画'" :aria-label="animationPlaying ? '暂停动画' : '播放动画'" @click="toggleFirePlayback">
              {{ animationPlaying ? 'Ⅱ' : '▶' }}
            </button>
            <button type="button" title="跳到最终火线" aria-label="跳到最终火线" @click="skipToLatestFireline">⏭</button>
          </div>
          <div class="playback-speed" aria-label="动画速度">
            <button v-for="item in playbackSpeedOptions" :key="item.value" type="button" :class="{ active: playbackSpeed === item.value }" @click="setPlaybackSpeed(item.value)">
              {{ item.label }}
            </button>
          </div>
        </div>
        <p v-else class="empty-state">运行后显示多时步火线。</p>
      </section>

      <section class="work-section environment-section">
        <div class="section-title">
          <h2>当前时步环境</h2>
          <span>{{ selectedStep >= 0 ? `T+${selectedElapsedMinutes} min` : '--' }}</span>
        </div>
        <div v-if="selectedEnvironment" class="environment-grid">
          <div>
            <span>温度</span>
            <strong>{{ formatNumber(selectedEnvironment.temperature_c, 1) }} °C</strong>
          </div>
          <div>
            <span>湿度</span>
            <strong>{{ formatNumber(selectedEnvironment.humidity_percent, 1) }}%</strong>
          </div>
          <div>
            <span>风速</span>
            <strong>{{ formatNumber(selectedEnvironment.wind_speed_m_s, 1) }} m/s</strong>
          </div>
          <div>
            <span>风向</span>
            <strong>{{ formatNumber(selectedEnvironment.wind_direction_deg, 0) }}°</strong>
          </div>
          <div>
            <span>燃料含水率</span>
            <strong>{{ formatNumber(selectedEnvironment.fuel_moisture, 3) }}</strong>
          </div>
          <div>
            <span>火险指数</span>
            <strong>{{ formatNumber(selectedEnvironment.fire_weather_index, 1) }}</strong>
          </div>
          <template v-if="isRasterRun && rasterLandscape">
            <div>
              <span>投影坐标系</span>
              <strong>{{ rasterLandscape.crs || '--' }}</strong>
            </div>
            <div>
              <span>栅格分辨率</span>
              <strong>{{ formatNumber(rasterLandscape.resolution_m, 0) }} m</strong>
            </div>
            <div>
              <span>计算网格</span>
              <strong>{{ rasterGridLabel }}</strong>
            </div>
          </template>
          <template v-else-if="selectedLandscape">
            <div>
              <span>最大上坡坡度</span>
              <strong>{{ formatNumber(selectedLandscape.max_uphill_slope_deg, 1) }}°</strong>
            </div>
            <div>
              <span>最大下坡坡度</span>
              <strong>{{ formatNumber(selectedLandscape.max_downhill_slope_deg, 1) }}°</strong>
            </div>
          </template>
        </div>
        <p v-else class="empty-state">选择火线时步后显示对应环境输入。</p>
      </section>
    </aside>

    <section class="map-stage">
      <CesiumMap ref="mapRef" class="map" :scene-id="scenarioId" />
      <div class="map-toolbar">
        <button :class="{ active: layerState.fire }" @click="toggleLayer('fire')">火线</button>
        <button :class="{ active: layerState.impact }" @click="toggleLayer('impact')">影响对象</button>
        <button :class="{ active: layerState.route }" @click="toggleLayer('route')">应急路线</button>
        <button :class="{ active: windLayerVisible }" @click="toggleWindLayer">风场</button>
        <button class="wind-focus" @click="focusWindField">定位风场</button>
      </div>
      <div class="map-weather-strip">
        <i :style="{ transform: `rotate(${displayedWindDirection}deg)` }">↑</i>
        <div>
          <span>{{ displayedWindDirectionLabel }}向 · {{ Math.round(displayedWindDirection) }}°</span>
          <strong>{{ formatNumber(displayedWeather.wind_speed_m_s, 1) }} m/s</strong>
        </div>
        <div>
          <span>温度</span>
          <strong>{{ formatNumber(displayedWeather.temperature_c, 0) }} °C</strong>
        </div>
        <div>
          <span>湿度</span>
          <strong>{{ formatNumber(displayedWeather.humidity_percent, 0) }}%</strong>
        </div>
      </div>
      <div class="map-legend">
        <strong>地图图例</strong>
        <span>
          <i class="fireline"></i>
          当前火线
        </span>
        <span>
          <i class="fire"></i>
          火场范围
        </span>
        <span>
          <i class="risk-high"></i>
          高风险区
        </span>
        <span>
          <i class="risk-medium"></i>
          中风险区
        </span>
        <span>
          <i class="risk-low"></i>
          低风险区
        </span>
        <span>
          <i class="wind-low"></i>
          低速风场
        </span>
        <span>
          <i class="wind-medium"></i>
          中速风场
        </span>
        <span>
          <i class="wind-high"></i>
          高速风场
        </span>
        <span>
          <i class="critical"></i>
          受威胁目标
        </span>
        <small>风险区：火线范围及边缘缓冲内的综合风险</small>
      </div>
      <div v-if="roadBlocked" class="map-alert">林区巡护道路已设置为阻断，路线已重新规划</div>
    </section>

    <aside class="predict-panel analysis-panel">
      <header class="panel-heading">
        <span>RISK ASSESSMENT</span>
        <h1>风险评估</h1>
        <p>最终火线、遥感与地物暴露的综合评估</p>
      </header>

      <div class="risk-model-note">
        <strong>演示级综合风险指数</strong>
        <span>用于方案比较，尚未经过历史火灾样本校准，不作为官方灾害等级。</span>
      </div>

      <section class="impact-summary">
        <article>
          <span>受影响居民点</span>
          <strong>{{ summary.affected_settlement_count || 0 }}</strong>
        </article>
        <article>
          <span>受影响人口</span>
          <strong>{{ summary.affected_population || 0 }}</strong>
        </article>
        <article>
          <span>中断道路</span>
          <strong>{{ summary.interrupted_road_count || 0 }}</strong>
        </article>
        <article>
          <span>受影响资源</span>
          <strong>{{ summary.affected_resource_count || 0 }}</strong>
        </article>
      </section>

      <section class="work-section list-section">
        <div class="section-title">
          <h2>影响对象</h2>
          <span>{{ affectedImpacts.length }}</span>
        </div>
        <div v-if="affectedImpacts.length" class="result-list">
          <article v-for="item in affectedImpacts" :key="item.record_id">
            <div>
              <strong>{{ item.name }}</strong>
              <span>{{ impactTypeLabel(item.object_type) }} · 距火线 {{ formatNumber(item.distance_to_fire_km, 2) }} km</span>
            </div>
            <b :class="`severity-${item.severity}`">{{ severityLabel(item.severity) }}</b>
          </article>
        </div>
        <p v-else class="empty-state">等待空间影响分析结果。</p>
      </section>

      <section class="work-section list-section risk-area-section">
        <div class="section-title">
          <h2>空间风险区域</h2>
          <span>{{ riskAreas.length }}</span>
        </div>
        <div v-if="riskAreas.length" class="result-list">
          <article v-for="area in riskAreas" :key="area.properties.object_id">
            <div>
              <strong>{{ riskLabel(area.properties.risk_level) }} · {{ riskRelationLabel(area.properties.zone_relation) }}</strong>
              <span>
                风险值 {{ formatNumber(area.properties.risk_score, 0) }} ·
                {{ area.properties.grid_cell_count || area.properties.sector_count }}
                个风险网格
              </span>
              <span>
                平均火线强度
                {{ formatNumber(area.properties.mean_fire_intensity_kw_m, 0) }}
                kW/m · 最大
                {{ formatNumber(area.properties.max_fire_intensity_kw_m, 0) }}
                kW/m
              </span>
            </div>
            <b :class="`severity-${area.properties.risk_level}`">{{ riskLabel(area.properties.risk_level) }}</b>
          </article>
        </div>
        <p v-else class="empty-state">推演完成后生成空间风险区域。</p>
      </section>

      <section class="work-section list-section route-section">
        <div class="section-title">
          <h2>A* 应急路线</h2>
          <span>{{ fireEvent.emergencyRoutes.length }}</span>
        </div>
        <div v-if="fireEvent.emergencyRoutes.length" class="route-list">
          <article v-for="route in fireEvent.emergencyRoutes" :key="route.route_id">
            <div class="route-head">
              <strong>{{ route.name }}</strong>
              <b :class="`risk-${route.risk_level}`">{{ riskLabel(route.risk_level) }}</b>
            </div>
            <div class="route-metrics">
              <span>{{ formatNumber(route.distance_km, 2) }} km</span>
              <span>{{ formatNumber(route.eta_minutes, 1) }} min</span>
              <span>{{ route.status === 'replanned' ? '已重算' : '可用' }}</span>
            </div>
            <small>A* 代价面：火线距离、下风向、坡度、燃料与道路可达性</small>
          </article>
        </div>
        <p v-else class="empty-state">等待路线规划结果。</p>
      </section>
    </aside>
  </main>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import CesiumMap from '../components/CesiumMap.vue'
import { useFireEventStore } from '../stores/fireEventStore'

type LayerName = 'fire' | 'impact' | 'route'

const fireEvent = useFireEventStore()
const mapRef = ref<InstanceType<typeof CesiumMap> | null>(null)
const windDialRef = ref<HTMLButtonElement | null>(null)
const scenarioId = ref(fireEvent.selectedScenarioId || 'dixie_fire_2021')
const mockPoint = ref({
  longitude: -121.38241,
  latitude: 39.87194,
  confidence: 0.96,
})
const busy = ref(false)
const hasError = ref(false)
const message = ref('等待运行成员丙模拟链路。')
const selectedStep = ref(-1)
const roadBlocked = ref(false)
const animationPlaying = ref(false)
const animationCompleted = ref(false)
const playbackProgress = ref(0)
const playbackSpeed = ref<'fast' | 'normal' | 'slow'>('fast')
const playbackSpeedOptions = [
  { value: 'fast' as const, label: '快速', durationMs: 3200 },
  { value: 'normal' as const, label: '标准', durationMs: 5200 },
  { value: 'slow' as const, label: '慢速', durationMs: 8000 },
]
let renderedFireRunId = ''
const layerState = ref({ fire: true, impact: true, route: false })
const windLayerVisible = ref(true)
const environmentInput = ref({
  temperatureC: 30,
  fuelMoisture: 0.16,
  fireWeatherIndex: 18,
  nextWeatherUpdateMinutes: 60,
})
const historicalInput = ref({ horizonHours: 6 })
const forecastFrames = ref([
  {
    id: 'current',
    elapsed_minutes: 0,
    wind_speed_m_s: 4,
    wind_direction_deg: 315,
    humidity_percent: 32,
    precipitation_mm_h: 0,
  },
])
const normalizedWindDirection = computed(() => ((Number(forecastFrames.value[0].wind_direction_deg || 0) % 360) + 360) % 360)
const windDirectionLabel = computed(() => {
  const labels = ['北', '东北', '东', '东南', '南', '西南', '西', '西北']
  return labels[Math.round(normalizedWindDirection.value / 45) % 8]
})
const temperatureRatio = computed(() => Math.max(0, Math.min(100, ((Number(environmentInput.value.temperatureC) + 20) / 80) * 100)))

const summary = computed(() => fireEvent.spatialAnalysisRun?.summary || {})
const affectedImpacts = computed(() => fireEvent.spatialImpacts.filter((item: any) => item.affected))
const riskAreas = computed(() => fireEvent.spatialAnalysisRun?.impact_geojson?.features?.filter((feature: any) => feature?.properties?.object_type === 'risk_area') || [])
const selectedFireStep = computed(() => fireEvent.spreadSteps[selectedStep.value] || null)
const selectedEnvironment = computed(() => selectedFireStep.value?.fireline_geojson?.properties?.environment || null)
const selectedLandscape = computed(() => selectedFireStep.value?.fireline_geojson?.properties?.landscape || null)
const isRasterRun = computed(() => fireEvent.spreadRun?.engine === 'raster_agent_tool')
const rasterLandscape = computed(() => fireEvent.spreadRun?.result_summary?.landscape || selectedLandscape.value)
const rasterGridLabel = computed(() => {
  const shape = rasterLandscape.value?.grid_shape
  return Array.isArray(shape) && shape.length === 2 ? `${shape[1]} x ${shape[0]}` : '--'
})
const selectedElapsedMinutes = computed(() => Number(selectedFireStep.value?.time_minute || 0))
const parentRunId = computed(() => fireEvent.spreadRun?.result_summary?.parent_run_id || null)
const historicalComparison = computed(() => fireEvent.spreadRun?.result_summary?.comparison || null)
const displayedWeather = computed(() => {
  if (historicalComparison.value && selectedEnvironment.value) return selectedEnvironment.value
  return {
    temperature_c: environmentInput.value.temperatureC,
    humidity_percent: forecastFrames.value[0].humidity_percent,
    wind_speed_m_s: forecastFrames.value[0].wind_speed_m_s,
    wind_direction_deg: normalizedWindDirection.value,
  }
})
const displayedWindDirection = computed(() => ((Number(displayedWeather.value.wind_direction_deg || 0) % 360) + 360) % 360)
const displayedWindDirectionLabel = computed(() => {
  const labels = ['北', '东北', '东', '东南', '南', '西南', '西', '西北']
  return labels[Math.round(displayedWindDirection.value / 45) % 8]
})
const calibration = computed(() => fireEvent.spreadRun?.result_summary?.calibration || null)
const temporalValidationSummary = computed(() => fireEvent.spreadRun?.result_summary?.temporal_validation_summary || null)
const historicalWeatherFrameLabel = computed(() => {
  const run = fireEvent.spreadRun
  const count = Number(run?.result_summary?.environment_frame_count || 0)
  const start = run?.result_summary?.historical_start_at
  const end = run?.result_summary?.historical_end_at
  if (!count || !start || !end) return '数据库小时气象'
  return `${count} 个数据库小时气象帧，${String(start).slice(0, 16)} 至 ${String(end).slice(0, 16)}`
})
const isRollingRun = computed(() => fireEvent.spreadRun?.result_summary?.run_mode === 'rolling_forecast')
const runModeLabel = computed(() => {
  const mode = fireEvent.spreadRun?.result_summary?.run_mode
  if (historicalComparison.value) return '历史数据验证'
  return mode === 'rolling_forecast' ? '栅格滚动续推' : '栅格初始推演'
})
const currentRunWindow = computed(() => {
  const run = fireEvent.spreadRun
  if (!run) return '--'
  return `T+${run.start_minute} 至 T+${run.start_minute + run.horizon_minutes} min`
})
const weatherUpdateLabel = computed(() => {
  const run = fireEvent.spreadRun
  if (!run) return '--'
  const validUntil = Number(run.result_summary?.forecast_valid_until_minute ?? run.start_minute + run.horizon_minutes)
  return `T+${validUntil} min`
})
const playbackDurationMs = computed(() => playbackSpeedOptions.find((item) => item.value === playbackSpeed.value)?.durationMs ?? 3200)
const playbackStatusLabel = computed(() => {
  if (animationCompleted.value) return '最终火线已就绪'
  if (animationPlaying.value) return `播放中 ${Math.round(playbackProgress.value)}%`
  return `已暂停 ${Math.round(playbackProgress.value)}%`
})
const canContinue = computed(() => Boolean(fireEvent.spreadRun) && !historicalComparison.value && !busy.value && animationCompleted.value && !animationPlaying.value)
const continueButtonLabel = computed(() => {
  if (!fireEvent.spreadRun) return '等待首次推演'
  if (historicalComparison.value) return '历史验证结果不可续推'
  if (!animationCompleted.value) return '等待最终火线检查点'
  return '从最终火线继续推演'
})
const engineLabel = computed(() => {
  if (!fireEvent.spreadRun) return '待推演'
  if (fireEvent.spreadRun.engine === 'raster_agent_tool') return 'UTM 栅格传播工具'
  return fireEvent.spreadRun.engine === 'dynamic_agent_tool' ? '动态推演工具' : fireEvent.spreadRun.engine
})
const environmentSourceLabel = computed(() => {
  const result = fireEvent.spreadRun?.result_summary || {}
  const count = Number(result.environment_frame_count || 0)
  const source = result.environment_source
  if (!source) return '等待环境时间序列'
  if (source === 'agent_supplied_timeline') return `${count} 个智能体环境帧`
  if (source === 'database_trend_projection') return `${count} 个观测趋势环境帧`
  if (source === 'database_hourly_weather') return `${count} 个历史小时气象帧`
  return `${count} 个动态环境帧`
})

function formatNumber(value: any, digits = 2) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed.toFixed(digits) : '--'
}

function gaugeStyle(value: number, minimum: number, maximum: number, color: string) {
  const ratio = Math.max(0, Math.min(1, (Number(value) - minimum) / (maximum - minimum)))
  return {
    '--gauge-value': `${ratio * 360}deg`,
    '--gauge-color': color,
  }
}

function updateWindDirection(event: PointerEvent) {
  const rect = windDialRef.value?.getBoundingClientRect()
  if (!rect) return
  const x = event.clientX - (rect.left + rect.width / 2)
  const y = event.clientY - (rect.top + rect.height / 2)
  const direction = (Math.atan2(x, -y) * 180) / Math.PI
  forecastFrames.value[0].wind_direction_deg = (Math.round((((direction % 360) + 360) % 360) / 5) * 5) % 360
}

function startWindDial(event: PointerEvent) {
  event.preventDefault()
  const dial = windDialRef.value
  if (!dial) return
  dial.setPointerCapture(event.pointerId)
  updateWindDirection(event)
  const move = (nextEvent: PointerEvent) => updateWindDirection(nextEvent)
  const finish = () => {
    dial.removeEventListener('pointermove', move)
    dial.removeEventListener('pointerup', finish)
    dial.removeEventListener('pointercancel', finish)
  }
  dial.addEventListener('pointermove', move)
  dial.addEventListener('pointerup', finish)
  dial.addEventListener('pointercancel', finish)
}

function syncManualWindField() {
  mapRef.value?.setManualWindField?.({
    longitude: Number(mockPoint.value.longitude),
    latitude: Number(mockPoint.value.latitude),
    speed: Number(forecastFrames.value[0].wind_speed_m_s),
    directionDeg: normalizedWindDirection.value,
    radiusKm: 90,
  })
  mapRef.value?.setWindFieldVisible?.(windLayerVisible.value)
}

function syncDisplayedWindField() {
  mapRef.value?.setManualWindField?.({
    longitude: Number(mockPoint.value.longitude),
    latitude: Number(mockPoint.value.latitude),
    speed: Number(displayedWeather.value.wind_speed_m_s),
    directionDeg: displayedWindDirection.value,
    radiusKm: 90,
  })
  mapRef.value?.setWindFieldVisible?.(windLayerVisible.value)
}

function signedPercent(value: any) {
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return '--'
  return `${parsed > 0 ? '+' : ''}${parsed.toFixed(1)}%`
}

function formatPercent(value: any) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? `${parsed.toFixed(1)}%` : '--'
}

function shortRunId(value: string) {
  return value ? `${value.slice(0, 12)}...` : '--'
}

function environmentTimeline(horizonMinutes: number, source: string) {
  const input = environmentInput.value
  const frame = forecastFrames.value[0]
  return [0, horizonMinutes].map((elapsedMinutes) => ({
    elapsed_minutes: elapsedMinutes,
    temperature_c: input.temperatureC,
    humidity_percent: Number(frame.humidity_percent),
    wind_speed_m_s: Number(frame.wind_speed_m_s),
    wind_direction_deg: Number(frame.wind_direction_deg),
    fuel_moisture: input.fuelMoisture,
    fire_weather_index: input.fireWeatherIndex,
    precipitation_mm_h: Number(frame.precipitation_mm_h || 0),
    source,
  }))
}

function severityLabel(value: string) {
  return (
    (
      {
        critical: '火线内',
        high: '高威胁',
        medium: '关注',
        low: '低',
      } as Record<string, string>
    )[value] || value
  )
}

function riskLabel(value: string) {
  return ({ high: '高风险', medium: '中风险', low: '低风险' } as Record<string, string>)[value] || value
}

function riskRelationLabel(value: string) {
  return (
    (
      {
        contains_active_fireline: '活动火线带',
        burned_footprint: '过火范围',
        external_threat_buffer: '外围威胁区',
      } as Record<string, string>
    )[value] || '风险区域'
  )
}

function impactTypeLabel(value: string) {
  return (
    (
      {
        settlement: '居民点',
        facility: '设施',
        road: '道路',
        power: '输电设施',
        watchtower: '瞭望塔',
        water_source: '水源',
      } as Record<string, string>
    )[value] || value
  )
}

function routeCoordinates(route: any): [number, number][] {
  return route?.geometry?.geojson?.coordinates || []
}

function handleFireFrame(payload: { index: number; total: number; progress: number }) {
  playbackProgress.value = payload.progress
  const nextIndex = Math.max(0, Math.min(fireEvent.spreadSteps.length - 1, payload.index))
  const stepChanged = selectedStep.value !== nextIndex
  selectedStep.value = nextIndex
  if (stepChanged && historicalComparison.value) nextTick(syncDisplayedWindField)
}

function handleFirePlaybackState(playing: boolean) {
  animationPlaying.value = playing
}

function handleFirePlaybackComplete() {
  animationPlaying.value = false
  animationCompleted.value = true
  playbackProgress.value = 100
  selectedStep.value = Math.max(0, fireEvent.spreadSteps.length - 1)
  if (!busy.value) {
    message.value = '最终火线检查点已就绪，可更新气象条件后继续推演。'
  }
}

function renderMap(options: { replayFire?: boolean; autoPlay?: boolean } = {}) {
  const map = mapRef.value
  if (!map) return
  map.clearDemoEntities?.()
  map.clearHotspots?.()

  const center: [number, number] = [mockPoint.value.longitude, mockPoint.value.latitude]
  map.addHotspotGeoJson?.({
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        properties: { name: '模拟确认火点', source: 'upstream_mock' },
        geometry: { type: 'Point', coordinates: center },
      },
    ],
  })

  const currentRunId = String(fireEvent.spreadRun?.run_id || '')
  if (!layerState.value.fire) {
    map.clearFireFronts?.()
    renderedFireRunId = ''
    animationPlaying.value = false
  } else if (fireEvent.forefireResult?.geojson?.features?.length && (options.replayFire || renderedFireRunId !== currentRunId)) {
    animationCompleted.value = false
    animationPlaying.value = false
    playbackProgress.value = 0
    selectedStep.value = 0
    map.addFireFrontTimeline?.(fireEvent.forefireResult.geojson, {
      durationMs: playbackDurationMs.value,
      autoPlay: options.autoPlay !== false,
      onFrame: handleFireFrame,
      onPlaybackState: handleFirePlaybackState,
      onComplete: handleFirePlaybackComplete,
    })
    renderedFireRunId = currentRunId
    if (options.autoPlay === false) {
      map.setFireTimelineProgress?.(100)
    }
  }

  if (layerState.value.impact) {
    affectedImpacts.value.forEach((item: any) => {
      if (item.geometry?.type !== 'Point') return
      const color = item.severity === 'critical' ? '#ef4444' : item.severity === 'high' ? '#f59e0b' : '#38bdf8'
      map.addDemoPoint?.({
        name: item.name,
        label: item.name,
        position: item.geometry.coordinates,
        color,
        size: item.severity === 'critical' ? 15 : 11,
      })
    })
  }

  const riskDrawOrder: Record<string, number> = { low: 0, medium: 1, high: 2 }
  ;[...riskAreas.value]
    .sort((a: any, b: any) => (riskDrawOrder[a.properties?.risk_level] ?? 0) - (riskDrawOrder[b.properties?.risk_level] ?? 0))
    .forEach((area: any) => {
      const coordinates = area.geometry?.coordinates
      if (!Array.isArray(coordinates) || !Array.isArray(coordinates[0]) || coordinates[0].length < 3) return
      const colors: Record<string, string> = {
        high: '#ef4444',
        medium: '#f59e0b',
        low: '#38bdf8',
      }
      map.addDemoArea?.({
        name: `${riskLabel(area.properties?.risk_level)} · ${riskRelationLabel(area.properties?.zone_relation)}`,
        coordinates,
        color: colors[area.properties?.risk_level] || '#94a3b8',
      })
    })

  if (layerState.value.route) {
    const colors: Record<string, string> = {
      rescue_approach: '#38bdf8',
      evacuation: '#22c55e',
      evacuation_backup: '#f59e0b',
    }
    fireEvent.emergencyRoutes.forEach((route: any) => {
      const coordinates = routeCoordinates(route)
      if (coordinates.length < 2) return
      map.addDemoRoute?.({
        name: route.name,
        coordinates,
        color: colors[route.route_type] || '#e2e8f0',
        width: route.route_type === 'evacuation' ? 7 : 5,
        arrow: true,
      })
    })
  }
  // 风险面通常只覆盖火场周边几公里，使用研究区总览高度会让它几乎不可见。
  map.flyTo?.({ center, zoom: riskAreas.value.length ? 14 : 11.5 })
}

async function ensureEvent() {
  const currentScenario = fireEvent.eventDetail?.scenario_id
  if (fireEvent.eventId && currentScenario === scenarioId.value) return
  await fireEvent.startSimulatedEvent({
    scenario_id: scenarioId.value,
    name: '成员丙火势推演模拟事件',
    ignition_point: mockPoint.value,
    metadata: {
      input_source: 'upstream_mock',
      owner: 'member/wydze',
      simulated: true,
    },
  })
}

async function runWorkflow() {
  busy.value = true
  hasError.value = false
  message.value = '正在准备模拟火点与环境快照...'
  try {
    await ensureEvent()
    message.value = '正在调用动态火情推演工具...'
    const weatherUpdateMinutes = Math.max(1, Number(environmentInput.value.nextWeatherUpdateMinutes || 1))
    await fireEvent.createSpreadRun({
      ignition_point: mockPoint.value,
      input_source: 'upstream_mock',
      run_mode: 'initial_forecast',
      environment_timeline: environmentTimeline(weatherUpdateMinutes, 'manual_initial_forecast'),
      initial_radius_m: 187.5,
      raster_resolution_m: 90,
      simulation_buffer_km: 25,
      wind_direction_convention: 'spread_toward',
    })
    message.value = '正在计算影响对象和 A* 应急路线...'
    await fireEvent.createSpatialAnalysis({
      include_routes: false,
      threat_buffer_km: 0.55,
      blocked_road_ids: roadBlocked.value ? ['road_forest_01'] : [],
    })
    selectedStep.value = 0
    message.value = `计算已完成，正在快速播放至 ${weatherUpdateMinutes} 分钟后的火线。`
    await nextTick()
    renderMap({ autoPlay: true })
  } catch (error: any) {
    hasError.value = true
    message.value = error?.message || '计算失败，请检查后端服务。'
  } finally {
    busy.value = false
  }
}

async function runHistoricalWorkflow() {
  busy.value = true
  hasError.value = false
  message.value = '正在读取 Dixie Fire 小时气象与真实地形燃料栅格...'
  try {
    mockPoint.value = {
      longitude: -121.38241,
      latitude: 39.87194,
      confidence: 0.95,
    }
    await fireEvent.createHistoricalSpreadRun(
      {
        horizon_hours: historicalInput.value.horizonHours,
        raster_resolution_m: 90,
        simulation_buffer_km: 25,
        initial_radius_m: 187.5,
        hotspot_comparison_radius_km: 20,
        wind_direction_convention: 'meteorological_from',
      },
      'dixie_fire_2021',
    )
    message.value = '正在基于栅格火场计算空间风险...'
    await fireEvent.createSpatialAnalysis(
      {
        include_routes: false,
        threat_buffer_km: 0.55,
      },
      'dixie_fire_2021',
    )
    selectedStep.value = 0
    message.value = `已使用 Dixie Fire 数据库小时气象完成 ${historicalInput.value.horizonHours} 小时推演。`
    await nextTick()
    renderMap({ autoPlay: true })
  } catch (error: any) {
    hasError.value = true
    message.value = error?.message || '历史栅格回放失败，请检查数据和后端服务。'
  } finally {
    busy.value = false
  }
}

async function runCalibrationWorkflow() {
  busy.value = true
  hasError.value = false
  message.value = '正在用同期 FIRMS 热点凸包比较候选参数...'
  try {
    await fireEvent.calibrateHistoricalSpreadRun(
      {
        horizon_hours: 24,
        raster_resolution_m: 90,
        simulation_buffer_km: 25,
        initial_radius_m: 187.5,
        hotspot_comparison_radius_km: 20,
        wind_direction_convention: 'meteorological_from',
      },
      'dixie_fire_2021',
    )
    selectedStep.value = 0
    message.value = '多时窗参数标定完成，已加载 6/12/24 小时平均评分最高的模拟火线。'
    await nextTick()
    renderMap({ autoPlay: true })
  } catch (error: any) {
    hasError.value = true
    message.value = error?.message || 'FIRMS 参数标定失败，请检查热点、气象和栅格数据。'
  } finally {
    busy.value = false
  }
}

async function continueWorkflow() {
  const previousRunId = fireEvent.spreadRun?.run_id
  if (!previousRunId) return

  busy.value = true
  hasError.value = false
  message.value = '正在从当前最终火线应用新环境继续推演...'
  try {
    const weatherUpdateMinutes = Math.max(1, Number(environmentInput.value.nextWeatherUpdateMinutes || 1))
    await fireEvent.createSpreadRun({
      continue_from_run_id: previousRunId,
      run_mode: 'rolling_forecast',
      input_source: 'manual_environment_update',
      environment_timeline: environmentTimeline(weatherUpdateMinutes, 'manual_rolling_update'),
      raster_resolution_m: 90,
      simulation_buffer_km: 25,
      wind_direction_convention: 'spread_toward',
    })
    message.value = '新火线已生成，正在重算影响对象和 A* 路线...'
    await fireEvent.createSpatialAnalysis({
      include_routes: false,
      threat_buffer_km: 0.55,
      blocked_road_ids: roadBlocked.value ? ['road_forest_01'] : [],
    })
    selectedStep.value = 0
    message.value = `续推计算已完成，正在播放 ${shortRunId(previousRunId)} 之后的新火线。`
    await nextTick()
    renderMap({ autoPlay: true })
  } catch (error: any) {
    hasError.value = true
    message.value = error?.message || '续推失败，请检查父运行和环境输入。'
  } finally {
    busy.value = false
  }
}

async function replanForBlockedRoad() {
  busy.value = true
  hasError.value = false
  roadBlocked.value = !roadBlocked.value
  message.value = roadBlocked.value ? '正在绕开阻断道路重新规划...' : '正在恢复道路条件重新规划...'
  try {
    await fireEvent.createSpatialAnalysis({
      threat_buffer_km: 0.55,
      blocked_road_ids: roadBlocked.value ? ['road_forest_01'] : [],
    })
    message.value = roadBlocked.value ? '道路阻断情景重算完成。' : '道路条件已恢复并完成重算。'
    await nextTick()
    renderMap()
  } catch (error: any) {
    roadBlocked.value = !roadBlocked.value
    hasError.value = true
    message.value = error?.message || '路线重算失败。'
  } finally {
    busy.value = false
  }
}

function selectStep(index: number) {
  selectedStep.value = index
  const progress = fireEvent.spreadSteps.length <= 1 ? 1 : index / (fireEvent.spreadSteps.length - 1)
  mapRef.value?.pauseFireTimeline?.()
  animationPlaying.value = false
  animationCompleted.value = index === fireEvent.spreadSteps.length - 1
  mapRef.value?.setFireTimelineProgress?.(progress * 100)
  if (historicalComparison.value) nextTick(syncDisplayedWindField)
}

function toggleFirePlayback() {
  if (animationPlaying.value) {
    mapRef.value?.pauseFireTimeline?.()
    return
  }
  if (animationCompleted.value) {
    animationCompleted.value = false
    playbackProgress.value = 0
  }
  mapRef.value?.playFireTimeline?.()
}

function skipToLatestFireline() {
  mapRef.value?.setFireTimelineProgress?.(100)
}

function setPlaybackSpeed(value: 'fast' | 'normal' | 'slow') {
  playbackSpeed.value = value
  mapRef.value?.setFireTimelineDuration?.(playbackDurationMs.value)
}

function toggleLayer(layer: LayerName) {
  layerState.value[layer] = !layerState.value[layer]
  renderMap({ autoPlay: false })
}

function toggleWindLayer() {
  windLayerVisible.value = !windLayerVisible.value
  mapRef.value?.setWindFieldVisible?.(windLayerVisible.value)
}

function focusWindField() {
  windLayerVisible.value = true
  mapRef.value?.focusWindField?.({
    center: [mockPoint.value.longitude, mockPoint.value.latitude],
    zoom: 11.5,
  })
}

onMounted(async () => {
  await nextTick()
  syncManualWindField()
  try {
    await fireEvent.loadScenarios()
    if (fireEvent.eventId) {
      await Promise.allSettled([fireEvent.loadLatestSpreadRun(), fireEvent.loadLatestSpatialAnalysis(), fireEvent.loadClockState()])
      await nextTick()
      renderMap({ autoPlay: false })
    }
  } catch (error) {
    console.warn('Backend scenario data is unavailable; keeping the local weather visualization active.', error)
  }
})

watch(scenarioId, (value) => {
  const scenario = fireEvent.scenarios.find((item: any) => item.scenario_id === value)
  if (!scenario) return
  mockPoint.value = {
    longitude: Number(scenario.longitude),
    latitude: Number(scenario.latitude),
    confidence: 0.96,
  }
})

watch(
  () => [forecastFrames.value[0].wind_speed_m_s, forecastFrames.value[0].wind_direction_deg, mockPoint.value.longitude, mockPoint.value.latitude],
  () => nextTick(syncManualWindField),
)

watch(
  () => [fireEvent.forefireResult, fireEvent.spatialAnalysisRun, fireEvent.emergencyRoutes],
  () => {
    if (busy.value) return
    nextTick(() => renderMap())
  },
  { deep: true },
)
</script>

<style scoped>
.predict-workbench {
  width: 100%;
  height: 100%;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(300px, 21vw) minmax(520px, 1fr) minmax(360px, 26vw);
  overflow: hidden;
  color: #e8f2fb;
  background: #07111b;
}

.predict-panel {
  min-width: 0;
  min-height: 0;
  overflow-y: auto;
  padding: 16px;
  background: #0a1926;
}

.control-panel {
  border-right: 1px solid rgba(125, 211, 252, 0.18);
}
.analysis-panel {
  border-left: 1px solid rgba(45, 212, 191, 0.2);
  background: #091a22;
}
.analysis-panel .panel-heading h1 {
  font-size: 0;
}
.analysis-panel .panel-heading h1::after {
  content: '风险评估';
  font-size: 20px;
}

.panel-heading {
  margin-bottom: 14px;
}
.panel-heading span {
  color: #67e8f9;
  font-size: 11px;
  font-weight: 800;
}
.panel-heading h1 {
  margin: 5px 0 3px;
  font-size: 20px;
  letter-spacing: 0;
}
.panel-heading p,
.empty-state,
.operation-message {
  color: #8fa6ba;
  font-size: 12px;
  line-height: 1.5;
}

.work-section {
  display: grid;
  gap: 10px;
  padding: 12px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 8px;
  background: rgba(4, 15, 25, 0.66);
}
.work-section + .work-section {
  margin-top: 12px;
}
.work-section > label,
.coordinate-grid label span {
  color: #a8bacb;
  font-size: 12px;
}

select,
input,
button {
  min-width: 0;
  min-height: 36px;
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 6px;
  background: #0d2130;
  color: #edf6ff;
  font: inherit;
}
select,
input {
  width: 100%;
  padding: 0 9px;
}
button {
  cursor: pointer;
  font-weight: 700;
}
button:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.input-source {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 9px;
  border: 1px solid rgba(245, 158, 11, 0.26);
  border-radius: 7px;
  background: rgba(120, 53, 15, 0.16);
}
.source-dot {
  width: 8px;
  height: 8px;
  flex: 0 0 8px;
  border-radius: 50%;
  background: #f59e0b;
  box-shadow: 0 0 8px rgba(245, 158, 11, 0.7);
}
.input-source div {
  min-width: 0;
  display: grid;
  gap: 2px;
}
.input-source strong {
  color: #fcd34d;
  font-size: 12px;
}
.input-source small {
  color: #bca477;
  font-size: 10px;
}
.landscape-source {
  min-width: 0;
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 3px 8px;
  padding: 8px 9px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-left: 3px solid #64748b;
  background: rgba(30, 41, 59, 0.28);
}
.landscape-source.active {
  border-left-color: #22c55e;
  background: rgba(20, 83, 45, 0.2);
}
.landscape-source span {
  color: #a7f3d0;
  font-size: 11px;
  font-weight: 800;
}
.landscape-source strong {
  min-width: 0;
  color: #ecfdf5;
  font-size: 11px;
  text-align: right;
  word-break: break-word;
}
.landscape-source small {
  grid-column: 1 / -1;
  color: #93b6a1;
  font-size: 10px;
}

.coordinate-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.coordinate-grid label {
  display: grid;
  gap: 5px;
}
.input-title {
  margin-top: 2px;
}
.environment-input-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}
.environment-input-grid label {
  min-width: 0;
  display: grid;
  gap: 5px;
}
.environment-input-grid span {
  color: #a8bacb;
  font-size: 11px;
}
.weather-update-input {
  grid-column: 1 / -1;
}
.weather-window-head,
.forecast-timeline-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.weather-window-head > div {
  min-width: 0;
  display: grid;
  gap: 2px;
}
.weather-window-head strong {
  color: #e0f2fe;
  font-size: 12px;
}
.weather-window-head small,
.forecast-timeline-head span {
  color: #8da9bb;
  font-size: 10px;
}
.weather-window-status {
  flex: 0 0 auto;
  padding: 4px 7px;
  border: 1px solid currentColor;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 800;
}
.weather-window-status.ready {
  color: #5eead4;
}
.weather-window-status.warning {
  color: #fbbf24;
}
.weather-window-status.rain {
  color: #7dd3fc;
}
.weather-console {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 10px;
  padding: 10px;
  border: 1px solid rgba(56, 189, 248, 0.2);
  background: rgba(8, 31, 46, 0.8);
}
.wind-control {
  display: grid;
  grid-template-columns: 124px minmax(0, 1fr);
  gap: 12px;
  align-items: center;
  padding-bottom: 10px;
  border-bottom: 1px solid rgba(125, 211, 252, 0.16);
}
.wind-dial {
  position: relative;
  width: 124px;
  height: 124px;
  min-height: 124px;
  padding: 0;
  border-radius: 50%;
  border-color: rgba(125, 211, 252, 0.45);
  background: radial-gradient(circle at center, #0b2232 0 42%, transparent 43%), repeating-conic-gradient(from -2deg, rgba(186, 230, 253, 0.6) 0 1deg, transparent 1deg 15deg), #071722;
  touch-action: none;
}
.wind-dial span {
  position: absolute;
  color: #9fc6d9;
  font-size: 9px;
  line-height: 1;
}
.wind-dial .north {
  top: 7px;
  left: 50%;
  transform: translateX(-50%);
}
.wind-dial .east {
  right: 7px;
  top: 50%;
  transform: translateY(-50%);
}
.wind-dial .south {
  bottom: 7px;
  left: 50%;
  transform: translateX(-50%);
}
.wind-dial .west {
  left: 7px;
  top: 50%;
  transform: translateY(-50%);
}
.wind-arrow {
  position: absolute;
  left: calc(50% - 2px);
  bottom: 50%;
  width: 4px;
  height: 44px;
  border-radius: 2px;
  background: #f97316;
  box-shadow: 0 0 8px rgba(249, 115, 22, 0.65);
  transform-origin: 50% 100%;
}
.wind-arrow::before {
  content: '';
  position: absolute;
  top: -2px;
  left: 50%;
  width: 10px;
  height: 10px;
  border-top: 3px solid #fff7ed;
  border-right: 3px solid #fff7ed;
  transform: translateX(-50%) rotate(-45deg);
}
.wind-dial b {
  position: absolute;
  top: 47px;
  left: 0;
  width: 100%;
  color: #f8fafc;
  font-size: 18px;
}
.wind-dial small {
  position: absolute;
  top: 70px;
  left: 0;
  width: 100%;
  color: #7dd3fc;
  font-size: 9px;
}
.dial-number {
  display: grid;
  gap: 3px;
  align-self: center;
}
.dial-number span,
.weather-gauge > span {
  color: #8da9bb;
  font-size: 9px;
}
.dial-number input {
  min-height: 29px;
  font-size: 11px;
}
.weather-gauges {
  min-width: 0;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}
.weather-gauge.wind-speed-gauge {
  order: -1;
}
.weather-gauge {
  min-width: 0;
  display: grid;
  grid-template-rows: auto 58px auto;
  justify-items: center;
  gap: 5px;
}
.weather-gauge input[type='range'] {
  min-height: 20px;
  height: 20px;
  padding: 0;
  accent-color: #2dd4bf;
}
.radial-gauge {
  --gauge-value: 0deg;
  --gauge-color: #38bdf8;
  position: relative;
  display: grid;
  width: 58px;
  height: 58px;
  place-items: center;
  border-radius: 50%;
  background: conic-gradient(var(--gauge-color) var(--gauge-value), #193142 0);
}
.radial-gauge::after {
  content: '';
  position: absolute;
  inset: 6px;
  border-radius: 50%;
  background: #0a1d2a;
}
.radial-gauge strong,
.temperature-gauge > strong {
  position: relative;
  z-index: 1;
  color: #f8fafc;
  font-size: 13px;
}
.radial-gauge small,
.temperature-gauge strong small {
  margin-left: 1px;
  color: #8da9bb;
  font-size: 8px;
}
.temperature-gauge {
  grid-template-rows: auto 58px auto auto;
}
.thermometer {
  position: relative;
  align-self: center;
  width: 15px;
  height: 50px;
  overflow: hidden;
  border: 2px solid #7893a5;
  border-radius: 8px 8px 10px 10px;
  background: #102837;
}
.thermometer i {
  position: absolute;
  right: 3px;
  bottom: 3px;
  left: 3px;
  min-height: 4px;
  border-radius: 4px;
  background: linear-gradient(#f59e0b, #ef4444);
}
.forecast-timeline {
  display: grid;
  gap: 8px;
  padding-top: 2px;
}
.forecast-timeline-head {
  align-items: baseline;
}
.forecast-timeline-head span:first-child {
  color: #cbd5e1;
  font-size: 11px;
  font-weight: 800;
}
.forecast-frame {
  display: grid;
  grid-template-columns: 64px repeat(4, minmax(0, 1fr));
  gap: 6px;
  align-items: end;
  padding: 8px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-left: 3px solid #64748b;
  background: rgba(15, 35, 49, 0.8);
}
.forecast-frame.current {
  border-left-color: #2dd4bf;
}
.forecast-frame.next {
  border-left-color: #f59e0b;
}
.forecast-frame-label {
  display: grid;
  align-self: center;
  gap: 3px;
}
.forecast-frame-label strong {
  color: #f8fafc;
  font-size: 11px;
}
.forecast-frame-label small,
.forecast-frame label span {
  color: #8da9bb;
  font-size: 9px;
}
.forecast-frame label {
  display: grid;
  gap: 3px;
  min-width: 0;
}
.forecast-frame input {
  min-height: 30px;
  padding: 0 5px;
  font-size: 11px;
}
.model-contract {
  display: grid;
  grid-template-columns: 20px minmax(0, 1fr) auto;
  gap: 7px;
  align-items: center;
  padding: 8px 9px;
  border: 1px solid rgba(34, 197, 94, 0.25);
  background: rgba(20, 83, 45, 0.16);
}
.contract-check {
  display: grid;
  width: 18px;
  height: 18px;
  place-items: center;
  border-radius: 50%;
  color: #052e16;
  background: #4ade80;
  font-size: 12px;
  font-weight: 900;
}
.model-contract div {
  display: grid;
  gap: 2px;
  min-width: 0;
}
.model-contract strong {
  color: #bbf7d0;
  font-size: 11px;
}
.model-contract small {
  color: #86b89a;
  font-size: 9px;
}
.model-contract b {
  color: #86efac;
  font-size: 11px;
}
.primary-command {
  background: #0f766e;
  border-color: #2dd4bf;
}
.historical-command {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 82px;
  gap: 8px;
  padding: 10px;
  border: 1px solid rgba(56, 189, 248, 0.3);
  border-left: 3px solid #38bdf8;
  background: rgba(12, 74, 110, 0.2);
}
.historical-command > div {
  min-width: 0;
  display: grid;
  gap: 3px;
}
.historical-command strong {
  color: #e0f2fe;
  font-size: 12px;
}
.historical-command small,
.historical-command label span {
  color: #8fb9ce;
  font-size: 10px;
}
.historical-command label {
  display: grid;
  gap: 4px;
}
.historical-command button {
  grid-column: 1 / -1;
  min-height: 36px;
  color: #ecfeff;
  border-color: #38bdf8;
  background: #075985;
}
.historical-comparison {
  display: grid;
  gap: 9px;
  margin: 12px 0;
  padding: 11px;
  border: 1px solid rgba(56, 189, 248, 0.25);
  border-left: 3px solid #38bdf8;
  background: #0b2030;
}
.historical-comparison header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.historical-comparison header div {
  display: grid;
  gap: 2px;
}
.historical-comparison header span,
.historical-comparison article span,
.historical-comparison > small {
  color: #8da9bb;
  font-size: 10px;
}
.historical-comparison header strong {
  color: #e0f2fe;
  font-size: 13px;
}
.historical-comparison header b {
  color: #fde68a;
  font-size: 10px;
}
.historical-comparison > div {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 7px;
}
.historical-comparison article {
  min-width: 0;
  display: grid;
  gap: 3px;
  padding: 8px;
  background: #0d293b;
}
.historical-comparison article strong {
  color: #f8fafc;
  font-size: 13px;
  word-break: break-word;
}
.continue-command {
  color: #ecfeff;
  background: #9a3412;
  border-color: #fb923c;
}
.secondary-command {
  background: #164e63;
  border-color: #38bdf8;
}
.run-lineage {
  min-width: 0;
  display: grid;
  grid-template-columns: auto 1fr;
  align-items: center;
  gap: 3px 8px;
  padding: 8px 9px;
  border-left: 3px solid #fb923c;
  background: rgba(124, 45, 18, 0.2);
}
.run-lineage span {
  color: #fed7aa;
  font-size: 11px;
  font-weight: 800;
}
.run-lineage strong {
  color: #fff7ed;
  font-size: 11px;
  text-align: right;
}
.run-lineage small {
  grid-column: 1 / -1;
  color: #c8a98f;
  font-size: 10px;
}
.checkpoint-card {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 7px;
  padding: 9px;
  border: 1px solid rgba(251, 146, 60, 0.3);
  background: rgba(124, 45, 18, 0.14);
}
.checkpoint-card > div {
  display: grid;
  gap: 3px;
}
.checkpoint-card span,
.checkpoint-card small {
  color: #c8a98f;
  font-size: 10px;
}
.checkpoint-card strong {
  color: #ffedd5;
  font-size: 13px;
}
.checkpoint-card small {
  grid-column: 1 / -1;
}
.operation-message.error {
  color: #fca5a5;
}

.metric-grid,
.impact-summary {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin: 12px 0;
}
.metric-grid article,
.impact-summary article {
  min-height: 80px;
  display: grid;
  align-content: center;
  gap: 4px;
  padding: 10px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  border-radius: 8px;
  background: #0d2232;
}
.metric-grid span,
.metric-grid small,
.impact-summary span {
  color: #91a8bb;
  font-size: 11px;
}
.metric-grid strong,
.impact-summary strong {
  color: #f8fafc;
  font-size: 20px;
  word-break: break-word;
}
.impact-summary strong {
  color: #5eead4;
  font-size: 24px;
}
.risk-model-note {
  display: grid;
  gap: 4px;
  padding: 9px 10px;
  border-left: 3px solid #f59e0b;
  background: rgba(120, 53, 15, 0.18);
}
.risk-model-note strong {
  color: #fde68a;
  font-size: 12px;
}
.risk-model-note span {
  color: #c7b79a;
  font-size: 10px;
  line-height: 1.45;
}

.section-title,
.route-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.section-title h2 {
  margin: 0;
  font-size: 14px;
}
.section-title > span {
  color: #67e8f9;
  font-size: 12px;
}
.timeline-list,
.result-list,
.route-list,
.landcover-list {
  display: grid;
  gap: 7px;
}
.timeline-list button {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 38px;
  padding: 0 9px;
  color: #9fb4c7;
  background: #0c1d2b;
  border-color: rgba(148, 163, 184, 0.14);
}
.timeline-list button.active {
  color: #ecfeff;
  border-color: #22d3ee;
  background: #164e63;
}
.playback-controls {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  padding-top: 3px;
}
.playback-state {
  min-width: 0;
  display: grid;
  gap: 2px;
}
.playback-state span {
  color: #829bad;
  font-size: 10px;
}
.playback-state strong {
  color: #dff7ff;
  font-size: 11px;
}
.playback-actions {
  display: flex;
  gap: 5px;
}
.playback-actions button {
  width: 36px;
  min-height: 34px;
  color: #cffafe;
  border-color: rgba(34, 211, 238, 0.32);
  background: #103246;
  font-size: 13px;
}
.playback-speed {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  padding: 3px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 6px;
  background: #081722;
}
.playback-speed button {
  min-height: 29px;
  color: #829bad;
  border-color: transparent;
  background: transparent;
  font-size: 10px;
}
.playback-speed button.active {
  color: #ecfeff;
  border-color: rgba(34, 211, 238, 0.3);
  background: #155e75;
}

.map-stage {
  position: relative;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  background: #02070d;
}
.map {
  position: absolute;
  inset: 0;
}
.map-toolbar,
.map-legend,
.map-alert {
  position: absolute;
  z-index: 5;
  border: 1px solid rgba(186, 230, 253, 0.2);
  border-radius: 7px;
  background: rgba(3, 12, 21, 0.84);
  backdrop-filter: blur(8px);
}
.route-section {
  display: none;
}
.map-toolbar {
  top: 14px;
  left: 14px;
  display: flex;
  gap: 5px;
  padding: 5px;
}
.map-toolbar button {
  min-height: 30px;
  padding: 0 10px;
  color: #8fa6ba;
  background: transparent;
  border-color: transparent;
  font-size: 12px;
}
.map-toolbar button.active {
  color: #ecfeff;
  background: #155e75;
  border-color: #22d3ee;
}
.map-toolbar button.wind-focus {
  color: #bae6fd;
  border-left-color: rgba(125, 211, 252, 0.35);
}
.map-toolbar button:nth-child(3) {
  display: none;
}
.map-weather-strip {
  position: absolute;
  z-index: 5;
  top: 14px;
  right: 14px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 10px;
  border: 1px solid rgba(186, 230, 253, 0.2);
  border-radius: 7px;
  background: rgba(3, 12, 21, 0.84);
  backdrop-filter: blur(8px);
}
.map-weather-strip > i {
  display: grid;
  width: 28px;
  height: 28px;
  place-items: center;
  color: #fb923c;
  font-size: 25px;
  font-style: normal;
}
.map-weather-strip div {
  display: grid;
  gap: 1px;
  padding-left: 10px;
  border-left: 1px solid rgba(148, 163, 184, 0.18);
}
.map-weather-strip span {
  color: #86a4b8;
  font-size: 9px;
}
.map-weather-strip strong {
  color: #f8fafc;
  font-size: 11px;
}
.map-legend {
  left: 14px;
  bottom: 14px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, auto));
  gap: 8px 13px;
  max-width: min(360px, calc(100% - 28px));
  padding: 10px 12px;
  color: #cbd5e1;
  font-size: 11px;
}
.map-legend strong {
  grid-column: 1 / -1;
  color: #f8fafc;
  font-size: 12px;
}
.map-legend span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.map-legend i {
  display: inline-block;
  width: 9px;
  height: 9px;
  border-radius: 2px;
}
.map-legend .fireline {
  width: 13px;
  height: 3px;
  border-radius: 0;
  background: #fff;
  box-shadow: 0 0 0 1px #ef4444;
}
.map-legend .fire {
  background: rgba(239, 68, 68, 0.78);
}
.map-legend .risk-high {
  background: #ef4444;
}
.map-legend .risk-medium {
  background: #f59e0b;
}
.map-legend .risk-low {
  background: #38bdf8;
}
.map-legend .wind-low {
  background: #38bdf8;
}
.map-legend .wind-medium {
  background: #22c55e;
}
.map-legend .wind-high {
  background: #facc15;
}
.map-legend .critical {
  background: #f59e0b;
}
.map-legend .rescue {
  background: #38bdf8;
}
.map-legend .evacuation {
  background: #22c55e;
}
.map-legend small {
  grid-column: 1 / -1;
  color: #93a9ba;
  line-height: 1.4;
}
.map-alert {
  top: 14px;
  right: 14px;
  padding: 9px 12px;
  color: #fde68a;
  border-color: rgba(245, 158, 11, 0.38);
  background: rgba(69, 26, 3, 0.86);
  font-size: 12px;
}

.result-list article,
.route-list article {
  padding: 10px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-radius: 7px;
  background: #0b2029;
}
.result-list article {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.result-list article > div {
  min-width: 0;
  display: grid;
  gap: 3px;
}
.result-list strong,
.route-head strong {
  font-size: 13px;
}
.result-list span,
.route-metrics,
.route-list small {
  color: #91a8bb;
  font-size: 11px;
}
.result-list b,
.route-head b {
  flex: 0 0 auto;
  padding: 3px 6px;
  border-radius: 4px;
  font-size: 10px;
}
.severity-critical,
.risk-high {
  color: #fecaca;
  background: rgba(220, 38, 38, 0.22);
}
.severity-high,
.risk-medium {
  color: #fde68a;
  background: rgba(217, 119, 6, 0.2);
}
.severity-medium,
.risk-low {
  color: #a7f3d0;
  background: rgba(5, 150, 105, 0.2);
}
.route-list article {
  display: grid;
  gap: 8px;
}
.route-metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;
}
.route-metrics span {
  padding: 5px;
  text-align: center;
  border-radius: 4px;
  background: rgba(15, 118, 110, 0.16);
}
.landcover-list div {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  padding-bottom: 7px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
  font-size: 12px;
}
.landcover-list span {
  color: #9fb4c7;
}
.landcover-list strong {
  color: #e2e8f0;
}

.environment-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 7px;
}
.environment-grid div {
  min-width: 0;
  display: grid;
  gap: 3px;
  padding: 7px 8px;
  border-radius: 6px;
  background: rgba(14, 116, 144, 0.13);
}
.environment-grid span {
  color: #8fa6ba;
  font-size: 10px;
}
.environment-grid strong {
  color: #dff7ff;
  font-size: 12px;
  word-break: break-word;
}

@media (max-width: 1180px) {
  .predict-workbench {
    grid-template-columns: 280px minmax(430px, 1fr) 330px;
  }
}
@media (max-width: 900px) {
  .predict-workbench {
    height: auto;
    grid-template-columns: 1fr;
    overflow: auto;
  }
  .map-stage {
    min-height: 520px;
    order: -1;
  }
  .predict-panel {
    overflow: visible;
  }
}
</style>
