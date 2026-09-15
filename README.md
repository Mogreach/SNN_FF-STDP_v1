# SNN FF-STDP 在线学习加速器（Zynq-7010）

这是一个部署到 Zynq-7010（`xc7z010clg400-1`）的单层 FF-STDP SNN 加速器归档。稳定工作流为：Python 生成数据与初始化文件 → Vivado 生成 bitstream/XSA → Vitis 裸机程序从 SD 卡载入数据到 DDR → PL 通过 AXI 读取脉冲并写回 goodness → UART 输出分类结果。

新人从 [总学习与上板指南](FF-STDP加速器设计（ZYNQ）.md) 开始；它是唯一的端到端操作说明。

## 目录

| 路径 | 作用 |
| --- | --- |
| `hardware_sim/` | Python 软件模型、量化、脉冲/权重/状态/ROM 生成 |
| `Gen_out/` | 当前任务的 `all_spikes.bin`、权重 COE、神经元状态与标签 |
| `user/src/` | 当前 RTL 唯一维护源；核心顶层为 `snn_ff/Top_test.v` |
| `user/sim/` | Vivado 与 Icarus 验证 testbench |
| `user/data/` | XDC 与 Vivado 使用的初始化数据 |
| `user/script/` | Block Design/功耗辅助脚本 |
| `prj/snn_pl_axi_ddr/` | Zynq-7010 Vivado 工程、XSA、bitstream 与 Vitis 工程 |

## 快速路径

1. 修改 `hardware_sim/hardware_sim_config.py`，运行生成脚本并检查 `Gen_out/MNIST/`。
2. 打开 `prj/snn_pl_axi_ddr/snn_pl_axi_ddr.xpr`；确认 Part 为 `xc7z010clg400-1`，更新 `sram_synaptic` 的 `weights_weight.coe`，综合、实现、Generate Bitstream、Export XSA。
3. 在 Vitis 用新的 XSA 更新 platform，编译 `prj/snn_pl_axi_ddr/vitis/snn_test/src/main.c`；复制 `test_labels.h`，核对样本数和 DDR 地址。
4. 将 boot 镜像和 `all_spikes.bin` 放入 FAT32 SD 卡，串口启动后输入 `c`，记录 UART 输出。

`prj/` 中的生成物不应替代当前源码；器件依据是当前 Vivado Project Part：`xc7z010clg400-1`。
