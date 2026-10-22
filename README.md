# SNN FF-STDP 在线学习加速器（Zynq-7010）

这是一个部署到 Zynq-7010（`xc7z010clg400-1`）的单层 FF-STDP SNN 加速器归档。稳定工作流为：Python 生成数据与初始化文件 → Vivado 生成 bitstream/XSA → Vitis 裸机程序从 SD 卡载入数据到 DDR → PL 通过 AXI 读取脉冲并写回 goodness → UART 输出分类结果。

项目总文档： [总学习与上板指南](FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89.md)
参考论文： [FF-STDP：一种基于前向-前向与STDP融合的低功耗在线学习SNN加速器-《电子学报》](https://www.bing.com/ck/a?!&&p=b52444191af55433bd476c2dca4bdcf8bbd3e2dc54093a2aca4872651083d1a1JmltdHM9MTc4OTUxNjgwMA&ptn=3&ver=2&hsh=4&fclid=05157bae-4e50-6c9a-0eb0-6e314f136d0a&psq=FF-STDP&u=a1aHR0cHM6Ly93d3cuZWpvdXJuYWwub3JnLmNuL2VuL2FydGljbGUvZG9pLzEwLjEyMjYzL0RaWEIuMjAyNjAyODQv) ，此版本为初始demo，硬件设计与论文略有不同。
## 目录

| 路径                    | 作用                                           |
|-----------------------|----------------------------------------------|
| `hardware_sim/`       | Python 软件模型、量化、脉冲/权重/状态/ROM 生成               |
| [`software_mlp/`](software_mlp/README.md) | MLP FF-STDP 监督/无监督训练、策略选择与多数据集评估 |
| `Gen_out/`            | 当前任务的 `all_spikes.bin`、权重 COE、神经元状态与标签       |
| `user/src/`           | 当前 RTL 唯一维护源；核心顶层为 `snn_ff/Top_test.v`       |
| `user/sim/`           | Vivado 与 Icarus 验证 testbench                 |
| `user/data/`          | XDC 与 Vivado 使用的初始化数据                        |
| `user/script/`        | Block Design/功耗辅助脚本                          |
| `prj/snn_pl_axi_ddr/` | Zynq-7010 Vivado 工程、XSA、bitstream 与 Vitis 工程 |

## 快速路径

1. 修改 `hardware_sim/hardware_sim_config.py`，运行生成脚本并检查 `Gen_out/MNIST/`。
2. 打开 `prj/snn_pl_axi_ddr/snn_pl_axi_ddr.xpr`；确认 Part 为 `xc7z010clg400-1`，更新 `sram_synaptic` 的 `weights_weight.coe`，综合、实现、Generate Bitstream、Export XSA。
3. 在 Vitis 用新的 XSA 更新 platform，编译 `prj/snn_pl_axi_ddr/vitis/snn_test/src/main.c`；复制 `test_labels.h`，核对样本数和 DDR 地址。
4. 将 `all_spikes.bin` 放入 FAT32 SD 卡，串口启动后输入 `c`，记录 UART 输出。
