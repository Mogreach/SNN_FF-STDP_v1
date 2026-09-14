# SAIF 活动文件

保存仿真导出的 Switching Activity Interchange Format 文件，用于 Vivado `report_power` 的动态功耗估计。

- `7030-784-512-512.saif`：板级/网络配置相关的历史活动文件。
- `dut_P8.saif`：并行度配置相关的活动文件。

SAIF 仅在层次路径、顶层、时钟和参数与当前综合网表匹配时有意义。重新跑仿真后，使用 `user/script/gen_saif.tcl` 的层次映射方式重新导入，不应把历史结果当作当前功耗结论。
