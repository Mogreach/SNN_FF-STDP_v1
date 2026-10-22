# FF-STDP 在线学习加速器：Zynq-7010 设计、验证与上板指南

> 文档定位：本文件是本仓库的总学习文档和复现入口，以当前稳定代码和 Zynq-7010 上板流程为准。设计推导、截图和历史调试经验均保留；
> 论文：FF-STDP：一种基于前向-前向与STDP融合的低功耗在线学习SNN加速器-《电子学报》

## 1. 前言

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

### 1.2 当前归档状态

| 项目        | 当前代码事实                                           | 主要依据                                     |
| --------- | ------------------------------------------------ | ---------------------------------------- |
| FPGA 器件   | Zynq-7010，`xc7z010clg400-1`                      | `prj/snn_pl_axi_ddr/snn_pl_axi_ddr.xpr`  |
| 工具版本      | Vivado 2020.2 工程                                 | 同上                                       |
| 网络顶层      | 当前维护版为单层 784→256                                 | `user/src/snn_ff/Top_test.v`             |
| 时间步       | RTL 当前默认 `TIME_STEP=8`                           | `Top_test.v`、AXI RTL                     |
| 后神经元并行度   | 当前顶层默认 8                                         | `Top_test.v`                             |
| AXI 数据口   | PL 为 AXI4 master，经 SmartConnect 接 PS `S_AXI_HP0` | `user/script/system.tcl`、当前 Block Design |
| PL/AXI 时钟 | 当前 BD 把 Top、AXI master、HP0 时钟都接到 FCLK0=100 MHz   | `system.tcl`                             |
| SD 卡      | PS7 SD0，MIO 40..45，卡检测 MIO10；FatFs 读取文件          | `system.tcl`、Vitis `main.c`              |
| 启动方式      | 两个低有效板上按键，经消抖和反相后驱动启动与训练开关                       | `system.tcl`、`key_debounce.v`            |
| PS↔PL 控制  | 当前未启用 EMIO GPIO；PS 只负责装载 DDR 和读取结果               | `system.tcl` 中 EMIO/GPIO 均禁用             |
| 结果写回      | 每个输入条目写一个 32-bit goodness                        | AXI master RTL                           |

### 1.3 上板前一致性检查

Python、RTL、Vivado 和 Vitis 已形成稳定流程；每次重新生成实验数据或修改参数时，仍必须检查以下一致性：

- `hardware_sim/hardware_sim_config.py` 与当前 `Top_test` 已统一为 784→256、T=8、并行度 8；`NET_PATH` 现指向仓库内的 `./hardware_sim/MNIST_91.pth`（相对仓库根目录），重新生成数据前仍需核对这个 checkpoint 的结构是否就是该配置。
- AXI 封装层的样本数/写基址会覆盖内层默认值。有效默认值是训练 `2×50000`、测试 `10×10000`、写基址 `0x12D1_2800`；不要只看 `_M_AXI.v` 文件顶部。
- PS 工程有多个 `main.c` 副本：`prj/snn_test/src/main.c` 默认文件名是 `fashionmnist.bin`，`prj/snn_pl_axi_ddr/vitis/snn_test/src/main.c` 默认是 `all_spikes.bin`。
- Vitis 程序写结果读取基址仍定义为 `0x0B00_0000`，与当前 AXI 封装写基址 `0x12D1_2800` 不一致。上板前必须选定一个地址并两端同步。
- 已有历史综合网表不等于当前源码可以干净重建；重新综合前仍需对当前 file set 做一次从零编译和回归。
- `gen_model_weight_coe.py` 当前只导出首层，适合现行单层顶层；若将来扩展为多层，需要改为逐层导出并解决源码标注的 COE 行对齐问题。当前归档中已无多层顶层文件。
- `gen_sigmoid.py` 已改为把 ROM RTL 写到 `user/src/snn_ff/rom/`（仓库锚定路径），重跑会覆盖现有 ROM 源码。
- 生成脚本的仓库内路径已用 `hardware_sim_config.py` 的 `REPO_ROOT` 锚定，不再依赖工作目录；但脚本顶部的 `sys.path.append('D:/OneDrive/...')` 仍指向仓库外的软件工程，换机器需改。
- `system.tcl` 是 Block Design 导出参考。使用它重建工程时，先在 Zynq-7010 工程中加入 `user/src`，并确认 Project Part 为 `xc7z010clg400-1`。
- 当前单层 `Top_test` 已通过 Icarus Verilog 11 干净展开；Icarus 环境用 `user/sim/iverilog/axi_input_fifo_model.sv` 行为模型替代 FIFO Generator IP，两套 TB 均可在 Icarus 下回归，xsim 工程回归仍应使用 Vivado 生成的行为模型。

## 2. 仓库文件树

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
2. PS/PL 连接、端口和时钟：当前 Vivado Block Design，辅以 `user/script/system.tcl`。
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

## 4. PS/PL 互连方案

### 4.1 数据通路

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

==**PS端主程序首先将SD卡的数据集内容烧录写入DDR3中，PL端的AXI模块负责读取搬运DDR3数据，生成AER事件数据输入给SNN加速器处理，处理完一个样本后通过AXI模块写回DDR3中，PS端待SNN处理完样本数后，读取写回结果，计算准确率，通过串口打印输出结果给上位机PC。**==
![Pasted_20260915232137_FF-STDP加速器设计（ZYNQ）](assets/FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89/Pasted_20260915232137_FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89.png)

### 4.2 时钟与复位

- PS FCLK0 配置为 100 MHz。
- `Top_test.CLK`、AXI master `SNN_CLK`/`m_axi_aclk`、SmartConnect、HP0 ACLK、按键消抖和 Processor System Reset 都接 FCLK0。
- `clk_wiz` 生成 50 MHz 和 100 MHz 输出，但从导出的连接看，这些输出没有作为 SNN/AXI 主时钟；旧文档的“AXI_ACLK=50 MHz”不适用于当前 BD。
- PS `FCLK_RESET0_N` 进入 `proc_sys_reset`。外设低有效复位直接给 AXI/SmartConnect/按键模块，同时经反相后作为 `Top_test` 的高有效 `RST` 和 clock wizard reset。

尽管当前两侧同为 100 MHz，AXI 输入桥仍使用独立 `wr_clk`/`rd_clk` 的异步 FIFO，保留了以后分频的能力。

### 4.3 SD、串口和按键配置信息

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
### 4.4 数据集导入方式
当前已支持SD自动导入的初始化功能，详情见：
```text
prj/snn_pl_axi_ddr/vitis/snn_test/src/main.c
```
如果没有SD卡，可以注释掉相应代码，采取手动导入方式，方法如下：
1. 将Python软件生成的二进制bin脉冲数据文件，通过Vitis的Restore Memory存在DDR中；
2. 连接好ZYNQ后，开启工程Debugger模式，在Xlinix选择Dump/Restore Memory，选择ZYNQ的cpu以及对应文件，填写好写入地址和长度即可。
3. 在Vitis的Memory Monitor处可以实时监测板子DDR数据。
![Pasted_20260915233155_FF-STDP加速器设计（ZYNQ）](assets/FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89/Pasted_20260915233155_FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89.png)
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
首先进入INIT初始化状态，等待按键启动，进入IDLE准备状态，一次进入读取数据、处理数据、写入数据、完成、下一个样本状态，完成一个样本的训练/测试，训练样本与测试样本依次排列，先输入训练样本，输入完后输出训练完成信号，再输入测试样本，至此完成后每个样本的goodness都写入ddr中。

`TRAIN_ENABLE_FLAG` 在 INIT 中被训练按键上升沿翻转。训练结束后，`IS_TRAIN` 拉低但继续处理测试条目；测试条目仍每条翻转 `IS_POS`，但推理逻辑主要依赖 `IS_TRAIN=0`。
### 5.3 读路径时序描述

1. AR 通道发 4-beat INCR burst。
2. 每次 `RVALID && RREADY` 接收 32 bit。
3. 字节倒序后写入 `axi_input_fifo`。
4. FIFO 写口是 32 bit，读口是 4 bit，读侧每次得到同一像素的 4 个时间位。
5. `parallel_to_serial` 扫描 4 bit 内的置位时间，并按像素计数生成神经元事件；完成全部 784 像素后产生时间/完成控制事件。
6. 每个 AER 事件严格等待 `AER_IN_ACK`。

### 5.4 写路径时序描述

SNN `PROCESS_DONE` 有效时将 `GOODNESS` 锁存到 `GOODNESS_reg`。两级采样寄存器检测 `PROCESS_DONE` 下降沿，状态机随后发起单 beat AXI 写。每条结果 4 byte，结果条目 `k` 的地址为：

```text
write_address(k) = WRITE_BASE + 4 × k
```

PS 对测试结果读取时还需跳过所有训练条目：

```text
test_result_base = WRITE_BASE + 4 × TRAIN_ENTRIES
```

若 `TRAIN_SAMPLES` 表示原始图像数，训练条目数为 `2×TRAIN_SAMPLES`；当前 PS 代码正是按 `TRAIN_SAMPLES * 2 * 4` 计算偏移。
### 5.5 并串转换事件发生模块
将脉冲数据编码为AER事件数据

![并串转换与事件发送](assets/FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89/image%2019.png)
> 红色箭头：输出神经元事件控制信号变化
> 绿色箭头：无输出神经元事件控制信号变化
> 蓝色箭头：输出TSTEP事件控制信号变化

- ready信号拉高时，FIFO读使能拉高一周期，随后拉高有效数据，打一拍存入并串转换模块，同时拉低ready信号；
- 对于并串准备`ready`信号，当`ready`和`din_valid`握手时，`ready`信号拉低；当计数器`cnt`低2位为`11`且`shift_en`，或者`tstep_vaild`与`Req`下降沿时，`ready`信号拉高；（时序逻辑）
- 对于移位使能`shift_en`信号，当`ready`信号和`tstep_vaild`拉低时，输出`dout`为0，则拉高；若为`dout`为1，需等待`Req`下降沿，`shift_en`才拉高；（组合逻辑）
- 对于计数器`cnt`，只有在`!ready && shift_en`时才计数，计数最大后同步置0。（时序逻辑）
- 对于时间步事件有效`tstep_vaild`信号，`cnt`等于`CNT_STEP`且`shift_en`时才拉高；`tstep_vaild`拉高后检测到`Req`下降沿拉低，其他保持。（时序逻辑）
- 对于请求`Req`信号，当`ready`信号拉低，且`Req`和`Ack`空闲时，`dout`为0或者`tstep_vaild`上升沿，`Req`信号拉高；收到`Ack`高电平回应时才拉低，其他保持。（时序逻辑）
- 当req拉低或者输出为0，且计数为3时，ready信号再次拉高；
## 6. SNN 硬件架构

![SNN 硬件框架](assets/FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89/Pasted_20260914114639_FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89.png)
基于Tiny ODIN的事件驱动设计，利用SRAM存储必要的神经元状态信息，以及突触权重值，通过神经元核心与突触核心分别控制读写，由控制器接受AER事件，控制驱动核心，通过时分复用同一核心完成所有神经元激活、权重更新等操作，最终输出结果。
### 6.1 顶层 `Top_test`

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

### 6.2  `ODIN_ffstdp`加速器核心

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
#### 编码方式

| ADDR<11> | ADDR<10> |  ADDR <9:0>   |    Event type     | Number of cycles |              Description              |
| :------: | :------: | :-----------: | :---------------: | :--------------: | :-----------------------------------: |
|    0     |    0     | 突触前神经元地址<9:0> |  神经元事件NEUR_EVENT  |   2*（64+1） clk   | 输入神经元脉冲事件，与之相连的所有突触都将累加一次膜电位到对应突触后神经元 |
|    0     |    1     |     0xFF      | 时间步事件TSTEP_EVENT  |   2*（64+1） clk   |          更新所有神经元状态，进入下一个时间步           |
|    1     |    0     |     0xFF      |  推理事件TREF_EVENT   | 2*（50176+1） clk  |            时间步结束，输出结果，更新权重            |
|    1     |    1     |       x       | 无效事件INVALID_EVENT |        0         |                  无意义                  |
#### 握手协议

| Pin        | Direction | Width  | Description                     |
| ---------- | --------- | ------ | ------------------------------- |
| AERIN_ADDR | Input     | 12-bit | AER address field.              |
| AERIN_REQ  | Input     | 1-bit  | AER request handshake line.     |
| AERIN_ACK  | Output    | 1-bit  | AER acknowledge handshake line. |
四相握手顺序：发送端置 `REQ` → 接收端置 `ACK` → 发送端撤 `REQ` → 接收端撤 `ACK`。`controller` 的 `WAIT_REQDN` 专门等待请求撤销，避免同一事件重复接收。
![[assets/FF-STDP加速器设计（ZYNQ）/Pasted_20260915235016_FF-STDP加速器设计（ZYNQ）.png|600]]

按输入神经元序号输入脉冲，激活对应神经元事件，即逐个对与之相连的784个突触后神经元的膜电位以及输出脉冲计数进行更新，并对该输入神经的脉冲计数累加（SRAM）。经过多个时间步后，发动一次时间步推理时间，按突触前神经元顺序，先访问突触前sram获得输入脉冲数，再逐个突触后sram，获取输出脉冲数以及权重参数，访问，更新所有权重
### 6.4 scheduler

`scheduler.v` 缓存两类来源：外部 AER 输入与神经元核心内部产生的事件。controller 提供 push/pop、地址、事件来源和虚拟事件字段；scheduler 返回 empty/full 和队头数据。controller 在 WAIT 状态依据队头高位决定进入神经元处理还是时间步处理。

### 6.5 controller

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

- 等待状态，由AER_REQ拉高时，先判断是NEUR_event还是TSTEP_event，进入PUSH阶段，将该事件打入调度器的fifo中，跳转至WAIT_REQDN，将应答信号AER_ACK拉高后进入WAIT等待；

- 当fifo满了，或者，没有外部事件输入且fifo不空时，根据调度器输出的前2位地址编码，判断是NEUR_event还是TSTEP_event，再进入各自ACT状态，表示此时正在处理该事件，执行数据更新；执行完再进入POP弹出状态，将调度器的事件弹出。

- 对于神经元NEUR_event，历遍完所有突触后神经元的膜电位更新后，在弹出状态更新突触前脉冲计数，最后进入WAIT等待状态；
	如下图所示，通过ctrl_cnt控制计数，控制SRAM的地址信号neur_cnt、片选写入信号cs、读使能信号we，实现每两个周期交替对SRAM内存模型单一地址的读写操作，通过NEUR_EVENT信号标识此时事件处理状态。
![Pasted_20260916002826_FF-STDP加速器设计（ZYNQ）](assets/FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89/Pasted_20260916002826_FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89.png)

- 对于TSTEP事件，历遍所有突触后神经元，判断是否发射脉冲及更新膜电位和脉冲计数，并同时将发射脉冲的突触后神经元地址打入调度器的输出fifo缓存，fifo只要空闲就自动发放事件。待历遍完后进入POP_AER_OUT状态，等待fifo所有缓存激活的神经元地址后（empty），再输出tstep事件，输出完后判断是否进行推理更新权重进入TREF状态，否则进入WAIT状态；
	如下图所示，与NERU_ACT时序相似，通过TSTEP_EVENT标识事件类型，控制计数ctrl_cnt控制神经元内存的读写，当有脉冲输出时拉高aer_push信号，将该脉冲编译对应神经元事件，打入到AER_OUT模块的fifo中缓存。

![Pasted_20260916002857_FF-STDP加速器设计（ZYNQ）](assets/FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89/Pasted_20260916002857_FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89.png)

- 对于TREF_event，历遍所有突触，根据突触前、后神经元脉冲计数计算梯度更新，并对计数置0，历遍完后进入WAIT状态。
	如下图所示，同样通过ctrl_cnt控制突出内存的读写，先从突触前神经元开始历遍所有突触权重，花费2个时钟周期对4个突出权重进行更新，期间AER_OUT模块计算累加Goodness值，突触后神经元脉冲计数清0。每历遍完一次，突触前神经元的脉冲计数清0。当历遍完所有突触权重时，tref_finish信号拉高，标志推理学习过程完成，控制器跳转至WAIT状态，同时Goodness被AXI接口模块寄存写回DDR。
![Pasted_20260916002906_FF-STDP加速器设计（ZYNQ）](assets/FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89/Pasted_20260916002906_FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89.png)

- 对于POP_NEUR状态，如下图所示，当ctrl_cnt控制计数达到指定计算周期后，跳转至POP_NEUR状态，同时对当前对应突触前神经元内存进行读写，更新脉冲计数，完成后进入WAIT等待状态。
![Pasted_20260916003140_FF-STDP加速器设计（ZYNQ）](assets/FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89/Pasted_20260916003140_FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89.png)

总的来说，控制器主要用来控制**不同RAM的读写操作**以及事件接受，不同事件对于RAM的控制情况如下：

|事件类型|突触前ram操作|突触后ram操作|突触内存ram操作|
|---|---|---|---|
|NEUR_EVENT|读/写|读/写|读|
|TSTEP_EVENT|无|读写|无|
|TREF_EVENT|读/写|读/写|读/写|

### 6.6 神经元模块
- `pre_neuron.v` 记录输入神经元在当前时间窗的脉冲计数/状态。
- `if_neuron.v` 对突触输入积分；时间步结束时比较阈值，发放则脉冲计数加一并把膜电位清零，TREF 再清零整个样本状态。
- `neuron_core.v` 并行处理 8 个后神经元，连接后状态 SRAM 与 AER 输出。
- `sram_post_neuron.v`、`sram_pre_neuron.v` 保存跨事件状态。

#### 神经元状态 RAM 参数

神经元状态不存放在突触权重 BRAM 中，而由 `neuron_core.v` 实例化两组参数化 RAM。突触前 RAM 以单个输入神经元为存储粒度；突触后 RAM 则以 `POST_NEUR_PARALLEL` 个 lane 为一个存储字，因此深度随并行度变化。当前顶层 `INPUT_NEURON=784`、`OUTPUT_NEURON=256`、`POST_NEUR_PARALLEL=8`，相应配置如下。

| RAM | RTL 模块/实例 | 存储粒度 | 单个神经元状态位宽 | RAM 数据位宽 | 深度 | RAM 地址位宽 | 当前值 |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| 突触前状态 RAM | `sram_pre_neuron` / `neurarray_pre` | 1 个输入神经元 | `PRE_NEUR_DATA_WIDTH` | `PRE_NEUR_DATA_WIDTH` | `INPUT_NEURON` | `PRE_NEUR_ADDR_WIDTH` | 8 bit × 784，10 bit 地址 |
| 突触后状态 RAM | `sram_post_neuron` / `neurarray_post` | `POST_NEUR_PARALLEL` 个后神经元 | `POST_NEUR_DATA_WIDTH` | `POST_NEUR_PARALLEL × POST_NEUR_DATA_WIDTH` | `OUTPUT_NEURON / POST_NEUR_PARALLEL` | `$clog2(OUTPUT_NEURON / POST_NEUR_PARALLEL)` | 160 bit × 32，5 bit 地址 |

突触后 RAM 的外部神经元地址仍是 `POST_NEUR_ADDR_WIDTH=10` bit；`neuron_core` 依据 `POST_NEUR_BYTE_ADDR_WIDTH=$clog2(POST_NEUR_PARALLEL)=3` 取其组地址部分，从而使连续的 8 个后神经元共享一个 160-bit 存储字。一般化地：

```text
post_ram_data_width = POST_NEUR_PARALLEL × POST_NEUR_DATA_WIDTH
post_ram_depth      = OUTPUT_NEURON / POST_NEUR_PARALLEL
post_ram_addr_width = clog2(post_ram_depth)
```

当改变输出神经元数量、并行度或状态字段位宽时，除 RTL 参数外，还必须同步更新 `hardware_sim/hardware_sim_config.py`、`gen_neuron_state.py` 生成的状态文件，以及 testbench 的 `$readmemh` 装载范围。

#### 突触后神经元状态定义

| Bitwise location in word | Parameter/state | Name         | Width | Description |
| ------------------------ | --------------- | ------------ | ----- | ----------- |
| 12-0                     | State           | core         | 13    | 膜电位的当前值。    |
| 13-18                    | state           | 脉冲计数         | 6     | 该神经元发放脉冲计数  |
| 19                       | Parameter       | neur_disable | 1     | 神经元使能       |
#### 突触前神经元状态定义

| Bitwise location in word | Parameter/state | Name | Width | Description |
| ------------------------ | --------------- | ---- | ----- | ----------- |
| 7-0                      | State           | 脉冲计数 | 8     | 输入脉冲计数      |

### 6.7 在线更新模块

![FF-STDP 更新数据通路](assets/FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89/Pasted_20260914115258_FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89.png)

训练时，`ffstdp_update.v` 根据：

- `IS_POS` 正/负条目标志；
- 突触前神经元脉冲计数；
- 突触后神经元脉冲计数/频率；
- `pos_derivative_rom.v` 或 `neg_derivative_rom.v` 查表结果；

Python 中梯度的核心形式为正负 sigmoid 导数乘以发放频率及学习率，然后量化到 `WEIGHT_WIDTH`。ROM 是离散近似，因此时间步或位宽变化必须重新生成，而不是只改 RTL parameter。==`hardware_sim/gen_sigmoid.py`可以直接生成对应`rom.v`文件==

### 6.8 突触权重模块
- **量化方式**：有符号INT9定点数
- **寻址方式**：突触前神经元地址以及突触后神经元的前8位用于指定word的地址，突触后的后2位用于指定byte地址==（取决于并行度，如果并行度为8则是后3位）==

| Synapse memory address | Width  | Contents                      |
| ---------------------- | ------ | ----------------------------- |
| Neuron address         | 10-bit | 神经元地址                         |
| Word address           | 16-bit | {突触前神经元地址<9:0>,突触后神经元地址<7:2>} |
| Byte address           | 2-bit  | 突触后神经元<1:0>                   |
|                        |        |                               |
- **使用Vivado 初始化带权重RAM IP：**

1. 首先生成RAM IP

![Pasted_20260916001006_FF-STDP加速器设计（ZYNQ）](assets/FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89/Pasted_20260916001006_FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89.png)

2. 设置位宽和深度

![Pasted_20260916001010_FF-STDP加速器设计（ZYNQ）](assets/FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89/Pasted_20260916001010_FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89.png)

3. 加载COE文件，COE文件可有python脚本`hardware_sim/gen_model_weight_coe.py`生成

![Pasted_20260916001017_FF-STDP加速器设计（ZYNQ）](assets/FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89/Pasted_20260916001017_FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89.png)

### 6.9 AER输出模块
`aer_out/aer_outs.v` 将 8 路后神经元发放结果转换回 12-bit AER 事件，并在一个时间步的所有输出事件发送完毕后产生下游时间步事件。模块内部使用 `syncFIFO_diffWidth`：写端一次写入 8 个 lane 的 AER 字，读端每次取出 1 个 12-bit 事件，因此同一组并行神经元的输出会被串行发送。

每个 lane 的输入事件按下式编码。未发放的 lane 不占用有效 AER 传输，写入 FIFO 的是无效码 `2'b11`；读端检测到无效码后不拉起请求。

```text
spike lane i : {2'b00, CTRL_POST_NEURON_ADDRESS + i}
silent lane  : {2'b11, 10'd0}
time step    : {2'b01, 10'd0}
```

#### 状态机设计

该模块没有单独定义枚举型 `state` 寄存器，而是由 `aer_out_trans`、`AEROUT_REQ`、同步后的 `AEROUT_ACK`、FIFO 空标志和 `aer_out_addr_last` 共同形成输出状态机。其等价状态与转移如下。

| 阶段 | 进入条件 | 主要动作 | 退出条件 |
| --- | --- | --- | --- |
| 并行结果入 FIFO | `CTRL_AEROUT_PUSH_NEUR=1` 且 FIFO 未满 | 将当前 8 lane 编码为 8 个 AER 字并写入异宽 FIFO | 写入完成，等待控制器进入输出阶段 |
| 取下一个神经元事件 | `CTRL_AEROUT_POP_NEUR=1`、FIFO 非空、没有进行中的传输且 ACK 为低 | `fifo_rd_en` 读出一个 12-bit 字；经过一级寄存后，只有事件类型非 `11` 的字才允许发送 | 得到有效神经元事件或跳过无效 lane |
| 发起 AER 请求 | `aer_out_start=1` 且同步 ACK 为低 | 锁存 `AEROUT_ADDR`，拉高 `AEROUT_REQ`，置 `aer_out_trans` | 接收端将 `AEROUT_ACK` 拉高 |
| 等待握手释放 | ACK 高 | 拉低 `AEROUT_REQ`，保持传输占用，防止重复取 FIFO | 检测到同步 ACK 的下降沿，清除 `aer_out_trans` |
| 发送时间步事件 | `CTRL_AEROUT_POP_TSTEP=1`、FIFO 已空、无进行中传输且尚未完成 | 发送 `{2'b01,10'd0}`，并置 `aer_out_addr_last` 标记该时间步最后一个事件 | 该事件的 ACK 完成后，`aer_out_addr_last` 下降沿形成 `AEROUT_CTRL_FINISH` |

`AEROUT_ACK` 经过两级同步和一个延迟寄存器后参与状态转移，避免把异步应答直接用于 FIFO 读使能或请求撤销。`AEROUT_CTRL_FINISH` 反馈给 `controller`：只有本时间步所有神经元事件和末尾时间步事件都完成握手后，控制器才允许继续处理下一阶段。`ONE_SAMPLE_FINISH` 由 `CTRL_AEROUT_TREF_FINISH` 的延迟链产生，用于将核心的一个样本完成时刻导出到 `Top_test.PROCESS_DONE`。

![Pasted_20260916003335_FF-STDP加速器设计（ZYNQ）](assets/FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89/Pasted_20260916003335_FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89.png)

#### Goodness计算
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

Python 数据生成环境使用 PyTorch、torchvision、NumPy、Matplotlib、Seaborn 等依赖；运行前激活项目已验证的虚拟环境，然后执行：

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

### 9.1 子模块-核心-系统验证

1. `tb_parallel_to_serial.sv`：确认 32→4 后的 4 个时间位如何变成 AER 地址/请求。
2. `tb_odin_ffstbp.sv`：单个 `ODIN_ffstdp` 核的激励。
3. `ffstdp_update` 单元测试：正/负方向、补码、饱和边界和 ROM 延迟（尚待补充）。
4. `tb_core_test.sv`：不经过 AXI，直接用 AER 握手驱动单层 `Top_test`。
5. `tb_axi4_rw_test_v1_0_M_AXI.sv`：DDR 行为模型、AXI、FIFO、SNN、结果写回全链路。

当前校验以 `tb_axi4_rw_test_v1_0_M_AXI.sv` 为 AXI+SNN 集成验收入口，`tb_core_test.sv` 为纯核心入口。两者默认都跑 2 个 MNIST 样本、8 个时间步：core 入口固定 `IS_TRAIN=0`，AXI 入口跑 2 个训练条目并核对 goodness 写回；当前都产生 `PROCESS_DONE` 并以 `PASS` 退出。恢复版 `if_neuron` 已完成阈值、计数、膜电位复位和 TREF 清零的单元 smoke test；当前 784×256 `Top_test` 完整层次也已通过 Icarus elaboration。

### 9.2 Icarus Verilog仿真环境

两套回归脚本位于 `user/sim/iverilog/`，源文件清单为 `core_test_filelist.f` 和 `axi_snn_filelist.f`，均使用仓库相对路径：

```sh
cd user/sim/iverilog
./run_core_test.sh     # 纯 SNN core -> build_core_test/
./run_axi_snn.sh       # AXI+SNN     -> build_axi_test/
```

Icarus 环境用 `axi_input_fifo_model.sv` 行为模型替代 Vivado 的 `axi_input_fifo` IP。若在 xsim 中跑系统级 testbench，应改用工程生成的行为模型，否则只能完成 RTL 展开检查。

两个 filelist 顶部都定义了 `SNN_RAM_SIM`，把突触权重存储切到行为模型。**FPGA 构建不定义该宏**，此时 `synaptic_core.v` 实例化工程里的 `sram_synaptic` BRAM IP。前、后神经元状态 RAM 在 RTL 中使用参数化自写 RAM；仿真初值由 testbench 按 DUT 层次通过 `$readmemh` 装载。完整说明见 `user/src/snn_ff/sram/README.md`。

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

### 10.1 打开工程

主工程：`prj/snn_pl_axi_ddr/snn_pl_axi_ddr.xpr`，Vivado 2020.2。

打开后先做以下检查，不要立即 Generate Bitstream：

1. Project Part 是 `xc7z010clg400-1`。
2. Sources 中只存在一个 `Top_test` 模块定义；排除同名历史文件。
3. module reference 指向 `user/src` 当前源码，而非失效的 Windows 绝对路径。
4. `axi_input_fifo`、突触 SRAM/BRAM IP 均未 locked，输出产品齐全。
5. **不要**把 `user/src/snn_ff/sram/sram_synaptic.v`（仿真行为模型）加入 file set——它与 `sram_synaptic` BRAM IP 同名。该文件已用 `` `ifdef SNN_RAM_SIM `` 整体包住，误加也不会重复定义，但仍应从 file set 中排除。
6. 未定义 `SNN_RAM_SIM`（不要为综合设置它）。
7. 在 Synthesis 的 Verilog Define 中设置两个初值路径宏，否则综合会直接报错：

   ```tcl
   set_property verilog_define {
     SNN_PRE_NEUR_STATE_FILE="<abs>/Gen_out/MNIST/pre_neuron_state.txt"
     SNN_POST_NEUR_STATE_FILE="<abs>/Gen_out/MNIST/post_neuron_state.txt" } \
     [get_filesets sources_1]
   ```

8. 打开当前 Block Design，Validate Design 通过。
9. 地址映射包含 PL master 到 HP0 的 512 MiB segment。
10. XDC 与目标板卡和顶层端口匹配。

### 10.2 从脚本重建 Block Design

`user/script/system.tcl` 可作为连接依据，但需先：

- 在正确的 Zynq-7010 工程中添加 `user/src`。
- 修正脚本的工程名、part 和目录。
- 确认所需 Xilinx IP 在 Vivado 2020.2 可用。
- 执行后 Validate Design，并核对端口、时钟、复位和地址。

### 10.3 综合/实现验收

- 无 latch、多驱动、截断和 CDC 严重警告。
- AXI master 与 HP0 数据宽转换符合预期（master 32 bit，HP0 配置 64 bit）。
- 所有时钟有约束；跨时钟路径只通过正确 CDC 结构。
- WNS/TNS 满足目标时钟，特别检查突触更新、并行加法树和大扇出控制信号。
- BRAM、LUT、FF、DSP 使用量符合目标 Zynq-7010 容量。
- 生成 bitstream 后导出包含 bitstream 的 XSA/HDF 供 Vitis 平台更新。

旧版时序优化截图仍可用于定位长路径：

![历史关键路径分析](assets/FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89/image%202.png)

## 11. Vitis 裸机程序与 SD 卡

### 11.1 实现位置

优先查看：

```text
prj/snn_pl_axi_ddr/vitis/snn_test/src/main.c
```

另一个历史副本位于 `prj/snn_test/src/main.c`。构建日志表明 application 链接了 `xilffs`，程序包含 `ff.h` 并使用 FatFs。

### 11.2 程序流程

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


## 13. Debug日志

### 13.1 复位信号接反
关于一周前写好的毕设fpga测试回路，但上板调试后出现数据流水以及状态机阻塞问题，历经4天日以继夜的仿真debug，均验证所有模块设计无时序问题，最后本人于2025年3月13日19：48分发现主模块复位信号接反，望周知！！！
![Pasted_20260916003808_FF-STDP加速器设计（ZYNQ）](assets/FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89/Pasted_20260916003808_FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89.png)
**现象**：在Block Design 接入ILA，上板测试后，观察AXI总线以及接口的状态机，发现AXI读写接口卡在PROCESS_DATA状态无法跳转。

**分析**：对比仿真结果确认功能无误后，推断是PROCESS_DONE信号一直没给出导致状态机卡住，而决定PROCESS_DONE信号的**先决条件是SNN模块接受1个样本的16个时间步数据后才会拉高，对于AXI读数据以及输入事件生成均确认无误后，发现SNN模块一直没有事件输出，于是检查该模块的所有接口、时序逻辑是否无误，最后发现输入的事件一直没有打入SNN的调度器中，检查相关信号**，确认了是复位信号异常，检查Block Design发现是该模块的复位信号接反了！！！
### 13.2 DDR大小端读写映射

  DDR 读写调试中，通过对比 Memory Monitor 与 ILA 抓取信号可发现：若导入 DDR 的字节序与 AXI 读取顺序不一致，输入事件会错位。当前数据以字节为单位按既定顺序写入 DDR，而 32-bit AXI 读写按低字节映射；后续 FIFO 又从高位依次取出数据，因此 AXI 读数据需要按字节重排，才能保证事件流顺序正确。
  ![Pasted_20260916003928_FF-STDP加速器设计（ZYNQ）](assets/FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89/Pasted_20260916003928_FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89.png)
修改代码如下：

```verilog
    // AXI以小端的形式读取DDR数据，然而本项目DDR数据以大端存储，为此需要对输入数据按字节为单位进行倒序排列
    genvar i;
    genvar j;
    generate
        for (i = 0; i < 4; i = i + 1) begin : reverse_bytes
            for (j = 0; j < 8; j = j + 1) begin : reverse_bits
                assign M_AXI_RDATA_REVERSED[i*8+j] = M_AXI_RDATA[(4-i-1)*8 +j];
            end
        end
    endgenerate
```
### 13.3 同步时钟信号

导入DDR数据按下按钮后，观察写回的数据，发现与仿真的输出结果对不上，经过多番调试，验证确认AXI总线传输无误后，观察Memory Monitor写回数据的变化规律，发现有些写回数据的大小与仿真的近似，但有些会错位，推测是因为AXI采样时钟与SNN时钟不同步导致采样发生错误，虽说**最初设计时，通过打拍的方式确保数据跨时钟传输无误，但是考虑到要传输的GOODNESS是32位的多位宽数据，每个bit的变化时间参差不齐，可能会采集到因路径延迟不同而导致的错误数据，即时序上存在 violation，**（参考： [跨时钟传输](https://mp.weixin.qq.com/s?__biz=Mzg3MTY2MjgzOQ==&mid=2247484828&idx=3&sn=feece1792c910479233038f937fdddc1&chksm=cefa5004f98dd9129dbb1430461feb36066a5e0d5780ecb5caf7bae6236b717bf9cfcb92bb28&scene=21#wechat_redirect)）。所以**改为同步时钟**后，数据能够准确采样并写入：
![Pasted_20260916004039_FF-STDP加速器设计（ZYNQ）](assets/FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89/Pasted_20260916004039_FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89.png)
![Pasted_20260916004045_FF-STDP加速器设计（ZYNQ）](assets/FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89/Pasted_20260916004045_FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89.png)

### 13.4 DDR内存空间映射
ZYNQ的DDR并非所有空间都可以使用！！！
![Pasted_20260916004146_FF-STDP加速器设计（ZYNQ）](assets/FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89/Pasted_20260916004146_FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89.png)

在本项目Block Design中，AXI接口显示主机最大地址映射

![历史 ILA 调试截图](assets/FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89/image%2025.png)

在Vitis中，lscript.ld显示了当前DDR可用的地址空间

### 13.5 优化
分析布局布线后的时序报告：
![Pasted_20260916004319_FF-STDP加速器设计（ZYNQ）](assets/FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89/Pasted_20260916004319_FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89.png)

可见关键走线延迟占比较大，限制工作频率，分析路径定位问题：

![Pasted_20260916004338_FF-STDP加速器设计（ZYNQ）](assets/FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89/Pasted_20260916004338_FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89.png)
![Pasted_20260916004346_FF-STDP加速器设计（ZYNQ）](assets/FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89/Pasted_20260916004346_FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89.png)

可见关键路径为突触权重读取到neuron核心累加膜电位时，走线延迟+逻辑延迟接近10ns，在spike脉冲输出到aer_out的fifo中，由于FIFO设置为BRAM实现，故此处输出也存在一部分走线延迟，达到了2ns之多。

**解决办法：**

1. 膜电位累加增加一级寄存器，打一拍写入

![Pasted_20260917114337_FF-STDP加速器设计（ZYNQ）](assets/FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89/Pasted_20260917114337_FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89.png)

2. 改变spike_out写法

![Pasted_20260917114405_FF-STDP加速器设计（ZYNQ）](assets/FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89/Pasted_20260917114405_FF-STDP%E5%8A%A0%E9%80%9F%E5%99%A8%E8%AE%BE%E8%AE%A1%EF%BC%88ZYNQ%EF%BC%89.png)

此处原来spike_out写在always外面，其赋值是有条件的，但这样写，state_core_next_i >= param_thr其路径会经过条件外的路径，造成不必要的延时；现直接结合到always块内的选择电路，只在time_step_event时才比较输出。
## 14. 维护规则

文档中的数字应同时注明来源文件和适用版本。参数变更提交至少包含：

- 配置差异；
- 新生成物及校验和；
- RTL 仿真结果；
- 综合时序/资源摘要；
- 上板 UART/ILA 结果；
- DDR 地址图更新；
- 本文及相关目录 README 更新。

图片统一保存在 `assets/FF-STDP加速器设计（ZYNQ）/`，Markdown 使用仓库相对路径。Vivado 系统 TB 的 `SPIKE_DATA_FILE` 属于运行环境配置，需按本机路径设置，不属于文档图片资源。

## 附录 A：关键文件速查

| 想理解/修改什么             | 首先打开                                                                |
| -------------------- | ------------------------------------------------------------------- |
| 当前网络层数和层间握手          | `user/src/snn_ff/Top_test.v`                                        |
| 单层 SNN 总结构           | `user/src/snn_ff/ODIN_ffstdp.v`                                     |
| 核内时序和状态机             | `user/src/snn_ff/controller.v`                                      |
| 事件排队                 | `user/src/snn_ff/scheduler.v`                                       |
| 神经元积分发放              | `user/src/snn_ff/neuron_core/if_neuron.v`                           |
| 在线权重更新               | `user/src/snn_ff/synaptic_core/ffstdp_update.v`                     |
| DDR burst、样本状态机      | `user/src/axi_rw/axi4_rw_test_v1_0_M_AXI.v`                         |
| 有效 AXI 顶层默认参数        | `user/src/axi_rw/axi4_rw_test_v1_0.v`                               |
| 32-bit 输入到 AER       | `user/src/axi_rw/parallel_to_serial.v`                              |
| PS/PL 连接与 SD MIO     | `user/script/system.tcl`、当前 Block Design                            |
| SD→DDR 与准确率          | `prj/snn_pl_axi_ddr/vitis/snn_test/src/main.c`                      |
| 数据与量化总配置             | `hardware_sim/hardware_sim_config.py`                               |
| 脉冲二进制生成              | `hardware_sim/gen_data_flow.py`                                     |
| 权重导出                 | `hardware_sim/gen_model_weight_coe.py`                              |
| 梯度 ROM               | `hardware_sim/gen_sigmoid.py`                                       |
| 板级约束                 | `user/data/axi4_ddr_rw.xdc`                                         |
| 存储器 FPGA/仿真双模式       | `user/src/snn_ff/sram/README.md`                                    |
| Icarus 回归入口          | `user/sim/iverilog/README.md`                                       |
| core / AXI testbench | `user/sim/tb_core_test.sv`、`user/sim/tb_axi4_rw_test_v1_0_M_AXI.sv` |

## 附录 B：一次实验的最小记录模板

```text
日期：
开发板/器件：Zynq-7010 / xc7z010clg400-1
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
