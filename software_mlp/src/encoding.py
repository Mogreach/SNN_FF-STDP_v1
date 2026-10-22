from __future__ import annotations

"""
Centralized encoding strategies for FF-SNN models.
Extensible via register_encoding_strategy() — add new methods without modifying model code.
"""

from dataclasses import dataclass
from typing import Callable

import torch
from spikingjelly.activation_based import encoding as sj_encoding
from spikingjelly.activation_based import functional


ENCODING_POISSON = "poisson"
ENCODING_FREQUENCY = "frequency"
ENCODING_IF = "if"
ENCODING_ENCODER_LAYER = "encoder_layer"


@dataclass(frozen=True)
class EncodingStrategySpec:
    encode_fn: Callable[[torch.Tensor, int], torch.Tensor]


_ENCODING_REGISTRY: dict[str, EncodingStrategySpec] = {}


def register_encoding_strategy(name: str, spec: EncodingStrategySpec) -> None:
    _ENCODING_REGISTRY[name] = spec


def list_encoding_strategies() -> tuple[str, ...]:
    return tuple(sorted(_ENCODING_REGISTRY))


def resolve_encoding_strategy(name: str) -> EncodingStrategySpec:
    if name not in _ENCODING_REGISTRY:
        raise ValueError(f"Unknown encoding strategy={name!r}. Registered: {list_encoding_strategies()}")
    return _ENCODING_REGISTRY[name]


def _poisson_encode(images: torch.Tensor, T: int) -> torch.Tensor:
    device = images.device
    spike_train = torch.zeros((T, *images.shape), device=device)
    for t in range(T):
        spike_train[t] += sj_encoding.PoissonEncoder()(images)
    return spike_train


def _frequency_encode(images: torch.Tensor, T: int) -> torch.Tensor:
    return images.unsqueeze(0).expand(T, -1, -1, -1, -1).contiguous()


def _integrate_and_fire_encode(images: torch.Tensor, T: int) -> torch.Tensor:
    B, C, H, W = images.shape
    device = images.device
    spike_train = torch.zeros((T, B, C, H, W), device=device)
    v_mem = torch.zeros((B, C, H, W), device=device)
    for t in range(T):
        v_mem += images
        spike = (v_mem >= 1.0).to(torch.float32)
        spike_train[t] = spike
        v_mem *= (1.0 - spike)
    return spike_train


register_encoding_strategy(ENCODING_POISSON, EncodingStrategySpec(encode_fn=_poisson_encode))
register_encoding_strategy(ENCODING_FREQUENCY, EncodingStrategySpec(encode_fn=_frequency_encode))
register_encoding_strategy(ENCODING_IF, EncodingStrategySpec(encode_fn=_integrate_and_fire_encode))
# Before the trainable first layer, encoder-layer mode is represented by the
# repeated analog frame. The first layer performs the actual spike conversion.
register_encoding_strategy(
    ENCODING_ENCODER_LAYER,
    EncodingStrategySpec(encode_fn=_frequency_encode),
)


def build_encoder(method: str, T: int) -> Callable[[torch.Tensor], torch.Tensor]:
    spec = resolve_encoding_strategy(method)
    return lambda images: spec.encode_fn(images, T=T)


def encode_with_first_layer(images: torch.Tensor, T: int,
                             first_layer: torch.nn.Module,
                             step_mode: str = "s") -> torch.Tensor:
    x_seq = _frequency_encode(images, T)
    if step_mode == "m":
        with torch.no_grad():
            spike_out = first_layer(x_seq)
        functional.reset_net(first_layer)
        out = spike_out[0] if isinstance(spike_out, (tuple, list)) else spike_out
    else:
        outputs = []
        with torch.no_grad():
            B = images.shape[0]
            device = images.device
            ln_mean = torch.zeros((B,), device=device)
            ln_var = torch.ones((B,), device=device)
            for t in range(T):
                out_t, _, _, _ = first_layer(x_seq[t], ln_mean, ln_var)
                if out_t.dim() == 4:
                    ln_mean = out_t.mean(dim=(1, 2, 3))
                    ln_var = out_t.var(dim=(1, 2, 3), unbiased=False)
                else:
                    ln_mean = out_t.mean(dim=1)
                    ln_var = out_t.var(dim=1, unbiased=False)
                outputs.append(out_t)
        functional.reset_net(first_layer)
        out = torch.stack(outputs, dim=0)
    return out
