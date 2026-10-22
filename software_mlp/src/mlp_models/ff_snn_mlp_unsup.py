"""
====================================================================
File          : ff_snn_mlp_unsup.py
Description   : Unsupervised MLP-based FF-SNN model definition and training logic
Author        : Morgreach
Version       : 1.0.0
Date          : 2025-04-18
contact       : Mogreach@users.noreply.github.com
License       : MIT
====================================================================
"""
from __future__ import annotations

import time
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from spikingjelly.activation_based import encoding, functional, layer, neuron, surrogate
from src.experiment import ExperimentModeConfig, ExperimentStrategyConfig, GradientProfilingSnapshot, StepResult
from src.ff_strategies.negative_sampling import (
    NEG_SAMPLE_SCFF, generate_pos_n_neg_sample, resolve_negative_sampling_strategy_name,
)
from src.ff_strategies.goodness import (
    GOODNESS_SPIKE_SQUARE_MEAN, compute_goodness, prepare_manual_goodness_input_gradient,
    resolve_goodness_strategy_name, supports_manual_goodness_gradient,
)
from src.ff_strategies.objectives import (
    HIDDEN_LOSS_PAIRWISE, HIDDEN_LOSS_SUPERVISED_DELTA, compute_hidden_pair_loss, resolve_hidden_loss_strategy_name,
)
from src.loss import delta_loss_gradient_calculation_mlp, pairwise_loss_gradient_calculation_mlp
from src.encoding import build_encoder, encode_with_first_layer
from src.optimization import build_optimizer


# ═══════════════════════════════════════════════════════════════════════════════
# Net (top-level)
# ═══════════════════════════════════════════════════════════════════════════════
class Net(torch.nn.Module):
    def __init__(self, dims, tau, epoch, T, lr, v_threshold, v_threshold_neg,
                 opt, loss_threshold, num_classes, momentum=0.9,
                 mode_config=None, strategy_config=None, device=None):
        super().__init__()
        self.T = T
        self.loss_threshold = loss_threshold
        self.encoder = encoding.PoissonEncoder()
        self.num_classes = num_classes
        self.mode_config = mode_config or ExperimentModeConfig()
        self.strategy_config = strategy_config or ExperimentStrategyConfig()
        self.step_mode = self.mode_config.step_mode
        self.encoding_method = self.mode_config.encoding_method
        self.device = torch.device(device) if device is not None else torch.device(
            "cuda" if torch.cuda.is_available() else "cpu")
        # runtime stats
        self.last_backward_peak_alloc_bytes = None
        self.last_backward_peak_reserved_bytes = None
        self.last_manual_grad_peak_alloc_bytes = None
        self.last_manual_grad_peak_reserved_bytes = None
        self.last_manual_grad_time_ms = None
        self.last_manual_grad_ops_est = None
        self.last_backward_cmp_peak_alloc_bytes = None
        self.last_backward_cmp_peak_reserved_bytes = None
        self.last_backward_cmp_time_ms = None
        self.label_reference_bank = None

        self.layers = nn.ModuleList()
        for layer_idx in range(len(dims) - 1):
            # Hidden layers follow the FF-style local objective, while the last
            # layer stays as the classifier/readout head.
            if layer_idx == len(dims) - 2:
                module = OutputLayer(
                    in_features=sum(dims[1:layer_idx+1]), out_features=dims[layer_idx+1],
                    epoch=epoch, T=T, lr=lr, v_threshold=v_threshold,
                    v_threshold_neg=v_threshold_neg, tau=tau,
                    loss_threshold=loss_threshold, mode_config=self.mode_config,
                    strategy_config=self.strategy_config,
                    optimizer_name=opt, momentum=momentum,
                ).to(self.device)
            else:
                module = Layer(
                    in_features=dims[layer_idx], out_features=dims[layer_idx+1],
                    epoch=epoch, T=T, lr=lr, v_threshold=v_threshold,
                    v_threshold_neg=v_threshold_neg, tau=tau,
                    loss_threshold=loss_threshold, mode_config=self.mode_config,
                    strategy_config=self.strategy_config,
                    optimizer_name=opt, momentum=momentum,
                ).to(self.device)
            self.layers.append(module)

        # Flatten/Linear/IFNode receive step_mode in their constructors.
        # Applying set_step_mode to these plain wrapper modules only emits
        # SpikingJelly warnings and changes no behavior.

    # ── runtime stat aggregation ────────────────────────────────────────
    def _aggregate_runtime_stats(self) -> GradientProfilingSnapshot:
        # Each layer records its own local stats; the network exposes only the
        # max / summed view that the runner cares about.
        def _max(a, b): return b if a is None else (max(a, b) if b is not None else a)
        max_backward_peak_alloc = max_backward_peak_reserved = None
        max_manual_peak_alloc = max_manual_peak_reserved = None
        max_backward_cmp_peak_alloc = max_backward_cmp_peak_reserved = None
        manual_time_total_ms = manual_ops_total_est = backward_cmp_time_total_ms = 0.0
        for layer_module in self.layers:
            max_backward_peak_alloc = _max(max_backward_peak_alloc, getattr(layer_module, "last_backward_peak_alloc_bytes", None))
            max_backward_peak_reserved = _max(max_backward_peak_reserved, getattr(layer_module, "last_backward_peak_reserved_bytes", None))
            max_manual_peak_alloc = _max(max_manual_peak_alloc, getattr(layer_module, "last_manual_grad_peak_alloc_bytes", None))
            max_manual_peak_reserved = _max(max_manual_peak_reserved, getattr(layer_module, "last_manual_grad_peak_reserved_bytes", None))
            max_backward_cmp_peak_alloc = _max(max_backward_cmp_peak_alloc, getattr(layer_module, "last_backward_cmp_peak_alloc_bytes", None))
            max_backward_cmp_peak_reserved = _max(max_backward_cmp_peak_reserved, getattr(layer_module, "last_backward_cmp_peak_reserved_bytes", None))
            if getattr(layer_module, "last_manual_grad_time_ms", None): manual_time_total_ms += float(layer_module.last_manual_grad_time_ms)
            if getattr(layer_module, "last_manual_grad_ops_est", None): manual_ops_total_est += float(layer_module.last_manual_grad_ops_est)
            if getattr(layer_module, "last_backward_cmp_time_ms", None): backward_cmp_time_total_ms += float(layer_module.last_backward_cmp_time_ms)
        snapshot = GradientProfilingSnapshot(
            backward_peak_alloc_bytes=max_backward_peak_alloc, backward_peak_reserved_bytes=max_backward_peak_reserved,
            manual_grad_peak_alloc_bytes=max_manual_peak_alloc, manual_grad_peak_reserved_bytes=max_manual_peak_reserved,
            manual_grad_time_ms=manual_time_total_ms if manual_time_total_ms > 0 else None,
            manual_grad_ops_est=manual_ops_total_est if manual_ops_total_est > 0 else None,
            backward_cmp_peak_alloc_bytes=max_backward_cmp_peak_alloc, backward_cmp_peak_reserved_bytes=max_backward_cmp_peak_reserved,
            backward_cmp_time_ms=backward_cmp_time_total_ms if backward_cmp_time_total_ms > 0 else None,
        )
        for attr in ["last_backward_peak_alloc_bytes","last_backward_peak_reserved_bytes",
                      "last_manual_grad_peak_alloc_bytes","last_manual_grad_peak_reserved_bytes",
                      "last_manual_grad_time_ms","last_manual_grad_ops_est",
                      "last_backward_cmp_peak_alloc_bytes","last_backward_cmp_peak_reserved_bytes",
                      "last_backward_cmp_time_ms"]:
            setattr(self, attr, getattr(snapshot, attr, None))
        return snapshot

    # ── prediction (multi-label goodness voting) ────────────────────────
    def set_label_reference_bank(self, reference_bank):
        self.label_reference_bank = reference_bank.detach().clone().to(self.device)

    def predict_multiple(self, x):
        goodness_per_label = []
        resolved_strategy = resolve_negative_sampling_strategy_name(
            self.strategy_config.neg_sample_strategy, self.mode_config)
        if resolved_strategy == NEG_SAMPLE_SCFF:
            if self.label_reference_bank is None:
                raise RuntimeError("SCFF prediction requires a label reference bank")
            sampling_context = {"label_reference_bank": self.label_reference_bank}
        else:
            sampling_context = None
        for label_idx in range(self.num_classes):
            goodness = []
            label = torch.full((x.shape[0],), label_idx, device=x.device, dtype=torch.long)
            h, _ = generate_pos_n_neg_sample(x, label, num_classes=self.num_classes,
                strategy_name=self.strategy_config.neg_sample_strategy,
                mode_config=self.mode_config, sampling_context=sampling_context)
            h = self._encode_predict_input(h)
            h = h.flatten(2)
            start_idx = 1 if self.mode_config.uses_encoder_layer_encoding else 0
            for layer_idx, layer_module in enumerate(self.layers):
                if layer_idx < start_idx: continue
                if layer_idx == len(self.layers) - 1: break
                _, h, _, layer_goodness, _, _ = layer_module._forward_spike_sequence(h)
                functional.reset_net(layer_module.layer)
                goodness.append(layer_goodness.sum(1))
            goodness_per_label.append(sum(goodness).unsqueeze(1))
        goodness_of_all_label = torch.cat(goodness_per_label, 1)
        return goodness_of_all_label.argmax(1)

    def _encode_predict_input(self, x):
        if self.mode_config.uses_encoder_layer_encoding:
            return encode_with_first_layer(x, self.T, self.layers[0], self.step_mode)
        encoder = build_encoder(self.encoding_method, self.T)
        return encoder(x)

    # ── training ─────────────────────────────────────────────────────────
    def _encode_training_samples(self, x, label):
        x_pos, x_neg = generate_pos_n_neg_sample(x, label, num_classes=self.num_classes,
            strategy_name=self.strategy_config.neg_sample_strategy, mode_config=self.mode_config)
        if self.mode_config.uses_encoder_layer_encoding:
            pos = encode_with_first_layer(x_pos, self.T, self.layers[0], self.step_mode)
            neg = encode_with_first_layer(x_neg, self.T, self.layers[0], self.step_mode)
        else:
            encoder = build_encoder(self.encoding_method, self.T)
            pos = encoder(x_pos)
            neg = encoder(x_neg)
        return pos.flatten(2), neg.flatten(2)

    def train_unsupervised(self, x, label, frozen) -> StepResult:
        return self._train_step(*self._encode_training_samples(x, label), label, frozen)

    def train_ff_stdp(self, x, label, frozen): return self.train_unsupervised(x, label, frozen)

    def _train_step(self, input_pos, input_neg, label, frozen) -> StepResult:
        # This module only owns the unsupervised MLP branch, so the hidden-layer
        # loop can stay explicit and easy to read.
        T, B, _ = input_pos.shape
        pos_goodness_per_layer, neg_goodness_per_layer = [], []
        pos_cos_sim_per_layer, neg_cos_sim_per_layer = [], []
        pos_spike_out_per_layer, neg_spike_out_per_layer = [], []
        pos_spike_in_of_output_layer = torch.empty((T, B, 0), device=input_pos.device)
        neg_spike_in_of_output_layer = torch.empty((T, B, 0), device=input_neg.device)
        for layer_idx, layer_module in enumerate(self.layers):
            if layer_idx == len(self.layers) - 1:
                layer_module.train_bp_stdp(pos_spike_in_of_output_layer, label); continue
            (input_pos, pos_goodness, pos_cos_sim,
             input_neg, neg_goodness, neg_cos_sim) = layer_module.train_unsupervised(input_pos, input_neg, frozen)
            pos_goodness_per_layer.append(pos_goodness)
            neg_goodness_per_layer.append(neg_goodness)
            pos_cos_sim_per_layer.append(pos_cos_sim)
            neg_cos_sim_per_layer.append(neg_cos_sim)
            pos_spike_out_per_layer.append(input_pos.mean().detach().cpu().item())
            neg_spike_out_per_layer.append(input_neg.mean().detach().cpu().item())
            pos_spike_in_of_output_layer = torch.cat((pos_spike_in_of_output_layer, input_pos), dim=2)
            neg_spike_in_of_output_layer = torch.cat((neg_spike_in_of_output_layer, input_neg), dim=2)
        profiler_snapshot = self._aggregate_runtime_stats()
        return StepResult(
            goodness_pos=pos_goodness_per_layer, goodness_neg=neg_goodness_per_layer,
            cos_pos=pos_cos_sim_per_layer, cos_neg=neg_cos_sim_per_layer,
            spike_out_pos=pos_spike_out_per_layer, spike_out_neg=neg_spike_out_per_layer,
            profiler=profiler_snapshot)

    def save(self, args, path):
        check_point = {"net": {f"layer_{i}": layer_module.state_dict() for i, layer_module in enumerate(self.layers)}, "args": args}
        torch.save(check_point, path)

    def load(self, path):
        check_point = torch.load(path)
        for i, layer_module in enumerate(self.layers):
            key = f"layer_{i}"
            if key in check_point["net"]:
                layer_module.load_state_dict(check_point["net"][key])
                print(f"[OK] Loaded {key}")
            else:
                print(f"[Skip] {key} not found in checkpoint, skipped.")
        print(check_point["args"])


# ═══════════════════════════════════════════════════════════════════════════════
# Layer (hidden, single-step IFNode, no LN)
# ═══════════════════════════════════════════════════════════════════════════════
class Layer(nn.Module):
    def __init__(self, in_features, out_features, epoch, T, lr, v_threshold, v_threshold_neg,
                 tau, loss_threshold, mode_config=None, strategy_config=None,
                 optimizer_name="adam", momentum=0.9):
        super().__init__()
        step_mode = mode_config.step_mode if mode_config is not None else "s"
        self.layer = nn.Sequential(
            layer.Flatten(step_mode=step_mode),
            layer.Linear(in_features, out_features, bias=False, step_mode=step_mode),
            neuron.IFNode(v_reset=None, v_threshold=v_threshold, surrogate_function=surrogate.ATan(),
                          step_mode=step_mode),
        )
        self.lr = lr; self.v_threshold = v_threshold
        self.in_features = in_features; self.out_features = out_features
        self.num_epochs = epoch; self.T = T; self.threshold = loss_threshold
        self.encoder = encoding.PoissonEncoder()
        self.opt = build_optimizer(
            self.parameters(), name=optimizer_name, lr=lr, momentum=momentum,
        )
        self.mode_config = mode_config or ExperimentModeConfig()
        self.strategy_config = strategy_config or ExperimentStrategyConfig()
        self.step_mode = self.mode_config.step_mode
        self._reset_runtime_stats()
        self.visible = False; self.spike_vis = torch.zeros(out_features).unsqueeze(1)

    def forward(self, x, *args):
        if self.step_mode == "m":
            x = self.layer[0](x)  # Flatten
            x = self.layer[1](x)  # Linear
            membrane_potential = x
            x = self.layer[2](x)  # IFNode
            return x, membrane_potential, None, None
        # The pre-IF activation is also needed by membrane-potential goodness.
        x = self.layer[0](x)
        membrane_potential = self.layer[1](x)
        spike = self.layer[2](membrane_potential)
        return spike, membrane_potential, None, None

    def initialize(self):
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.normal_(module.weight.data, std=np.sqrt(2 / self.out_features))
                module.weight.data += 0.1

    def cal_goodness(self, freq, *, membrane_potential=None):
        return compute_goodness(freq, T=self.T, strategy_name=self.strategy_config.goodness_strategy,
                                default_strategy_name=GOODNESS_SPIKE_SQUARE_MEAN, membrane_potential=membrane_potential)

    def _validate_manual_strategy_combo(self) -> str:
        resolved_goodness = resolve_goodness_strategy_name(
            self.strategy_config.goodness_strategy,
            default_strategy_name=GOODNESS_SPIKE_SQUARE_MEAN,
        )
        resolved_loss = resolve_hidden_loss_strategy_name(self.strategy_config.hidden_loss_strategy, self.mode_config)
        if not supports_manual_goodness_gradient(resolved_goodness, default_strategy_name=GOODNESS_SPIKE_SQUARE_MEAN):
            raise NotImplementedError(
                "Analytical manual gradients for the MLP hidden layer only "
                "support goodness strategies that define a manual analytical "
                "gradient rule. Use autograd mode or register the goodness "
                "strategy with manual_activity_transform and "
                "manual_input_gradient_transform.")
        if resolved_loss not in {HIDDEN_LOSS_PAIRWISE, HIDDEN_LOSS_SUPERVISED_DELTA}:
            raise NotImplementedError(
                "Analytical manual gradients for the MLP hidden layer only "
                "support local loss strategies 'pairwise_goodness' and "
                "'supervised_delta'. Use autograd mode or extend loss.py "
                "with a matching analytical gradient.")
        return resolved_loss

    def _get_linear_weight(self):
        for module in self.layer.modules():
            if isinstance(module, nn.Linear): return module.weight
        raise RuntimeError("Linear layer not found.")

    def _begin_profile(self):
        device = self._get_linear_weight().device
        use_cuda_mem_stat = device.type == "cuda" and (self.mode_config.profiling.capture_manual_grad_metrics
                                                        or self.mode_config.profiling.capture_autograd_comparison)
        if use_cuda_mem_stat:
            torch.cuda.synchronize(device)
            base_alloc = torch.cuda.memory_allocated(device)
            base_reserved = torch.cuda.memory_reserved(device)
            torch.cuda.reset_peak_memory_stats(device)
        else: base_alloc = base_reserved = None
        start_time = time.perf_counter()
        return device, use_cuda_mem_stat, base_alloc, base_reserved, start_time

    def _end_profile(self, profile_ctx):
        device, use_cuda_mem_stat, base_alloc, base_reserved, start_time = profile_ctx
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        if use_cuda_mem_stat:
            torch.cuda.synchronize(device)
            peak_alloc = max(0., float(torch.cuda.max_memory_allocated(device) - base_alloc))
            peak_reserved = max(0., float(torch.cuda.max_memory_reserved(device) - base_reserved))
        else: peak_alloc = peak_reserved = None
        return peak_alloc, peak_reserved, elapsed_ms

    def _reset_runtime_stats(self):
        for attr in ["last_backward_peak_alloc_bytes","last_backward_peak_reserved_bytes",
                      "last_manual_grad_peak_alloc_bytes","last_manual_grad_peak_reserved_bytes",
                      "last_manual_grad_time_ms","last_manual_grad_ops_est",
                      "last_backward_cmp_peak_alloc_bytes","last_backward_cmp_peak_reserved_bytes",
                      "last_backward_cmp_time_ms"]:
            setattr(self, attr, None)

    # ── spike sequence forward (T-loop) ─────────────────────────────────
    def _forward_spike_sequence(self, encoded):
        if self.step_mode == "m":
            spike_out, membrane_potential, _, _ = self.forward(encoded)
            out_freq = spike_out.mean(0)
            goodness = self.cal_goodness(out_freq, membrane_potential=(membrane_potential.mean(0) if membrane_potential is not None else None))
            return encoded.sum(0), spike_out, out_freq, goodness, None, None
        # This helper isolates the repeated "simulate over T, then summarize into
        # firing frequency and goodness" pattern shared by pos/neg samples.
        _, batch_size, _ = encoded.shape
        output_spike = torch.zeros(self.T, batch_size, self.out_features, device=encoded.device)
        membrane_potential_sum = torch.zeros(batch_size, self.out_features, device=encoded.device)
        ln_mean = torch.zeros((batch_size,), device=encoded.device)
        ln_var = torch.zeros((batch_size,), device=encoded.device)
        for t in range(self.T):
            spike_out, membrane_potential, ln_mean, ln_var = self.forward(encoded[t], ln_mean, ln_var)
            output_spike[t] += spike_out
            # The original single-step IF path returns no membrane-potential
            # tensor; spike-based goodness therefore needs no accumulation.
            if membrane_potential is not None:
                membrane_potential_sum += membrane_potential
        out_freq = output_spike.mean(0)
        goodness = self.cal_goodness(out_freq, membrane_potential=(membrane_potential_sum / self.T))
        return encoded.sum(0), output_spike, out_freq, goodness, ln_mean, ln_var

    def _prepare_manual_goodness_input_gradient(self, freq):
        return prepare_manual_goodness_input_gradient(freq, T=self.T,
            strategy_name=self.strategy_config.goodness_strategy, default_strategy_name=GOODNESS_SPIKE_SQUARE_MEAN)

    def _zero_manual_branch_state(self, input_spike_sum, goodness_input_gradient, goodness, ln_var, ln_mean):
        return (torch.zeros_like(input_spike_sum), torch.zeros_like(goodness_input_gradient),
                torch.zeros_like(goodness),
                torch.zeros_like(ln_var) if ln_var is not None else None,
                torch.zeros_like(ln_mean) if ln_mean is not None else None)

    def _manual_hidden_loss_gradient(self, pos_input_spike_sum, pos_goodness_input_gradient,
                                      pos_goodness, pos_ln_var, pos_ln_mean,
                                      neg_input_spike_sum, neg_goodness_input_gradient,
                                      neg_goodness, neg_ln_var, neg_ln_mean,
                                      batch_size, hidden_loss_name):
        profile_ctx = self._begin_profile()
        with torch.no_grad():
            if hidden_loss_name == HIDDEN_LOSS_SUPERVISED_DELTA:
                weight_grad, _ = delta_loss_gradient_calculation_mlp(
                    pos_input_spike_sum, pos_goodness_input_gradient, pos_goodness, pos_ln_var, pos_ln_mean,
                    neg_input_spike_sum, neg_goodness_input_gradient, neg_goodness, neg_ln_var, neg_ln_mean,
                    self.threshold, self.v_threshold, batch_size)
            else:
                weight_grad, _ = pairwise_loss_gradient_calculation_mlp(
                    pos_input_spike_sum, pos_goodness_input_gradient, pos_goodness, pos_ln_var, pos_ln_mean,
                    neg_input_spike_sum, neg_goodness_input_gradient, neg_goodness, neg_ln_var, neg_ln_mean,
                    self.threshold, self.v_threshold, batch_size)
        peak_alloc, peak_reserved, elapsed_ms = self._end_profile(profile_ctx)
        return weight_grad.detach(), peak_alloc, peak_reserved, elapsed_ms

    def _apply_manual_update(self, weight_grad, frozen):
        if frozen: return
        with torch.no_grad():
            # Keep the original direct weight update rule for the manual branch.
            self._get_linear_weight().add_(self.lr * weight_grad)

    def _apply_autograd_update(self, pos_goodness, neg_goodness, frozen):
        if frozen: return
        profile_ctx = self._begin_profile()
        self.opt.zero_grad()
        loss = compute_hidden_pair_loss(pos_goodness, neg_goodness, threshold=self.threshold,
            strategy_name=self.strategy_config.hidden_loss_strategy, mode_config=self.mode_config)
        scaler = getattr(self, '_scaler', None)
        if scaler is not None: scaler.scale(loss).backward(); scaler.unscale_(self.opt); scaler.step(self.opt)
        else: loss.backward(); self.opt.step()
        peak_alloc, peak_reserved, _ = self._end_profile(profile_ctx)
        if peak_alloc is not None:
            self.last_backward_peak_alloc_bytes = max(self.last_backward_peak_alloc_bytes or 0., peak_alloc)
            self.last_backward_peak_reserved_bytes = max(self.last_backward_peak_reserved_bytes or 0., peak_reserved)

    def _autograd_hidden_loss_comparison(self, pos_goodness, neg_goodness):
        profile_ctx = self._begin_profile()
        self.opt.zero_grad()
        loss = compute_hidden_pair_loss(pos_goodness, neg_goodness, threshold=self.threshold,
            strategy_name=self.strategy_config.hidden_loss_strategy, mode_config=self.mode_config)
        loss.backward()
        grad = self._get_linear_weight().grad.detach().clone()
        peak_alloc, peak_reserved, elapsed_ms = self._end_profile(profile_ctx)
        self.opt.zero_grad()
        return grad, peak_alloc, peak_reserved, elapsed_ms

    # ── main training entry ─────────────────────────────────────────────
    def train_unsupervised(self, pos_encoded, neg_encoded, frozen):
        # Hidden-layer unsupervised path:
        # local goodness objective + manual/autograd switch from mode_config.
        _, batch_size, _ = pos_encoded.shape
        self._reset_runtime_stats()
        needs_manual_grad = self.mode_config.uses_manual_update
        manual_hidden_loss_name = None
        if needs_manual_grad: manual_hidden_loss_name = self._validate_manual_strategy_combo()
        pos_cos_sim = neg_cos_sim = None

        if needs_manual_grad:
            if self.mode_config.uses_separate_update_schedule:
                # Preserve the original experiment: update once after the
                # positive branch and once after the negative branch.
                (pos_input_spike_sum, pos_output_spike, pos_out_freq,
                 pos_goodness, pos_ln_mean, pos_ln_var) = self._forward_spike_sequence(pos_encoded)
                pos_goodness_input_gradient = self._prepare_manual_goodness_input_gradient(pos_out_freq)
                (zero_neg_input_spike_sum, zero_neg_goodness_input_gradient,
                 zero_neg_goodness, zero_neg_ln_var, zero_neg_ln_mean) = self._zero_manual_branch_state(
                    pos_input_spike_sum, pos_goodness_input_gradient, pos_goodness, pos_ln_var, pos_ln_mean)
                (pos_weight_grad, pos_manual_peak_alloc,
                 pos_manual_peak_reserved, pos_manual_time_ms) = self._manual_hidden_loss_gradient(
                    pos_input_spike_sum, pos_goodness_input_gradient, pos_goodness, pos_ln_var, pos_ln_mean,
                    zero_neg_input_spike_sum, zero_neg_goodness_input_gradient,
                    zero_neg_goodness, zero_neg_ln_var, zero_neg_ln_mean,
                    batch_size, manual_hidden_loss_name)
                if self.mode_config.profiling.capture_autograd_comparison:
                    (pos_autograd_grad, pos_bp_peak_alloc,
                     pos_bp_peak_reserved, pos_bp_time_ms) = self._autograd_hidden_loss_comparison(pos_goodness, zero_neg_goodness)
                self._apply_manual_update(pos_weight_grad, frozen)
                functional.reset_net(self.layer)

                (neg_input_spike_sum, neg_output_spike, neg_out_freq,
                 neg_goodness, neg_ln_mean, neg_ln_var) = self._forward_spike_sequence(neg_encoded)
                neg_goodness_input_gradient = self._prepare_manual_goodness_input_gradient(neg_out_freq)
                (zero_pos_input_spike_sum, zero_pos_goodness_input_gradient,
                 zero_pos_goodness, zero_pos_ln_var, zero_pos_ln_mean) = self._zero_manual_branch_state(
                    neg_input_spike_sum, neg_goodness_input_gradient, neg_goodness, neg_ln_var, neg_ln_mean)
                (neg_weight_grad, neg_manual_peak_alloc,
                 neg_manual_peak_reserved, neg_manual_time_ms) = self._manual_hidden_loss_gradient(
                    zero_pos_input_spike_sum, zero_pos_goodness_input_gradient,
                    zero_pos_goodness, zero_pos_ln_var, zero_pos_ln_mean,
                    neg_input_spike_sum, neg_goodness_input_gradient,
                    neg_goodness, neg_ln_var, neg_ln_mean,
                    batch_size, manual_hidden_loss_name)
                if self.mode_config.profiling.capture_autograd_comparison:
                    (neg_autograd_grad, neg_bp_peak_alloc,
                     neg_bp_peak_reserved, neg_bp_time_ms) = self._autograd_hidden_loss_comparison(zero_pos_goodness, neg_goodness)
                self._apply_manual_update(neg_weight_grad, frozen)
                functional.reset_net(self.layer)

                alloc_vals = [v for v in [pos_manual_peak_alloc, neg_manual_peak_alloc] if v is not None]
                reserved_vals = [v for v in [pos_manual_peak_reserved, neg_manual_peak_reserved] if v is not None]
                self.last_manual_grad_peak_alloc_bytes = max(alloc_vals) if alloc_vals else None
                self.last_manual_grad_peak_reserved_bytes = max(reserved_vals) if reserved_vals else None
                self.last_manual_grad_time_ms = float((pos_manual_time_ms or 0.) + (neg_manual_time_ms or 0.))
                if self.mode_config.profiling.capture_autograd_comparison:
                    cmp_alloc = [v for v in [pos_bp_peak_alloc, neg_bp_peak_alloc] if v is not None]
                    cmp_reserved = [v for v in [pos_bp_peak_reserved, neg_bp_peak_reserved] if v is not None]
                    self.last_backward_cmp_peak_alloc_bytes = max(cmp_alloc) if cmp_alloc else None
                    self.last_backward_cmp_peak_reserved_bytes = max(cmp_reserved) if cmp_reserved else None
                    self.last_backward_cmp_time_ms = float((pos_bp_time_ms or 0.) + (neg_bp_time_ms or 0.))
                    if pos_weight_grad is not None:
                        pos_cos_sim = torch.cosine_similarity(pos_autograd_grad.flatten(), -pos_weight_grad.flatten(), dim=0).detach().cpu().item()
                    if neg_weight_grad is not None:
                        neg_cos_sim = torch.cosine_similarity(neg_autograd_grad.flatten(), -neg_weight_grad.flatten(), dim=0).detach().cpu().item()
            else:
                # Paired manual mode now shares the same loss selector as the
                # separate schedule, but uses the real pos/neg branches together.
                (pos_input_spike_sum, pos_output_spike, pos_out_freq,
                 pos_goodness, pos_ln_mean, pos_ln_var) = self._forward_spike_sequence(pos_encoded)
                functional.reset_net(self.layer)
                pos_goodness_input_gradient = self._prepare_manual_goodness_input_gradient(pos_out_freq)
                (neg_input_spike_sum, neg_output_spike, neg_out_freq,
                 neg_goodness, neg_ln_mean, neg_ln_var) = self._forward_spike_sequence(neg_encoded)
                functional.reset_net(self.layer)
                neg_goodness_input_gradient = self._prepare_manual_goodness_input_gradient(neg_out_freq)
                (weight_grad, manual_peak_alloc,
                 manual_peak_reserved, manual_time_ms) = self._manual_hidden_loss_gradient(
                    pos_input_spike_sum, pos_goodness_input_gradient, pos_goodness, pos_ln_var, pos_ln_mean,
                    neg_input_spike_sum, neg_goodness_input_gradient, neg_goodness, neg_ln_var, neg_ln_mean,
                    batch_size, manual_hidden_loss_name)
                self.last_manual_grad_peak_alloc_bytes = manual_peak_alloc
                self.last_manual_grad_peak_reserved_bytes = manual_peak_reserved
                self.last_manual_grad_time_ms = float(manual_time_ms or 0.)
                if self.mode_config.profiling.capture_autograd_comparison:
                    (autograd_grad, bp_peak_alloc,
                     bp_peak_reserved, bp_time_ms) = self._autograd_hidden_loss_comparison(pos_goodness, neg_goodness)
                    self.last_backward_cmp_peak_alloc_bytes = bp_peak_alloc
                    self.last_backward_cmp_peak_reserved_bytes = bp_peak_reserved
                    self.last_backward_cmp_time_ms = float(bp_time_ms or 0.)
                    cos_sim = torch.cosine_similarity(autograd_grad.flatten(), -weight_grad.flatten(), dim=0).detach().cpu().item()
                    pos_cos_sim = neg_cos_sim = cos_sim
                self._apply_manual_update(weight_grad, frozen)
            self.last_manual_grad_ops_est = float(4. * batch_size * self.out_features * self.in_features)
        else:
            # ── autograd branch ──
            (pos_input_spike_sum, pos_output_spike, pos_out_freq,
             pos_goodness, pos_ln_mean, pos_ln_var) = self._forward_spike_sequence(pos_encoded)
            if self.mode_config.uses_separate_update_schedule:
                self._apply_autograd_update(pos_goodness, torch.zeros_like(pos_goodness), frozen)
            functional.reset_net(self.layer)
            (neg_input_spike_sum, neg_output_spike, neg_out_freq,
             neg_goodness, neg_ln_mean, neg_ln_var) = self._forward_spike_sequence(neg_encoded)
            if self.mode_config.uses_separate_update_schedule:
                self._apply_autograd_update(torch.zeros_like(neg_goodness), neg_goodness, frozen)
            else: self._apply_autograd_update(pos_goodness, neg_goodness, frozen)
            functional.reset_net(self.layer)
        return (pos_output_spike.detach(), pos_goodness.detach().mean().cpu().item(), pos_cos_sim,
                neg_output_spike.detach(), neg_goodness.detach().mean().cpu().item(), neg_cos_sim)

    def train_ff_stdp(self, pos_encoded, neg_encoded, frozen):
        return self.train_unsupervised(pos_encoded, neg_encoded, frozen)

    def predict(self, x):
        if self.step_mode == "m":
            return self.forward(x)
        """x [T,B,in_features] → [T,B,out_features] via T-loop."""
        batch_size = x.shape[1]
        output = torch.zeros(self.T, batch_size, self.out_features, device=x.device)
        ln_mean = torch.zeros((batch_size,), device=x.device)
        ln_var = torch.zeros((batch_size,), device=x.device)
        for t in range(self.T):
            spike_out, _, ln_mean, ln_var = self.forward(x[t], ln_mean, ln_var)
            output[t] += spike_out
        functional.reset_net(self.layer)
        return output


# ═══════════════════════════════════════════════════════════════════════════════
# OutputLayer
# ═══════════════════════════════════════════════════════════════════════════════
class OutputLayer(nn.Module):
    def __init__(self, in_features, out_features, epoch, T, lr, v_threshold, v_threshold_neg,
                 tau, loss_threshold, mode_config=None, strategy_config=None,
                 optimizer_name="adam", momentum=0.9):
        super().__init__()
        step_mode = mode_config.step_mode if mode_config is not None else "s"
        self.layer = nn.Sequential(
            layer.Flatten(step_mode=step_mode),
            layer.Linear(in_features, out_features, bias=False, step_mode=step_mode),
        )
        self.lr = lr; self.spike_input_rate = 0
        self.in_features = in_features; self.out_features = out_features
        self.num_epochs = epoch; self.T = T; self.threshold = loss_threshold
        self.encoder = encoding.PoissonEncoder()
        self.opt = build_optimizer(
            self.parameters(), name=optimizer_name, lr=lr, momentum=momentum,
        )
        self.mode_config = mode_config or ExperimentModeConfig()
        self.strategy_config = strategy_config or ExperimentStrategyConfig()
        self._reset_runtime_stats()
        self.step_mode = step_mode
        self.visible = False; self.spike_vis = torch.zeros(out_features).unsqueeze(1)

    def _reset_runtime_stats(self):
        for attr in ["last_backward_peak_alloc_bytes","last_backward_peak_reserved_bytes",
                      "last_manual_grad_peak_alloc_bytes","last_manual_grad_peak_reserved_bytes",
                      "last_manual_grad_time_ms","last_manual_grad_ops_est",
                      "last_backward_cmp_peak_alloc_bytes","last_backward_cmp_peak_reserved_bytes",
                      "last_backward_cmp_time_ms"]:
            setattr(self, attr, None)

    def forward(self, x):
        return self.layer(x)

    def train_bp_stdp(self, x_encoded, label):
        self._reset_runtime_stats()
        batch_size = x_encoded.shape[1]
        device = x_encoded.device
        use_cuda_mem_stat = device.type == "cuda" and (self.mode_config.profiling.capture_manual_grad_metrics
                                                        or self.mode_config.profiling.capture_autograd_comparison)
        if self.step_mode == "m":
            output_spike = self.forward(x_encoded)
        else:
            output_spike = torch.zeros(self.T, batch_size, self.out_features, device=device)
            for t in range(self.T):
                output_spike[t] += self.forward(x_encoded[t])
        spike_freq = output_spike.mean(0)
        self.opt.zero_grad()
        loss = F.cross_entropy(spike_freq.view(-1, self.out_features), label.view(-1))
        scaler = getattr(self, '_scaler', None)
        if scaler is not None: loss = scaler.scale(loss)
        if use_cuda_mem_stat:
            torch.cuda.synchronize(device)
            base_alloc = torch.cuda.memory_allocated(device)
            base_reserved = torch.cuda.memory_reserved(device)
            torch.cuda.reset_peak_memory_stats(device)
        loss.backward()
        if use_cuda_mem_stat:
            torch.cuda.synchronize(device)
            self.last_backward_peak_alloc_bytes = max(0., float(torch.cuda.max_memory_allocated(device) - base_alloc))
            self.last_backward_peak_reserved_bytes = max(0., float(torch.cuda.max_memory_reserved(device) - base_reserved))
        else: self.last_backward_peak_alloc_bytes = self.last_backward_peak_reserved_bytes = None
        if scaler is not None: scaler.unscale_(self.opt); scaler.step(self.opt)
        else: self.opt.step()
        functional.reset_net(self.layer)
        return output_spike.detach()

    def predict(self, x):
        if self.step_mode == "m":
            return self.forward(x)
        """x [T,B,in_features] → [T,B,out_features]."""
        output = torch.zeros(self.T, x.shape[1], self.out_features, device=x.device)
        for t in range(self.T):
            spike_out = self.forward(x[t])
            output[t] += spike_out
        functional.reset_net(self.layer)
        return output
