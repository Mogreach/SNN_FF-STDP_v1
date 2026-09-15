# SNN FF-STDP 核心

本目录实现事件驱动 SNN 核、层级串接和在线 FF-STDP 更新。

## 层次结构

- `Top_test.v`：当前单层 784→256 板级/集成仿真顶层；为输出 AER 生成延迟 ack，并把单核完成信号导出为 `PROCESS_DONE`。
- `ODIN_ffstdp.v`：单层核心，组合 controller、scheduler、神经元、突触、SRAM、AER 输出与梯度 ROM。
- `controller.v`：核心内部 9 状态二进制编码控制器，安排 RAM 读、计算和写回节拍。
- `scheduler.v`：外部输入事件、内部神经元事件和时间事件的 FIFO 调度。
- `aer_out/`：`aer_outs.v` 汇总并行 lane 的发放并累计 goodness，`adder_tree.v` 为其配套加法树。
- `neuron_core/`：`pre_neuron.v`、`if_neuron.v` 与 `neuron_core.v`。
- `synaptic_core/`：`synaptic_core.v` 与在线更新 `ffstdp_update.v`。
- `sram/`、`rom/`、`fifo/`：存储器封装、梯度查找表与行为 FIFO。

> 早期笔记提到的多层变体 `Top_test_1.v`、`Top_784-512-512.v`、`aer_in_lrf_mapper.sv`、`aer_core_event_arbiter.sv`，以及 `goodness_moving_avg.v`，**均不在当前归档中**。`Top_test` 把预留的 `AVG_GOODNESS` 显式接零；SPI 通路（原 `spi_slave.v` 及 controller/synaptic_core/neuron_core 中的编程端口）已在整理中删除，当前核只走 AER 输入。

## AER 编码

AER 地址最高两位是事件类型：`00` 神经元脉冲，`01` 时间步事件，其余编码留给控制/虚拟事件；低位承载神经元地址。通信使用四相 req/ack 握手，发送端必须等待 ack 后撤销 req，并等待 ack 撤销后发送下一事件。

## 核心控制状态机

`WAIT` 接收调度事件；`PUSH` 入队；`NEUR_ACT`/`TSTEP_ACT` 分别执行神经元或时间步计算；`POP_NEUR`、`POP_NEUR_OUT`、`POP_TSTEP` 清除相应事件；`TREF` 在全部时间步后复位/结算样本；`WAIT_REQDN` 等待 AER 请求撤销。训练模式还会遍历突触前计数并写回权重。

具体存储器、神经元与突触模块见各子目录 README。

## 当前源级校验状态

当前单层 `Top_test` 使用参数化 8-lane 数据通路，20-bit 后神经元状态按 `{enable[1], spike_count[6], membrane[13]}` 拼接。`if_neuron` 的流水寄存器在 reset 时清零；更改其流水级数必须同步调整 controller 周期预算。

Icarus 环境用 `user/sim/iverilog/axi_input_fifo_model.sv` 行为模型替代 Vivado 的 `axi_input_fifo` IP 模型，因此 `tb_core_test.sv` 和 `tb_axi4_rw_test_v1_0_M_AXI.sv` 都能在 Icarus 下直接回归；见 `user/sim/iverilog/README.md`。Vivado/xsim 工程回归仍应使用工程生成的 IP 模型。
