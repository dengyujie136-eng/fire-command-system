import { watch } from 'vue'
import { DEFAULT_MAP_CENTER, WIND_VIEW_CENTER, WIND_VIEW_ZOOM, useFireEventStore } from '../stores/fireEventStore'

type LngLat = [number, number]

type CesiumMapLike = {
  clearFireFronts?: () => void
  clearHotspots?: () => void
  clearDemoEntities?: () => void
  addHotspotGeoJson?: (geojson: any) => void
  addFireFrontTimeline?: (geojson: any, options?: any) => void
  addDemoPoint?: (options: { name: string, position: LngLat, color?: string, label?: string, size?: number }) => void
  addDemoRoute?: (options: { name: string, coordinates: LngLat[], color?: string, width?: number, arrow?: boolean }) => void
  addDemoArea?: (options: { name: string, coordinates: LngLat[], color?: string, label?: string }) => void
  pauseFireTimeline?: () => void
  setFireTimelineProgress?: (progress: number) => void
  flyTo?: (options: { center?: LngLat, zoom?: number }) => void
}


function asLngLat(point: any): LngLat | null {
  if (Array.isArray(point) && Number.isFinite(Number(point[0])) && Number.isFinite(Number(point[1]))) {
    return [Number(point[0]), Number(point[1])]
  }
  if (point && Number.isFinite(Number(point.longitude ?? point.lng)) && Number.isFinite(Number(point.latitude ?? point.lat))) {
    return [Number(point.longitude ?? point.lng), Number(point.latitude ?? point.lat)]
  }
  return null
}

function firstLngLat(...candidates: any[]): LngLat | null {
  for (const candidate of candidates) {
    const point = asLngLat(candidate)
    if (point) return point
  }
  return null
}

function routeCoordinates(route: any): LngLat[] {
  const raw = route?.coordinates
    || route?.waypoints
    || route?.path
    || route?.geometry?.coordinates
    || route?.geometry?.geojson?.coordinates
    || route?.geojson?.coordinates
    || route?.geometry?.points
    || route?.points
    || []
  if (!Array.isArray(raw)) return []
  const line = raw[0] && Array.isArray(raw[0][0]) ? raw[0] : raw
  return line.map(asLngLat).filter(Boolean) as LngLat[]
}

function routeColor(_route: any, index: number) {
  const routePalette = ['#22c55e', '#f59e0b', '#38bdf8']
  return routePalette[index % routePalette.length]
}

function areaCoordinates(area: any): LngLat[] {
  const raw = area?.coordinates
    || area?.polygon
    || area?.boundary
    || area?.geometry?.coordinates
    || area?.geometry?.geojson?.coordinates
    || area?.geojson?.coordinates
    || []
  if (!Array.isArray(raw)) return []
  const ring = raw[0] && Array.isArray(raw[0][0]) ? raw[0] : raw
  return ring.map(asLngLat).filter(Boolean) as LngLat[]
}

function collectFireRings(geojson: any): LngLat[][] {
  const features = Array.isArray(geojson?.features) ? geojson.features : []
  return features.flatMap((feature: any) => {
    const coordinates = feature?.geometry?.coordinates || []
    if (feature?.geometry?.type === 'Polygon') return [coordinates?.[0] || []]
    if (feature?.geometry?.type === 'MultiPolygon') return coordinates.map((polygon: any) => polygon?.[0] || [])
    return []
  }).map((ring: any[]) => ring.map(asLngLat).filter(Boolean) as LngLat[]).filter((ring: LngLat[]) => ring.length >= 3)
}

function centerOfPoints(points: LngLat[]): LngLat | null {
  const valid = points.filter(([lng, lat]) => Number.isFinite(lng) && Number.isFinite(lat))
  if (!valid.length) return null
  const bounds = valid.reduce((acc, [lng, lat]) => ({
    minLng: Math.min(acc.minLng, lng),
    maxLng: Math.max(acc.maxLng, lng),
    minLat: Math.min(acc.minLat, lat),
    maxLat: Math.max(acc.maxLat, lat)
  }), { minLng: Infinity, maxLng: -Infinity, minLat: Infinity, maxLat: -Infinity })
  return [
    (bounds.minLng + bounds.maxLng) / 2,
    (bounds.minLat + bounds.maxLat) / 2
  ]
}

function fireCenter(geojson: any): LngLat | null {
  const rings = collectFireRings(geojson)
  return centerOfPoints(rings.flat())
}

function routePackagePoints(fireEvent: ReturnType<typeof useFireEventStore>): LngLat[] {
  const routePackage = fireEvent.routePackage || {}
  const routeOptionsPackage = fireEvent.routeOptionsPackage || {}
  const routes = [
    ...(routePackage.route_options || []),
    ...(routePackage.evacuation_routes || []),
    ...(routePackage.rescue_routes || []),
    ...(routePackage.safe_routes || []),
    ...(routeOptionsPackage.route_options || [])
  ].slice(0, 6)
  return routes.flatMap(routeCoordinates)
}

function uavPackagePoints(fireEvent: ReturnType<typeof useFireEventStore>): LngLat[] {
  const uavPackage = fireEvent.uavPackage || {}
  const tasks = [
    ...(uavPackage.uav_tasks || []),
    ...(uavPackage.tasks || []),
    ...(uavPackage.assignments || []),
    ...(uavPackage.current_tasks || []),
  ]
  return tasks.map((task: any, index: number) => uavTaskPosition(task, index)).filter(Boolean) as LngLat[]
}

function resourcePackagePoints(fireEvent: ReturnType<typeof useFireEventStore>): LngLat[] {
  const resourcePackage = fireEvent.resourcePackage || {}
  const tasks = resourcePackage.personnel_assignments || resourcePackage.dispatch_tasks || resourcePackage.tasks || []
  const zones = resourcePackage.dispatch_zones || resourcePackage.resource_zones || resourcePackage.zones || resourcePackage.areas || []
  return [
    ...tasks.flatMap((item: any) => [
      ...dispatchRouteCoordinates(item),
      asLngLat(item.position || item.location || item.target_point || item.coordinates)
    ]),
    ...zones.flatMap(areaCoordinates)
  ].filter(Boolean) as LngLat[]
}

function bestViewCenter(
  fireEvent: ReturnType<typeof useFireEventStore>,
  mode: MapSyncMode | undefined,
  activePoint: LngLat | null,
): LngLat {
  if (activePoint) return activePoint
  const geojson = fireEvent.forefireResult?.geojson
  const candidates: Array<LngLat | null> = []
  if (mode === 'route' || mode === 'command') candidates.push(centerOfPoints(routePackagePoints(fireEvent)))
  if (mode === 'uav') candidates.push(centerOfPoints(uavPackagePoints(fireEvent)))
  if (mode === 'resource') candidates.push(centerOfPoints(resourcePackagePoints(fireEvent)))
  if (mode === 'predict' || mode === 'command' || mode === 'fusion') candidates.push(fireCenter(geojson))
  candidates.push(fireCenter(geojson))
  return candidates.find(Boolean) || WIND_VIEW_CENTER
}

function dispatchRouteCoordinates(item: any): LngLat[] {
  const explicit = routeCoordinates(item)
  if (explicit.length >= 2) return explicit
  const start = firstLngLat(
    item.source_point,
    item.source_location,
    item.origin,
    item.from,
    item.start,
    item.resource_point,
    item.depot,
    item.base
  )
  const end = firstLngLat(
    item.target_point,
    item.target_location,
    item.destination,
    item.to,
    item.end,
    item.location,
    item.position,
    item.coordinates
  )
  return start && end ? [start, end] : []
}

function uavTaskPosition(task: any, index: number): LngLat | null {
  const direct = firstLngLat(
    task.current_position,
    task.position,
    task.location,
    task.target_point,
    task.target_location,
    task.coordinates,
    task.waypoint
  )
  if (direct) return direct
  const lng = Number(task.lng ?? task.longitude)
  const lat = Number(task.lat ?? task.latitude)
  if (Number.isFinite(lng) && Number.isFinite(lat)) return [lng, lat]
  const route = routeCoordinates(task)
  if (route.length) return route[Math.min(index, route.length - 1)]
  return null
}

function renderPackageMap(map: CesiumMapLike, fireEvent: ReturnType<typeof useFireEventStore>, mode?: MapSyncMode) {
  const mapPackage = fireEvent.mapPackage || {}
  const routePackage = fireEvent.routePackage || {}
  const routeOptionsPackage = fireEvent.routeOptionsPackage || {}
  const uavPackage = fireEvent.uavPackage || {}
  const resourcePackage = fireEvent.resourcePackage || {}

  const routeGroups = mode === 'command' || mode === 'route'
    ? [
        ...(routePackage.route_options || []),
        ...(routePackage.evacuation_routes || []),
        ...(routePackage.rescue_routes || []),
        ...(routePackage.safe_routes || []),
        ...(routeOptionsPackage.route_options || [])
      ].filter((route, index, items) => {
        const id = route.route_id || route.id || route.name || JSON.stringify(route.geometry || route.coordinates || index)
        return items.findIndex((item) => (item.route_id || item.id || item.name || JSON.stringify(item.geometry || item.coordinates || index)) === id) === index
      }).slice(0, 3)
    : []

  routeGroups.forEach((route: any, index: number) => {
    const coordinates = routeCoordinates(route)
    if (coordinates.length >= 2) {
      map.addDemoRoute?.({
        name: route.name || route.route_name || route.route_id || `route-${index + 1}`,
        coordinates,
        color: routeColor(route, index),
        width: route.width || 6
      })
    }
  })

  const areas = mode === 'resource'
    ? [
        ...(resourcePackage.dispatch_zones || []),
        ...(resourcePackage.resource_zones || []),
        ...(resourcePackage.zones || []),
        ...(resourcePackage.areas || [])
      ]
    : []
  areas.forEach((area: any, index: number) => {
    const coordinates = areaCoordinates(area)
    if (coordinates.length >= 3) {
      const color = area.color || ['#ef4444', '#f59e0b', '#22c55e'][index % 3]
      const name = area.name || area.zone_name || area.zone_id || `资源分区 ${index + 1}`
      const label = area.label || area.zone_id || area.id || name
      const summary = area.summary || area.assignment || area.resource || area.recommended_resource || ''
      map.addDemoArea?.({
        name,
        label,
        coordinates,
        color
      })
      const center = centerOfPoints(coordinates)
      if (center && summary) {
        map.addDemoPoint?.({
          name: summary,
          label: summary,
          position: center,
          color,
          size: 9
        })
      }
    }
  })

  const uavTasks = mode === 'uav'
    ? [
        ...(uavPackage.uav_tasks || []),
        ...(uavPackage.tasks || []),
        ...(uavPackage.assignments || []),
        ...(uavPackage.current_tasks || []),
        ...(uavPackage.online_uavs || []),
        ...(uavPackage.drones || []),
        ...(uavPackage.uavs || []),
        ...(uavPackage.list || []),
      ]
    : []
  uavTasks.forEach((task: any, index: number) => {
    const position = uavTaskPosition(task, index)
    if (position) {
      const name = task.uav_id || task.drone_id || task.vehicle_id || task.name || `UAV-${index + 1}`
      const action = task.action || task.mission || task.task || task.target || '执行任务'
      map.addDemoPoint?.({
          name: `${name} ${action}`,
          label: `${name} ${action}`,
          position,
          color: task.color || '#38bdf8',
          size: 14
        })
    }
  })

  const assignments = mode === 'resource'
    ? (resourcePackage.personnel_assignments || resourcePackage.dispatch_tasks || [])
    : []
  assignments.forEach((item: any, index: number) => {
    const dispatchRoute = dispatchRouteCoordinates(item)
    if (mode === 'resource' && dispatchRoute.length >= 2) {
      map.addDemoRoute?.({
        name: item.action || item.name || item.task_id || `调度方向 ${index + 1}`,
        coordinates: dispatchRoute,
        color: item.color || '#f59e0b',
        width: 5,
        arrow: true
      })
    }
    const position = mode === 'resource'
      ? asLngLat(item.position || item.location || item.target_point || item.coordinates)
      : null
    if (position) {
      map.addDemoPoint?.({
        name: item.name || item.owner || item.task_id || `resource-${index + 1}`,
        label: item.name || item.owner || item.action || '',
        position,
        color: item.color || '#f59e0b',
        size: 11
      })
    }
  })

  return routeGroups.length || areas.length || uavTasks.length || assignments.length
}

function hotspotGeoJson(center: LngLat = DEFAULT_MAP_CENTER, name = '可信火点') {
  return {
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        properties: {
          name,
          level: 'high',
          source: 'active_fire_event'
        },
        geometry: {
          type: 'Point',
          coordinates: center
        }
      }
    ]
  }
}

type MapSyncMode = 'monitor' | 'predict' | 'uav' | 'route' | 'resource' | 'command' | 'fusion'

type MapSyncOptions = {
  zoom?: number
  mode?: MapSyncMode
  showHotspotBeforePrediction?: boolean
  showFireFrontAfterPrediction?: boolean
  showAgentLayersOnlyAfterDecision?: boolean
}

export function syncActiveFireToMap(getMap: () => CesiumMapLike | null, options: MapSyncOptions = {}) {
  const fireEvent = useFireEventStore()
  const showHotspotBeforePrediction = options.showHotspotBeforePrediction ?? options.mode === 'monitor'
  const showFireFrontAfterPrediction = options.showFireFrontAfterPrediction ?? true
  const showAgentLayersOnlyAfterDecision = options.showAgentLayersOnlyAfterDecision ?? true

  const render = () => {
    const map = getMap()
    if (!map) return

    map.clearHotspots?.()
    map.clearFireFronts?.()
    map.clearDemoEntities?.()

    const activePoint = firstLngLat(
      fireEvent.trustedFirePoint,
      fireEvent.eventDetail
        ? {
            longitude: fireEvent.eventDetail.ignition_longitude,
            latitude: fireEvent.eventDetail.ignition_latitude
          }
        : null
    )

    if (showHotspotBeforePrediction && activePoint) {
      map.addHotspotGeoJson?.(hotspotGeoJson(activePoint, fireEvent.trustedFirePoint ? '可信火点' : '事件起火点'))
    }
    const viewCenter = () => bestViewCenter(fireEvent, options.mode, activePoint)
    const viewZoom = () => {
      if (options.zoom) return options.zoom
      if (options.mode === 'route' || options.mode === 'resource' || options.mode === 'command') return 10.8
      return WIND_VIEW_ZOOM
    }

    if (!fireEvent.hasPredictedFire) {
      map.flyTo?.({ center: viewCenter(), zoom: viewZoom() })
      return
    }

    const geojson = fireEvent.forefireResult?.geojson
    if (showFireFrontAfterPrediction && geojson?.features?.length) {
      map.addFireFrontTimeline?.(geojson, { intervalMs: 1200 })
    }

    if (showAgentLayersOnlyAfterDecision && !fireEvent.hasAgentDecision) {
      map.flyTo?.({ center: viewCenter(), zoom: viewZoom() })
      return
    }

    const renderedFromPackages = renderPackageMap(map, fireEvent, options.mode)
    if (renderedFromPackages) {
      map.flyTo?.({ center: viewCenter(), zoom: viewZoom() })
      return
    }

    if (showAgentLayersOnlyAfterDecision) {
      map.flyTo?.({ center: viewCenter(), zoom: viewZoom() })
      return
    }

    // No synthetic fallback routes: wait for Agent packages before drawing route/UAV/resource layers.

    map.flyTo?.({ center: viewCenter(), zoom: viewZoom() })
  }

  const stop = watch(
    () => [
      fireEvent.eventId,
      fireEvent.eventDetail,
      fireEvent.trustedFirePoint,
      fireEvent.hasPredictedFire,
      fireEvent.hasAgentDecision,
      fireEvent.forefireResult,
      fireEvent.spreadSteps,
      fireEvent.agentResult,
      fireEvent.recommendationPackage,
      fireEvent.routePackage,
      fireEvent.resetSignal,
    ],
    render,
    { deep: true }
  )

  setTimeout(render, 0)
  return { render, stop }
}


