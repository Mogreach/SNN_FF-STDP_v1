# FashionMNIST 生成物

文件角色与 `../MNIST/` 相同，但数据集为 FashionMNIST。使用本目录时，令 `main.c` 的 `FILE_NAME` 与 SD 卡文件名一致，并确认 Vitis 编译的 `test_labels.h` 来自本目录。

权重、梯度 ROM、时间步、样本数量和 DDR 地址必须作为一组配置同步更新，不能与 MNIST 目录交叉混用。
