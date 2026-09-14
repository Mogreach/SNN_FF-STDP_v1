# 单元测试

模块级 testbench 目录，当前存放：

- `tb_parallel_to_serial.sv`：`parallel_to_serial` 的 4-bit 解包与 AER 像素事件；
- `tb_odin_ffstbp.sv`：单个 `ODIN_ffstdp` 核的激励（含 784→256 全连接数据流）。

这两个 TB 尚未接入 `iverilog/` 下的自动脚本，需要自行指定源文件清单运行。后续建议补齐 `ffstdp_update`、AER 输出仲裁等自检式测试，并让失败以非零仿真退出码体现。
