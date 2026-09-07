from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class SimulatedObservation:
    source_type: str
    source_name: str
    stage: str
    longitude: float
    latitude: float
    confidence: float
    observed_at: datetime
    attributes: dict[str, Any] = field(default_factory=dict)
    is_simulated: bool = True
    data_source_mode: str = "simulation"
