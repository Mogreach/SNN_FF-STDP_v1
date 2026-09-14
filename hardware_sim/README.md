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

这些脚本依赖外部 `SNN-forwardforward` 工程及 PyTorch、torchvision、NumPy、Brian2、Matplotlib/Seaborn。`gen_data_flow.py` 与 `gen_model_weight_coe.py` 顶部仍有 `sys.path.append('D:/OneDrive/SNN_FFSTDP/SNN-forwardforward')`——**这是仓库外软件工程的路径，换机器后需要改成实际位置或用 `PYTHONPATH` 提供**，本轮未改动。

除上述外部依赖外，脚本自身路径已以 `hardware_sim_config.py` 里的 `REPO_ROOT`（由 `__file__` 推出）为锚点，因此**从任何目录运行都会写到同一个 `Gen_out/<TASK>/`**，不需要先 `cd` 到仓库根。`NET_PATH` 同样锚定到仓库内的 `hardware_sim/MNIST_91.pth`，换成仓库外 checkpoint 时改这一个常量即可；`USER_SRC_ROOT` 供 `gen_sigmoid.py` 写 ROM RTL。

注意：`gen_*` 脚本会直接覆盖 `Gen_out/<TASK>/` 下的同名产物。重跑前先确认当前数据是否还需要保留。

## 当前注意事项

- 配置文件与当前 `Top_test` 都是 784→256、T=8、后神经元并行度 8、权重 9 bit。
- `gen_model_weight_coe.py` 只处理遍历到的第一层，并在源码中标记 COE 对齐问题。
- `gen_sigmoid.py` 生成 ROM RTL 时直接写到 `user/src/snn_ff/rom/`（已锚定），重跑会覆盖 `pos_derivative_rom.v`/`neg_derivative_rom.v`，改动前先确认是否要保留当前版本。
- `gen_data_flow.py` 的样本上限和 RTL/Vitis 宏应人工对齐，生成后用文件大小公式复核。

因此这些脚本属于可复现基础和历史工作流，而不是当前可一键运行的流水线。
