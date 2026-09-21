<template>
  <section class="catalog-panel" data-testid="data-catalog">
    <header class="catalog-header">
      <div>
        <span>Data Catalog</span>
        <h3>数据资产</h3>
      </div>
      <button
        class="refresh-button"
        type="button"
        title="刷新数据目录"
        aria-label="刷新数据目录"
        :disabled="loading"
        @click="loadCatalog"
      >
        ↻
      </button>
    </header>

    <p v-if="loading && !historicalCatalog" class="catalog-message">正在读取数据目录...</p>
    <p v-else-if="error" class="catalog-message error">{{ error }}</p>

    <template v-if="historicalCatalog && realtimeCatalog">
      <div class="catalog-group" data-testid="historical-assets">
        <div class="group-heading">
          <strong>历史事件数据</strong>
          <span>Dixie Fire</span>
        </div>
        <details v-for="item in historicalItems" :key="item.id" class="asset-item">
          <summary>
            <i :class="statusClass(item.status)" aria-hidden="true"></i>
            <span class="asset-title">
              <b>{{ item.name }}</b>
              <small>{{ item.type }}</small>
            </span>
            <span class="asset-value">{{ formatCount(item.count) }}</span>
          </summary>
          <dl>
            <dt>Source</dt><dd>{{ item.source }}</dd>
            <dt>Status</dt><dd :class="statusClass(item.status)">{{ item.status }}</dd>
            <dt>Time range</dt><dd>{{ formatRange(item.timeRange) }}</dd>
            <dt>In database</dt><dd>{{ formatFlag(item.inDatabase) }}</dd>
            <dt>Local files</dt><dd>{{ formatFlag(item.localFile) }}</dd>
            <dt>Notes</dt><dd>{{ item.note }}</dd>
          </dl>
        </details>
      </div>

      <div class="catalog-group" data-testid="realtime-assets">
        <div class="group-heading">
          <strong>实时 / 演示数据</strong>
          <span>{{ formatCount(realtimeStatistics.observations) }} batches</span>
        </div>
        <details v-for="item in realtimeItems" :key="item.id" class="asset-item">
          <summary>
            <i :class="statusClass(item.status)" aria-hidden="true"></i>
            <span class="asset-title">
              <b>{{ item.name }}</b>
              <small>{{ item.type }}</small>
            </span>
            <span class="asset-value">{{ formatCount(item.count) }}</span>
          </summary>
          <dl>
            <dt>Source</dt><dd>{{ item.source }}</dd>
            <dt>Status</dt><dd :class="statusClass(item.status)">{{ item.status }}</dd>
            <dt>Time range</dt><dd>{{ formatRange(item.timeRange) }}</dd>
            <dt>In database</dt><dd>{{ formatFlag(item.inDatabase) }}</dd>
            <dt>Local files</dt><dd>{{ formatFlag(item.localFile) }}</dd>
            <dt>Notes</dt><dd>{{ item.note }}</dd>
          </dl>
        </details>
      </div>
    </template>

    <p v-if="updatedAt" class="catalog-updated">Updated {{ updatedAt }}</p>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { dataCatalogAPI } from '../api/modules'

type AssetStatus = 'Available' | 'Missing' | 'Partial'
type CatalogAsset = {
  id: string
  name: string
  type: string
  source: string
  status: AssetStatus
  count?: number | null
  timeRange?: Array<string | null> | null
  inDatabase?: boolean
  localFile?: boolean
  note: string
}

const historicalCatalog = ref<any>(null)
const realtimeCatalog = ref<any>(null)
const loading = ref(false)
const error = ref('')
const updatedAt = ref('')

const historicalStatistics = computed(() => historicalCatalog.value?.statistics || {})
const realtimeStatistics = computed(() => realtimeCatalog.value?.statistics || {})

function manifest(fragment: string) {
  return historicalCatalog.value?.manifests?.find((item: any) => item.dataset_id?.includes(fragment))
}

function staticAsset(id: string) {
  return historicalCatalog.value?.local_assets?.[id] || {}
}

function availability(count: number | null | undefined, inDatabase?: boolean, localFile?: boolean): AssetStatus {
  const hasCount = typeof count === 'number' && count > 0
  const available = hasCount || inDatabase === true || localFile === true
  if (!available) return 'Missing'
  if (inDatabase === false || localFile === false) return 'Partial'
  return 'Available'
}

const historicalItems = computed<CatalogAsset[]>(() => {
  const stats = historicalStatistics.value
  const firms = manifest('firms_viirs')
  const mtbs = manifest('mtbs')
  const daily = manifest('nasa_power_daily')
  const hourly = manifest('nasa_power_hourly')
  const dem = staticAsset('dem')
  const fuel = staticAsset('fuel')
  const worldcover = staticAsset('worldcover')
  const forefire = staticAsset('forefire_input')
  const sentinel = staticAsset('sentinel2')

  return [
    {
      id: 'firms-raw',
      name: 'FIRMS raw observations',
      type: 'Historical hotspots',
      source: 'NASA FIRMS VIIRS S-NPP',
      status: availability(stats.firms_raw, stats.firms_raw > 0, firms?.local_file),
      count: stats.firms_raw,
      timeRange: [stats.firms_start, stats.firms_end],
      inDatabase: stats.firms_raw > 0,
      localFile: firms?.local_file,
      note: 'Historical source observations inside the Dixie Fire study period.'
    },
    {
      id: 'candidate-hotspots',
      name: 'Candidate hotspots',
      type: 'Derived candidates',
      source: 'FIRMS filtering pipeline',
      status: availability(stats.candidate_hotspots, stats.candidate_hotspots > 0, firms?.local_file),
      count: stats.candidate_hotspots,
      timeRange: [stats.hotspots_start, stats.hotspots_end],
      inDatabase: stats.candidate_hotspots > 0,
      localFile: firms?.local_file,
      note: 'Candidate detections; not independently confirmed fires.'
    },
    {
      id: 'hotspot-clusters',
      name: 'Ten-minute clusters',
      type: 'Aggregated hotspots',
      source: 'FIRMS candidate clustering',
      status: availability(stats.hotspot_clusters, stats.hotspot_clusters > 0, firms?.local_file),
      count: stats.hotspot_clusters,
      timeRange: [stats.clusters_start, stats.clusters_end],
      inDatabase: stats.hotspot_clusters > 0,
      localFile: firms?.local_file,
      note: 'Spatial-temporal clusters used by replay and map layers.'
    },
    {
      id: 'mtbs',
      name: 'MTBS burned area',
      type: 'Burn perimeter',
      source: 'Monitoring Trends in Burn Severity',
      status: availability(stats.burned_areas, stats.burned_areas > 0, mtbs?.local_file),
      count: stats.burned_areas,
      timeRange: [stats.burned_area_start, stats.burned_area_end],
      inDatabase: stats.burned_areas > 0,
      localFile: mtbs?.local_file,
      note: 'Final burned-area geometry used for historical validation.'
    },
    {
      id: 'weather-daily',
      name: 'Daily weather',
      type: 'Meteorological series',
      source: 'NASA POWER',
      status: availability(stats.weather_daily, stats.weather_daily > 0, daily?.local_file),
      count: stats.weather_daily,
      timeRange: [stats.weather_daily_start, stats.weather_daily_end],
      inDatabase: stats.weather_daily > 0,
      localFile: daily?.local_file,
      note: 'Daily temperature, humidity, wind and precipitation baseline.'
    },
    {
      id: 'weather-hourly',
      name: 'Hourly weather',
      type: 'Meteorological series',
      source: 'NASA POWER',
      status: availability(stats.weather_hourly, stats.weather_hourly > 0, hourly?.local_file),
      count: stats.weather_hourly,
      timeRange: [stats.weather_hourly_start, stats.weather_hourly_end],
      inDatabase: stats.weather_hourly > 0,
      localFile: hourly?.local_file,
      note: 'Hourly weather input for fire-spread preparation.'
    },
    {
      id: 'dem',
      name: 'DEM',
      type: 'Terrain raster',
      source: 'Copernicus DEM GLO-30',
      status: availability(null, undefined, dem.available),
      count: dem.file_count,
      timeRange: manifest('copernicus_dem')?.temporal_extent,
      localFile: dem.available,
      note: dem.repository_path || 'Local terrain raster.'
    },
    {
      id: 'fuel',
      name: 'Fuel / WorldCover',
      type: 'Fuel and land-cover rasters',
      source: 'ESA WorldCover 2021',
      status: fuel.available && worldcover.available ? 'Available' : (fuel.available || worldcover.available ? 'Partial' : 'Missing'),
      count: Number(fuel.file_count || 0) + Number(worldcover.file_count || 0),
      timeRange: manifest('worldcover')?.temporal_extent,
      localFile: fuel.available && worldcover.available,
      note: 'WorldCover and the derived course-demo fuel classification.'
    },
    {
      id: 'forefire-input',
      name: 'ForeFire input',
      type: 'Preparation manifest',
      source: 'Local deterministic preprocessing',
      status: availability(null, undefined, forefire.available),
      count: forefire.file_count,
      timeRange: manifest('forefire_input')?.temporal_extent,
      localFile: forefire.available,
      note: forefire.repository_path || 'ForeFire input preparation manifest.'
    },
    {
      id: 'sentinel2',
      name: 'Sentinel-2',
      type: 'Optical imagery',
      source: 'Copernicus Sentinel-2',
      status: availability(null, undefined, sentinel.available),
      count: sentinel.file_count,
      localFile: sentinel.available,
      note: sentinel.available ? 'Local Sentinel-2 assets detected.' : 'No non-empty Sentinel-2 asset is installed in this workspace.'
    }
  ]
})

const realtimeItems = computed<CatalogAsset[]>(() => {
  const stats = realtimeStatistics.value
  const items = realtimeCatalog.value?.items || []
  const nrt = items.find((item: any) => item.id === 'goes18_north_america_west') || {}
  const goes = items.find((item: any) => item.id === 'park_fire_2024_goes18_demo') || {}
  const archive = items.find((item: any) => item.id === 'firms_archive_california_nevada_2025') || {}

  return [
    {
      id: 'firms-nrt',
      name: 'FIRMS NRT',
      type: 'Latest candidate batch',
      source: nrt.latest_observation?.source || 'NASA FIRMS NRT / VIIRS',
      status: availability(nrt.latest_observation?.hotspot_count, Boolean(nrt.available), Boolean(nrt.latest_observation?.source_file)),
      count: nrt.latest_observation?.hotspot_count,
      timeRange: nrt.latest_observation?.observed_at ? [nrt.latest_observation.observed_at, nrt.latest_observation.observed_at] : null,
      inDatabase: Boolean(nrt.available),
      localFile: Boolean(nrt.latest_observation?.source_file),
      note: 'Latest locally persisted western North America candidate batch.'
    },
    {
      id: 'firms-archive',
      name: 'FIRMS archive demo',
      type: 'Three-month replay',
      source: archive.source || 'FIRMS VIIRS S-NPP',
      status: availability(archive.record_count, undefined, archive.local_file),
      count: archive.record_count,
      timeRange: archive.time_range,
      localFile: archive.local_file,
      note: 'Pre-downloaded historical data replayed as simulated daily reception.'
    },
    {
      id: 'goes-demo',
      name: 'GOES-18 demo',
      type: 'Satellite image slots',
      source: goes.source || 'GOES-18 ABI C07/C14 + FDCC',
      status: availability(goes.record_count, undefined, goes.local_file),
      count: goes.record_count,
      timeRange: goes.time_range,
      localFile: goes.local_file,
      note: 'Real satellite imagery with simulated reception and FDCC validation.'
    },
    {
      id: 'realtime-observations',
      name: 'Realtime observations',
      type: 'Observation batches',
      source: 'Member A realtime ingestion',
      status: availability(stats.observations, stats.observations > 0),
      count: stats.observations,
      timeRange: [stats.observations_start, stats.observations_end],
      inDatabase: stats.observations > 0,
      note: 'Persisted acquisition batches for supported regions.'
    },
    {
      id: 'realtime-hotspots',
      name: 'Realtime candidate hotspots',
      type: 'Candidate detections',
      source: 'FIRMS NRT / VIIRS',
      status: availability(stats.candidate_hotspots, stats.candidate_hotspots > 0),
      count: stats.candidate_hotspots,
      timeRange: [stats.hotspots_start, stats.hotspots_end],
      inDatabase: stats.candidate_hotspots > 0,
      note: 'Candidate records only; confirmation is handled separately.'
    }
  ]
})

async function loadCatalog() {
  loading.value = true
  error.value = ''
  try {
    const [historical, realtime] = await Promise.all([
      dataCatalogAPI.getHistorical(),
      dataCatalogAPI.getRealtime()
    ])
    historicalCatalog.value = historical
    realtimeCatalog.value = realtime
    updatedAt.value = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  } catch (reason: any) {
    error.value = reason?.message || '数据目录读取失败'
  } finally {
    loading.value = false
  }
}

function formatCount(value?: number | null) {
  return typeof value === 'number' ? value.toLocaleString() : '—'
}

function formatRange(value?: Array<string | null> | null) {
  if (!value?.length || !value[0]) return 'N/A'
  const compact = (raw: string | null) => raw ? raw.replace('T', ' ').replace(/:00(?:\.000)?Z$/, 'Z') : ''
  const start = compact(value[0])
  const end = compact(value[1])
  return !end || start === end ? start : `${start} – ${end}`
}

function formatFlag(value?: boolean) {
  return value === undefined ? 'N/A' : value ? 'Yes' : 'No'
}

function statusClass(status: AssetStatus) {
  return `status-${status.toLowerCase()}`
}

onMounted(loadCatalog)
</script>

<style scoped>
.catalog-panel {
  display: grid;
  gap: 12px;
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid rgba(148, 163, 184, 0.22);
}

.catalog-header,
.group-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.catalog-header > div {
  min-width: 0;
}

.catalog-header span {
  display: block;
  margin-bottom: 4px;
  color: #7dd3fc;
  font-size: 11px;
  font-weight: 800;
  text-transform: uppercase;
}

.catalog-header h3 {
  margin: 0;
  color: #f8fafc;
  font-size: 15px;
}

.refresh-button {
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  border: 1px solid rgba(103, 232, 249, 0.32);
  border-radius: 6px;
  background: #123447;
  color: #a5f3fc;
  font-size: 20px;
  line-height: 1;
  cursor: pointer;
}

.refresh-button:disabled {
  cursor: wait;
  opacity: 0.5;
}

.catalog-group {
  display: grid;
  gap: 7px;
}

.group-heading {
  padding: 0 2px 3px;
}

.group-heading strong {
  color: #dbeafe;
  font-size: 12px;
}

.group-heading span,
.catalog-updated {
  color: #7890aa;
  font-size: 10px;
}

.asset-item {
  border: 1px solid rgba(148, 163, 184, 0.16);
  border-radius: 7px;
  background: rgba(13, 28, 44, 0.78);
  overflow: hidden;
}

.asset-item summary {
  min-height: 50px;
  display: grid;
  grid-template-columns: 9px minmax(0, 1fr) auto 12px;
  align-items: center;
  gap: 8px;
  padding: 7px 9px;
  cursor: pointer;
  list-style: none;
}

.asset-item summary::-webkit-details-marker {
  display: none;
}

.asset-item summary::after {
  content: "›";
  grid-column: 4;
  grid-row: 1;
  margin-left: 5px;
  color: #71859d;
  font-size: 16px;
  transform: rotate(90deg);
}

.asset-item[open] summary::after {
  transform: rotate(-90deg);
}

.asset-item i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #64748b;
}

.asset-title {
  min-width: 0;
  display: grid;
  gap: 2px;
}

.asset-title b,
.asset-title small {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.asset-title b {
  color: #f8fafc;
  font-size: 12px;
}

.asset-title small {
  color: #8fa4bb;
  font-size: 10px;
}

.asset-value {
  color: #67e8f9;
  font-size: 11px;
  font-weight: 800;
}

.asset-item dl {
  display: grid;
  grid-template-columns: 74px minmax(0, 1fr);
  gap: 6px 8px;
  margin: 0;
  padding: 9px;
  border-top: 1px solid rgba(148, 163, 184, 0.14);
  background: rgba(5, 16, 27, 0.72);
  font-size: 10px;
  line-height: 1.45;
}

.asset-item dt {
  color: #7890aa;
}

.asset-item dd {
  min-width: 0;
  margin: 0;
  color: #c7d7e8;
  overflow-wrap: anywhere;
}

.status-available {
  color: #5eead4 !important;
}

i.status-available {
  background: #2dd4bf;
}

.status-partial {
  color: #fbbf24 !important;
}

i.status-partial {
  background: #f59e0b;
}

.status-missing {
  color: #fda4af !important;
}

i.status-missing {
  background: #fb7185;
}

.catalog-message {
  margin: 0;
  color: #93c5fd;
  font-size: 11px;
  line-height: 1.45;
}

.catalog-message.error {
  color: #fda4af;
}

.catalog-updated {
  margin: 0;
  text-align: right;
}
</style>
