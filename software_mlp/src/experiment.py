"""MLP experiment settings and training-result types."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class ProfilingOptions:
    capture_manual_grad_metrics: bool = False
    capture_autograd_comparison: bool = False


@dataclass(frozen=True)
class ExperimentModeConfig:
    learning_mode: str = "unsupervised"
    hidden_layer_update_mode: str = "autograd"
    update_schedule: str = "separate"
    step_mode: str = "s"
    encoding_method: str = "poisson"
    profiling: ProfilingOptions = field(default_factory=ProfilingOptions)

    def __post_init__(self):
        choices = {
            "learning_mode": ("unsupervised", "supervised"),
            "hidden_layer_update_mode": ("autograd", "manual"),
            "update_schedule": ("separate", "paired"),
            "step_mode": ("s", "m"),
            "encoding_method": ("poisson", "frequency", "encoder_layer"),
        }
        for key, allowed in choices.items():
            if getattr(self, key) not in allowed:
                raise ValueError(f"Unsupported {key}={getattr(self, key)!r}; choose from {allowed}")

    @property
    def is_unsupervised(self): return self.learning_mode == "unsupervised"

    @property
    def is_supervised(self): return self.learning_mode == "supervised"

    @property
    def uses_manual_update(self): return self.hidden_layer_update_mode == "manual"

    @property
    def uses_separate_update_schedule(self): return self.update_schedule == "separate"

    @property
    def uses_encoder_layer_encoding(self): return self.encoding_method == "encoder_layer"


@dataclass(frozen=True)
class ExperimentStrategyConfig:
    neg_sample_strategy: str = "auto"
    goodness_strategy: str = "auto"
    hidden_loss_strategy: str = "auto"


@dataclass
class GradientProfilingSnapshot:
    backward_peak_alloc_bytes: Optional[float] = None
    backward_peak_reserved_bytes: Optional[float] = None
    manual_grad_peak_alloc_bytes: Optional[float] = None
    manual_grad_peak_reserved_bytes: Optional[float] = None
    manual_grad_time_ms: Optional[float] = None
    manual_grad_ops_est: Optional[float] = None
    backward_cmp_peak_alloc_bytes: Optional[float] = None
    backward_cmp_peak_reserved_bytes: Optional[float] = None
    backward_cmp_time_ms: Optional[float] = None


@dataclass
class StepResult:
    goodness_pos: list[float]
    goodness_neg: list[float]
    cos_pos: list[Optional[float]]
    cos_neg: list[Optional[float]]
    spike_out_pos: list[float]
    spike_out_neg: list[float]
    profiler: GradientProfilingSnapshot = field(default_factory=GradientProfilingSnapshot)
