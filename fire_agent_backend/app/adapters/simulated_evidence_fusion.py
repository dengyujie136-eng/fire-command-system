from dataclasses import dataclass

from app.models.observation import Observation


@dataclass(frozen=True)
class EvidenceContribution:
    observation_id: str
    source_type: str
    reliability: float
    weight: float
    contribution: float
    explanation: str


@dataclass(frozen=True)
class FusionComputation:
    confidence: float
    longitude: float
    latitude: float
    confirmed: bool
    decision: str
    quality: dict
    contributions: list[EvidenceContribution]


class SimulatedEvidenceFusionAdapter:
    """Computes a deterministic evidence fusion result from processed observations."""

    RELIABILITY = {
        "satellite": 0.78,
        "uav": 0.93,
        "watchtower": 0.82,
        "canopy_sensor": 0.74,
        "ground_sensor": 0.79,
    }

    def fuse(self, observations: list[Observation]) -> FusionComputation:
        if not observations:
            raise ValueError("Cannot fuse an empty observation list.")

        raw_scores: list[tuple[Observation, float, float]] = []
        for obs in observations:
            reliability = self.RELIABILITY.get(obs.source_type, 0.65)
            raw_scores.append((obs, reliability, max(0.0, obs.confidence * reliability)))

        total = sum(score for _, _, score in raw_scores) or 1.0
        contributions: list[EvidenceContribution] = []
        lng = 0.0
        lat = 0.0
        for obs, reliability, score in raw_scores:
            weight = score / total
            lng += obs.longitude * weight
            lat += obs.latitude * weight
            contributions.append(
                EvidenceContribution(
                    observation_id=obs.observation_id,
                    source_type=obs.source_type,
                    reliability=round(reliability, 3),
                    weight=round(weight, 4),
                    contribution=round(obs.confidence * reliability, 4),
                    explanation=f"{obs.source_type} evidence contributed with confidence {obs.confidence:.2f} and reliability {reliability:.2f}.",
                )
            )

        source_types = {obs.source_type for obs in observations}
        coverage_bonus = min(0.12, len(source_types) * 0.018)
        confidence = min(0.98, sum(obs.confidence * c.weight for obs, c in zip(observations, contributions)) + coverage_bonus)
        confirmed = confidence >= 0.82 and len(source_types) >= 4

        return FusionComputation(
            confidence=round(confidence, 3),
            longitude=round(lng, 7),
            latitude=round(lat, 7),
            confirmed=confirmed,
            decision="trusted_fire_point" if confirmed else "needs_review",
            quality={
                "completeness": round(min(1.0, len(source_types) / 5), 3),
                "accuracy": round(confidence, 3),
                "source_count": len(source_types),
                "observation_count": len(observations),
            },
            contributions=contributions,
        )
