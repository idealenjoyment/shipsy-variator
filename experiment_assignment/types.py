from dataclasses import dataclass
from typing import List, Any, Optional

@dataclass(frozen=True)
class VariantBoundary:
    variant_id: str
    cumulative_upper: float

@dataclass(frozen=True)
class TargetingRule:
    attribute: str
    operator: str
    value: Any = None
    values: Optional[List[Any]] = None

@dataclass
class ExperimentConfig:
    key: str
    status: str
    variants: List[VariantBoundary]
    targeting: Optional[List[TargetingRule]] = None
