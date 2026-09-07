from datetime import timedelta
from random import Random

from app.adapters.contracts import SimulatedObservation
from app.models.event import FireEvent


class SimulatedSatelliteDetectionAdapter:
    """Simulates processed outputs from a three-stage satellite fire detection chain."""

    def collect(self, event: FireEvent) -> list[SimulatedObservation]:
        rng = Random(f"{event.event_id}:satellite")
        base_lng = event.ignition_longitude
        base_lat = event.ignition_latitude
        base_time = event.started_at

        def jitter(scale: float) -> tuple[float, float]:
            return (
                base_lng + rng.uniform(-scale, scale),
                base_lat + rng.uniform(-scale, scale),
            )

        wide_lng, wide_lat = jitter(0.004)
        precise_lng, precise_lat = jitter(0.0016)
        verified_lng, verified_lat = jitter(0.0009)

        return [
            SimulatedObservation(
                source_type="satellite",
                source_name="simulated_fy4_thermal",
                stage="wide_scan",
                longitude=wide_lng,
                latitude=wide_lat,
                confidence=0.64,
                observed_at=base_time,
                attributes={
                    "chain_stage": "wide_scan",
                    "thermal_anomaly": True,
                    "brightness_temperature": 318.6,
                    "pixel_size_m": 1000,
                    "cloud_cover": 0.18,
                    "candidate_rank": 1,
                },
            ),
            SimulatedObservation(
                source_type="satellite",
                source_name="simulated_gaofen_infrared",
                stage="precision_filter",
                longitude=precise_lng,
                latitude=precise_lat,
                confidence=0.78,
                observed_at=base_time + timedelta(minutes=3),
                attributes={
                    "chain_stage": "precision_filter",
                    "thermal_anomaly": True,
                    "cloud_filtered": True,
                    "industrial_heat_filtered": True,
                    "bare_ground_filtered": True,
                    "pixel_size_m": 30,
                },
            ),
            SimulatedObservation(
                source_type="satellite",
                source_name="simulated_sentinel_temporal",
                stage="temporal_verification",
                longitude=verified_lng,
                latitude=verified_lat,
                confidence=0.84,
                observed_at=base_time + timedelta(minutes=6),
                attributes={
                    "chain_stage": "temporal_verification",
                    "multi_temporal_growth": True,
                    "front_expansion_hint": "northeast",
                    "time_window_minutes": 12,
                },
            ),
        ]
