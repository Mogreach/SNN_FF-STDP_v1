# MNIST 生成物

本目录保存 MNIST 的硬件输入和初始化数据。

- `all_spikes.bin`：按“训练正样本、训练负样本、测试标签 0~9 候选”顺序排列的脉冲数据，供 SD 卡或调试器加载到 DDR。
- `test_labels.h`：PS 端统计分类准确率所需的真实标签数组。
- `weights_weight.coe/.txt`：量化并打包的突触权重；`.coe` 面向存储器初始化，`.txt` 面向仿真或拆分。
- `weights_bank_*.txt`：按每 bank 2048 行拆分的权重。
- `pre_neuron_state.txt`、`post_neuron_state.txt`：神经元 SRAM 初始状态。
- `pos_derivative.coe`、`neg_derivative.coe`：正/负样本 FF-STDP 更新查找表。

文件格式取决于 `hardware_sim/hardware_sim_config.py`。当前配置与 `user/src/snn_ff/Top_test.v` 一致：`T=8`、输入 784、输出 256、后神经元并行度 8、权重 9 bit、单 lane 后神经元状态 20 bit。
