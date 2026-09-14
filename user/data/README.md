# data

Vivado 使用的人工维护数据文件。

- `axi4_ddr_rw.xdc`：当前板级按键与状态指示引脚约束，包含 `key_init`、`key_train_enable`、`train_enable_flag`、`train_finish_flag`。
- `top_test.xdc`：早期独立顶层的时钟、复位和 AER 引脚约束，未必属于当前 Block Design 顶层。
- `weights_weight.coe`：历史权重初始化文件；应与 `Gen_out/<TASK>` 中当前生成版本核对后再使用。

约束文件中的封装引脚与板卡型号强相关。切换板卡或顶层时不要同时启用相互冲突的 XDC。
