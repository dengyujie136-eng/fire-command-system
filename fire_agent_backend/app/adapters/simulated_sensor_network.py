from datetime import timedelta
from random import Random

from app.adapters.contracts import SimulatedObservation
from app.models.event import FireEvent


class SimulatedSensorNetworkAdapter:
    """Simulates processed observations from the four-layer sensing network."""

    def collect(self, event: FireEvent) -> list[SimulatedObservation]:
        rng = Random(f"{event.event_id}:sensor_network")
        base_lng = event.ignition_longitude
        base_lat = event.ignition_latitude
        base_time = event.started_at

        def jitter(scale: float) -> tuple[float, float]:
            return (
                base_lng + rng.uniform(-scale, scale),
                base_lat + rng.uniform(-scale, scale),
            )

        uav_lng, uav_lat = jitter(0.0008)
        tower_lng, tower_lat = jitter(0.0022)
        canopy_lng, canopy_lat = jitter(0.0014)
        ground_lng, ground_lat = jitter(0.0012)

        return [
            SimulatedObservation(
                source_type="uav",
                source_name="simulated_uav_01",
                stage="low_altitude_review",
                longitude=uav_lng,
                latitude=uav_lat,
                confidence=0.91,
                observed_at=base_time + timedelta(minutes=8),
                attributes={
                    "layer": "air_low_altitude",
                    "thermal_confirmed": True,
                    "smoke_visible": True,
                    "flame_visible": False,
                    "image_quality": 0.86,
                    "altitude_m": 260,
                },
            ),
            SimulatedObservation(
                source_type="watchtower",
                source_name="simulated_watchtower_northwest",
                stage="high_point_smoke_detection",
                longitude=tower_lng,
                latitude=tower_lat,
                confidence=0.82,
                observed_at=base_time + timedelta(minutes=5),
                attributes={
                    "layer": "high_point",
                    "smoke_detected": True,
                    "flame_light_detected": False,
                    "visibility_km": 7.4,
                    "camera_status": "online",
                },
            ),
            SimulatedObservation(
                source_type="canopy_sensor",
                source_name="simulated_canopy_robot_03",
                stage="canopy_anomaly",
                longitude=canopy_lng,
                latitude=canopy_lat,
                confidence=0.74,
                observed_at=base_time + timedelta(minutes=4),
                attributes={
                    "layer": "canopy",
                    "temperature_c": 43.8,
                    "humidity_percent": 24.5,
                    "co_ppm": 18.4,
                    "canopy_stress_index": 0.71,
                },
            ),
            SimulatedObservation(
                source_type="ground_sensor",
                source_name="simulated_ground_sensor_12",
                stage="ground_environment_anomaly",
                longitude=ground_lng,
                latitude=ground_lat,
                confidence=0.79,
                observed_at=base_time + timedelta(minutes=2),
                attributes={
                    "layer": "ground",
                    "temperature_c": 39.2,
                    "humidity_percent": 28.1,
                    "smoke_ug_m3": 184,
                    "wind_speed_m_s": 4.2,
                    "wind_direction_deg": 45,
                },
            ),
        ]
