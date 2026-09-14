# hardware_sim

这一目录负责把软件侧 FF-SNN 模型、数据集与 RTL 所需的定点/二进制格式衔接起来。

| 文件 | 作用 | 主要输出 |
| --- | --- | --- |
| `hardware_sim_config.py` | 集中配置任务、模型路径、维度、并行度、位宽、量化尺度和阈值 | 被其余脚本导入 |
| `gen_data_flow.py` | 载入软件模型和数据集，生成正/负训练样本、10 候选测试样本和标签 | `all_spikes.bin`、`test_labels.h` |
| `gen_model_weight_coe.py` | 提取首层权重、定点量化、按并行度打包并拆 bank | 权重 `.coe/.txt`、`weights_bank_*.txt` |
| `gen_neuron_state.py` | 构造前/后神经元 SRAM 初值 | `pre_neuron_state.txt`、`post_neuron_state.txt` |
| `gen_sigmoid.py` | 计算 FF 正/负梯度查找表并量化 | `pos_derivative.coe`、`neg_derivative.coe`；也可生成 ROM RTL |
| `test_debug.py` | 软件模型准确率、goodness、发放率和权重可视化 | 交互图和调试输出 |

## 使用前提

这些脚本依赖外部 `SNN-forwardforward` 工程及 PyTorch、torchvision、NumPy、Brian2、Matplotlib/Seaborn。`gen_data_flow.py` 与 `gen_model_weight_coe.py` 顶部仍保留 Windows 绝对 `sys.path.append('D:/OneDrive/...')`；迁移机器后必须先改成当前软件模型路径，或用 `PYTHONPATH` 提供。脚本按仓库根目录为工作目录运行，输出写入 `./Gen_out/<TASK>/`。

`NET_PATH`（在 `hardware_sim_config.py`）是相对仓库根目录的模型 checkpoint 路径，当前指向仓库内的 `./hardware_sim/MNIST_91.pth`。改成仓库外 checkpoint 时沿用同样的“相对根目录”写法。

## 当前注意事项

- 配置文件与当前 `Top_test` 都是 784→256、T=8、后神经元并行度 8、权重 9 bit。
- `gen_model_weight_coe.py` 只处理遍历到的第一层，并在源码中标记 COE 对齐问题。
- `gen_sigmoid.py` 生成 ROM RTL 时写的是 `./hardware/src/snn_ff/rom/...`，本仓库实际路径为 `./user/src/snn_ff/rom/...`。该路径在重跑前需修正，否则只使用它同时导出的 `Gen_out/<TASK>/*.coe`。
- `gen_data_flow.py` 的样本上限和 RTL/Vitis 宏应人工对齐，生成后用文件大小公式复核。

因此这些脚本属于可复现基础和历史工作流，而不是当前可一键运行的流水线。
