# RTL 源码

当前可维护 RTL 入口是 `snn_ff/Top_test.v`，实现单层 `784→256` FF-STDP SNN，并由 `axi_rw/` 从 PS DDR 获取脉冲、写回 goodness。目标工程为 Zynq-7010（`xc7z010clg400-1`）。

## 结构

- `snn_ff/`：核心状态机、scheduler、神经元、突触、SRAM、ROM 和 AER 输出。
- `axi_rw/`：PL AXI4 master、DDR 数据读取、FIFO、AER 串行化、结果写回。
- `key_debounce.v`：板上启动/训练按键消抖。

## 修改规则

1. 网络/位宽/并行度先改 `snn_ff/Top_test.v`，再同步 `hardware_sim/hardware_sim_config.py`。
2. 突触参数变化时重新生成 `weights_weight.coe`，并在 Vivado 更新 `sram_synaptic`（72×25088 是当前固定几何）。
3. 样本数、DDR 基址、输入排列变化时同步 `axi_rw` 和 Vitis `main.c`。
4. 在 Vivado 刷新 module reference，综合的 source 必须指向本目录，而不是 `prj/` 的历史副本。

历史 LRF/多层设计笔记和同名工程快照不属于当前实现，不应作为新增功能的基础。
