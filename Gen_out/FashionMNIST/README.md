# FashionMNIST 生成物

文件角色与 `../MNIST/` 相同，但数据集为 FashionMNIST。PS 历史工程存在两个 `main.c` 副本：一个读取 `fashionmnist.bin`，另一个读取 `all_spikes.bin`。使用本目录时需确认 SD 卡文件名、Vitis 工程实际编译的源码副本以及 `test_labels.h` 来自同一数据集。

权重、梯度 ROM、时间步、样本数量和 DDR 地址必须作为一组配置同步更新，不能与 MNIST 目录交叉混用。
