# 参考 RTL 回迁记录

基准目录：`/home/mogreach/WorkSpace/Work-Local-Server/Temp/SNN_FFSTDP_a450adf/user/src`。

当前 `user/src` 的 RTL 主体已按该目录回迁，包括 controller 状态机、AER 输出、神经元/突触核心和 FIFO 实现；当前仓库自行补充的 README 未删除。

## 为适配 Icarus core/AXI test 保留的差异

- `synaptic_core.v` 在实例化点用 `SNN_RAM_SIM` 宏选择突触权重存储：仿真走行为 `sram_synaptic` 模型，FPGA 走参考版依赖的 Vivado BRAM IP。
- `aer_outs.v` 为 `genvar` 地址偏移引入定宽中间信号 `LANE_OFFSET`/`lane_neuron_addr`，消除 Icarus 的“不定宽拼接”编译错误。
- 补充 `CTRL_TSTEP_EVENT_negedge`、`ctrl_state` 的显式声明，消除隐式网络。
- 突触权重存储器由 `SNN_RAM_SIM` 宏二选一：仿真模式用行为 `sram_synaptic.v`，FPGA 模式用工程里的 `sram_synaptic` IP。细节见 `user/src/snn_ff/sram/README.md`。
- 神经元状态初值：两个模式均由 testbench 按 DUT 层次 `$readmemh` 写入（见 `tb_core_test.sv`、`tb_axi4_rw_test_v1_0_M_AXI.sv`）。FPGA 实际上电实验应由复位/软件初始化策略明确控制，不能依赖 testbench 层级加载。

## 相对基准的主动清理

- 删除 SPI 通路：`spi_slave.v` 及 controller/synaptic_core/neuron_core/ODIN_ffstdp 中的编程端口（`CTRL_SYNA_WR/RD_EVENT`、`CTRL_SYNA_PROG_DATA`、`CTRL_WR/RD_NEUR_EVENT`、`CTRL_POST_NEUR_PROG_DATA`、`NEUR_STATE`）。当前核只走 AER 输入。
- 删除无引用的中间量（`post_neuron_byte_addr`、`post_neuron_thresold_next`、AER goodness 旧加法中间量）。
- 保留 `ctrl_state`、`SCHED_FULL` 作为波形调试观测接口。

## 验证状态

```sh
cd user/sim/iverilog
./run_core_test.sh     # 纯 SNN core，2 样本，IS_TRAIN=0
./run_axi_snn.sh       # AXI+SNN，2 训练样本 + 写响应
```

两套回归当前均通过：core 两个样本都产生 `PROCESS_DONE` 并以 `PASS` 退出；AXI 两个样本及其 AXI 写响应完成并以 `PASS` 退出。详细命令与产物见 `README.md`。

AXI TB 的 `IS_TRAIN` 已接回 AXI 模块的输出信号，不能连接为常量。
