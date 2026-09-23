<template>
  <div class="cesium-map-shell">
    <div ref="containerRef" class="cesium-map"></div>
    <canvas v-if="showWindField" ref="windHeatCanvasRef" class="wind-heat-canvas" aria-hidden="true"></canvas>
    <canvas v-if="showWindField" ref="windCanvasRef" class="wind-field-canvas" aria-hidden="true"></canvas>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import * as Cesium from 'cesium'
import 'cesium/Build/Cesium/Widgets/widgets.css'
import { DEFAULT_MAP_CENTER, WIND_VIEW_CENTER, WIND_VIEW_HEIGHT } from '../stores/fireEventStore'

type LngLat = [number, number]

const props = withDefaults(
  defineProps<{
    longitude?: number
    latitude?: number
    height?: number
    sceneId?: string
    showWindField?: boolean
  }>(),
  {
    longitude: WIND_VIEW_CENTER[0],
    latitude: WIND_VIEW_CENTER[1],
    height: WIND_VIEW_HEIGHT,
    sceneId: 'dixie_fire_2021',
    showWindField: true,
  },
)

const containerRef = ref<HTMLDivElement>()
const windHeatCanvasRef = ref<HTMLCanvasElement>()
const windCanvasRef = ref<HTMLCanvasElement>()
let viewer: Cesium.Viewer | null = null
let hotspotEntities: Cesium.Entity[] = []
let fireFrontEntities: Cesium.Entity[] = []
let demoEntities: Cesium.Entity[] = []
let fireParticleSystem: Cesium.ParticleSystem | null = null
let fireAnimationTimer: ReturnType<typeof setInterval> | null = null
let activeFireFrameIndex = 0
let activeFireElapsedSeconds = 0
let activeFireRings: LngLat[][] = []
let fireTimelineFrames: FireFrame[] = []
let fireHistoryEntities: Array<{
  entity: Cesium.Entity
  elapsedSeconds: number
}> = []
let fireTimelineOptions: FireTimelineOptions = {}
let lastFireAnimationTick = 0
let fireTimelineCompletedNotified = false
let imageryOverlayLayer: Cesium.ImageryLayer | null = null
let vectorOverlayLayer: Cesium.ImageryLayer | null = null
let nirEntities: Cesium.Entity[] = []
let windField: WindFieldResponse | null = null
let activeWindStepIndex = 0
let windVisible = props.showWindField
let windAnimationFrame: number | null = null
let windParticles: WindParticle[] = []
let windHeatFrameCounter = 0
let terrainEnabled = true
let mapClickHandler: Cesium.ScreenSpaceEventHandler | null = null
let mapEditMode: 'NORMAL' | 'SELECT_COMMAND_POST' | 'SELECT_STAGING_AREA' | 'ADD_RESOURCE_POINT' = 'NORMAL'

type FireFrame = {
  rings: LngLat[][]
  step: number
  elapsedSeconds: number
  areaSquareMeters: number
}

type FireTimelineOptions = {
  durationMs?: number
  autoPlay?: boolean
  onFrame?: (payload: { index: number; total: number; elapsedSeconds: number; progress: number }) => void
  onPlaybackState?: (playing: boolean) => void
  onComplete?: () => void
}

type WindVector = {
  lng: number
  lat: number
  u: number
  v: number
  speed: number
  direction_deg: number
}

type WindStep = {
  step: number
  elapsed_minutes: number
  vectors: WindVector[]
}

type WindFieldResponse = {
  event_id: string
  bounds: [number, number, number, number]
  max_speed: number
  time_steps: WindStep[]
}

type WindParticle = {
  lng: number
  lat: number
  phase: number
}

function featureElapsedSeconds(feature: any, fallback = 0) {
  const direct = Number(feature?.properties?.elapsed_seconds)
  if (Number.isFinite(direct)) return direct
  const outputFile = String(feature?.properties?.output_file || '')
  const match = outputFile.match(/front_t(\d+)/)
  return match ? Number(match[1]) : fallback
}

function flyHome() {
  if (!viewer) return
  viewer.camera.setView({
    destination: Cesium.Cartesian3.fromDegrees(props.longitude, props.latitude, props.height),
    orientation: {
      heading: Cesium.Math.toRadians(18),
      pitch: Cesium.Math.toRadians(-62),
      roll: 0,
    },
  })
}

function zoomToHeight(zoom?: number) {
  if (!zoom) return props.height
  return Math.max(6000, 3000000 / Math.pow(2, Math.max(0, zoom - 7)))
}

function flyTo(options?: { center?: [number, number]; zoom?: number; height?: number }) {
  if (!viewer) return
  const [lng, lat] = options?.center ?? [props.longitude, props.latitude]
  viewer.camera.flyTo({
    destination: Cesium.Cartesian3.fromDegrees(lng, lat, options?.height ?? zoomToHeight(options?.zoom)),
    orientation: {
      heading: Cesium.Math.toRadians(18),
      pitch: Cesium.Math.toRadians(-62),
      roll: 0,
    },
    duration: 0.8,
  })
}

function focusWindField(options?: { center?: [number, number]; zoom?: number }) {
  if (!props.showWindField) return
  windVisible = true
  windHeatCanvasRef.value?.classList.remove('is-hidden')
  windCanvasRef.value?.classList.remove('is-hidden')
  if (windField && !windAnimationFrame) startWindAnimation()
  flyTo({ center: options?.center, zoom: options?.zoom ?? 11.5 })
}

function resize() {
  viewer?.resize()
}

function zoomIn() {
  viewer?.camera.zoomIn(props.height * 0.18)
}

function zoomOut() {
  viewer?.camera.zoomOut(props.height * 0.18)
}

function clearHotspots() {
  if (!viewer) return
  hotspotEntities.forEach((entity) => viewer?.entities.remove(entity))
  hotspotEntities = []
}

function clearFireFronts() {
  if (!viewer) return
  pauseFireTimeline()
  if (fireParticleSystem) {
    viewer.scene.primitives.remove(fireParticleSystem)
    fireParticleSystem = null
  }
  activeFireFrameIndex = 0
  activeFireRings = []
  fireTimelineFrames = []
  fireHistoryEntities = []
  fireTimelineOptions = {}
  fireTimelineCompletedNotified = false
  fireFrontEntities.forEach((entity) => viewer?.entities.remove(entity))
  fireFrontEntities = []
}

function clearDemoEntities() {
  if (!viewer) return
  demoEntities.forEach((entity) => viewer?.entities.remove(entity))
  demoEntities = []
}

function cancelMapPointSelection() {
  mapClickHandler?.destroy()
  mapClickHandler = null
  mapEditMode = 'NORMAL'
}

function beginMapPointSelection(
  mode: 'SELECT_COMMAND_POST' | 'SELECT_STAGING_AREA' | 'ADD_RESOURCE_POINT',
  callback: (point: { longitude: number; latitude: number; mode: string }) => void,
) {
  if (!viewer) return
  cancelMapPointSelection()
  mapEditMode = mode
  mapClickHandler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas)
  mapClickHandler.setInputAction((movement: { position: Cesium.Cartesian2 }) => {
    if (!viewer || mapEditMode === 'NORMAL') return
    const ray = viewer.camera.getPickRay(movement.position)
    const cartesian = ray ? viewer.scene.globe.pick(ray, viewer.scene) : undefined
    if (!cartesian) return
    const cartographic = Cesium.Cartographic.fromCartesian(cartesian)
    callback({
      longitude: Cesium.Math.toDegrees(cartographic.longitude),
      latitude: Cesium.Math.toDegrees(cartographic.latitude),
      mode: mapEditMode,
    })
    cancelMapPointSelection()
  }, Cesium.ScreenSpaceEventType.LEFT_CLICK)
}

function addHotspotGeoJson(geojson: any) {
  if (!viewer || !geojson?.features?.length) return
  clearHotspots()

  geojson.features
    .filter((feature: any) => feature?.geometry?.type === 'Point')
    .forEach((feature: any) => {
      const [lng, lat] = feature.geometry.coordinates
      const entity = viewer!.entities.add({
        name: feature.properties?.name || 'High-risk fire hotspot',
        position: Cesium.Cartesian3.fromDegrees(lng, lat, 80),
        point: {
          pixelSize: 18,
          color: Cesium.Color.RED.withAlpha(0.95),
          outlineColor: Cesium.Color.WHITE,
          outlineWidth: 2,
          heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        },
        label: {
          text: '高危火点',
          font: '14px sans-serif',
          fillColor: Cesium.Color.WHITE,
          outlineColor: Cesium.Color.BLACK,
          outlineWidth: 3,
          style: Cesium.LabelStyle.FILL_AND_OUTLINE,
          pixelOffset: new Cesium.Cartesian2(0, -28),
          heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        },
      })
      hotspotEntities.push(entity)
    })
}

function addDemoPoint(options: {
  name: string
  position: LngLat
  color?: string
  label?: string
  size?: number
  symbol?: 'point' | 'command' | 'staging' | 'team' | 'approach' | 'target'
}) {
  if (!viewer) return
  const color = Cesium.Color.fromCssColorString(options.color || '#38bdf8')
  const symbol = options.symbol || 'point'
  const entity = viewer.entities.add({
    name: options.name,
    position: Cesium.Cartesian3.fromDegrees(options.position[0], options.position[1], 120),
    ...(symbol === 'point' ? {
      point: {
        pixelSize: options.size || 12,
        color: color.withAlpha(0.95),
        outlineColor: Cesium.Color.WHITE.withAlpha(0.85),
        outlineWidth: 2,
        heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
    } : {
      billboard: {
        image: operationalSymbolTexture(symbol, options.color || '#38bdf8'),
        width: options.size || 24,
        height: options.size || 24,
        verticalOrigin: Cesium.VerticalOrigin.CENTER,
        heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
    }),
    label: {
      text: options.label || options.name,
      font: '12px sans-serif',
      fillColor: Cesium.Color.WHITE,
      outlineColor: Cesium.Color.BLACK,
      outlineWidth: 3,
      style: Cesium.LabelStyle.FILL_AND_OUTLINE,
      pixelOffset: new Cesium.Cartesian2(0, -24),
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      disableDepthTestDistance: Number.POSITIVE_INFINITY,
    },
  })
  demoEntities.push(entity)
}

function operationalSymbolTexture(symbol: 'command' | 'staging' | 'team' | 'approach' | 'target', color: string) {
  const canvas = document.createElement('canvas')
  canvas.width = 64
  canvas.height = 64
  const ctx = canvas.getContext('2d')
  if (!ctx) return canvas
  ctx.clearRect(0, 0, 64, 64)
  ctx.shadowColor = color
  ctx.shadowBlur = 12
  ctx.fillStyle = color
  ctx.strokeStyle = 'rgba(255,255,255,0.94)'
  ctx.lineWidth = 3
  ctx.beginPath()
  if (symbol === 'command') {
    ctx.moveTo(32, 7); ctx.lineTo(56, 32); ctx.lineTo(32, 57); ctx.lineTo(8, 32)
  } else if (symbol === 'staging') {
    ctx.rect(12, 12, 40, 40)
  } else if (symbol === 'team') {
    ctx.moveTo(32, 8); ctx.lineTo(57, 53); ctx.lineTo(7, 53)
  } else if (symbol === 'approach') {
    ctx.moveTo(32, 7); ctx.lineTo(52, 19); ctx.lineTo(52, 45); ctx.lineTo(32, 57); ctx.lineTo(12, 45); ctx.lineTo(12, 19)
  } else {
    ctx.moveTo(32, 7); ctx.lineTo(54, 16); ctx.lineTo(49, 50); ctx.lineTo(32, 58); ctx.lineTo(15, 50); ctx.lineTo(10, 16)
  }
  ctx.closePath()
  ctx.fill()
  ctx.stroke()
  return canvas
}

function addDemoRoute(options: { name: string; coordinates: LngLat[]; color?: string; width?: number; arrow?: boolean }) {
  if (!viewer || options.coordinates.length < 2) return
  const routeColor = Cesium.Color.fromCssColorString(options.color || '#60a5fa')
  const entity = viewer.entities.add({
    name: options.name,
    polyline: {
      // 路径贴地绘制，避免三维地形开启后固定椭球高度被山体遮挡。
      positions: ringToGroundPositions(options.coordinates),
      width: options.width || 4,
      material: new Cesium.PolylineGlowMaterialProperty({
        glowPower: 0.18,
        color: routeColor.withAlpha(0.86),
      }),
      clampToGround: true,
      disableDepthTestDistance: Number.POSITIVE_INFINITY,
    },
  })
  demoEntities.push(entity)

  if (options.arrow) {
    const end = options.coordinates[options.coordinates.length - 1]
    const arrowEntity = viewer.entities.add({
      name: `${options.name}-arrow`,
      position: Cesium.Cartesian3.fromDegrees(end[0], end[1]),
      billboard: {
        image: arrowTexture(options.color || '#60a5fa'),
        width: 28,
        height: 28,
        verticalOrigin: Cesium.VerticalOrigin.CENTER,
        heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
      label: {
        text: options.name,
        font: '12px sans-serif',
        fillColor: Cesium.Color.WHITE,
        outlineColor: Cesium.Color.BLACK,
        outlineWidth: 3,
        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
        pixelOffset: new Cesium.Cartesian2(0, -26),
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
    })
    demoEntities.push(arrowEntity)
  }
}

function arrowTexture(color: string) {
  const canvas = document.createElement('canvas')
  canvas.width = 64
  canvas.height = 64
  const ctx = canvas.getContext('2d')
  if (!ctx) return canvas
  ctx.clearRect(0, 0, 64, 64)
  ctx.shadowColor = color
  ctx.shadowBlur = 14
  ctx.fillStyle = color
  ctx.beginPath()
  ctx.moveTo(50, 32)
  ctx.lineTo(18, 14)
  ctx.lineTo(26, 32)
  ctx.lineTo(18, 50)
  ctx.closePath()
  ctx.fill()
  ctx.strokeStyle = 'rgba(255,255,255,0.88)'
  ctx.lineWidth = 3
  ctx.stroke()
  return canvas
}

function polygonCentroid(coordinates: LngLat[]): LngLat {
  const sum = coordinates.reduce((acc, [lng, lat]) => ({ lng: acc.lng + lng, lat: acc.lat + lat }), { lng: 0, lat: 0 })
  return [sum.lng / coordinates.length, sum.lat / coordinates.length]
}

function addDemoArea(options: { name: string; coordinates: LngLat[] | LngLat[][]; color?: string; label?: string }) {
  if (!viewer || options.coordinates.length < 1) return
  const rings = Array.isArray(options.coordinates[0]?.[0]) ? (options.coordinates as LngLat[][]) : [options.coordinates as LngLat[]]
  const outerRing = rings[0]
  if (!outerRing || outerRing.length < 3) return
  const color = Cesium.Color.fromCssColorString(options.color || '#22c55e')
  const entity = viewer.entities.add({
    name: options.name,
    polygon: {
      // ABC 分区贴地显示，避免被三维地形深度测试盖住。
      hierarchy: new Cesium.PolygonHierarchy(
        ringToGroundPositions(outerRing),
        rings.slice(1).map((ring) => new Cesium.PolygonHierarchy(ringToGroundPositions(ring))),
      ),
      material: color.withAlpha(0.36),
      outline: true,
      outlineColor: color.withAlpha(0.98),
      clampToGround: true,
    },
  })
  demoEntities.push(entity)

  // Ground polygons can lose their outline against Cesium terrain. Keep a
  // separate bright polyline so risk boundaries remain readable at a glance.
  const boundaryEntities = rings.map((ring, index) =>
    viewer!.entities.add({
      name: `${options.name}-boundary-${index + 1}`,
      polyline: {
        positions: ringToGroundPositions(ring),
        width: 4,
        material: new Cesium.PolylineGlowMaterialProperty({
          glowPower: 0.12,
          color: color.withAlpha(1.0),
        }),
        clampToGround: true,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
    }),
  )
  demoEntities.push(...boundaryEntities)

  if (options.label) {
    const center = polygonCentroid(outerRing)
    const labelEntity = viewer.entities.add({
      name: `${options.name}-label`,
      position: Cesium.Cartesian3.fromDegrees(center[0], center[1]),
      label: {
        text: options.label,
        font: 'bold 13px sans-serif',
        fillColor: Cesium.Color.WHITE,
        outlineColor: Cesium.Color.BLACK,
        outlineWidth: 4,
        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
        heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
    })
    demoEntities.push(labelEntity)
  }
}

function removeLayerIfPresent(layer: Cesium.ImageryLayer | null) {
  if (viewer && layer) viewer.imageryLayers.remove(layer, true)
}

function setImageryOverlayVisible(visible: boolean) {
  if (!viewer) return
  if (!visible) {
    removeLayerIfPresent(imageryOverlayLayer)
    imageryOverlayLayer = null
    return
  }
  if (imageryOverlayLayer) return
  const provider = new Cesium.UrlTemplateImageryProvider({
    url: 'https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    credit: 'Esri World Imagery',
  })
  imageryOverlayLayer = viewer.imageryLayers.addImageryProvider(provider)
  imageryOverlayLayer.alpha = 0.78
  imageryOverlayLayer.brightness = 1.08
  imageryOverlayLayer.contrast = 1.08
}

function setVectorOverlayVisible(visible: boolean) {
  if (!viewer) return
  if (!visible) {
    removeLayerIfPresent(vectorOverlayLayer)
    vectorOverlayLayer = null
    return
  }
  if (vectorOverlayLayer) return
  const provider = new Cesium.UrlTemplateImageryProvider({
    url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    credit: 'OpenStreetMap contributors',
  })
  vectorOverlayLayer = viewer.imageryLayers.addImageryProvider(provider)
  vectorOverlayLayer.alpha = 0.42
}

function clearNirSimulationLayer() {
  if (!viewer) return
  nirEntities.forEach((entity) => viewer?.entities.remove(entity))
  nirEntities = []
}

function setNirSimulationVisible(visible: boolean, options: { hotspotVisible?: boolean } = {}) {
  if (!viewer) return
  clearNirSimulationLayer()
  if (!visible || !options.hotspotVisible) return

  const [lng, lat] = [101.269444, 28.530278]
  const burnedRing: LngLat[] = [
    [lng - 0.0175, lat + 0.0068],
    [lng - 0.0098, lat + 0.0162],
    [lng + 0.0038, lat + 0.0185],
    [lng + 0.0176, lat + 0.0106],
    [lng + 0.0215, lat - 0.0028],
    [lng + 0.0112, lat - 0.0168],
    [lng - 0.0058, lat - 0.0184],
    [lng - 0.0192, lat - 0.0076],
  ]

  const vegetationEntity = viewer.entities.add({
    name: '近红外-植被响应区',
    polygon: {
      // 贴地绘制，避免三维地形打开后固定高度面被地形遮挡或悬浮。
      hierarchy: new Cesium.PolygonHierarchy(ringToGroundPositions(burnedRing)),
      material: Cesium.Color.fromCssColorString('#c026d3').withAlpha(0.36),
      outline: true,
      outlineColor: Cesium.Color.fromCssColorString('#f0abfc').withAlpha(0.95),
      clampToGround: true,
    },
  })

  const fireCoreEntity = viewer.entities.add({
    name: '近红外-高温核心',
    position: Cesium.Cartesian3.fromDegrees(lng, lat),
    ellipse: {
      semiMajorAxis: 520,
      semiMinorAxis: 420,
      rotation: Cesium.Math.toRadians(24),
      material: Cesium.Color.fromCssColorString('#fff7ad').withAlpha(0.58),
      outline: true,
      outlineColor: Cesium.Color.fromCssColorString('#fb923c').withAlpha(0.95),
      height: 0,
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
    },
  })

  const smokeEdgeEntity = viewer.entities.add({
    name: '近红外-烟羽暗化边缘',
    position: Cesium.Cartesian3.fromDegrees(lng - 0.0028, lat + 0.0032),
    ellipse: {
      semiMajorAxis: 1650,
      semiMinorAxis: 860,
      rotation: Cesium.Math.toRadians(-18),
      material: Cesium.Color.fromCssColorString('#3b0764').withAlpha(0.38),
      outline: true,
      outlineColor: Cesium.Color.fromCssColorString('#a855f7').withAlpha(0.48),
      height: 0,
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
    },
  })

  const heatHaloEntity = viewer.entities.add({
    name: '近红外-500米复核范围',
    position: Cesium.Cartesian3.fromDegrees(lng, lat),
    ellipse: {
      semiMajorAxis: 1450,
      semiMinorAxis: 1450,
      material: Cesium.Color.fromCssColorString('#ef4444').withAlpha(0.22),
      outline: true,
      outlineColor: Cesium.Color.fromCssColorString('#f97316').withAlpha(0.78),
      height: 0,
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
    },
  })

  nirEntities = [vegetationEntity, fireCoreEntity, smokeEdgeEntity, heatHaloEntity]
}

function ringsFromFeature(feature: any): LngLat[][] {
  const geometry = feature?.geometry
  if (geometry?.type === 'Polygon') {
    return [geometry.coordinates?.[0]].filter(Array.isArray)
  }
  if (geometry?.type === 'MultiPolygon') {
    return geometry.coordinates?.map((polygon: any) => polygon?.[0]).filter(Array.isArray) ?? []
  }
  return []
}

function ringToPositions(ring: LngLat[], height = 0) {
  return ring.map(([lng, lat]) => Cesium.Cartesian3.fromDegrees(lng, lat, height))
}

function ringToGroundPositions(ring: LngLat[]) {
  // 火线和过火面直接使用经纬度贴地绘制，避免三维地形打开后固定高度图层悬浮。
  return ring.map(([lng, lat]) => Cesium.Cartesian3.fromDegrees(lng, lat))
}

function ignitionRing(center: LngLat = DEFAULT_MAP_CENTER, radiusDegrees = 0.00028, samples = 96): LngLat[] {
  const [lng, lat] = center
  return Array.from({ length: samples }, (_, index) => {
    const angle = (Math.PI * 2 * index) / samples
    return [lng + Math.cos(angle) * radiusDegrees, lat + Math.sin(angle) * radiusDegrees]
  })
}

function ringCentroid(ring: LngLat[]) {
  if (!ring.length) return { lng: DEFAULT_MAP_CENTER[0], lat: DEFAULT_MAP_CENTER[1] }
  const sum = ring.reduce((acc, [lng, lat]) => ({ lng: acc.lng + lng, lat: acc.lat + lat }), { lng: 0, lat: 0 })
  return { lng: sum.lng / ring.length, lat: sum.lat / ring.length }
}

function resampleRingByAngle(ring: LngLat[], samples = 128): LngLat[] {
  if (!ring.length) return ignitionRing(DEFAULT_MAP_CENTER, 0.00028, samples)
  const center = ringCentroid(ring)
  const closed = ring.length > 2 && ring[0][0] === ring[ring.length - 1][0] && ring[0][1] === ring[ring.length - 1][1] ? ring.slice(0, -1) : ring
  return Array.from({ length: samples }, (_, index) => {
    const angle = (Math.PI * 2 * index) / samples
    const direction = { x: Math.cos(angle), y: Math.sin(angle) }
    let best = closed[0]
    let bestScore = -Infinity
    for (const point of closed) {
      const vx = point[0] - center.lng
      const vy = point[1] - center.lat
      const distance = Math.hypot(vx, vy) || 1
      const alignment = (vx / distance) * direction.x + (vy / distance) * direction.y
      const score = alignment * 1000 + distance
      if (score > bestScore) {
        bestScore = score
        best = point
      }
    }
    return best
  })
}

function interpolateRings(fromRing: LngLat[], toRing: LngLat[], ratio: number): LngLat[] {
  const samples = Math.max(96, fromRing.length, toRing.length)
  const from = resampleRingByAngle(fromRing, samples)
  const to = resampleRingByAngle(toRing, samples)
  const eased = ratio * ratio * (3 - 2 * ratio)
  return to.map(([lng, lat], index) => [from[index][0] + (lng - from[index][0]) * eased, from[index][1] + (lat - from[index][1]) * eased])
}

function ringsAtElapsedSeconds(elapsedSeconds: number): LngLat[][] {
  const frames = fireTimelineFrames
  if (!frames.length) return []
  if (elapsedSeconds <= frames[0].elapsedSeconds) return frames[0].rings
  const last = frames[frames.length - 1]
  if (elapsedSeconds >= last.elapsedSeconds) return last.rings
  const nextIndex = frames.findIndex((frame) => frame.elapsedSeconds >= elapsedSeconds)
  const prev = frames[Math.max(0, nextIndex - 1)]
  const next = frames[nextIndex]
  const span = Math.max(1, next.elapsedSeconds - prev.elapsedSeconds)
  const ratio = Math.max(0, Math.min(1, (elapsedSeconds - prev.elapsedSeconds) / span))
  const count = Math.max(prev.rings.length, next.rings.length)
  return Array.from({ length: count }, (_, index) => {
    const fallbackCenter = frameCenter(next.rings?.length ? next.rings : fireTimelineFrames[0]?.rings || [])
    const fromRing = prev.rings[index] || prev.rings[0] || ignitionRing([fallbackCenter.lng, fallbackCenter.lat])
    const toRing = next.rings[index] || next.rings[0] || fromRing
    return interpolateRings(fromRing, toRing, ratio)
  })
}

function ringAreaSquareMeters(ring: LngLat[]) {
  if (ring.length < 3) return 0
  const center = frameCenter([ring])
  const metersPerDegreeLat = (Math.PI * 6371189) / 180
  const metersPerDegreeLon = (Math.PI * 6342516 * Math.cos(Cesium.Math.toRadians(center.lat))) / 180
  const points = ring.map(([lng, lat]) => ({
    x: (lng - center.lng) * metersPerDegreeLon,
    y: (lat - center.lat) * metersPerDegreeLat,
  }))
  let area = 0
  for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
    area += points[j].x * points[i].y - points[i].x * points[j].y
  }
  return Math.abs(area) / 2
}

function ringsAreaSquareMeters(rings: LngLat[][]) {
  return rings.reduce((sum, ring) => sum + ringAreaSquareMeters(ring), 0)
}

function pointInRing(lng: number, lat: number, ring: LngLat[]) {
  let inside = false
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i]
    const [xj, yj] = ring[j]
    const intersects = yi > lat !== yj > lat && lng < ((xj - xi) * (lat - yi)) / (yj - yi || Number.EPSILON) + xi
    if (intersects) inside = !inside
  }
  return inside
}

function pointInActiveFire(lng: number, lat: number) {
  return activeFireRings.some((ring) => pointInRing(lng, lat, ring))
}

function ringBounds(ring: LngLat[]) {
  return ring.reduce(
    (bounds, [lng, lat]) => ({
      minLng: Math.min(bounds.minLng, lng),
      maxLng: Math.max(bounds.maxLng, lng),
      minLat: Math.min(bounds.minLat, lat),
      maxLat: Math.max(bounds.maxLat, lat),
    }),
    {
      minLng: Infinity,
      maxLng: -Infinity,
      minLat: Infinity,
      maxLat: -Infinity,
    },
  )
}

function randomPointInActiveFire() {
  const ring = activeFireRings[0]
  if (!ring?.length) return null
  const bounds = ringBounds(ring)
  for (let i = 0; i < 24; i++) {
    const lng = bounds.minLng + Math.random() * (bounds.maxLng - bounds.minLng)
    const lat = bounds.minLat + Math.random() * (bounds.maxLat - bounds.minLat)
    if (pointInActiveFire(lng, lat)) return { lng, lat }
  }
  const center = frameCenter(activeFireRings)
  return pointInActiveFire(center.lng, center.lat) ? center : null
}

function makeFireGlowMaterial() {
  return new Cesium.PolylineGlowMaterialProperty({
    glowPower: 0.42,
    taperPower: 0.72,
    color: new Cesium.CallbackProperty(() => {
      const pulse = 0.82 + 0.16 * Math.sin(Date.now() / 160)
      return Cesium.Color.fromCssColorString('#ff2f1f').withAlpha(pulse)
    }, false),
  })
}

function fireGroundHeatTexture() {
  const canvas = document.createElement('canvas')
  canvas.width = 192
  canvas.height = 192
  const ctx = canvas.getContext('2d')!
  const base = ctx.createRadialGradient(96, 96, 6, 96, 96, 98)
  base.addColorStop(0, 'rgba(255,236,120,0.92)')
  base.addColorStop(0.22, 'rgba(255,70,26,0.76)')
  base.addColorStop(0.55, 'rgba(158,18,18,0.42)')
  base.addColorStop(0.78, 'rgba(45,8,8,0.18)')
  base.addColorStop(1, 'rgba(0,0,0,0)')
  ctx.fillStyle = base
  ctx.fillRect(0, 0, canvas.width, canvas.height)

  for (let i = 0; i < 160; i += 1) {
    const x = Math.random() * canvas.width
    const y = Math.random() * canvas.height
    const radius = 8 + Math.random() * 32
    const alpha = 0.08 + Math.random() * 0.22
    const hot = ctx.createRadialGradient(x, y, 0, x, y, radius)
    hot.addColorStop(0, `rgba(255,${90 + Math.random() * 120},28,${alpha})`)
    hot.addColorStop(0.48, `rgba(255,32,18,${alpha * 0.5})`)
    hot.addColorStop(1, 'rgba(0,0,0,0)')
    ctx.fillStyle = hot
    ctx.beginPath()
    ctx.arc(x, y, radius, 0, Math.PI * 2)
    ctx.fill()
  }

  for (let i = 0; i < 18; i += 1) {
    ctx.strokeStyle = `rgba(255,35,18,${0.05 + Math.random() * 0.08})`
    ctx.lineWidth = 3 + Math.random() * 7
    ctx.beginPath()
    const startY = Math.random() * canvas.height
    ctx.moveTo(-20, startY)
    for (let x = 0; x <= canvas.width + 20; x += 32) {
      ctx.lineTo(x, startY + Math.sin((x + i * 19) / 24) * (10 + Math.random() * 16))
    }
    ctx.stroke()
  }

  return canvas.toDataURL('image/png')
}

function makeFireHeatMaterial() {
  const texture = fireGroundHeatTexture()
  return new Cesium.ImageMaterialProperty({
    image: texture,
    transparent: true,
    repeat: new Cesium.Cartesian2(2.8, 2.8),
    // 用动态 alpha 做地表热力膜闪烁，不再使用竖直粒子，效果更接近视频里的贴地蔓延。
    color: new Cesium.CallbackProperty(() => {
      const pulse = 0.62 + 0.16 * Math.sin(Date.now() / 360)
      return Cesium.Color.WHITE.withAlpha(pulse)
    }, false) as any,
  })
}

function makeFireFrontMaterial(color = '#ff2418', alpha = 0.95, glowPower = 0.55) {
  return new Cesium.PolylineGlowMaterialProperty({
    glowPower,
    taperPower: 0.78,
    color: new Cesium.CallbackProperty(() => {
      const pulse = alpha * (0.86 + 0.14 * Math.sin(Date.now() / 130))
      return Cesium.Color.fromCssColorString(color).withAlpha(pulse)
    }, false),
  })
}

function fireFrontSparkMaterial() {
  return new Cesium.PolylineGlowMaterialProperty({
    glowPower: 0.72,
    taperPower: 0.9,
    color: new Cesium.CallbackProperty(() => {
      const pulse = 0.64 + 0.26 * Math.sin(Date.now() / 95)
      return Cesium.Color.fromCssColorString('#ff1111').withAlpha(pulse)
    }, false),
  })
}

function ringCenter(ring: LngLat[]) {
  const lng = ring.reduce((sum, point) => sum + point[0], 0) / Math.max(1, ring.length)
  const lat = ring.reduce((sum, point) => sum + point[1], 0) / Math.max(1, ring.length)
  return { lng, lat }
}

function scaleRing(ring: LngLat[] | undefined, scale: number): LngLat[] {
  if (!ring?.length) return []
  const center = ringCenter(ring)
  return ring.map(([lng, lat]) => [center.lng + (lng - center.lng) * scale, center.lat + (lat - center.lat) * scale])
}

function frameCenter(rings: LngLat[][]) {
  const points = rings.flat()
  const lng = points.reduce((sum, point) => sum + point[0], 0) / Math.max(1, points.length)
  const lat = points.reduce((sum, point) => sum + point[1], 0) / Math.max(1, points.length)
  return { lng, lat }
}

function clearWindField() {
  stopWindAnimation()
  for (const canvas of [windHeatCanvasRef.value, windCanvasRef.value]) {
    const context = canvas?.getContext('2d')
    if (canvas && context) context.clearRect(0, 0, canvas.width, canvas.height)
  }
  windField = null
  activeWindStepIndex = 0
  windParticles = []
}

function resizeWindCanvas() {
  const host = containerRef.value
  if (!host) return
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  const width = Math.max(1, host.clientWidth)
  const height = Math.max(1, host.clientHeight)
  const targetWidth = Math.round(width * dpr)
  const targetHeight = Math.round(height * dpr)
  for (const canvas of [windHeatCanvasRef.value, windCanvasRef.value]) {
    if (!canvas || (canvas.width === targetWidth && canvas.height === targetHeight)) continue
    canvas.width = targetWidth
    canvas.height = targetHeight
    canvas.style.width = `${width}px`
    canvas.style.height = `${height}px`
    canvas.getContext('2d')?.setTransform(dpr, 0, 0, dpr, 0, 0)
  }
}

function currentWindStep() {
  return windField?.time_steps?.[activeWindStepIndex]
}

function randomWindParticle(): WindParticle {
  const bounds = windField?.bounds ?? [props.longitude - 0.4, props.latitude - 0.3, props.longitude + 0.4, props.latitude + 0.3]
  return {
    lng: bounds[0] + Math.random() * (bounds[2] - bounds[0]),
    lat: bounds[1] + Math.random() * (bounds[3] - bounds[1]),
    phase: Math.random(),
  }
}

function resetWindParticles() {
  const canvas = windCanvasRef.value
  const area = (canvas?.clientWidth ?? 900) * (canvas?.clientHeight ?? 600)
  const particleCount = Math.max(1000, Math.min(1600, Math.round(area / 750)))
  windParticles = Array.from({ length: particleCount }, randomWindParticle)
}

function vectorAt(lng: number, lat: number) {
  const step = currentWindStep()
  const bounds = windField?.bounds
  if (!step?.vectors?.length || !bounds) return null
  if (lng < bounds[0] || lng > bounds[2] || lat < bounds[1] || lat > bounds[3]) return null
  let weightTotal = 0
  let u = 0
  let v = 0
  let speed = 0
  for (const vector of step.vectors) {
    const dx = vector.lng - lng
    const dy = vector.lat - lat
    const weight = 1 / Math.max(1e-8, dx * dx + dy * dy)
    weightTotal += weight
    u += vector.u * weight
    v += vector.v * weight
    speed += vector.speed * weight
  }
  if (!weightTotal) return null
  return {
    lng,
    lat,
    u: u / weightTotal,
    v: v / weightTotal,
    speed: speed / weightTotal,
    direction_deg: ((Math.atan2(u, v) * 180) / Math.PI + 360) % 360,
  }
}

function screenPoint(lng: number, lat: number) {
  if (!viewer) return null
  const point = Cesium.SceneTransforms.worldToWindowCoordinates(viewer.scene, Cesium.Cartesian3.fromDegrees(lng, lat, 3000))
  if (!point || !Number.isFinite(point.x) || !Number.isFinite(point.y)) return null
  return point
}

function windHeatColor(speedRatio: number, alpha: number) {
  if (speedRatio > 0.72) return `rgba(250, 204, 21, ${alpha})`
  if (speedRatio > 0.42) return `rgba(34, 197, 94, ${alpha})`
  return `rgba(56, 189, 248, ${alpha})`
}

function drawWindHeatLayer() {
  const canvas = windHeatCanvasRef.value
  const context = canvas?.getContext('2d')
  const vectors = currentWindStep()?.vectors || []
  if (!canvas || !context || !windField || !vectors.length) return
  const width = canvas.clientWidth
  const height = canvas.clientHeight
  context.clearRect(0, 0, width, height)
  context.globalCompositeOperation = 'source-over'
  const maxSpeed = Math.max(0.1, windField.max_speed || 1)
  const radius = Math.max(70, Math.min(150, Math.min(width, height) / 6))

  for (const vector of vectors) {
    const point = screenPoint(vector.lng, vector.lat)
    if (!point || point.x < -radius || point.x > width + radius || point.y < -radius || point.y > height + radius) continue
    const speedRatio = Math.min(1, vector.speed / maxSpeed)
    const gradient = context.createRadialGradient(point.x, point.y, 0, point.x, point.y, radius)
    gradient.addColorStop(0, windHeatColor(speedRatio, 0.075))
    gradient.addColorStop(0.58, windHeatColor(speedRatio, 0.035))
    gradient.addColorStop(1, windHeatColor(speedRatio, 0))
    context.fillStyle = gradient
    context.fillRect(point.x - radius, point.y - radius, radius * 2, radius * 2)
  }
}

function drawWindFrame() {
  if (!windVisible || !viewer || !windField?.time_steps?.length) {
    windAnimationFrame = requestAnimationFrame(drawWindFrame)
    return
  }
  resizeWindCanvas()
  windHeatFrameCounter += 1
  if (windHeatFrameCounter % 24 === 1) drawWindHeatLayer()
  const canvas = windCanvasRef.value
  const context = canvas?.getContext('2d')
  if (!canvas || !context) return
  const width = canvas.clientWidth
  const height = canvas.clientHeight
  context.clearRect(0, 0, width, height)
  context.globalCompositeOperation = 'source-over'
  context.lineCap = 'round'
  context.lineJoin = 'round'
  const animationTime = performance.now() / 1000
  const cameraHeight = viewer.camera.positionCartographic.height
  const closeZoom = Math.max(0, Math.min(1, (26000 - cameraHeight) / 22000))

  for (const particle of windParticles) {
    const vector = vectorAt(particle.lng, particle.lat)
    const start = screenPoint(particle.lng, particle.lat)
    if (!vector || !start || start.x < -40 || start.x > width + 40 || start.y < -40 || start.y > height + 40) continue
    const direction = Math.atan2(vector.u, vector.v)
    const directionProbe = screenPoint(particle.lng + Math.sin(direction) * 0.002, particle.lat + Math.cos(direction) * 0.002)
    if (!directionProbe) continue
    const screenAngle = Math.atan2(directionProbe.y - start.y, directionProbe.x - start.x)
    const flowProgress = (animationTime * 0.16 + particle.phase) % 1
    const edgeFade = Math.min(1, flowProgress / 0.14, (1 - flowProgress) / 0.14)
    const travelDistance = 28 + closeZoom * 34
    const arrowLength = 12 + closeZoom * 9
    const travelOffset = (flowProgress - 0.5) * travelDistance
    const arrowStartX = start.x + Math.cos(screenAngle) * travelOffset
    const arrowStartY = start.y + Math.sin(screenAngle) * travelOffset
    const endX = arrowStartX + Math.cos(screenAngle) * arrowLength
    const endY = arrowStartY + Math.sin(screenAngle) * arrowLength
    if (closeZoom > 0.15) {
      const trailLength = 12 + closeZoom * 26
      const tailX = arrowStartX - Math.cos(screenAngle) * trailLength
      const tailY = arrowStartY - Math.sin(screenAngle) * trailLength
      const trail = context.createLinearGradient(tailX, tailY, endX, endY)
      trail.addColorStop(0, 'rgba(34, 211, 238, 0)')
      trail.addColorStop(0.65, 'rgba(34, 211, 238, 0.25)')
      trail.addColorStop(1, 'rgba(224, 242, 254, 0.75)')
      context.beginPath()
      context.moveTo(tailX, tailY)
      context.lineTo(endX, endY)
      context.strokeStyle = trail
      context.lineWidth = 1.5 + closeZoom * 1.4
      context.stroke()
    }
    const arrowColor = `rgba(224, 242, 254, ${0.3 + edgeFade * 0.62})`
    context.beginPath()
    context.moveTo(arrowStartX, arrowStartY)
    context.lineTo(endX, endY)
    context.strokeStyle = arrowColor
    context.lineWidth = 1.4
    context.stroke()

    const arrowSize = 4
    const wingAngle = Math.PI * 0.78
    context.beginPath()
    context.moveTo(endX, endY)
    context.lineTo(endX + Math.cos(screenAngle + wingAngle) * arrowSize, endY + Math.sin(screenAngle + wingAngle) * arrowSize)
    context.lineTo(endX + Math.cos(screenAngle - wingAngle) * arrowSize, endY + Math.sin(screenAngle - wingAngle) * arrowSize)
    context.closePath()
    context.fillStyle = arrowColor
    context.fill()
  }
  context.globalCompositeOperation = 'source-over'
  windAnimationFrame = requestAnimationFrame(drawWindFrame)
}

function stopWindAnimation() {
  if (windAnimationFrame !== null) {
    cancelAnimationFrame(windAnimationFrame)
    windAnimationFrame = null
  }
}

function startWindAnimation() {
  stopWindAnimation()
  resizeWindCanvas()
  resetWindParticles()
  windHeatFrameCounter = 0
  drawWindHeatLayer()
  windAnimationFrame = requestAnimationFrame(drawWindFrame)
}

function renderWindFieldStep(stepIndex: number) {
  if (!windField?.time_steps?.length) return
  const nextIndex = Math.max(0, Math.min(windField.time_steps.length - 1, stepIndex))
  activeWindStepIndex = nextIndex
  if (!windAnimationFrame) startWindAnimation()
}

function setWindFieldElapsedMinutes(elapsedMinutes: number) {
  if (!windField?.time_steps?.length) return
  const nextIndex = windField.time_steps.reduce((bestIndex, step, index) => {
    const bestDelta = Math.abs(windField!.time_steps[bestIndex].elapsed_minutes - elapsedMinutes)
    const nextDelta = Math.abs(step.elapsed_minutes - elapsedMinutes)
    return nextDelta < bestDelta ? index : bestIndex
  }, 0)
  renderWindFieldStep(nextIndex)
}

function setWindFieldVisible(visible: boolean) {
  windVisible = props.showWindField && visible
  windHeatCanvasRef.value?.classList.toggle('is-hidden', !visible)
  windCanvasRef.value?.classList.toggle('is-hidden', !visible)
  if (visible && windField && !windAnimationFrame) startWindAnimation()
}

function setManualWindField(options: { longitude: number; latitude: number; speed: number; directionDeg: number; radiusKm?: number }) {
  const latitude = Number(options.latitude)
  const longitude = Number(options.longitude)
  const speed = Math.max(0, Number(options.speed) || 0)
  const directionDeg = (((Number(options.directionDeg) || 0) % 360) + 360) % 360
  const radiusKm = Math.max(2, Math.min(90, Number(options.radiusKm) || 8))
  const latitudeRadius = radiusKm / 111.32
  const longitudeRadius = radiusKm / Math.max(20, 111.32 * Math.cos((latitude * Math.PI) / 180))
  const vectors: WindVector[] = []
  let maximumSpeed = speed

  for (let row = 0; row < 11; row += 1) {
    for (let col = 0; col < 15; col += 1) {
      const normalizedX = (col - 7) / 7
      const normalizedY = (row - 5) / 5
      const directionOffset = 24 * Math.sin(normalizedX * Math.PI * 2.5) * Math.cos(normalizedY * Math.PI) - 18 * Math.sin(normalizedY * Math.PI * 2) * Math.cos(normalizedX * Math.PI)
      const localDirection = directionDeg + directionOffset
      const localSpeed = Math.max(0, speed * (1 + 0.24 * Math.sin(normalizedX * Math.PI * 2) + 0.16 * Math.cos(normalizedY * Math.PI * 2.5) - 0.08 * normalizedX * normalizedY))
      const radians = (localDirection * Math.PI) / 180
      maximumSpeed = Math.max(maximumSpeed, localSpeed)
      vectors.push({
        lng: longitude - longitudeRadius + (longitudeRadius * 2 * col) / 14,
        lat: latitude - latitudeRadius + (latitudeRadius * 2 * row) / 10,
        u: Math.sin(radians) * localSpeed,
        v: Math.cos(radians) * localSpeed,
        speed: localSpeed,
        direction_deg: ((localDirection % 360) + 360) % 360,
      })
    }
  }

  windField = {
    event_id: props.sceneId || 'manual_weather',
    bounds: [longitude - longitudeRadius, latitude - latitudeRadius, longitude + longitudeRadius, latitude + latitudeRadius],
    max_speed: Math.max(1, maximumSpeed),
    time_steps: [{ step: 0, elapsed_minutes: 0, vectors }],
  }
  activeWindStepIndex = 0
  startWindAnimation()
  setWindFieldVisible(windVisible)
}

async function setTerrainEnabled(enabled: boolean) {
  terrainEnabled = enabled
  if (!viewer) return
  const currentViewer = viewer
  try {
    if (enabled) {
      const terrainProvider = await Cesium.createWorldTerrainAsync({
        requestVertexNormals: true,
        requestWaterMask: false,
      })
      if (!viewer || viewer !== currentViewer || viewer.isDestroyed()) return
      currentViewer.terrainProvider = terrainProvider
      currentViewer.scene.globe.depthTestAgainstTerrain = true
      // The simulation timeline is independent from Cesium's astronomical
      // clock. Keep terrain readable instead of showing an unrelated night side.
      currentViewer.scene.globe.enableLighting = false
      currentViewer.scene.verticalExaggeration = 1.8
      currentViewer.scene.verticalExaggerationRelativeHeight = 1800
      return
    }
    currentViewer.terrainProvider = new Cesium.EllipsoidTerrainProvider()
    currentViewer.scene.globe.depthTestAgainstTerrain = false
    currentViewer.scene.globe.enableLighting = false
    currentViewer.scene.verticalExaggeration = 1
  } catch (error) {
    console.warn('Cesium terrain unavailable, falling back to ellipsoid terrain:', error)
    if (!viewer || viewer !== currentViewer || viewer.isDestroyed()) return
    currentViewer.terrainProvider = new Cesium.EllipsoidTerrainProvider()
    currentViewer.scene.globe.depthTestAgainstTerrain = false
    currentViewer.scene.globe.enableLighting = false
    currentViewer.scene.verticalExaggeration = 1
  }
}

function getCurrentWindSummary() {
  const step = currentWindStep()
  const vectors = step?.vectors || []
  if (!vectors.length) return null
  const summary = vectors.reduce(
    (acc, vector) => {
      acc.u += vector.u
      acc.v += vector.v
      acc.speed += vector.speed
      return acc
    },
    { u: 0, v: 0, speed: 0 },
  )
  const count = vectors.length
  const avgU = summary.u / count
  const avgV = summary.v / count
  return {
    elapsed_minutes: step?.elapsed_minutes ?? 0,
    speed: summary.speed / count,
    direction_deg: ((Math.atan2(avgU, avgV) * 180) / Math.PI + 360) % 360,
  }
}

async function loadWindField() {
  if (!viewer || !props.showWindField) return
  // 使用相对路径，让 ZeroTier 远程访问者也通过当前前端服务代理到本机后端。
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? ''
  const params = new URLSearchParams({
    max_points: '260',
    scene_id: props.sceneId || 'dixie_fire_2021',
  })
  try {
    const response = await fetch(`${apiBaseUrl}/api/weather/wind-field?${params.toString()}`)
    if (!response.ok) throw new Error(`Wind field API failed with status ${response.status}`)
    windField = await response.json()
    renderWindFieldStep(activeWindStepIndex)
  } catch (error) {
    console.warn('Wind field layer unavailable:', error)
  }
}

function notifyFireFrame() {
  if (!fireTimelineFrames.length) return
  const frame = fireTimelineFrames[activeFireFrameIndex]
  const totalSeconds = fireTimelineFrames[fireTimelineFrames.length - 1]?.elapsedSeconds || 0
  fireTimelineOptions.onFrame?.({
    index: activeFireFrameIndex,
    total: fireTimelineFrames.length,
    elapsedSeconds: activeFireElapsedSeconds,
    progress: totalSeconds > 0 ? (activeFireElapsedSeconds / totalSeconds) * 100 : 100,
  })
}

function updateFireHistoryVisibility() {
  fireHistoryEntities.forEach(({ entity, elapsedSeconds }) => {
    entity.show = elapsedSeconds <= activeFireElapsedSeconds
  })
}

function setFireElapsedSeconds(elapsedSeconds: number) {
  if (!fireTimelineFrames.length) return
  const totalSeconds = fireTimelineFrames[fireTimelineFrames.length - 1]?.elapsedSeconds || 0
  activeFireElapsedSeconds = Math.max(0, Math.min(totalSeconds, elapsedSeconds))
  activeFireFrameIndex = fireTimelineFrames.reduce((bestIndex, frame, index) => {
    const bestDelta = Math.abs(fireTimelineFrames[bestIndex].elapsedSeconds - activeFireElapsedSeconds)
    const nextDelta = Math.abs(frame.elapsedSeconds - activeFireElapsedSeconds)
    return nextDelta < bestDelta ? index : bestIndex
  }, 0)
  activeFireRings = ringsAtElapsedSeconds(activeFireElapsedSeconds)
  setWindFieldElapsedMinutes(activeFireElapsedSeconds / 60)
  updateFireHistoryVisibility()
  notifyFireFrame()
}

function ringsAtOffsetSeconds(offsetSeconds: number) {
  if (!fireTimelineFrames.length) return []
  const totalSeconds = fireTimelineFrames[fireTimelineFrames.length - 1]?.elapsedSeconds || 0
  const targetSeconds = Math.max(0, Math.min(totalSeconds, activeFireElapsedSeconds + offsetSeconds))
  return ringsAtElapsedSeconds(targetSeconds)
}

function setFireFrame(index: number) {
  if (!fireTimelineFrames.length) return
  const frameIndex = Math.max(0, Math.min(fireTimelineFrames.length - 1, index))
  setFireElapsedSeconds(fireTimelineFrames[frameIndex].elapsedSeconds)
}

function pauseFireTimeline() {
  if (fireAnimationTimer) {
    clearInterval(fireAnimationTimer)
    fireAnimationTimer = null
  }
  fireTimelineOptions.onPlaybackState?.(false)
}

function notifyFireTimelineComplete() {
  if (fireTimelineCompletedNotified) return
  fireTimelineCompletedNotified = true
  fireTimelineOptions.onComplete?.()
}

function playFireTimeline() {
  if (!fireTimelineFrames.length || fireAnimationTimer) return
  const totalSeconds = fireTimelineFrames[fireTimelineFrames.length - 1]?.elapsedSeconds || 0
  if (activeFireElapsedSeconds >= totalSeconds) {
    fireTimelineCompletedNotified = false
    setFireElapsedSeconds(0)
  }
  lastFireAnimationTick = Date.now()
  fireTimelineOptions.onPlaybackState?.(true)
  fireAnimationTimer = setInterval(() => {
    const now = Date.now()
    const deltaMs = Math.max(16, now - lastFireAnimationTick)
    lastFireAnimationTick = now
    const playbackDurationMs = Math.max(1800, fireTimelineOptions.durationMs ?? 4500)
    const simulatedSecondsPerMs = totalSeconds / playbackDurationMs
    const nextElapsed = activeFireElapsedSeconds + deltaMs * simulatedSecondsPerMs
    if (nextElapsed >= totalSeconds) {
      setFireElapsedSeconds(totalSeconds)
      pauseFireTimeline()
      notifyFireTimelineComplete()
      return
    }
    setFireElapsedSeconds(nextElapsed)
  }, 80)
}

function resetFireTimeline() {
  pauseFireTimeline()
  setFireFrame(0)
}

function setFireTimelineProgress(progress: number) {
  if (!fireTimelineFrames.length) return
  const bounded = Math.max(0, Math.min(100, progress))
  const totalSeconds = fireTimelineFrames[fireTimelineFrames.length - 1]?.elapsedSeconds || 0
  const targetSeconds = totalSeconds > 0 ? (bounded / 100) * totalSeconds : 0
  setFireElapsedSeconds(targetSeconds)
  if (bounded >= 100) {
    pauseFireTimeline()
    notifyFireTimelineComplete()
  } else {
    fireTimelineCompletedNotified = false
  }
}

function setFireTimelineDuration(durationMs: number) {
  fireTimelineOptions.durationMs = Math.max(1800, Number(durationMs) || 4500)
}

function addFireFrontTimeline(geojson: any, options: FireTimelineOptions = {}) {
  if (!viewer || !geojson?.features?.length) return
  clearFireFronts()

  const frameGroups = new Map<number, FireFrame>()
  ;[...geojson.features]
    .filter((feature: any) => ['Polygon', 'MultiPolygon'].includes(feature?.geometry?.type))
    .forEach((feature: any, index: number) => {
      const rings = ringsFromFeature(feature)
      if (!rings.length) return
      const elapsedSeconds = featureElapsedSeconds(feature, index + 1)
      const existing = frameGroups.get(elapsedSeconds)
      if (existing) {
        // 同一 elapsed_seconds 可能包含多个火线面，合并为同一帧，避免一个时刻被拆成多次播放造成乱序感。
        existing.rings.push(...rings)
        existing.areaSquareMeters = ringsAreaSquareMeters(existing.rings)
        return
      }
      frameGroups.set(elapsedSeconds, {
        rings,
        step: feature.properties?.step ?? index + 1,
        elapsedSeconds,
        areaSquareMeters: ringsAreaSquareMeters(rings),
      })
    })

  const frames = [...frameGroups.values()].sort((a, b) => {
    if (a.elapsedSeconds !== b.elapsedSeconds) return a.elapsedSeconds - b.elapsedSeconds
    // 对异常同秒或缺少时间字段的数据，用过火面积兜底，保证视觉上由内向外扩散。
    return a.areaSquareMeters - b.areaSquareMeters
  })
  if (!frames.length) return
  const ignitionCenter = frameCenter(frames[0].rings)
  const initialFrame: FireFrame = {
    rings: [ignitionRing([ignitionCenter.lng, ignitionCenter.lat])],
    step: 0,
    elapsedSeconds: 0,
    areaSquareMeters: 0,
  }
  fireTimelineFrames = frames[0]?.elapsedSeconds === 0 ? frames : [initialFrame, ...frames]
  fireTimelineOptions = options
  fireTimelineCompletedNotified = false
  setFireElapsedSeconds(0)

  const timelineFrames = fireTimelineFrames
  const maxRingCount = Math.max(...timelineFrames.map((frame) => frame.rings.length))
  for (let ringIndex = 0; ringIndex < maxRingCount; ringIndex += 1) {
    const futureProjectionEntities = [
      {
        offsetSeconds: 30 * 60,
        color: '#ff8a18',
        alpha: 0.16,
        name: '30min orange forecast',
      },
      {
        offsetSeconds: 60 * 60,
        color: '#ffd84a',
        alpha: 0.12,
        name: '60min yellow forecast',
      },
    ].map((forecast) =>
      viewer!.entities.add({
        name: `Fire ${forecast.name} ${ringIndex + 1}`,
        polygon: {
          hierarchy: new Cesium.CallbackProperty(() => {
            const ring = ringsAtOffsetSeconds(forecast.offsetSeconds)?.[ringIndex]
            return ring?.length ? new Cesium.PolygonHierarchy(ringToGroundPositions(ring)) : undefined
          }, false),
          // 参考 FireSight 的 red now / orange future / yellow later 分层，未来态势仅作半透明贴地预判。
          clampToGround: true,
          material: new Cesium.ColorMaterialProperty(
            new Cesium.CallbackProperty(() => {
              const pulse = forecast.alpha * (0.86 + 0.14 * Math.sin(Date.now() / 520))
              return Cesium.Color.fromCssColorString(forecast.color).withAlpha(pulse)
            }, false),
          ),
        },
      }),
    )

    const burnedEntity = viewer.entities.add({
      name: `Fire burned membrane ${ringIndex + 1}`,
      polygon: {
        hierarchy: new Cesium.CallbackProperty(() => {
          const ring = activeFireRings?.[ringIndex]
          return ring?.length ? new Cesium.PolygonHierarchy(ringToGroundPositions(ring)) : undefined
        }, false),
        // 已扫过区域用黑膜贴地覆盖，形成火势从火点向外连续吞噬的视觉效果。
        clampToGround: true,
        material: new Cesium.ColorMaterialProperty(
          new Cesium.CallbackProperty(() => {
            const pulse = 0.34 + 0.05 * Math.sin(Date.now() / 420)
            return Cesium.Color.fromCssColorString('#050505').withAlpha(pulse)
          }, false),
        ),
      },
    })

    const heatEntity = viewer.entities.add({
      name: `Fire active heat texture ${ringIndex + 1}`,
      polygon: {
        hierarchy: new Cesium.CallbackProperty(() => {
          const ring = activeFireRings?.[ringIndex]
          const heatRing = scaleRing(ring, 1.012)
          return heatRing.length ? new Cesium.PolygonHierarchy(ringToGroundPositions(heatRing)) : undefined
        }, false),
        // 红橙热力贴图覆盖当前燃烧区，形成类似视频中由火点向外铺开的地表火场。
        clampToGround: true,
        material: makeFireHeatMaterial(),
      },
    })

    const innerGlowEntity = viewer.entities.add({
      name: `Fire inner heat glow ${ringIndex + 1}`,
      polygon: {
        hierarchy: new Cesium.CallbackProperty(() => {
          const ring = activeFireRings?.[ringIndex]
          const glowRing = scaleRing(ring, 0.86 + 0.025 * Math.sin(Date.now() / 480))
          return glowRing.length ? new Cesium.PolygonHierarchy(ringToGroundPositions(glowRing)) : undefined
        }, false),
        // 中心热核让扩散区域不是单一色块，视觉上更像热红外火场。
        clampToGround: true,
        material: new Cesium.ColorMaterialProperty(
          new Cesium.CallbackProperty(() => {
            const pulse = 0.2 + 0.08 * Math.sin(Date.now() / 220)
            return Cesium.Color.fromCssColorString('#ff3b1f').withAlpha(pulse)
          }, false),
        ),
      },
    })

    const frontBandEntity = viewer.entities.add({
      name: `Fire thermal front ${ringIndex + 1}`,
      polyline: {
        positions: new Cesium.CallbackProperty(() => {
          const ring = activeFireRings?.[ringIndex]
          return ring?.length ? ringToGroundPositions([...ring, ring[0]]) : []
        }, false),
        width: 4,
        material: makeFireFrontMaterial('#ff2d20', 0.94, 0.1),
        // Render the modeled perimeter once. Offset animated bands made a
        // single raster boundary look like several conflicting firelines.
        clampToGround: true,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
    })

    const frontHeatSpotCount = 18
    const frontHeatSpotEntities = Array.from({ length: frontHeatSpotCount }, (_, spotIndex) => {
      const phase = (spotIndex / frontHeatSpotCount) * Math.PI * 2
      return viewer!.entities.add({
        name: `Fire front ground heat spot ${ringIndex + 1}-${spotIndex + 1}`,
        position: new Cesium.CallbackProperty(() => {
          const ring = activeFireRings?.[ringIndex]
          if (!ring?.length) return undefined
          const ratio = (spotIndex + 0.5 + 0.16 * Math.sin(Date.now() / 900 + phase)) / frontHeatSpotCount
          const point = ring[Math.floor(Math.max(0, Math.min(0.999, ratio)) * ring.length)] || ring[0]
          return Cesium.Cartesian3.fromDegrees(point[0], point[1])
        }, false),
        ellipse: {
          // 少量小型贴地热斑打破纯线条感，但避免回到明显“火苗/大颗粒”的视觉。
          semiMajorAxis: new Cesium.CallbackProperty(() => 34 + 7 * Math.sin(Date.now() / 210 + phase), false),
          semiMinorAxis: new Cesium.CallbackProperty(() => 22 + 5 * Math.sin(Date.now() / 260 + phase), false),
          rotation: new Cesium.CallbackProperty(() => phase + Date.now() / 2600, false),
          height: 0,
          heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
          material: new Cesium.ColorMaterialProperty(
            new Cesium.CallbackProperty(() => {
              const pulse = 0.2 + 0.12 * Math.sin(Date.now() / 180 + phase)
              return Cesium.Color.fromCssColorString('#ff1d18').withAlpha(pulse)
            }, false),
          ),
          outline: false,
        },
      })
    })

    fireFrontEntities.push(...futureProjectionEntities, burnedEntity, heatEntity, innerGlowEntity, frontBandEntity, ...frontHeatSpotEntities)
  }

  timelineFrames.forEach((frame, frameIndex) => {
    frame.rings.forEach((ring, ringIndex) => {
      const historyEntity = viewer!.entities.add({
        name: `Fire history ${frame.elapsedSeconds}-${ringIndex + 1}`,
        show: false,
        polyline: {
          positions: ringToGroundPositions([...ring, ring[0]]),
          width: Math.max(2, 4 - frameIndex * 0.22),
          material: Cesium.Color.fromCssColorString(frameIndex === timelineFrames.length - 1 ? '#ffea70' : '#ff7a1a').withAlpha(frameIndex === timelineFrames.length - 1 ? 0.95 : 0.42),
          // 每 72 分钟历史火线也贴地保留，避免多条火线按高度堆叠遮挡地图。
          clampToGround: true,
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        },
      })
      fireFrontEntities.push(historyEntity)
      fireHistoryEntities.push({
        entity: historyEntity,
        elapsedSeconds: frame.elapsedSeconds,
      })
    })
  })

  updateFireHistoryVisibility()

  if (fireFrontEntities.length) {
    viewer.flyTo(fireFrontEntities, {
      duration: 0.8,
      offset: new Cesium.HeadingPitchRange(0, Cesium.Math.toRadians(-80), 9000),
    })
  }

  if (options.autoPlay !== false) {
    playFireTimeline()
  }
}

function on(eventName: string, callback: (...args: any[]) => void) {
  if (eventName === 'load') setTimeout(callback, 0)
}

function addSource() {}
function addLayer() {}
function getLayer() {
  return false
}
function removeLayer() {}
function removeSource() {}
function addControl() {}
function remove() {}

defineExpose({
  flyHome,
  flyTo,
  focusWindField,
  resize,
  zoomIn,
  zoomOut,
  addHotspotGeoJson,
  clearHotspots,
  addDemoPoint,
  addDemoRoute,
  addDemoArea,
  clearDemoEntities,
  beginMapPointSelection,
  cancelMapPointSelection,
  setImageryOverlayVisible,
  setVectorOverlayVisible,
  setNirSimulationVisible,
  clearNirSimulationLayer,
  setTerrainEnabled,
  setManualWindField,
  setWindFieldVisible,
  getCurrentWindSummary,
  addFireFrontTimeline,
  playFireTimeline,
  pauseFireTimeline,
  resetFireTimeline,
  setFireTimelineProgress,
  setFireTimelineDuration,
  clearFireFronts,
  on,
  addSource,
  addLayer,
  getLayer,
  removeLayer,
  removeSource,
  addControl,
  remove,
  getViewer: () => viewer,
})

onMounted(async () => {
  if (!containerRef.value) return

  const token = import.meta.env.VITE_CESIUM_ION_TOKEN
  if (token) Cesium.Ion.defaultAccessToken = token

  viewer = new Cesium.Viewer(containerRef.value, {
    animation: false,
    timeline: false,
    baseLayerPicker: false,
    geocoder: false,
    homeButton: false,
    sceneModePicker: false,
    navigationHelpButton: false,
    fullscreenButton: false,
    infoBox: false,
    selectionIndicator: false,
    shouldAnimate: true,
  })

  viewer.scene.globe.enableLighting = false
  viewer.scene.globe.baseColor = Cesium.Color.fromCssColorString('#17263a')
  viewer.scene.skyAtmosphere.show = true
  viewer.scene.fxaa = true
  viewer.scene.screenSpaceCameraController.minimumZoomDistance = 2000

  flyHome()
  await setTerrainEnabled(terrainEnabled)
})

onUnmounted(() => {
  cancelMapPointSelection()
  clearFireFronts()
  setImageryOverlayVisible(false)
  setVectorOverlayVisible(false)
  clearNirSimulationLayer()
  clearWindField()
  clearHotspots()
  clearDemoEntities()
  viewer?.destroy()
  viewer = null
})
</script>

<style scoped>
.cesium-map-shell {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: #050b14;
}

.cesium-map {
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: #050b14;
}

.wind-heat-canvas,
.wind-field-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  transition: opacity 160ms ease;
}

.wind-heat-canvas {
  z-index: 1;
  opacity: 0.9;
  mix-blend-mode: screen;
}

.wind-field-canvas {
  z-index: 2;
  opacity: 0.78;
}

.wind-heat-canvas.is-hidden,
.wind-field-canvas.is-hidden {
  opacity: 0;
}

.cesium-map :deep(.cesium-widget),
.cesium-map :deep(.cesium-widget canvas) {
  width: 100%;
  height: 100%;
}
</style>
