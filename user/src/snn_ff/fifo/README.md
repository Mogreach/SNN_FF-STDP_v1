# FIFO

- `fifo.v`：基础 FIFO 实现。
- `sync_fifo.v`：同步同宽 FIFO，用于调度事件缓存。
- `sync_fifo_diff_width.v`：同步异宽 FIFO，用于宽数据拆分/拼接场景。

这里的 FIFO 与 AXI 路径使用的 `axi_input_fifo` 不同；后者是 Vivado FIFO Generator IP，在 Block Design/IP 工程中生成。验证 FIFO 时应覆盖满、空、同时读写以及复位边界。
