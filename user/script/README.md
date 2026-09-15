# Vivado 辅助脚本

- `system.tcl`：PS7、时钟、SmartConnect、AXI 与按键连接的 Block Design 导出参考。
- `gen_saif.tcl`：导入 SAIF、生成时序/功耗报告的辅助脚本。
- `brian2_sim/`：软件侧参考资料。

当前工程目标为 Zynq-7010（`xc7z010clg400-1`）。`system.tcl` 中自动新建工程的 part 是历史值，不能直接执行来创建当前工程；应先在 7010 工程中加入 `user/src`，再把脚本用于比对或重建 BD 连接。执行后必须 Validate Design，并重新确认 PS7、FCLK、HP 口、UART、SD 和按键约束。
