# SRAM 封装

- `sram_pre_neuron.v`：突触前状态存储。
- `sram_post_neuron.v`：后神经元膜电位/脉冲计数等状态存储。
- `sram_synaptic_bank.v`：按并行 lane/bank 组织突触权重。
- `sram_synaptic_sim.v`：仿真使用的突触存储模型。
- `sram_wrapper.v`：统一片上存储器访问时序和位宽适配。

控制器按固定周期预算安排 SRAM 读、计算、写回；更换 BRAM/URAM IP 或寄存输出级数会改变 `NEUR_ACT`、`TSTEP_ACT`、`TREF` 的时序，不能只替换存储模块而不回归 controller。
