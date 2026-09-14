# script

- `system.tcl`：Vivado 导出的 Block Design 重建脚本。当前设计启用 PS7 的 SD0（MIO 40..45、CD=MIO10）、UART0（MIO14..15）、FCLK0=100 MHz 和 S_AXI_HP0；PL AXI master 通过 SmartConnect 访问 512 MiB DDR 映射。两个板上按键经 `key_debounce` 和反相逻辑产生启动/训练使能。
- `gen_saif.tcl`：读取 SAIF 并生成时序与功耗报告的参考脚本，内部工程路径和层次名需要按当前机器修改。
- `brian2_sim/`：为 Brian2 侧参考仿真预留的目录。

执行 `system.tcl` 前先把 `user/src` 加入 Vivado sources，否则 `Top_test`、`axi4_rw_test_v1_0` 和 `key_debounce` module reference 无法创建。
