# user

项目中人工维护的 RTL、约束、脚本和 testbench 集合，也是理解硬件实现的首要入口。

- `src/`：SNN 核心、板级多层封装和 AXI DDR 主机。
- `sim/`：模块级、系统级 testbench 及 Icarus Verilog 配置。
- `data/`：XDC 和初始化文件。
- `script/`：Block Design 重建与 SAIF/功耗分析脚本。

Vivado 工程会引用这里的 module reference。移动源码或更改顶层模块名后，需要重新检查 `system.tcl`、Block Design 的 module reference 和综合 file set。
