# SNN FF-STDP ZYNQ 在线学习加速器

本仓库归档了一个面向 Zynq-7000 的 SNN Forward-Forward / FF-STDP 在线学习加速器，包括数据生成、定点量化、RTL、仿真、Vivado 工程、Vitis 裸机程序和历史验证资料。

新人请先阅读 [FF-STDP 加速器设计与复现指南](FF-STDP加速器设计（ZYNQ）.md)。该文档以当前代码为准，说明数据格式、模块层次、AXI/DDR 数据流、控制状态机、SD 卡导入、仿真和上板步骤，并列出当前归档中尚未闭环的事项。

## 目录导航

| 路径 | 内容 |
| --- | --- |
| `hardware_sim/` | 软件模型对接、脉冲数据生成、量化和初始化文件生成脚本 |
| `Gen_out/` | MNIST/FashionMNIST 数据、权重、神经元状态和 SAIF 产物 |
| `user/src/` | 可维护的 RTL 源码；核心入口为 `snn_ff/Top_test.v` |
| `user/sim/` | 模块级和系统级 testbench、Icarus Verilog 回归脚本与工作区 |
| `user/data/` | 约束和存储器初始化文件 |
| `user/script/` | Block Design 重建及功耗分析脚本 |
| `prj/` | Vivado/Vitis 工程、生成物和 PS 裸机程序；体量大且含历史工程副本 |
| `assets/` | 主设计文档的图片附件 |

## 推荐阅读顺序

1. 总指南的“项目现状”和“端到端数据流”。
2. `hardware_sim/README.md`，理解二进制输入与定点参数怎样生成。
3. `user/src/README.md` 和 `user/src/snn_ff/README.md`，理解 RTL 层次。
4. `user/src/axi_rw/README.md`，理解 PL 如何经 AXI HP0 访问 DDR。
5. `user/sim/README.md` 和 `user/sim/iverilog/README.md`，先跑通两套 Icarus 回归，再按总指南进行 Vivado/Vitis 和上板验证。

## 归档边界

`prj/` 是历史 FPGA 工程快照，不是唯一可信源码。模块功能优先查看 `user/src/`，Block Design 连接优先查看 `user/script/system.tcl` 和工程中的 `design_7030.bd`，PS/SD 卡行为查看 `prj/snn_pl_axi_ddr/vitis/snn_test/src/main.c`。修改参数时必须同步检查 Python 配置、RTL 顶层、AXI 参数、Vitis 宏和 DDR 地址规划。
