# 梯度 ROM

`pos_derivative_rom.v` 与 `neg_derivative_rom.v` 保存正/负样本对应的离散 FF 梯度查找表，地址由前、后神经元的脉冲计数/频率组合形成，输出供 `ffstdp_update.v` 更新权重。

理论值和 `.coe` 可由 `hardware_sim/gen_sigmoid.py` 生成，但该脚本的 RTL 输出路径仍是旧路径，且位宽/时间步需与当前 `WEIGHT_WIDTH=9`、`TIME_STEP=8` 配置一致。替换 ROM 后应对正负符号、补码、1-cycle 注册延迟和饱和边界做单元验证。
