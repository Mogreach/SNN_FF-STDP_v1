# Core test 构建产物

运行上一级的 `./run_core_test.sh` 后，本目录生成：

- `tb_core_test.vvp`：Icarus Verilog 仿真可执行文件；
- `tb_core_test.vcd`：完整 `tb_core_test` 与 DUT 层级波形；
- `tb_core_test.log`：仿真日志。

除本 README 外，这些生成文件均由 Git 忽略。

默认回归配置为 2 个 MNIST 样本、8 个时间步、`IS_TRAIN=0`。最近一次验证结果为两个样本均产生 `PROCESS_DONE`，脚本最终打印 `PASS`。完整层级波形约为 77 MiB，后续扩大样本数时需留意磁盘占用。
