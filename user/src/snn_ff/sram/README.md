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
| 突触前状态存储 | `sram_pre_neuron.v` 参数化自写 RAM | 同左 |
| 突触后状态存储 | `sram_post_neuron.v` 参数化自写 RAM | 同左 |

仅突触权重存储器的行为模型与 FPGA IP 同名、端口不同。因此只有 `synaptic_core.v` 在实例化点用 `` `ifdef SNN_RAM_SIM `` 选择，且只有 `sram_synaptic.v` 被该宏包住。神经元状态存储器在两种模式下都使用参数化自写 RAM。

Icarus 侧由 filelist 顶部的一行启用：

```
+define+SNN_RAM_SIM
```

Vivado 侧不定义任何东西即走默认（FPGA）分支。

### FPGA 模式的突触权重 IP

默认 FPGA 分支要求 Vivado 工程中存在单端口 `blk_mem_gen` IP `sram_synaptic`，端口为 `clka/ena/wea/addra/dina/douta`。权重初值由该 IP 的 `Coe_File` 配置。

| IP 名称 | 默认几何 | 初始化文件 |
| --- | --- | --- |
| `sram_synaptic` | 72bit×25088 | `weights_weight.coe` |
| `sram_pre_neuron` | 参数化自写 RAM | TB 层级 `$readmemh` |
| `sram_post_neuron` | 参数化自写 RAM | TB 层级 `$readmemh` |

改变权重存储相关参数时，必须重新生成 `sram_synaptic` IP；神经元状态 RAM 随 RTL 参数变化。`hardware_sim/gen_neuron_state.py` 生成 `pre_neuron_state.txt`、`post_neuron_state.txt` 供 TB 层级加载；同名 `.coe` 为可选产物。

## 仿真层次路径

两个 testbench 依赖以下层次来灌初值，改动实例名会直接让仿真失败：

- `u_synaptic_core.u_sram_synaptic.SRAM`
- `neuron_core_inst.neurarray_pre.SRAM` / `neurarray_post.SRAM`
