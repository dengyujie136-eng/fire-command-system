import { watch } from 'vue'
import { useDixieFireStore } from '../stores/dixieFireStore'

type DixieMapLike = {
  addDixieHotspotsGeoJson?: (geojson: any) => void
  addDixieBurnedAreaGeoJson?: (geojson: any) => void
  clearDixieLayers?: () => void
  flyTo?: (options?: { center?: [number, number], zoom?: number, height?: number }) => void
}

function hotspotFeature(item: any) {
  const location = item?.location || item?.center || {}
  const longitude = Number(location.longitude ?? item?.longitude)
  const latitude = Number(location.latitude ?? item?.latitude)
  if (!Number.isFinite(longitude) || !Number.isFinite(latitude)) return null
  return {
    type: 'Feature',
    properties: {
      id: item.candidate_id || item.cluster_id,
      observed_at: item.observed_at,
      status: item.status,
      confidence_score: item.confidence_score ?? item.mean_confidence,
      frp_mw: item.frp_mw ?? item.max_frp_mw,
      data_owner: item.data_owner,
      satellite: item.product_fields?.firms?.satellite,
      source_product: item.source_product,
      point_count: item.point_count,
    },
    geometry: {
      type: 'Point',
      coordinates: [longitude, latitude],
    },
  }
}

function hotspotsGeoJson(items: any[]) {
  return {
    type: 'FeatureCollection',
    features: items.map(hotspotFeature).filter(Boolean),
  }
}

function burnedAreaGeoJson(item: any) {
  const geometry = item?.geometry
  if (!geometry) return { type: 'FeatureCollection', features: [] }
  return {
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        properties: {
          source_dataset: item.source_dataset,
          source_name: item.source_name,
          assessment_date: item.assessment_date,
          area_acres: item.area_acres,
          area_m2: item.area_m2,
        },
        geometry,
      },
    ],
  }
}

function burnedAreaCenter(item: any): [number, number] | null {
  const geometry = item?.geometry
  const polygons = geometry?.type === 'Polygon'
    ? [geometry.coordinates]
    : geometry?.type === 'MultiPolygon'
      ? geometry.coordinates
      : []
  let west = Number.POSITIVE_INFINITY
  let east = Number.NEGATIVE_INFINITY
  let south = Number.POSITIVE_INFINITY
  let north = Number.NEGATIVE_INFINITY

  polygons.forEach((polygon: any) => {
    polygon?.forEach((ring: any) => {
      ring?.forEach((position: any) => {
        const longitude = Number(position?.[0])
        const latitude = Number(position?.[1])
        if (!Number.isFinite(longitude) || !Number.isFinite(latitude)) return
        west = Math.min(west, longitude)
        east = Math.max(east, longitude)
        south = Math.min(south, latitude)
        north = Math.max(north, latitude)
      })
    })
  })

  if (![west, east, south, north].every(Number.isFinite)) return null
  return [(west + east) / 2, (south + north) / 2]
}

function bestCenter(store: ReturnType<typeof useDixieFireStore>): [number, number] | null {
  const burnedCenter = burnedAreaCenter(store.burnedArea)
  if (burnedCenter) return burnedCenter
  const point = store.event?.ignition_point
  if (point?.longitude && point?.latitude) return [Number(point.longitude), Number(point.latitude)]
  const first = store.hotspots[0]?.location
  if (first?.longitude && first?.latitude) return [Number(first.longitude), Number(first.latitude)]
  return null
}

export function syncDixieFireToMap(getMap: () => DixieMapLike | null) {
  const dixieFire = useDixieFireStore()
  let lastFocusedHotspots: any[] | null = null
  let lastFocusedBurnedArea: any | null = null

  const render = () => {
    const map = getMap()
    if (!map) return

    map.clearDixieLayers?.()

    if (dixieFire.layerVisibility.burnedArea && dixieFire.burnedArea) {
      map.addDixieBurnedAreaGeoJson?.(burnedAreaGeoJson(dixieFire.burnedArea))
    }

    if (dixieFire.layerVisibility.hotspots && dixieFire.hotspots.length) {
      map.addDixieHotspotsGeoJson?.(hotspotsGeoJson(dixieFire.hotspots))
    }

    const dataChanged = dixieFire.hotspots !== lastFocusedHotspots || dixieFire.burnedArea !== lastFocusedBurnedArea
    if (!dixieFire.loading && dixieFire.isLoaded && dataChanged) {
      const center = bestCenter(dixieFire)
      if (center) map.flyTo?.({ center, height: 250000 })
      lastFocusedHotspots = dixieFire.hotspots
      lastFocusedBurnedArea = dixieFire.burnedArea
    }
  }

  const stop = watch(
    () => [
      dixieFire.hotspots,
      dixieFire.burnedArea,
      dixieFire.loading,
      dixieFire.layerVisibility.hotspots,
      dixieFire.layerVisibility.burnedArea,
    ],
    render,
    { deep: true }
  )

  setTimeout(render, 0)
  return { render, stop }
}
