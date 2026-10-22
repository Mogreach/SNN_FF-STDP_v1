# MLP FF-STDP 软件实验

本目录提供基于 PyTorch 与 SpikingJelly 的多层脉冲 MLP 实验。隐藏层使用正负样本的局部 goodness 目标更新，层间脉冲表示停止梯度传播；末层是交叉熵训练的分类头。支持监督和无监督两条训练/推理路径、可选负样本策略、goodness 定义和隐藏层损失，以及 MNIST、FashionMNIST、CIFAR10、CIFAR100 四种静态图像数据集。

## 文件树

```text
software_mlp/
├── README.md
├── .gitignore                  # 不跟踪运行产物、checkpoint 和缓存
├── run_experiment.py           # 数据加载、参数校验、训练、验证、测试
└── src/
    ├── experiment.py          # 学习模式、策略配置、逐步训练结果
    ├── encoding.py            # Poisson、频率与首层编码
    ├── optimization.py        # Adam/SGD 构建
    ├── loss.py                # MLP FF 损失和手动梯度
    ├── ff_strategies/
    │   ├── negative_sampling.py  # 正/负样本构造与注册表
    │   ├── goodness.py           # goodness 计算与手动梯度规则
    │   └── objectives.py         # 隐藏层局部目标
    └── mlp_models/
        ├── ff_snn_mlp_sup.py    # 监督路径：隐藏层 + 分类头
        └── ff_snn_mlp_unsup.py  # 无监督路径：隐藏层 + 分类头
```

`runs/` 在首次运行时按需创建；`config.json`、`checkpoint_last.pth`、`checkpoint_best.pth` 都保存在每次运行独立的输出目录中。脚本拒绝写入非空输出目录，避免覆盖历史实验。

## 环境与数据

依赖 Python、PyTorch、torchvision、SpikingJelly 和 NumPy。已验证的本地组合是 `torch 1.13.0`、`torchvision 0.14.0`、`spikingjelly 0.0.0.0.14`、`numpy 1.22.4`。在项目根目录运行 `python software_mlp/run_experiment.py --help` 可查看完整参数。无数据下载步骤；请先在 `--data-dir` 指定的 torchvision 数据根目录准备好数据。

| `--dataset` | 单张图像 | 输入宽度 | 类别数 | 典型 `--dims` |
| --- | --- | ---: | ---: | --- |
| `MNIST` | `[1,28,28]` | 784 | 10 | `784 256 10` |
| `FashionMNIST` | `[1,28,28]` | 784 | 10 | `784 256 10` |
| `CIFAR10` | `[3,32,32]` | 3072 | 10 | `3072 256 10` |
| `CIFAR100` | `[3,32,32]` | 3072 | 100 | `3072 256 100` |

未提供 `--dims` 时会按数据集自动选择表中的结构。数据目录应含 `MNIST/raw/`、`FashionMNIST/raw/`、`cifar-10-batches-py/` 或 `cifar-100-python/` 中对应的子目录。全部使用 `ToTensor()`，不做 CIFAR 数据增强或标准化，以保持 Poisson 编码输入在 `[0,1]`。训练集按类别、以固定 `--seed` 分出验证集；官方测试集仅用于训练后的最终评估。

## 训练与评估

先用小批次确认环境和数据路径；下例只评估每个划分的首个 batch，准确率**不能当作正式实验结果**：

```bash
python software_mlp/run_experiment.py \
  --dataset MNIST --learning-mode unsupervised --device cpu \
  --epochs 1 --batch-size 2 --eval-batch-size 2 --T 2 --dims 784 16 10 \
  --max-train-batches 1 --max-eval-batches 1 \
  --data-dir /path/to/data --out-dir software_mlp/runs/mnist_smoke
```

完整无监督 MNIST 和监督 FashionMNIST 示例：

```bash
python software_mlp/run_experiment.py \
  --dataset MNIST --learning-mode unsupervised --device cuda:0 \
  --data-dir /path/to/data --out-dir software_mlp/runs/mnist_unsup_seed42

python software_mlp/run_experiment.py \
  --dataset FashionMNIST --learning-mode supervised --device cuda:0 \
  --data-dir /path/to/data --out-dir software_mlp/runs/fashion_sup_seed42
```

CIFAR10 可以在相同入口使用 `--dataset CIFAR10`；CIFAR100 的无监督模式默认采用全图 Fourier 标签策略：

```bash
python software_mlp/run_experiment.py \
  --dataset CIFAR100 --learning-mode unsupervised --device cuda:0 \
  --data-dir /path/to/data --out-dir software_mlp/runs/cifar100_unsup_seed42
```

默认实验条件为 200 epoch、batch 500、`T=8`、Adam、学习率 `0.015625`、Poisson 编码、单步 `IFNode`、`autograd`、正负样本分别更新（`separate`）。最后约 5% 的 epoch 冻结隐藏层，仅更新分类头。每个 epoch 打印验证准确率和最后一个训练 batch 的各层正负 goodness；`checkpoint_best.pth` 按最佳验证准确率选择，最终打印该权重的测试准确率。仅评估 checkpoint 时，须传入与训练一致的数据集、模式、结构和策略，例如：

```bash
python software_mlp/run_experiment.py \
  --dataset MNIST --learning-mode unsupervised --dims 784 256 10 --T 8 \
  --data-dir /path/to/data --device cuda:0 --eval-only \
  --checkpoint software_mlp/runs/mnist_unsup_seed42/checkpoint_best.pth
```

`--checkpoint` 只加载模型参数，不恢复优化器或 epoch，不能作为断点续训。完整实验请使用独立的 `--out-dir`，并保留输出目录中的配置文件。

## 学习路径与数据流

输入批次为 `[B,C,H,W]`；正负样本构造后经编码得到 `[T,B,C,H,W]`，再展平为 `[T,B,C·H·W]`。隐藏层执行 `Linear → IFNode`，统计时间窗口内的发放频率并计算 goodness。隐藏层逐层局部优化，向下一层传递的脉冲表示会 `detach()`；末层是无 IF 神经元的线性分类头，使用各隐藏层脉冲的拼接表示与真实标签计算交叉熵。

- `unsupervised`：默认用真类/错误类标签覆盖图像构造正负样本，隐藏层默认优化 `pairwise_goodness`。推理时依次假设每个候选标签，累计隐藏层 goodness，选择最大者；分类头不参与这个投票。选择 `SCFF` 时会从训练集建立每类一张参考图，使候选标签在推理时对应不同的混合输入。
- `supervised`：默认用 `SCFF` 构造正负图像，隐藏层默认优化正负 goodness 差值的 `supervised_delta`；分类头用正分支脉冲和真实标签训练。推理时直接把图像输入网络，按分类头跨时间步累积分数最高的类别决策，不枚举候选标签。

`--hidden-update autograd` 用局部损失反传更新本层参数；`manual` 使用 `loss.py` 中的解析近似梯度。`--update-schedule separate` 使正、负分支分开更新，`paired` 则在同一次局部目标中合并两分支。改变这些条件后应使用新的输出目录。`--encoding poisson` 对像素概率逐时间步采样二值输入脉冲；`frequency` 在每个时间步重复连续像素值。`--step-mode s` 逐时间步运行，`m` 让 SpikingJelly 多步运行。

## 负样本策略：`--neg-sample`

| 名称 | 正样本 | 负样本与用途 |
| --- | --- | --- |
| `auto` | 根据学习模式选择 | 无监督默认 `embed_label_onehot`；监督默认 `SCFF`。无监督 CIFAR100 例外，默认 `global_fourier_label`。 |
| `embed_label_onehot` | 清空第一行前 $K$ 个像素，再在真实类别的位置写入图像最大值 | 改写为随机错误类别；用于按候选标签计算 goodness。$K$ 为类别数，要求图像宽度至少 $K$。 |
| `embed_zero_onehot` | 第一行前 $K$ 个像素全部置 1 | 在真实类别位置置 0；对应另一种正/负标签覆盖定义。也要求宽度至少 $K$。 |
| `SCFF` | 同一图像与自身相加，按图像空间范围 min-max 归一化 | 与 batch 内另一张图像相加并归一化，比较“自组合”和“异组合”；训练 batch 至少 2 张。无监督推理另用每类参考图构造候选标签输入。 |
| `global_fourier_label` | 全图混合真实类别对应的正弦/余弦二维纹理，混合强度 0.35 | 换成随机错误类别纹理并归一化；不占用固定宽度标签区，适用于 CIFAR100。 |

`negative_sampling.py` 还提供连续空间掩码拼接负样本的辅助函数，但它不是本入口的注册策略。CIFAR100 的 100 类超过 32 像素图像宽度，因此显式选择两种第一行标签覆盖策略会在启动前报错。`SCFF` 在训练 batch 为 1 时无法构造不同图像，也会提前报错。

## Goodness 与局部目标

设 $T$ 为时间步数、$f_j$ 为隐藏神经元 $j$ 的平均发放频率、$S_j=T f_j$ 为窗口内发放数、$V_j$ 为平均膜电位，$N$ 为隐藏神经元数：

| `--goodness` | 每样本计算式 | 含义 |
| --- | --- | --- |
| `auto` | 与 `spike_square_mean` 相同 | 两种学习模式的默认值。 |
| `spike_square` | $S_j^2$，保留每个神经元 | 强调高发放数神经元，输出是向量。 |
| `spike_square_mean` | $\frac{1}{N}\sum_j S_j^2$ | 发放数平方的神经元均值，默认标量 goodness。 |
| `freq_square` | $T f_j^2$，保留每个神经元 | 基于发放频率的向量 goodness。 |
| `freq_square_mean` | $\frac{T}{N}\sum_j f_j^2$ | 基于发放频率的标量 goodness。 |
| `membrane_potential_square_mean` | $\frac{T}{N}\sum_j V_j^2$ | 使用 IF 前平均膜电位；仅支持 `autograd` 更新。 |

设正、负 goodness 为 $G^+$、$G^-$，阈值参数为 $\theta$：

| `--hidden-loss` | 定义 | 默认用途 |
| --- | --- | --- |
| `auto` | 按学习模式选择 | 无监督选 `pairwise_goodness`，监督选 `supervised_delta`。 |
| `pairwise_goodness` | 对 $\theta-G^+$ 和 $G^--\theta$ 分别作 softplus 后取均值 | 推高正样本 goodness、压低负样本 goodness。 |
| `supervised_delta` | $\operatorname{softplus}[-\theta(G^+-G^-)]$ 的均值 | 优化正负 goodness 间隔；这里 `--loss-threshold` 同时充当该式系数。 |

`manual` 仅适用于具有手动梯度规则的脉冲/频率 goodness；`membrane_potential_square_mean + manual` 会被拒绝。不同 goodness 的量纲不同，调整策略时应重新检查 `--loss-threshold`，不要直接横向比较未校准的损失数值。

本目录只完成了小批次功能验证，尚未在这里重新跑完默认的 200 epoch；CIFAR 数据运行需要用户提供对应数据集文件。
