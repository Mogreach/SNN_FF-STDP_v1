# SNN FF-STDP 核心

本目录实现事件驱动 SNN 核、层级串接和在线 FF-STDP 更新。

## 层次结构

- `Top_test.v`：当前单层 784→256 板级/集成仿真顶层；为输出 AER 生成延迟 ack，并把单核完成信号导出为 `PROCESS_DONE`。
- `Top_test_1.v`：最多 8 层的参数化生成版本，依赖 `Top_test_cfg.vh`；属于可扩展变体。
- `Top_784-512-512.v`：固定网络的历史副本，模块名同样是 `Top_test`，不可与当前文件同时编译。
- `ODIN_ffstdp.v`：单层核心，组合 controller、scheduler、神经元、突触、SRAM、AER 输出与梯度 ROM。
- `controller.v`：核心内部 9 状态 one-hot 控制器。
- `scheduler.v`：外部输入事件、内部神经元事件和时间事件的 FIFO 调度。
- `aer_in_lrf_mapper.sv`：层间 AER 地址/事件映射。
- `aer_core_event_arbiter.sv`：多个核心输出仲裁。
- `goodness_moving_avg.v`：各核 goodness 的指数移动平均模块；当前 `Top_test` 未实例化它，并把预留的 `AVG_GOODNESS` 显式接零。
- `spi_slave.v`：参数/存储器访问的 SPI 辅助路径。

## AER 编码

AER 地址最高两位是事件类型：`00` 神经元脉冲，`01` 时间步事件，其余编码留给控制/虚拟事件；低位承载神经元地址。通信使用四相 req/ack 握手，发送端必须等待 ack 后撤销 req，并等待 ack 撤销后发送下一事件。

## 核心控制状态机

`WAIT` 接收调度事件；`PUSH` 入队；`NEUR_ACT`/`TSTEP_ACT` 分别执行神经元或时间步计算；`POP_NEUR`、`POP_NEUR_OUT`、`POP_TSTEP` 清除相应事件；`TREF` 在全部时间步后复位/结算样本；`WAIT_REQDN` 等待 AER 请求撤销。训练模式还会遍历突触前计数并写回权重。

具体存储器、神经元与突触模块见各子目录 README。

## 当前源级校验状态

当前单层 `Top_test` 已通过 Icarus Verilog 11 的完整层次展开。恢复版 `if_neuron` 的上层参数/端口已重新对齐，AER lane 地址已定宽，20-bit 后神经元状态按 `{enable[1], spike_count[6], membrane[13]}` 拼接。系统级功能回归仍应使用 Vivado/xsim 的 `axi_input_fifo` IP 行为模型完成。
