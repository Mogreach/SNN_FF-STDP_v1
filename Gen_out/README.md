# Gen_out

脚本生成物归档目录。`hardware_sim/` 中的脚本依据 `hardware_sim_config.py` 的 `TASK`、网络规模和量化位宽，在这里输出供 RTL 初始化、仿真、SD 卡加载和结果对比使用的数据。

| 子目录 | 用途 |
| --- | --- |
| `MNIST/` | 当前默认任务的脉冲、标签、权重和状态数据 |
| `FashionMNIST/` | FashionMNIST 对应产物 |
| `Saif/` | Vivado 功耗分析所用的活动文件 |

不要只替换单个文件后直接综合。`TIME_STEP`、神经元数、并行度或权重位宽变化时，应重新生成同一任务下所有相关文件，并同步检查 RTL 参数与 DDR 容量。
