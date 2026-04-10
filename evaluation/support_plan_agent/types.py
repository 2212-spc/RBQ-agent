from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


@dataclass(slots=True)
class ObservableSlot:
    label: str
    role: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ObservableSketch:
    output_slots: List[ObservableSlot]
    filter_hints: List[Dict[str, Any]] = field(default_factory=list)
    time_hints: Dict[str, List[int]] = field(default_factory=lambda: {"years": [], "months": []})
    measure_hints: List[str] = field(default_factory=list)
    grouping_hints: List[str] = field(default_factory=list)
    operator_hints: List[str] = field(default_factory=list)
    order_hint: Dict[str, Any] = field(default_factory=dict)
    raw_response: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AtomicObligation:
    name: str
    probability: float
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RolePrior:
    role: str
    target: str
    probability: float
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ObligationSketch:
    obligations: List[AtomicObligation]
    role_priors: List[RolePrior] = field(default_factory=list)
    family_labels: List[Dict[str, Any]] = field(default_factory=list)
    raw_response: Dict[str, Any] = field(default_factory=dict)

    def probability(self, name: str) -> float:
        for obligation in self.obligations:
            if obligation.name == name:
                return obligation.probability
        return 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Binding:
    source_id: str
    file_name: str
    view_name: str
    column_name: str
    role: str
    score: float
    reasons: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AnchorPath:
    path_source_ids: List[str]
    edges: List[Dict[str, Any]]
    score: float
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SupportPlan:
    output_bindings: List[Binding]
    plan_kind: str = "direct_join"
    output_join_paths: List[AnchorPath] = field(default_factory=list)
    filter_join_paths: List[AnchorPath] = field(default_factory=list)
    order_join_path: AnchorPath | None = None
    support_binding: Binding | None = None
    anchor_binding: AnchorPath | None = None
    evidence_bindings: List[Binding] = field(default_factory=list)
    measure_binding: Binding | None = None
    order_binding: Binding | None = None
    filter_bindings: List[Binding] = field(default_factory=list)
    operator_plan: Dict[str, Any] = field(default_factory=dict)
    satisfied_obligations: List[str] = field(default_factory=list)
    unmet_obligations: List[str] = field(default_factory=list)
    confidence: float = 0.0
    source_trace: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    evidence_source_ids: List[str] = field(default_factory=list)
    aggregation_unit_kind: str | None = None
    aggregation_anchor_source_id: str | None = None
    aggregation_mode: str | None = None
    ranking_target_kind: str | None = None
    plan_score: "PlanScore | None" = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PlanScore:
    family_name: str
    base_retrieval_score: float
    output_consistency: float
    filter_consistency: float
    aggregation_consistency: float
    ordering_consistency: float
    obligation_consistency: float
    shape_sanity: float
    semantic_complete: bool
    semantic_gap_count: int = 0
    semantic_complete_reasons: List[str] = field(default_factory=list)
    hard_invalid: bool = False
    hard_invalid_reasons: List[str] = field(default_factory=list)
    total: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class IRStep:
    op: str
    args: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SupportPlanIR:
    kind: str
    compile_ready: bool
    steps: List[IRStep] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    compile_reason: str | None = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
