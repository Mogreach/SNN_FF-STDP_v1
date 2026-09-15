# RTL 验证

系统 TB 位于本目录，Icarus 工作流位于 `iverilog/`，模块级试验保留在 `unit_test/`。

| TB | 内容 |
| --- | --- |
| `tb_core_test.sv` | 直接 AER 驱动 `Top_test`，隔离 AXI，默认 2 样本、推理模式 |
| `tb_axi4_rw_test_v1_0_M_AXI.sv` | DDR AXI 读取、FIFO、AER、SNN、goodness 写回全链路 |
| `unit_test/` | FIFO、神经元、STDP 等模块级验证 |

运行 Icarus：

```bash
cd user/sim/iverilog
./run_core_test.sh
./run_axi_snn.sh
```

Icarus 定义 `SNN_RAM_SIM`，突触权重使用行为 RAM；Vivado/xsim 默认使用 `sram_synaptic` IP。两个系统 TB 的 bin/权重/状态文件路径设计为绝对路径，换机器或切换数据集必须修改 TB 顶部四个文件参数。

TB 会在启动时检查 pre/post RAM 初始化，并在 scheduler 非空输出、pre/post 写入值出现 X 时立即停止。首次 `$fatal` 才是根因；不要在被 X 污染的仿真会话中继续运行。
