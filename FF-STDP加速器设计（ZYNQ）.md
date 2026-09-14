# FF-STDP 在线学习加速器：Zynq 设计、验证与复现指南

> 文档定位：本文件是本仓库的总学习文档和复现入口，以当前归档代码为准。旧版设计笔记中的概念、截图和调试经验被保留，但与当前代码不一致的 Zynq-7010、DMA FIFO 环路、50 MHz 单时钟和 EMIO 控制方案不再作为已实现功能描述。

## 1. 先看这里

### 1.1 项目做什么

本项目把 Forward-Forward（FF）思想与脉冲神经网络、局部 FF-STDP 权重更新结合，设计为运行在 Zynq-7000 上的在线学习加速器：

1. 软件侧将图像及候选标签编码成固定时间步的脉冲序列。
2. PS 裸机程序从 SD 卡读取二进制数据并写入共享 DDR。
3. PL 中的 AXI master 经 PS 的 S_AXI_HP0 端口读取 DDR。
4. 32-bit 数据经过异步 FIFO 和并串转换，变为 AER 地址事件送入 SNN。
5. 当前单层 SNN（784→256）处理事件；训练时局部更新突触权重，推理时只累计 goodness。
6. 每个输入条目的 32-bit goodness 由 PL 写回 DDR。
7. PS 对每张测试图像的 10 个候选 goodness 取最大值，与标签比较并打印准确率。

![PS/PL DDR 数据流](assets/FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89/Pasted_20260914114336_FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89.png)

### 1.2 当前归档的真实状态

| 项目        | 当前代码事实                                           | 主要依据                                      |
| --------- | ------------------------------------------------ | ----------------------------------------- |
| FPGA 器件   | 主工程是 `xc7z030fbg484-1`，另留有 Z-7010 历史 run         | `prj/snn_pl_axi_ddr/snn_pl_axi_ddr.xpr`   |
| 工具版本      | Vivado 2020.2 工程                                 | 同上                                        |
| 网络顶层      | 当前维护版为单层 784→256                                | `user/src/snn_ff/Top_test.v`              |
| 时间步       | RTL 当前默认 `TIME_STEP=8`                           | `Top_test.v`、AXI RTL                      |
| 后神经元并行度   | 当前顶层默认 8                                         | `Top_test.v`                              |
| AXI 数据口   | PL 为 AXI4 master，经 SmartConnect 接 PS `S_AXI_HP0` | `user/script/system.tcl`、`design_7030.bd` |
| PL/AXI 时钟 | 当前 BD 把 Top、AXI master、HP0 时钟都接到 FCLK0=100 MHz   | `system.tcl`                              |
| SD 卡      | PS7 SD0，MIO 40..45，卡检测 MIO10；FatFs 读取文件          | `system.tcl`、Vitis `main.c`               |
| 启动方式      | 两个低有效板上按键，经消抖和反相后驱动启动与训练开关                       | `system.tcl`、`key_debounce.v`             |
| PS↔PL 控制  | 当前未启用 EMIO GPIO；PS 只负责装载 DDR 和读取结果               | `system.tcl` 中 EMIO/GPIO 均禁用              |
| 结果写回      | 每个输入条目写一个 32-bit goodness                        | AXI master RTL                            |

### 1.3 已知不一致，复现前必须处理

当前仓库是研发归档，不是“克隆后一步跑通”的发布包。以下差异需要先统一：

- `hardware_sim/hardware_sim_config.py` 与当前 `Top_test` 已统一为 784→256、T=8、并行度 8；`NET_PATH` 现指向仓库内的 `./hardware_sim/MNIST_91.pth`（相对仓库根目录），重新生成数据前仍需核对这个 checkpoint 的结构是否就是该配置。
- AXI 封装层的样本数/写基址会覆盖内层默认值。有效默认值是训练 `2×50000`、测试 `10×10000`、写基址 `0x12D1_2800`；不要只看 `_M_AXI.v` 文件顶部。
- PS 工程有多个 `main.c` 副本：`prj/snn_test/src/main.c` 默认文件名是 `fashionmnist.bin`，`prj/snn_pl_axi_ddr/vitis/snn_test/src/main.c` 默认是 `all_spikes.bin`。
- Vitis 程序写结果读取基址仍定义为 `0x0B00_0000`，与当前 AXI 封装写基址 `0x12D1_2800` 不一致。上板前必须选定一个地址并两端同步。
- 已有历史综合网表不等于当前源码可以干净重建；重新综合前仍需对当前 file set 做一次从零编译和回归。
- `gen_model_weight_coe.py` 当前只导出首层，适合现行单层顶层；若将来扩展为多层，需要改为逐层导出并解决源码标注的 COE 行对齐问题。当前归档中已无多层顶层文件。
- `gen_sigmoid.py` 生成 ROM RTL 时写入的是不存在的 `hardware/src/...`，应改为 `user/src/snn_ff/rom/...` 或只使用它同时导出的 COE。
- `system.tcl` 是历史导出脚本，脚本开头临时建工程使用 `xc7z010clg400-1`，而主工程/当前 BD 是 Z-7030。应在 Z-7030 工程中复用 BD 内容，不能盲目执行默认建工程分支。
- 当前单层 `Top_test` 已通过 Icarus Verilog 11 干净展开；Icarus 环境用 `user/sim/iverilog/axi_input_fifo_model.sv` 行为模型替代 FIFO Generator IP，两套 TB 均可在 Icarus 下回归，xsim 工程回归仍应使用 Vivado 生成的行为模型。

这些项目在本文末尾给出建议修复顺序。

## 2. 仓库地图与可信来源

```text
SNN_FFSTDP_version_1/
├── README.md                         # 仓库入口
├── FF-STDP加速器设计（ZYNQ）.md      # 本文
├── hardware_sim/                    # 数据/量化/初始化生成脚本
├── Gen_out/                         # MNIST、FashionMNIST、SAIF 生成物
├── user/
│   ├── src/
│   │   ├── axi_rw/                  # DDR AXI master + 32→4 FIFO 后端 + AER 转换
│   │   └── snn_ff/                  # 当前单层顶层、控制器、神经元、突触、SRAM、ROM、FIFO
│   ├── sim/                         # testbench 与 Icarus 工作区
│   ├── data/                        # XDC、历史 COE
│   └── script/                      # Block Design、SAIF/功耗脚本
├── prj/                             # Vivado/Vitis 工程快照和生成物
└── assets/FF-STDP加速器设计（ZYNQ）/ # 本文图片
```

遇到重复信息时按以下优先级判断：

1. 算法和硬件模块行为：`user/src/` 当前源码。
2. PS/PL 连接、端口和时钟：当前 `design_7030.bd`，辅以 `user/script/system.tcl`。
3. SD 卡与裸机软件：实际 Vitis application 所引用的 `main.c`。
4. 仿真预期：`user/sim/`，但需先检查 testbench 是否仍匹配端口。
5. 截图和旧文档：只作为背景和调试证据，不覆盖源码事实。

每个非 `prj` 目录都有 README，可从局部说明继续阅读。

## 3. 算法到硬件的数据约定

### 3.1 FF 正样本、负样本与测试候选

软件侧将类别信息覆盖到图像的前 10 个位置：

- 正训练条目：覆盖真实标签。
- 负训练条目：随机选择一个非真实标签。
- 测试条目：每张图依次覆盖标签 0~9，共产生 10 个候选。

训练数据在 `gen_data_flow.py` 中按每张图“正、负”交替追加，因此 AXI 控制器每完成一条就翻转 `IS_POS`。测试阶段每 10 条为一组，PS 取最大 goodness 的索引作为预测类别。

### 3.2 脉冲张量展开

逻辑张量可理解为：

```text
[输入条目][时间步 T][像素/输入神经元 N]
```

当前 `N=784`、`T=8`。单条目位数与字节数：

```text
bits_per_entry  = T × N = 8 × 784 = 6272 bit
bytes_per_entry = T × N / 8 = 784 byte
```

AXI 口为 32 bit、读 burst 为 4 beat，因此每 burst 搬运 16 byte，一条目需要：

```text
784 / 16 = 49 bursts
```

这正对应 `_M_AXI.v` 的 `ONE_SAMPLE_READ_BURST_COUNT` 计算。

![输入脉冲组织](assets/FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89/Pasted_20260914114516_FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89.png)

### 3.3 二进制与字节序

PS 程序每次从 SD 卡读 4096 byte，并按以下方式组成 32-bit 小端 CPU word：

```c
word = buffer[i]
     | buffer[i + 1] << 8
     | buffer[i + 2] << 16
     | buffer[i + 3] << 24;
```

PL AXI master读回后又对 32-bit word 做“字节倒序、字节内位序不变”，再写入 32→4 bit 异步 FIFO。这个约定会直接影响时间位的先后顺序。修改 Python 的 `packbits`、PS 写法或 AXI 字节倒序时，必须用一个已知 32-bit 测试图样端到端核对，不能仅凭“大小端”名称判断。

旧调试记录中的映射截图可作为对照：

![DDR 大小端调试](assets/FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89/image%205.png)

### 3.4 定点与存储布局

当前 Python 配置给出的主要格式为：

| 数据 | 当前脚本配置 | 说明 |
| --- | --- | --- |
| 权重 | 有符号 9 bit，`WEIGHT_MAX=1` | scale=`1/256` |
| 输入 | 有符号 8 bit，`INPUT_MAX=8` | 当前脉冲通路实际以 bit 事件为主 |
| bias | 有符号 16 bit，`BIAS_MAX=128` | 软件模型参数 |
| 后神经元状态 | `{enable[1], spike_count[6], membrane[13]}`；单 lane 20 bit，8 lane 打包 160 bit | `1+6+13=20` |
| 前神经元状态 | `TIME_STEP=8` bit/神经元 | 记录时间窗内活动 |
| goodness | 核内累计并由顶层/DDR 输出 32 bit | 当前是单层结果，不做跨层求和 |

`gen_model_weight_coe.py` 先把权重转置为“输入神经元优先、后神经元分 lane”，再按 `POST_PARALLEL×WEIGHT_WIDTH` 打包。打包时列表反转以形成低位 lane 顺序。任何 SRAM bank 映射修改都应同时更新这个打包逻辑。

## 4. PL 顶层与 PS/PL 互连

### 4.1 当前 Block Design

当前主通路不是 AXI DMA + AXI Stream FIFO，而是自定义 AXI4 master：

```text
SD card --FatFs--> PS CPU --Xil_Out32--> DDR
                                      |
                                      v
Top_test <--- AER bridge/FIFO <--- custom AXI4 master
   |                                      |
   +---- GOODNESS / PROCESS_DONE ---------+
                                          |
                                          +--- AXI4 write ---> DDR
PS CPU --Xil_In32--------------------------+
```

PL master 经 SmartConnect 接 `processing_system7_0/S_AXI_HP0`，地址空间映射为 `0x0000_0000` 起的 512 MiB DDR/Low OCM segment。PS 的 `M_AXI_GP0` 当前没有启用，因此不存在 PS 通过 AXI-Lite 配置 PL 寄存器的通路。

![当前 PS/PL 内存交互概念图](assets/FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89/image%2018.png)

### 4.2 时钟与复位

- PS FCLK0 配置为 100 MHz。
- `Top_test.CLK`、AXI master `SNN_CLK`/`m_axi_aclk`、SmartConnect、HP0 ACLK、按键消抖和 Processor System Reset 都接 FCLK0。
- `clk_wiz` 生成 50 MHz 和 100 MHz 输出，但从导出的连接看，这些输出没有作为 SNN/AXI 主时钟；旧文档的“AXI_ACLK=50 MHz”不适用于当前 BD。
- PS `FCLK_RESET0_N` 进入 `proc_sys_reset`。外设低有效复位直接给 AXI/SmartConnect/按键模块，同时经反相后作为 `Top_test` 的高有效 `RST` 和 clock wizard reset。

尽管当前两侧同为 100 MHz，AXI 输入桥仍使用独立 `wr_clk`/`rd_clk` 的异步 FIFO，保留了以后分频的能力。

### 4.3 SD、串口和按键

PS 配置：

- SD0：MIO 40..45，Card Detect=MIO10。
- UART0：MIO14..15，115200 baud。
- EMIO SD、EMIO GPIO 和 PS GPIO 外设：当前均关闭。

PL 外部引脚来自 `user/data/axi4_ddr_rw.xdc`：

| 信号 | 引脚 | 作用 |
| --- | --- | --- |
| `key_init` | L14 | 消抖、反相后产生一次 AXI 流程启动 |
| `key_train_enable` | K16 | 消抖、反相后切换训练使能标志 |
| `train_enable_flag` | H15 | 当前训练使能状态指示 |
| `train_finish_flag` | L15 | 训练阶段结束指示 |

按键模块默认 `CNT_MAX=1_000_000`。源码注释按 50 MHz 计算为 20 ms，但当前连接为 100 MHz，实际约 10 ms；若要维持 20 ms，应把计数改为 2,000,000。

## 5. AXI DDR 控制器

### 5.1 文件和接口

入口文件：

- `user/src/axi_rw/axi4_rw_test_v1_0.v`：顶层封装和参数覆盖。
- `user/src/axi_rw/axi4_rw_test_v1_0_M_AXI.v`：AXI 通道、主状态机、FIFO 与事件发送。
- `user/src/axi_rw/parallel_to_serial.v`：4 个时间位到 AER 事件的串行转换。

与 SNN 相连的主要接口：

| 方向 | 信号 | 含义 |
| --- | --- | --- |
| AXI→SNN | `AER_IN_ADDR[11:0]` | 事件类型和输入神经元地址 |
| AXI→SNN | `AER_IN_REQ` | AER 请求 |
| SNN→AXI | `AER_IN_ACK` | AER 应答 |
| AXI→SNN | `IS_POS` | 正/负训练条目标志 |
| AXI→SNN | `IS_TRAIN` | 在线学习/只推理 |
| SNN→AXI | `GOODNESS[31:0]` | 当前条目 goodness |
| SNN→AXI | `PROCESS_DONE` | 末层处理完成脉冲 |

### 5.2 外层实验状态机

![旧版状态机示意，具体条件以当前 RTL 为准](assets/FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89/Pasted_20260914114536_FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89.png)

| 状态 | 当前 RTL 行为 | 转移条件 |
| --- | --- | --- |
| `INIT` | 清样本计数；接收训练开关；等待启动 | `INIT_AXI_TXN` 上升沿 |
| `IDLE` | 准备首个读地址 | 当前实现等待 `M_AXI_ARREADY` |
| `READ_DATA` | 连续发起 burst，读数据写入异步 FIFO | 一条目的 49 个 burst 完成 |
| `PROCESS_DATA` | FIFO 被 SNN 侧消费，等待网络结束 | 同步后的 `PROCESS_DONE` 下降沿 |
| `WRITE_DATA` | 把锁存的 goodness 写到结果区 | 1-beat 写响应完成 |
| `DONE` | 样本计数加一 | 下一拍无条件进入 `NEXT_SAMPLE` |
| `NEXT_SAMPLE` | 翻转 `IS_POS`；判断训练/测试阶段 | 未完成则回 `IDLE`，全部完成回 `INIT` |

`TRAIN_ENABLE_FLAG` 在 INIT 中被训练按键上升沿翻转。训练结束后，`IS_TRAIN` 拉低但继续处理测试条目；测试条目仍每条翻转 `IS_POS`，但推理逻辑主要依赖 `IS_TRAIN=0`。

### 5.3 读路径

1. AR 通道发 4-beat INCR burst。
2. 每次 `RVALID && RREADY` 接收 32 bit。
3. 字节倒序后写入 `axi_input_fifo`。
4. FIFO 写口是 32 bit，读口是 4 bit，读侧每次得到同一像素的 4 个时间位。
5. `parallel_to_serial` 扫描 4 bit 内的置位时间，并按像素计数生成神经元事件；完成全部 784 像素后产生时间/完成控制事件。
6. 每个 AER 事件严格等待 `AER_IN_ACK`。

![并串转换与事件发送](assets/FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89/image%2019.png)

### 5.4 写路径

SNN `PROCESS_DONE` 有效时将 `GOODNESS` 锁存到 `GOODNESS_reg`。两级采样寄存器检测 `PROCESS_DONE` 下降沿，状态机随后发起单 beat AXI 写。每条结果 4 byte，结果条目 `k` 的地址为：

```text
write_address(k) = WRITE_BASE + 4 × k
```

PS 对测试结果读取时还需跳过所有训练条目：

```text
test_result_base = WRITE_BASE + 4 × TRAIN_ENTRIES
```

若 `TRAIN_SAMPLES` 表示原始图像数，训练条目数为 `2×TRAIN_SAMPLES`；当前 PS 代码正是按 `TRAIN_SAMPLES * 2 * 4` 计算偏移。

## 6. SNN 硬件架构

![SNN 硬件框架](assets/FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89/Pasted_20260914114639_FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89.png)

### 6.1 当前单层顶层 `Top_test`

当前 `Top_test.v` 实例化一个 `ODIN_ffstdp`：

```text
external AER
    |
    v
ODIN: 784 -> 256, POST_NEUR_PARALLEL=8
    | terminal delayed ack
    v
PROCESS_DONE + GOODNESS
```

核的输出 AER 由顶层形成 6 拍延迟 ack，以便输出事件完整排空。`ONE_SAMPLE_FINISH` 直接导出为 `PROCESS_DONE`，核内的 32-bit `GOODNESS` 直接导出，不再经过历史两层版本的跨层累加器。

`AVG_GOODNESS` 在 `Top_test` 中显式接零是安全的：`synaptic_core.v` 当前没有把该信号接入 `ffstdp_update`，因此它只是保留接口，不参与权重更新。只有重新启用 moving-average 学习分支时，才必须重新实现 goodness 移动平均模块及其清零/有效握手。早期笔记提到的多层变体 `Top_test_1.v`、`Top_784-512-512.v` 已不在当前归档中，`user/src` 内只有 `Top_test` 一个顶层定义。

### 6.2 单层 `ODIN_ffstdp`

单层核心的主要组成：

```text
AER input
       |
       v
  controller <----> scheduler FIFO
       |
       +----> pre-neuron SRAM
       +----> synaptic SRAM/banks ---> synaptic_core ---> neuron_core
       +----> post-neuron SRAM              |                 |
       +----> gradient ROM + ffstdp_update <-+                 v
                                                           AER output
```

`ODIN_ffstdp.v` 是阅读核心的最佳入口。它把 controller、scheduler、SRAM、突触核心、神经元核心、FF-STDP 更新以及 AER 输出串起来，并导出单层 goodness 和样本完成信号。

### 6.3 AER 编码与握手

AER 地址高两位定义事件类型：

| 高两位 | 事件 | 低位含义 |
| --- | --- | --- |
| `00` | 神经元事件 | 神经元地址 |
| `01` | 时间步事件 | 时间步/控制字段 |
| 其他 | 内部/虚拟控制事件 | 以 controller/scheduler 实现为准 |

四相握手顺序：发送端置 `REQ` → 接收端置 `ACK` → 发送端撤 `REQ` → 接收端撤 `ACK`。`controller` 的 `WAIT_REQDN` 专门等待请求撤销，避免同一事件重复接收。

### 6.4 scheduler

`scheduler.v` 缓存两类来源：外部 AER 输入与神经元核心内部产生的事件。controller 提供 push/pop、地址、事件来源和虚拟事件字段；scheduler 返回 empty/full 和队头数据。controller 在 WAIT 状态依据队头高位决定进入神经元处理还是时间步处理。

### 6.5 controller 的 9 状态

![核心控制器状态机](assets/FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89/Pasted_20260914115321_FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89.png)

| 状态 | 职责 |
| --- | --- |
| `WAIT` | 空闲/解析新事件；选择 neuron、timestep 或 push |
| `PUSH` | 将外部或内部事件压入 scheduler |
| `WAIT_REQDN` | AER 接收后等待请求撤销 |
| `NEUR_ACT` | 遍历并行后神经元，读取状态/权重、积分与写回 |
| `POP_NEUR` | 完成神经元事件后弹出 scheduler 队头 |
| `TSTEP_ACT` | 遍历后神经元，执行时间步相关更新和输出判断 |
| `POP_NEUR_OUT` | 清理本时间步产生的神经元输出事件 |
| `POP_TSTEP` | 弹出时间步事件，更新 `T_step_cnt` |
| `TREF` | 时间窗结束后的 refractory/样本结算和状态整理 |

当前周期预算由 controller 常量给出：`NEUR_ACT` 每并行组 3 拍，`TSTEP_ACT` 每组 2 拍，`TREF` 每组 4 拍。SRAM 或计算流水级改变时必须同步这些常量。

### 6.6 神经元状态和计算

![后神经元存储模型](assets/FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89/Pasted_20260914114732_FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89.png)

- `pre_neuron.v` 记录输入神经元在当前时间窗的脉冲计数/状态。
- `if_neuron.v` 对突触输入积分；时间步结束时比较阈值，发放则脉冲计数加一并把膜电位清零，TREF 再清零整个样本状态。
- `neuron_core.v` 并行处理 8 个后神经元，连接后状态 SRAM 与 AER 输出。
- `sram_post_neuron.v`、`sram_pre_neuron.v` 保存跨事件状态。

当前后神经元状态位宽不是 19 bit，也不是时间位向量，而是 `{enable, spike_count, membrane}={1,6,13}=20 bit`。恢复的 `if_neuron` 与该“次数计数”格式一致，它不带 `current_time_step` 端口；该端口只连接 `pre_neuron`。当前正阈值按 `V_THRESHOLD_POS=1.2`、权重比例 `1/256` 编码为 307。初始化文件由 `gen_neuron_state.py` 生成，替换前应逐位核对 RTL 解包。

### 6.7 突触、梯度 ROM 与在线更新

![FF-STDP 更新数据通路](assets/FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89/Pasted_20260914115258_FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89.png)

训练时，`ffstdp_update.v` 根据：

- `IS_POS` 正/负条目标志；
- 突触前神经元脉冲计数；
- 突触后神经元脉冲计数/频率；
- `pos_derivative_rom.v` 或 `neg_derivative_rom.v` 查表结果；

计算定点增量，对旧权重加减、饱和后写回 `sram_synaptic_bank.v`。推理时 controller 不走完整权重更新遍历。

Python 中梯度的核心形式为正负 sigmoid 导数乘以发放频率及学习率，然后量化到 `WEIGHT_WIDTH`。ROM 是离散近似，因此时间步或位宽变化必须重新生成，而不是只改 RTL parameter。

### 6.8 goodness

goodness 来自 256 个后神经元在一个时间窗内的发放次数平方和：`aer_outs` 每次处理 8 lane，平方后经加法树累加到 32-bit `GOODNESS`。样本完成时顶层直接导出这个单层结果。测试分类不在 PL 内完成，PS 以每张图 10 个候选的最大 goodness 作为类别。

## 7. DDR 地址规划

### 7.1 统一计算方法

设：

```text
T                 = 时间步
N                 = 输入神经元数
train_images      = 原始训练图像数
test_images       = 原始测试图像数
train_candidates  = 2
test_candidates   = 10
entry_bytes       = T × N / 8
train_entries     = train_images × 2
test_entries      = test_images × 10
input_bytes       = (train_entries + test_entries) × entry_bytes
result_bytes      = (train_entries + test_entries) × 4
```

按当前全量默认值 `T=8`、`N=784`、训练 50,000 图、测试 10,000 图：

| 区域 | 条目数 | 字节数 | 十六进制大小 |
| --- | ---: | ---: | ---: |
| 训练输入 | 100,000 | 78,400,000 | `0x04AC_4A00` |
| 测试输入 | 100,000 | 78,400,000 | `0x04AC_4A00` |
| 总输入 | 200,000 | 156,800,000 | `0x0958_9400` |
| 总结果 | 200,000 | 800,000 | `0x000C_3500` |

若输入基址为 `0x0020_0000`，输入末地址（开区间）是 `0x0978_9400`。当前 AXI 封装结果基址 `0x12D1_2800` 与输入区不重叠且处于 512 MiB 映射内；PS 的旧结果基址 `0x0B00_0000` 也不重叠，但两者必须统一。

### 7.2 地址检查清单

每次改实验规模都检查：

1. `read_base + input_bytes <= DDR 映射上限`。
2. 输入区与结果区不重叠。
3. 结果区与 PS 程序、heap/stack、bitstream 或其他保留区不冲突。
4. 所有基址按 4 byte 对齐；burst 起始最好按 burst byte 数对齐。
5. `all_spikes.bin` 实际文件大小等于期望 `input_bytes`。
6. AXI `TOTAL_TRAIN_SIZE/TOTAL_TEST_SIZE` 与文件条目数一致。
7. PS 统计所读的结果基址与 PL 写基址一致。

![历史 DDR 地址映射调试](assets/FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89/626c829f04c72030d47244dc0c3eb70.png)

## 8. 数据与初始化文件生成

### 8.1 环境

脚本依赖仓库外部 `SNN-forwardforward` 软件工程。建议建立 Python 虚拟环境，并安装该工程实际需要的版本：PyTorch、torchvision、NumPy、Brian2、Matplotlib、Seaborn。然后：

1. 把脚本里的 Windows `sys.path.append('D:/OneDrive/...')` 改成当前软件模型路径，或通过 `PYTHONPATH` 提供。
2. 修改 `hardware_sim/hardware_sim_config.py`：任务名、模型权重、层规模、时间步、并行度、位宽、阈值。
3. 确认所有脚本从仓库根目录运行。

### 8.2 推荐生成顺序

```sh
python hardware_sim/gen_data_flow.py
python hardware_sim/gen_model_weight_coe.py
python hardware_sim/gen_neuron_state.py
python hardware_sim/gen_sigmoid.py
```

这只是调用顺序示例；在解决前述路径、层数和 COE 对齐问题前，不应把命令视为可直接复现实验的保证。

### 8.3 生成后验证

- 用 `stat`/`du` 检查 `all_spikes.bin` 大小，并用第 7 章公式计算条目数。
- 随机抽一条输入，用 Python 解包并与写入前脉冲张量比较。
- 检查权重文件行宽严格等于 `POST_PARALLEL×WEIGHT_WIDTH`。
- 检查每个 bank 2048 行，末尾补零仅出现在最后一个 bank。
- 对有符号最小值、0、最大值逐一验证补码和 RTL 解包。
- `test_labels.h` 的标签数量应等于原始测试图像数，而不是候选条目数。

## 9. RTL 仿真流程

### 9.1 推荐分层验证

1. `tb_parallel_to_serial.sv`：确认 32→4 后的 4 个时间位如何变成 AER 地址/请求。
2. `tb_odin_ffstbp.sv`：单个 `ODIN_ffstdp` 核的激励。
3. `ffstdp_update` 单元测试：正/负方向、补码、饱和边界和 ROM 延迟（尚待补充）。
4. `tb_core_test.sv`：不经过 AXI，直接用 AER 握手驱动单层 `Top_test`。
5. `tb_axi4_rw_test_v1_0_M_AXI.sv`：DDR 行为模型、AXI、FIFO、SNN、结果写回全链路。

当前校验以 `tb_axi4_rw_test_v1_0_M_AXI.sv` 为 AXI+SNN 集成验收入口，`tb_core_test.sv` 为纯核心入口。两者默认都跑 2 个 MNIST 样本、8 个时间步：core 入口固定 `IS_TRAIN=0`，AXI 入口跑 2 个训练条目并核对 goodness 写回；当前都产生 `PROCESS_DONE` 并以 `PASS` 退出。恢复版 `if_neuron` 已完成阈值、计数、膜电位复位和 TREF 清零的单元 smoke test；当前 784×256 `Top_test` 完整层次也已通过 Icarus elaboration。

### 9.2 Icarus Verilog

两套回归脚本位于 `user/sim/iverilog/`，源文件清单为 `core_test_filelist.f` 和 `axi_snn_filelist.f`，均使用仓库相对路径：

```sh
cd user/sim/iverilog
./run_core_test.sh     # 纯 SNN core -> build_core_test/
./run_axi_snn.sh       # AXI+SNN     -> build_axi_test/
```

Icarus 环境用 `axi_input_fifo_model.sv` 行为模型替代 Vivado 的 `axi_input_fifo` IP。若在 xsim 中跑系统级 testbench，应改用工程生成的行为模型，否则只能完成 RTL 展开检查。

### 9.3 Vivado/xsim 系统 testbench 数据路径

`tb_axi4_rw_test_v1_0_M_AXI.sv` 使用 `$fopen(SPIKE_DATA_FILE, "rb")` 和 `$fread` 直接读取生成的原始 `all_spikes.bin`，不是 `$readmemh` 文本。Vivado 仿真会把工作目录切换到工程生成的 run 目录，因此这里有意使用绝对路径。每次换机器、移动仓库或切换 MNIST/FashionMNIST 时，必须修改 testbench 文件顶部的四个路径参数：

```systemverilog
parameter SPIKE_DATA_FILE        = "/本机绝对路径/Gen_out/MNIST/all_spikes.bin";
parameter WEIGHT_DATA_FILE       = "/本机绝对路径/Gen_out/MNIST/weights_weight.txt";
parameter POST_NEURON_STATE_FILE = "/本机绝对路径/Gen_out/MNIST/post_neuron_state.txt";
parameter PRE_NEURON_STATE_FILE  = "/本机绝对路径/Gen_out/MNIST/pre_neuron_state.txt";
```

`tb_core_test.sv` 顶部是同样四个参数。两个 TB 都从 DUT 层次写入行为 SRAM 的初值，SRAM 模块本身不再加载文件。

同时核对 `TOTAL_TRAIN_SIZE`、`TOTAL_TEST_SIZE`、`TIME_TOTAL_STEP` 和 `DATA_SIZE`。TB 的 byte RAM 深度按下式计算，并会在文件不足时立即报错：

```text
(TOTAL_TRAIN_SIZE + TOTAL_TEST_SIZE) × TIME_TOTAL_STEP × DATA_SIZE / 8
```

当前 TB 默认跑 2 个训练条目（`TOTAL_TEST_SIZE=0`）、`STOP_AFTER_FIRST_PROCESS_DONE=0`，即完整跑到 AXI goodness 写回为止。若只需快速 smoke test，把 `STOP_AFTER_FIRST_PROCESS_DONE` 设为 `1'b1`，第一次 `PROCESS_DONE` 后即结束；若要跑批量数据，再同时覆盖训练/测试条目数。

### 9.4 波形验收点

- 复位极性和释放时序正确。
- ARVALID/ARREADY、RVALID/RREADY/RLAST 完成 49 个 burst。
- FIFO 无 overflow/underflow；宽度转换顺序正确。
- AER req/ack 完成四相握手，神经元地址从 0 到 783。
- 单条目结束前正好覆盖 8 个时间步。
- `PROCESS_DONE` 是可被 AXI 时钟采到的脉冲，并且下降沿之后才写 goodness。
- 训练正/负条目 `IS_POS` 交替，训练结束后 `IS_TRAIN=0`。
- AW/W/B 通道只写一个 32-bit 结果，地址每条增加 4。
- 单层完成处的 `GOODNESS` 在写事务前被稳定锁存。

![历史行为仿真波形](assets/FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89/image%2012.png)

## 10. Vivado 综合与实现

### 10.1 打开历史工程

主工程：`prj/snn_pl_axi_ddr/snn_pl_axi_ddr.xpr`，Vivado 2020.2。

打开后先做以下检查，不要立即 Generate Bitstream：

1. Project Part 是 `xc7z030fbg484-1`。
2. Sources 中只存在一个 `Top_test` 模块定义；排除同名历史文件。
3. module reference 指向 `user/src` 当前源码，而非失效的 Windows 绝对路径。
4. `axi_input_fifo`、突触 SRAM/BRAM IP 均未 locked，输出产品齐全。
5. Block Design 选择 `design_7030`，Validate Design 通过。
6. 地址映射包含 PL master 到 HP0 的 512 MiB segment。
7. XDC 与目标板卡和顶层端口匹配。

### 10.2 从脚本重建 Block Design

`user/script/system.tcl` 可作为连接依据，但需先：

- 在正确的 Z-7030 工程中添加 `user/src`。
- 修正脚本的工程名、part 和目录。
- 确认所需 Xilinx IP 在 Vivado 2020.2 可用。
- 执行后 Validate Design，并与 `design_7030.bd` 对比端口、时钟、复位和地址。

### 10.3 综合/实现验收

- 无 latch、多驱动、截断和 CDC 严重警告。
- AXI master 与 HP0 数据宽转换符合预期（master 32 bit，HP0 配置 64 bit）。
- 所有时钟有约束；跨时钟路径只通过正确 CDC 结构。
- WNS/TNS 满足目标时钟，特别检查突触更新、并行加法树和大扇出控制信号。
- BRAM、LUT、FF、DSP 使用量符合目标 Z-7030 容量。
- 生成 bitstream 后导出包含 bitstream 的 XSA/HDF 供 Vitis 平台更新。

旧版时序优化截图仍可用于定位长路径：

![历史关键路径分析](assets/FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89/image%202.png)

## 11. Vitis 裸机程序与 SD 卡

### 11.1 当前实现位置

优先查看：

```text
prj/snn_pl_axi_ddr/vitis/snn_test/src/main.c
```

另一个历史副本位于 `prj/snn_test/src/main.c`。构建日志表明 application 链接了 `xilffs`，程序包含 `ff.h` 并使用 FatFs。

### 11.2 当前程序流程

1. `Xil_DCacheDisable()`，避免 CPU cache 与 PL 共享 DDR 时出现一致性问题。
2. `f_mount("0:/")` 挂载 SD 卡。
3. 若挂载失败，当前程序会尝试 `f_mkfs(..., FM_FAT32, ...)` 格式化再挂载。
4. `f_open(FILE_NAME, FA_READ)` 打开脉冲文件。
5. 每次 `f_read` 4096 byte，4 byte 拼成一个 word 后以 `Xil_Out32` 写入 `0x0020_0000` 起始 DDR。
6. 文件读完后关闭，并等待串口字符。
7. 收到字符 `c` 后，从结果区读取每组 10 个 goodness、求最大下标、比较 `test_labels[]` 并打印准确率。

### 11.3 重要安全修正

当前 `platform_init_fs()` 在挂载失败时会格式化 SD 卡。挂载失败也可能只是卡未插好、分区不兼容或驱动配置错误。正式归档/实验建议删除自动格式化分支，改成报错退出；需要格式化时由用户在 PC 端明确执行并保留备份。

另外，当前读文件循环按 4 byte 分组，但未处理 `br` 不是 4 的倍数时 `buffer[i+1..3]` 越界。规范的数据文件应为 4-byte 对齐，同时代码也应检查末块长度。

### 11.4 SD 卡准备

1. 使用 FAT32 分区。
2. 把选定数据集的脉冲文件放在分区根目录，文件名与 `FILE_NAME` 完全一致。
3. 使用同一生成批次的 `test_labels.h` 更新 Vitis application。
4. 在 PC 上记录文件大小和校验和。
5. 插卡前断电，确认板卡启动模式和 SD 卡槽对应 PS SD0。

### 11.5 当前控制方式，不是 EMIO

SD 加载完成不自动启动 PL；用户仍需按 `key_train_enable` 选择是否训练，再按 `key_init` 启动。PS 程序也不会轮询 `PROCESS_DONE`，而是在用户通过串口输入 `c` 后直接读取结果。

若要实现旧计划中的“PS 加载一批 → EMIO 启动 → 等待 done → 读取结果”，需要新增硬件控制接口并修改 BD/PS 软件。当前仓库没有这一闭环，不能在复现步骤中假定已经存在。

## 12. 完整上板流程

### 12.1 上板前冻结一份实验配置

建议用表格记录：数据集、模型 checkpoint、网络层数、T、并行度、各位宽、训练/测试图像数、输入/结果基址、bitstream 时间戳、`all_spikes.bin` 校验和和 Vitis ELF 时间戳。

至少统一以下常量：

| 位置 | 必须一致的内容 |
| --- | --- |
| `hardware_sim_config.py` | T、层规模、并行度、权重/状态位宽 |
| 数据生成脚本 | 训练/测试图像数、候选排列、任务名 |
| `Top_test.v` | T、层规模、并行度、位宽 |
| AXI 封装 | T、N、训练/测试条目、读写基址 |
| Vitis `main.c` | 文件名、原始图像数、读写基址、候选组大小 |
| `test_labels.h` | 与测试集样本顺序一致 |

### 12.2 推荐执行顺序

1. 修正并运行数据/量化脚本，生成一套自洽的 `Gen_out/<TASK>`。
2. 用小规模样本先做 RTL 全链路仿真，验证地址、字节序和 goodness。
3. 在 Vivado 中更新 RTL/IP/COE，Validate BD。
4. 综合、实现、检查时序与资源、生成 bitstream。
5. 导出硬件平台并更新 Vitis platform/BSP；BSP 启用 `xilffs`。
6. 修改 PS 程序的文件名、样本数和结果基址，替换 `test_labels.h`。
7. 构建 ELF，把 `all_spikes.bin` 复制到 FAT32 SD 卡根目录。
8. 连接 JTAG 和 UART 115200，配置 FPGA，运行 ELF。
9. 串口确认 SD mount、open、DDR load 均成功，并记录最终 `addr`。
10. 按训练使能键选择模式；按启动键开始 PL 流程。
11. 观察 `train_enable_flag`/`train_finish_flag`，必要时用 ILA 观察 AXI/AER/done。
12. 确认全部条目完成后，在串口输入 `c`，读取并打印测试准确率。

### 12.3 首次上板建议用小规模

先把训练、测试规模降到几张图，并相应生成短文件、修改 AXI 条目数和 Vitis 宏。小规模验收包括：

- SD 读入末地址精确等于 `base + file_size`。
- DDR 前 32 byte 与 PC 文件逐字节一致。
- AXI 读地址每条前进 784 byte。
- 训练结果数和测试结果数正确。
- 一张测试图的 10 个 goodness 可在 Vitis Memory 或串口逐项核对。

确认小规模正确后再切换全量，能显著缩短定位周期。

## 13. ILA 与故障定位

### 13.1 SD 卡挂载或读文件失败

按顺序检查：SD0 MIO 配置 → BSP `xilffs` → FAT32 分区 → 文件名大小写 → 卡检测 MIO10 → 是否误用了另一个 `main.c`。不要首先依赖程序自动格式化。

### 13.2 PL 一直停在 INIT

检查 `key_init` 引脚、电平极性、消抖输出、反相器输出与 `init_txn_pulse`。当前按键低有效，BD 中又有逻辑反相；复位释放后用 ILA 观察是否形成 0→1 边沿。

### 13.3 AXI 停在 IDLE/READ_DATA

- IDLE：观察 `ARREADY`；当前转移条件直接依赖它。
- READ_DATA：观察 `ARVALID/ARREADY/RVALID/RREADY/RLAST`、read index 和 burst counter。
- 同时观察 FIFO full；满时读通路会背压。
- 检查地址是否超出 HP0 segment 或跨入 PS 保留区。

### 13.4 SNN 不结束

观察 FIFO empty、`pts_ready`、AER req/ack、scheduler empty/full、controller state、时间步计数和末层 req/ack。常见原因是时间位顺序错误、最后事件没有完整握手、末层 ack 延迟不匹配或 SRAM 延迟变化后 controller 周期预算未更新。

### 13.5 写回值全零或地址错误

观察 `PROCESS_DONE`、`GOODNESS`、`GOODNESS_reg`、下降沿检测、AWADDR/WDATA/WSTRB/BRESP。再确认 PS 读取的是同一 `WRITE_BASE`，并跳过了正确数量的训练条目。

### 13.6 软件读取旧值

当前程序直接禁用了 DCache。如果改为启用 cache，PS 在读取 PL 写入区域前必须 invalidate cache；PS 写完输入供 PL 读取前必须 flush。不要同时保留 cache 又省略维护操作。

![历史 ILA 调试截图](assets/FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89/image%2025.png)

## 14. 历史方案与当前方案的区别

### 14.1 AXI DMA 环路

旧笔记记录了“PS 配置 AXI DMA，MM2S→AXI Stream FIFO→S2MM”的教学验证：

![历史 DMA 环路](assets/FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89/image%2010.png)

这用于早期验证 DDR/DMA，并非当前 SNN 数据通路。当前通路由 `axi4_rw_test_v1_0_M_AXI.v` 直接发 AXI4 burst，不依赖 AXI DMA IP 或 AXI Stream Data FIFO。

### 14.2 Zynq-7010 与 Zynq-7030

仓库同时保留 7010 历史脚本/run 和以 `design_7030` 命名的当前 BD；主工程多数 current runs 指向 `xc7z030fbg484-1`。器件资源、封装引脚和 DDR 容量不能从旧 7010 笔记照搬。复现实验应以实际开发板丝印、原理图和 Vivado Project Part 三者一致为准。

### 14.3 计划中的 EMIO 自动控制

旧计划是 PS 通过 EMIO 拉起 PL、等待 done，再循环加载/统计。目前 PS7 配置中 `PCW_EN_EMIO_GPIO=0` 且 GPIO peripheral 关闭，PL 使用外部按键。要实现自动控制，推荐增加一个 AXI GPIO 或 AXI-Lite 控制寄存器块，比只用无寄存握手的单 bit EMIO 更容易扩展状态、错误码和中断。

## 15. 当前归档的改进路线

按阻塞程度排序：

1. 建立唯一配置源：用 JSON/YAML 生成 Python、RTL include 和 PS 头文件中的网络/样本/地址常量。
2. 固化当前目标：Z-7030、单层 784→256、T=8、并行度 8，并从同一个 checkpoint 重新生成权重/状态/ROM。
3. 在 Vivado/xsim 中用 `tb_axi4_rw_test_v1_0_M_AXI.sv` 完成小样本全链路自检，加入 AXI backpressure、超时和 goodness 对照。
4. 为 AXI 主状态机补齐防御性 default 处理，继续审查 IDLE/ARREADY 和跨时钟 done 脉冲。
5. 统一 PL `WRITE_BASE` 与 PS `DDR_PL_OUT_WR_BASE`。
6. 让 SD 程序不自动格式化、处理非 4-byte 末块、检查文件大小和 DDR 上界。
7. 把按键启动替换为 PS 可控寄存器，并加入 busy/done/error/IRQ；保留按键作为调试旁路。
8. 增加权重打包/解包 round-trip 单元测试；`gen_model_weight_coe.py` 目前只导出首层，与现行单层网络一致。
9. 清理脚本中的失效 Windows 路径（`gen_data_flow.py`/`gen_model_weight_coe.py` 的 `sys.path`、`gen_sigmoid.py` 的 ROM 输出路径），提供可重建 Vivado Tcl 与 Vitis workspace 创建说明；系统 TB 的数据绝对路径保留为显式本机配置项。
10. 把系统 testbench 改为自检式，并在小数据集上比较软件与 RTL 每条 goodness。
11. 最后再做并行度、关键路径、BRAM bank 和功耗优化。

## 16. 维护规则

文档中的数字应同时注明来源文件和适用版本。参数变更提交至少包含：

- 配置差异；
- 新生成物及校验和；
- RTL 仿真结果；
- 综合时序/资源摘要；
- 上板 UART/ILA 结果；
- DDR 地址图更新；
- 本文及相关目录 README 更新。

图片统一保存在 `assets/FF-STDP加速器设计（ZYNQ）/`，Markdown 使用仓库相对路径。不要再创建“图片和附件”目录。唯一例外是 Vivado 系统 TB 的 `SPIKE_DATA_FILE`：它是运行环境配置，必须按本机修改，不能复制为文档图片链接。

## 附录 A：关键文件速查

| 想理解/修改什么 | 首先打开 |
| --- | --- |
| 当前网络层数和层间握手 | `user/src/snn_ff/Top_test.v` |
| 单层 SNN 总结构 | `user/src/snn_ff/ODIN_ffstdp.v` |
| 核内时序和状态机 | `user/src/snn_ff/controller.v` |
| 事件排队 | `user/src/snn_ff/scheduler.v` |
| 神经元积分发放 | `user/src/snn_ff/neuron_core/if_neuron.v` |
| 在线权重更新 | `user/src/snn_ff/synaptic_core/ffstdp_update.v` |
| DDR burst、样本状态机 | `user/src/axi_rw/axi4_rw_test_v1_0_M_AXI.v` |
| 有效 AXI 顶层默认参数 | `user/src/axi_rw/axi4_rw_test_v1_0.v` |
| 32-bit 输入到 AER | `user/src/axi_rw/parallel_to_serial.v` |
| PS/PL 连接与 SD MIO | `user/script/system.tcl`、`design_7030.bd` |
| SD→DDR 与准确率 | `prj/snn_pl_axi_ddr/vitis/snn_test/src/main.c` |
| 数据与量化总配置 | `hardware_sim/hardware_sim_config.py` |
| 脉冲二进制生成 | `hardware_sim/gen_data_flow.py` |
| 权重导出 | `hardware_sim/gen_model_weight_coe.py` |
| 梯度 ROM | `hardware_sim/gen_sigmoid.py` |
| 板级约束 | `user/data/axi4_ddr_rw.xdc` |
| Icarus 回归入口 | `user/sim/iverilog/README.md` |
| core / AXI testbench | `user/sim/tb_core_test.sv`、`user/sim/tb_axi4_rw_test_v1_0_M_AXI.sv` |

## 附录 B：一次实验的最小记录模板

```text
日期：
开发板/器件：xc7z030fbg484-1
Vivado/Vitis：2020.2
数据集：
模型 checkpoint：
网络：784 -> 256
TIME_STEP：8
POST_NEUR_PARALLEL：8
训练图像/条目：
测试图像/条目：
输入 DDR：[base, end)
结果 DDR：[base, end)
all_spikes.bin size/SHA256：
bitstream/ELF：
仿真结果：
WNS/TNS：
LUT/FF/BRAM/DSP：
上板准确率：
UART 日志：
ILA 记录：
已知偏差：
```
