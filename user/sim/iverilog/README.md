# Icarus Verilog

Icarus Verilog 仿真工作区。`build/iverilog_filelist.f` 保存源文件清单，当前条目带有原 Windows 绝对路径，换机后必须改为本仓库路径。

典型命令形式：

```sh
iverilog -g2012 -f build/iverilog_filelist.f -o build/tb_odin_ffstdp_iverilog.vvp
vvp build/tb_odin_ffstdp_iverilog.vvp
```

生成的 `.vvp`、`.vcd`、`.view` 是历史产物，不代表当前源码仍能无修改通过。
