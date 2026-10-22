"""Train or evaluate supervised/unsupervised MLP FF-STDP on image datasets.

Datasets are read from an external torchvision data directory. Use --data-dir
if the default location does not exist on this machine.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader, Subset
from torchvision import datasets, transforms

from src.experiment import ExperimentModeConfig, ExperimentStrategyConfig
from src.ff_strategies.goodness import list_goodness_strategies
from src.ff_strategies.negative_sampling import (
    NEG_SAMPLE_SCFF, list_negative_sampling_strategies,
    resolve_negative_sampling_strategy_name,
)
from src.ff_strategies.objectives import list_hidden_loss_strategies
from src.mlp_models.ff_snn_mlp_sup import Net as SupervisedNet
from src.mlp_models.ff_snn_mlp_unsup import Net as UnsupervisedNet


# Original machine: /home/mogreach/WorkSpace/Work-Local-Server/SNN_FFSTDP/SNN-forwardforward/data
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "SNN_FFSTDP" / "SNN-forwardforward" / "data"
DATASET_SPECS = {
    "MNIST": (datasets.MNIST, 1, 28, 28, 10),
    "FashionMNIST": (datasets.FashionMNIST, 1, 28, 28, 10),
    "CIFAR10": (datasets.CIFAR10, 3, 32, 32, 10),
    "CIFAR100": (datasets.CIFAR100, 3, 32, 32, 100),
}


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=tuple(DATASET_SPECS), default="MNIST")
    parser.add_argument("--learning-mode", choices=("unsupervised", "supervised"), default="unsupervised")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--out-dir", type=Path, help="Fresh directory for this run; existing nonempty directories are rejected")
    parser.add_argument("--device", default="cuda:0" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dims", type=int, nargs="+", help="Input, hidden layer(s), classes; default derives from dataset")
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--eval-batch-size", type=int, default=500)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--val-ratio", type=float, default=0.1)
    parser.add_argument("--T", type=int, default=8)
    parser.add_argument("--lr", type=float, default=0.015625)
    parser.add_argument("--opt", choices=("adam", "sgd"), default="adam")
    parser.add_argument("--momentum", type=float, default=0.9)
    parser.add_argument("--tau", type=float, default=2.0)
    parser.add_argument("--v-threshold", type=float, default=1.2)
    parser.add_argument("--v-threshold-neg", type=float, default=-1.0)
    parser.add_argument("--loss-threshold", type=float, default=0.25)
    parser.add_argument("--hidden-update", choices=("autograd", "manual"), default="autograd")
    parser.add_argument("--update-schedule", choices=("separate", "paired"), default="separate")
    parser.add_argument("--step-mode", choices=("s", "m"), default="s")
    parser.add_argument("--encoding", choices=("poisson", "frequency"), default="poisson")
    parser.add_argument("--neg-sample", choices=("auto", *list_negative_sampling_strategies()), default="auto")
    parser.add_argument("--goodness", choices=("auto", *list_goodness_strategies()), default="auto")
    parser.add_argument("--hidden-loss", choices=("auto", *list_hidden_loss_strategies()), default="auto")
    parser.add_argument("--max-train-batches", type=int, default=0, help="0 = full epoch; positive = smoke limit")
    parser.add_argument("--max-eval-batches", type=int, default=0, help="0 = full evaluation; positive = smoke limit")
    parser.add_argument("--eval-only", action="store_true")
    parser.add_argument("--checkpoint", type=Path, help="Checkpoint to evaluate (weights only; no optimizer resume)")
    args = parser.parse_args()
    _, channels, height, width, num_classes = DATASET_SPECS[args.dataset]
    input_features = channels * height * width
    if args.dims is None:
        args.dims = [input_features, 256, num_classes]
    if (len(args.dims) < 3 or args.dims[0] != input_features
            or args.dims[-1] != num_classes or any(dim < 1 for dim in args.dims)):
        parser.error(f"--dims must start at {input_features}, end at {num_classes}, "
                     "and include at least one positive-width hidden layer")
    if args.neg_sample == "auto" and args.dataset == "CIFAR100" and args.learning_mode == "unsupervised":
        args.neg_sample = "global_fourier_label"
    if args.neg_sample in ("embed_label_onehot", "embed_zero_onehot") and num_classes > width:
        parser.error(f"{args.neg_sample} needs at least {num_classes} first-row pixels; "
                     f"{args.dataset} has width {width}. Use global_fourier_label or SCFF")
    if args.goodness == "membrane_potential_square_mean" and args.hidden_update == "manual":
        parser.error("membrane-potential goodness has no manual-gradient rule; use autograd")
    if not 0 < args.val_ratio < 1:
        parser.error("--val-ratio must be between 0 and 1")
    if args.eval_only and args.checkpoint is None:
        parser.error("--eval-only requires --checkpoint")
    if args.epochs < 1 or args.batch_size < 1 or args.T < 1:
        parser.error("epochs, batch-size and T must be positive")
    if args.batch_size < 2 and (args.neg_sample == "SCFF" or
            (args.neg_sample == "auto" and args.learning_mode == "supervised")) and not args.eval_only:
        parser.error("SCFF requires training batch-size >= 2 to construct a distinct negative")
    if args.out_dir is None:
        args.out_dir = (Path(__file__).resolve().parent / "runs" /
                        f"{args.dataset.lower()}_{args.learning_mode}_seed{args.seed}")
    return args


def seed_everything(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def stratified_indices(targets, val_ratio, seed):
    generator = torch.Generator().manual_seed(seed)
    targets = torch.as_tensor(targets)
    train_ids, val_ids = [], []
    for label in torch.unique(targets).tolist():
        class_ids = torch.nonzero(targets == label).flatten()
        shuffled = class_ids[torch.randperm(len(class_ids), generator=generator)].tolist()
        val_count = max(1, round(len(shuffled) * val_ratio))
        val_ids.extend(shuffled[:val_count])
        train_ids.extend(shuffled[val_count:])
    return train_ids, val_ids


def make_loaders(args):
    # All four torchvision datasets live under --data-dir; none are copied here.
    dataset_type = DATASET_SPECS[args.dataset][0]
    transform = transforms.ToTensor()
    try:
        full_train = dataset_type(root=str(args.data_dir), train=True, download=False, transform=transform)
        test = dataset_type(root=str(args.data_dir), train=False, download=False, transform=transform)
    except RuntimeError as exc:
        raise SystemExit(f"Dataset missing at {args.data_dir}; set --data-dir to the existing dataset root. {exc}") from exc
    train_ids, val_ids = stratified_indices(full_train.targets, args.val_ratio, args.seed)
    uses_scff = args.neg_sample == "SCFF" or (
        args.neg_sample == "auto" and args.learning_mode == "supervised")
    if uses_scff and len(train_ids) % args.batch_size == 1:
        raise SystemExit("SCFF would leave a one-image final training batch; choose another --batch-size")
    generator = torch.Generator().manual_seed(args.seed)
    train = DataLoader(Subset(full_train, train_ids), batch_size=args.batch_size, shuffle=True,
                       generator=generator, num_workers=args.workers)
    val = DataLoader(Subset(full_train, val_ids), batch_size=args.eval_batch_size,
                     shuffle=False, num_workers=args.workers)
    test = DataLoader(test, batch_size=args.eval_batch_size, shuffle=False, num_workers=args.workers)
    return train, val, test


@torch.no_grad()
def accuracy(model, loader, device, learning_mode, max_batches=0):
    model.eval()
    correct = count = 0
    for batch_idx, (x, y) in enumerate(loader):
        if max_batches and batch_idx >= max_batches:
            break
        x, y = x.to(device), y.to(device)
        prediction = (model.predict_multiple(x) if learning_mode == "unsupervised"
                      else model.predict_winner(x))
        correct += int((prediction == y).sum().item())
        count += y.numel()
    return correct / count if count else float("nan"), count


def load_weights(model, path, device):
    checkpoint = torch.load(path, map_location=device)
    for index, layer in enumerate(model.layers):
        layer.load_state_dict(checkpoint["net"][f"layer_{index}"])


def build_label_reference_bank(dataset, num_classes):
    """Pick one training image per class for label-conditioned SCFF voting."""
    references = [None] * num_classes
    missing = set(range(num_classes))
    for sample, label in dataset:
        label = int(label)
        if label in missing:
            references[label] = sample.detach().clone().float()
            missing.remove(label)
            if not missing:
                break
    if missing:
        raise RuntimeError(f"Cannot build SCFF reference bank; missing classes {sorted(missing)}")
    return torch.stack(references)


def main():
    args = parse_args()
    seed_everything(args.seed)
    device = torch.device(args.device)
    train_loader, val_loader, test_loader = make_loaders(args)
    mode = ExperimentModeConfig(learning_mode=args.learning_mode,
                                hidden_layer_update_mode=args.hidden_update,
                                update_schedule=args.update_schedule,
                                step_mode=args.step_mode, encoding_method=args.encoding)
    strategies = ExperimentStrategyConfig(neg_sample_strategy=args.neg_sample,
                                          goodness_strategy=args.goodness,
                                          hidden_loss_strategy=args.hidden_loss)
    _, _, _, _, num_classes = DATASET_SPECS[args.dataset]
    model_type = UnsupervisedNet if mode.is_unsupervised else SupervisedNet
    model = model_type(dims=args.dims, tau=args.tau, epoch=args.epochs, T=args.T, lr=args.lr,
                v_threshold=args.v_threshold, v_threshold_neg=args.v_threshold_neg,
                opt=args.opt, loss_threshold=args.loss_threshold, num_classes=num_classes,
                momentum=args.momentum, mode_config=mode,
                strategy_config=strategies, device=device).to(device)
    resolved_neg_sample = resolve_negative_sampling_strategy_name(args.neg_sample, mode)
    if mode.is_unsupervised and resolved_neg_sample == NEG_SAMPLE_SCFF:
        model.set_label_reference_bank(build_label_reference_bank(train_loader.dataset, num_classes))
    if args.checkpoint:
        load_weights(model, args.checkpoint, device)
    if args.eval_only:
        score, count = accuracy(model, test_loader, device, args.learning_mode, args.max_eval_batches)
        print(f"test_accuracy={score:.4f} evaluated={count}", flush=True)
        return

    # Refuse to overwrite a previous run: use a fresh --out-dir per experiment.
    if args.out_dir.exists() and any(args.out_dir.iterdir()):
        raise SystemExit(f"Output directory is not empty: {args.out_dir}")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    run_config = {
        **{key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()},
        "train_samples": len(train_loader.dataset),
        "val_samples": len(val_loader.dataset),
        "test_samples": len(test_loader.dataset),
    }
    (args.out_dir / "config.json").write_text(
        json.dumps(run_config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    best_val = -1.0
    for epoch in range(args.epochs):
        model.train()
        # Reserve the last 5% of epochs for classifier-head settling.
        frozen = args.epochs > 1 and epoch >= max(1, int(0.95 * args.epochs))
        result = None
        for batch_idx, (x, y) in enumerate(train_loader):
            if args.max_train_batches and batch_idx >= args.max_train_batches:
                break
            if mode.is_unsupervised:
                result = model.train_unsupervised(x.to(device), y.to(device), frozen)
            else:
                result = model.train_supervised(x.to(device), y.to(device), frozen)
        val_acc, val_count = accuracy(model, val_loader, device, args.learning_mode, args.max_eval_batches)
        print(f"epoch={epoch + 1}/{args.epochs} val_accuracy={val_acc:.4f} "
              f"evaluated={val_count} pos_goodness={result.goodness_pos if result else []} "
              f"neg_goodness={result.goodness_neg if result else []}", flush=True)
        model.save(run_config, args.out_dir / "checkpoint_last.pth")
        if val_acc > best_val:
            best_val = val_acc
            model.save(run_config, args.out_dir / "checkpoint_best.pth")
    load_weights(model, args.out_dir / "checkpoint_best.pth", device)
    test_acc, test_count = accuracy(model, test_loader, device, args.learning_mode, args.max_eval_batches)
    print(f"best_val_accuracy={best_val:.4f} best_checkpoint_test_accuracy={test_acc:.4f} "
          f"test_evaluated={test_count}", flush=True)


if __name__ == "__main__":
    main()
