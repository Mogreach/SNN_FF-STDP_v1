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

这些脚本依赖外部 `SNN-forwardforward` 工程及 PyTorch、torchvision、NumPy、Brian2、Matplotlib/Seaborn。源码中仍保留 Windows 绝对 `sys.path`，且模型路径是仓库外相对路径；迁移机器后先修改这两处。建议从仓库根目录运行，以便 `Gen_out/<TASK>` 路径正确。

## 当前注意事项

- 配置文件与当前 `Top_test` 都是 784→256、T=8、后神经元并行度 8、权重 9 bit。
- `gen_model_weight_coe.py` 只处理遍历到的第一层，并在源码中标记 COE 对齐问题。
- `gen_sigmoid.py` 生成 RTL 的输出路径仍写成 `./hardware/src/...`，本仓库实际路径为 `./user/src/...`。
- `gen_data_flow.py` 的样本上限和 RTL/Vitis 宏应人工对齐，生成后用文件大小公式复核。

因此这些脚本属于可复现基础和历史工作流，而不是当前可一键运行的流水线。
