# AXI DDR 读写与 AER 输入桥

`axi4_rw_test_v1_0.v` 是封装层，实例化 `axi4_rw_test_v1_0_M_AXI.v`；后者是系统级控制器和 AXI4 master。`parallel_to_serial.v` 把 FIFO 每次输出的 4 个时间位转换为逐像素 AER 事件。

## 当前默认参数

- 时间步 8，输入维度 784。
- 训练条目 `2×50000`，测试条目 `10×10000`（封装层默认值；内层默认值不同，但实例化时由封装层覆盖）。
- 读基址 `0x0020_0000`，写基址 `0x12D1_2800`（同样以封装层覆盖值为准）。
- AXI 数据宽 32 bit，读 burst 4 beat，写 burst 1 beat。
- 单条输入占 `TIME_STEP×DATA_SIZE` bit，即 6272 bit = 784 byte；每次读取 49 个 16-byte burst。

## 数据路径

DDR → AXI R 通道 → 32-bit 字节倒序 → 异步 `axi_input_fifo`（32→4 bit）→ `parallel_to_serial` → AER req/ack → `Top_test`。`PROCESS_DONE` 下降沿触发写阶段，锁存的 32-bit `GOODNESS` 经 AXI W/B 通道写回 DDR。

## 主状态机

`INIT → IDLE → READ_DATA → PROCESS_DATA → WRITE_DATA → DONE → NEXT_SAMPLE`。`INIT_AXI_TXN` 上升沿离开 INIT；训练阶段 `IS_POS` 每条翻转；达到训练条目数后 `IS_TRAIN` 拉低并继续测试条目。

## 注意事项

- `M_AXI_ACLK` 与 `SNN_CLK` 在当前 Block Design 中都接 FCLK0=100 MHz，异步 FIFO仍保留了跨时钟设计。
- 源码通过 `PROCESS_DONE` 的下降沿进入写阶段，因此顶层 done 必须形成可采样脉冲。
- `tb_axi4_rw_test_v1_0_M_AXI.sv` 是当前 AXI+SNN 验收入口；其 `SPIKE_DATA_FILE` 必须改成本机二进制数据的绝对路径。
- 历史工程的综合网表存在，但仍应从当前源码做一次干净重建与回归，不能用旧网表替代源级验证。
- 状态机 `IDLE` 直接依赖 `M_AXI_ARREADY`。读完成判断已改为最后一个 burst 的 `RVALID && RREADY && RLAST`，后续仍应在 xsim 中加入 backpressure 覆盖。
