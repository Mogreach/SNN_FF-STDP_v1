from __future__ import annotations

from collections.abc import Iterable

import torch


VALID_OPTIMIZERS = ("adam", "sgd")


def build_optimizer(
    parameters: Iterable[torch.nn.Parameter],
    *,
    name: str,
    lr: float,
    momentum: float,
    weight_decay: float = 0.0,
) -> torch.optim.Optimizer:
    """Build every experiment optimizer from the shared CLI configuration."""
    if weight_decay < 0:
        raise ValueError("weight_decay must be non-negative")
    normalized_name = name.lower()
    if normalized_name == "adam":
        return torch.optim.Adam(parameters, lr=lr, weight_decay=weight_decay)
    if normalized_name == "sgd":
        return torch.optim.SGD(
            parameters, lr=lr, momentum=momentum, weight_decay=weight_decay,
        )
    raise ValueError(
        f"Unsupported optimizer={name!r}; expected one of {VALID_OPTIMIZERS}."
    )
