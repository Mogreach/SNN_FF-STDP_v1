# sim

RTL 验证入口。测试粒度从小模块到整机数据通路逐步增加。

| Testbench | 覆盖内容 |
| --- | --- |
| `tb_parallel_to_serial.sv` | 4-bit FIFO 数据解包、像素地址事件和 AER 握手 |
| `tb_axi4_rw_test_v1_0_M_AXI.sv` | AXI DDR 读、FIFO 跨时钟域、SNN 处理、goodness 写回的系统流程 |
| `tb_odin_ffstbp.sv` | 单个 `ODIN_ffstdp` 核心 |
| `tb_top_lrf_odins.sv` | 多层/多核顶层连接 |
| `tb_aer_core_event_arbiter.sv` | AER 输出仲裁 |
| `tb_aer_lrf_mapper.sv` | 层间 AER 映射 |

建议先通过单元 testbench，再运行系统 testbench。波形重点观察 AXI 五通道握手、FIFO full/empty、AER req/ack、`PROCESS_DONE`、`GOODNESS`、样本计数和主状态机。部分 testbench 名称/端口来自旧版，编译前需与当前 RTL 接口核对。

## 当前系统验收入口

以 `tb_axi4_rw_test_v1_0_M_AXI.sv` 作为 AXI + SNN 的主集成 testbench。它连接当前 `axi4_rw_test_v1_0` 与单层 `Top_test`，覆盖 DDR 行为数据、49 次 AXI read burst、32→4 bit FIFO、AER 输入、SNN 处理以及 goodness 写回。

为避免误跑完整数据集，TB 默认 `TOTAL_TRAIN_SIZE=1`、`TOTAL_TEST_SIZE=0`，并在第一次观察到 `PROCESS_DONE` 后打印 PASS、调用 `$finish`。这就是日常接口/控制回归的验收点。若需要继续检查 goodness 的 AXI 写回，把 `STOP_AFTER_FIRST_PROCESS_DONE` 覆盖为 0；只有做批量回归时才增大训练/测试条目数。

TB 使用 `$fopen(..., "rb")`/`$fread` 直接读取 `all_spikes.bin`。由于 Vivado/xsim 的运行目录通常位于工程生成目录，`SPIKE_DATA_FILE` 故意采用绝对路径；在另一台机器或移动仓库后，运行仿真前必须把文件顶部的该参数改为本机 `Gen_out/<TASK>/all_spikes.bin` 绝对路径。若文件打不开或长度小于 `（训练条目+测试条目）×TIME_TOTAL_STEP×DATA_SIZE/8`，TB 会立即 `$fatal`。

系统 TB 依赖 Vivado 生成的 `axi_input_fifo` 仿真模型，推荐把它设置为 simulation top 后用 xsim 运行。普通 Icarus 环境若没有该 IP 的行为模型，只能完成其余 RTL 的展开检查。

归档整理时曾用临时 32→4 bit FIFO 行为模型，把同一 TB 覆盖为 `DATA_SIZE=16`、`OUTPUT_NEURON=8`、`T=8`、1 个训练条目进行快速 smoke test：8 个 timestep 均被接受，随后产生 `PROCESS_DONE`、goodness=101，并完成写响应后正常退出。该结果证明控制闭环可走通，但不能替代默认 784×256 配置在 xsim 下的全尺寸结果对照。
