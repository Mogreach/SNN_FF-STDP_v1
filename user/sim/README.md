# sim

RTL 验证入口。测试粒度从模块级到整机数据通路逐级增加。脚本与 Icarus 工作区在 `iverilog/`，模块级 testbench 保留在 `unit_test/`。

## Testbench 清单

| Testbench | 覆盖内容 | 运行方式 |
| --- | --- | --- |
| `tb_parallel_to_serial.sv` | 4-bit FIFO 数据解包、像素地址事件和 AER 握手 | 模块级，需自行编译 |
| `tb_odin_ffstbp.sv` | 单个 `ODIN_ffstdp` 核心，含多层历史激励 | 模块级，需自行编译 |
| `tb_core_test.sv` | 不经过 AXI，直接用 AER 握手驱动单层 `Top_test`，`IS_TRAIN=0` | `iverilog/run_core_test.sh` |
| `tb_axi4_rw_test_v1_0_M_AXI.sv` | AXI DDR 读、FIFO 跨时钟域、SNN 处理、goodness 写回的系统流程 | `iverilog/run_axi_snn.sh` |

建议先通过模块级 testbench，再运行系统 testbench。波形重点观察 AXI 五通道握手、FIFO full/empty、AER req/ack、`PROCESS_DONE`、`GOODNESS`、样本计数和主状态机。

## 当前验收入口

**AXI + SNN 系统回归**：`tb_axi4_rw_test_v1_0_M_AXI.sv` 连接当前 `axi4_rw_test_v1_0` 与单层 `Top_test`，覆盖 DDR 行为数据、49 次 AXI read burst、32→4 bit FIFO、AER 输入、SNN 处理以及 goodness 写回。默认 `TOTAL_TRAIN_SIZE=2`、`TOTAL_TEST_SIZE=0`，跑完两个样本及其写响应后打印 `PASS` 并 `$finish`。

`STOP_AFTER_FIRST_PROCESS_DONE` 默认为 `1'b0`，即跑完所有样本并等 AXI 写响应，便于核对 goodness 是否真正写入 DDR；设为 `1'b1` 则只做快速 smoke test——观察到第一个 `PROCESS_DONE` 后就打印 PASS 并结束，不等待写回。

**纯 SNN core 回归**：`tb_core_test.sv` 把同一单层 `Top_test` 的 AER 输入直接接到 testbench 的事件发生器，默认 2 个样本、`IS_TRAIN=0`，用于隔离 AXI 之外的核心行为。

两个 TB 都用 `$fopen(..., "rb")`/`$fread` 直接读取 `all_spikes.bin`，并用 `$readmemb`/`$readmemh` 加载权重与神经元状态。**这些路径都是绝对路径**（原因是 Vivado/xsim 会把工作目录切到工程 run 目录），换机器或移动仓库后必须先修改 TB 顶部的 `SPIKE_DATA_FILE`、`WEIGHT_DATA_FILE`、`POST_NEURON_STATE_FILE`、`PRE_NEURON_STATE_FILE`，指向本机 `Gen_out/<TASK>/` 下对应文件。若文件打不开或长度小于 `（训练条目+测试条目）×TIME_TOTAL_STEP×DATA_SIZE/8`，TB 会立即 `$fatal`。

`axi_input_fifo` 在 Vivado 中由 FIFO Generator IP 提供；Icarus 环境改用 `iverilog/axi_input_fifo_model.sv` 行为模型，因此两套 TB 都能在 Icarus 下直接回归。工程内回归仍应使用 Vivado 生成的 IP 模型。

详细命令、产物位置和最近一次回归结果见 `iverilog/README.md` 与 `iverilog/REFERENCE_BASELINE.md`。
