# Icarus Verilog

Icarus Verilog 仿真工作区，提供 AXI+SNN 和纯 SNN core 两套入口。

## 纯 SNN core 推理测试

入口为 `../tb_core_test.sv`。默认读取 2 个样本，固定 `IS_TRAIN=0`，不经过 AXI，直接用 AER 握手向 `Top_test` 送事件：

```sh
./run_core_test.sh
```

输出位于 `build_core_test/`：完整层级 VCD、VVP 和日志。调试时可运行：

```sh
gtkwave build_core_test/tb_core_test.vcd
```

日志按样本报告输入事件数、接受的时间步数、输出脉冲事务数、goodness 和 `PROCESS_DONE` 时间。TB 还会在神经元状态或 AER FIFO 写入未知值时立即报错退出。

## AXI+SNN 测试

入口为 `../tb_axi4_rw_test_v1_0_M_AXI.sv`，当前默认读取 3 个训练样本（可在 TB 参数中调整），并使用 `axi_input_fifo_model.sv` 代替仅在 Vivado 工程中存在的 FIFO Generator 仿真模型。

从本目录运行：

```sh
./run_axi_snn.sh
```

输出位于 `build_axi_test/`：

- `tb_axi4_rw_test_v1_0_M_AXI.vvp`：仿真可执行文件；
- `tb_axi4_rw_test_v1_0_M_AXI.vcd`：精简波形；
- `tb_axi4_rw_test_v1_0_M_AXI.log`：终端日志。

两个 TB 中的 spike、权重和神经元状态文件均使用绝对路径，移动仓库或换机器后必须先修改 TB 顶部的 `SPIKE_DATA_FILE`、`WEIGHT_DATA_FILE`、`POST_NEURON_STATE_FILE`、`PRE_NEURON_STATE_FILE`。AXI VCD 默认只记录关键控制信号；core test VCD 则记录完整层级。

`build_axi_test/` 与 `build_core_test/` 除各自 README 外的内容均由 Git 忽略，不要提交生成的 vvp/vcd/log。

参考 RTL 回迁与 Icarus 兼容性调整见 [REFERENCE_BASELINE.md](REFERENCE_BASELINE.md)。
