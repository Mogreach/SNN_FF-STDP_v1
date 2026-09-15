# 神经元核心

- `pre_neuron.v`：维护突触前脉冲/计数状态，为在线权重更新提供 presynaptic 活动信息。
- `if_neuron.v`：积分发放神经元，对加权输入累加膜电位、比较阈值并产生脉冲。
- `neuron_core.v`：组织 `POST_NEUR_PARALLEL` 路并行后神经元，连接状态 SRAM、突触结果、AER 输出和 goodness 统计。

当前顶层默认并行度为 8。每个后神经元的 20-bit 状态严格按 `{enable[1], spike_count[6], membrane[13]}` 组织，8 lane SRAM 字宽为 160 bit；这正是 `1+6+13=20`。改变任一字段必须同步修改 `POST_NEUR_DATA_WIDTH`、生成脚本和 SRAM 初始化文件。

`if_neuron.v` 使用“脉冲次数”而不是时间位向量：神经元事件累加有符号权重，时间步事件比较阈值并在发放后把膜电位清零、计数加一，TREF 清零膜电位和计数。内部读数据流水寄存器在高有效 reset 时清零，避免首次访问传播 X。当前阈值依据 Python 配置 `V_THRESHOLD_POS=1.2` 和权重比例 `1/256` 编码为 307。
