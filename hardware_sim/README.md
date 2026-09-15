# Python 数据与量化生成

本目录把软件模型输出转换为当前 RTL、Vivado BRAM 和 Vitis 所需文件。统一配置在 `hardware_sim_config.py`：默认 MNIST、784 输入、256 输出、8 个并行后神经元、9-bit 权重、8 个时间步。

| 脚本 | 输出 |
| --- | --- |
| `gen_data_flow.py` | `all_spikes.bin`、`test_labels.h` |
| `gen_model_weight_coe.py` | `weights_weight.coe/.txt`、bank 文件 |
| `gen_neuron_state.py` | pre/post 状态 `.txt/.coe` |
| `gen_sigmoid.py` | 正负导数 COE 与 RTL ROM |

在已配置的 Python 环境中，从仓库根执行：

```bash
python hardware_sim/gen_data_flow.py
python hardware_sim/gen_model_weight_coe.py
python hardware_sim/gen_neuron_state.py
python hardware_sim/gen_sigmoid.py
```

代码依赖 PyTorch、torchvision、SpikingJelly、NumPy、bitarray、Matplotlib、Seaborn 和 tqdm。生成物固定输出至 `Gen_out/<TASK>/`；每次生成会覆盖同名文件。

生成后：将 `weights_weight.coe` 配置给 Vivado `sram_synaptic` IP，将 `all_spikes.bin` 放入 SD 卡，将 `test_labels.h` 复制到 Vitis application `src/`。检查 `weights_weight.txt` 为 25088 行、pre/post 状态分别为 784/32 行，再开始综合或上板。
