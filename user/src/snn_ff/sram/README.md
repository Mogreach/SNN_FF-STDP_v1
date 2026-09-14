# SRAM 封装

## 文件

- `sram_pre_neuron.v`：突触前状态存储。
- `sram_post_neuron.v`：后神经元膜电位/脉冲计数等状态存储。
- `sram_synaptic.v`：仿真用的突触权重行为模型（仅仿真模式编译，见下）。
- `sram_synaptic_bank.v`、`sram_synaptic_sim.v`、`sram_wrapper.v`：早期尝试的替代实现，当前 RTL 未实例化，保留作参考。

控制器按固定周期预算安排 SRAM 读、计算、写回；更换 BRAM/URAM IP 或寄存输出级数会改变 `NEUR_ACT`、`TSTEP_ACT`、`TREF` 的时序，不能只替换存储模块而不回归 controller。

## 两种构建模式：`SNN_RAM_SIM`

存储器实现由编译宏 `SNN_RAM_SIM` 二选一：

| | FPGA 模式（默认） | 仿真模式 |
| --- | --- | --- |
| 触发条件 | **不定义** `SNN_RAM_SIM` | 定义 `SNN_RAM_SIM` |
| 突触权重存储 | 工程中的 `sram_synaptic` IP（`blk_mem_gen`，72bit×25088，`clka/ena/wea/addra/dina/douta`） | `sram_synaptic.v` 行为模型 |
| 神经元初值 | 模块内可综合 `initial $readmemh` | 由 testbench 按 DUT 层次写入 |

两者模块名都叫 `sram_synaptic` 但端口不同，因此 `synaptic_core.v` 在实例化点用 `` `ifdef `` 选择，且 `sram_synaptic.v` 整个文件被 `` `ifdef SNN_RAM_SIM `` 包住——这样即使把整个 `user/src` 一起加进 Vivado，也不会和 IP 产生重复定义。

Icarus 侧由 filelist 顶部的一行启用：

```
+define+SNN_RAM_SIM
```

Vivado 侧不定义任何东西即走默认（FPGA）分支。

### FPGA 模式的神经元初值必须外部传入

`Gen_out/<TASK>` 下的状态文件路径**没有默认值**，必须在 Vivado 的 Synthesis 设置里通过 Verilog Define 传入两个字符串宏：

```tcl
set_property verilog_define { \
  SNN_PRE_NEUR_STATE_FILE="C:/path/to/pre_neuron_state.txt" \
  SNN_POST_NEUR_STATE_FILE="C:/path/to/post_neuron_state.txt" } \
  [get_filesets sources_1]
```

未传入会在综合时由 `` `error `` 直接报错。这样设计的原因是 Vivado 解析 `$readmem*` 的相对路径时以综合 run 目录（`<project>.runs/synth_1`）为基准，不是仓库根；写死本机绝对路径又会在别人 clone 后静默读到错误文件，不如让配置缺失在编译期就暴露。

权重初值走 IP 自己的 `Coe_File`（`user/data/weights_weight.coe`），不经过这两个宏。

## 仿真层次路径

两个 testbench 依赖以下层次来灌初值，改动实例名会直接让仿真失败：

- `u_synaptic_core.u_sram_synaptic.SRAM`
- `neuron_core_inst.neurarray_pre.SRAM` / `neurarray_post.SRAM`
