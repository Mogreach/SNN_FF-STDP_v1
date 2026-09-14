module sram_post_neuron #(
    parameter  ADDR_WIDTH = 8,
    parameter  DATA_WIDTH = 32,
    parameter  SRAM_DEPTH = 256
)

(

    // Global inputs
    input          CK,                       // Clock (synchronous read/write)

    // Control and data inputs
    input          CS,                       // Chip select
    input          WE,                       // Write enable
    input  [ADDR_WIDTH-1:0] A,                        // Address bus 
    input  [DATA_WIDTH-1:0] D,                        // Data input bus (write)

    // Data output
    output [DATA_WIDTH-1:0] Q                         // Data output bus (read)   
);
    /*
     *  Simple behavioral code for simulation, to be replaced by a 256-word 32-bit SRAM macro 
     *  or Block RAM (BRAM) memory with the same format for FPGA implementations.
     */     
        // Vivado RAM style directive
        (* ram_style = "distributed" *)
        reg [DATA_WIDTH-1:0] SRAM[0:SRAM_DEPTH-1];
        reg [DATA_WIDTH-1:0] Qr;

`ifndef SNN_RAM_SIM
        // 仅 FPGA 模式：可综合的上电初值，Vivado 会写进 LUTRAM/BRAM 的 INIT。
        // 路径必须外部传入：Vivado 解析 $readmem* 的相对路径时以综合 run 目录
        // 为基准，不是仓库根。在 Synthesis 的 Verilog Define 中设置：
        //   SNN_POST_NEUR_STATE_FILE="<post_neuron_state.txt 的绝对路径>"
`ifndef SNN_POST_NEUR_STATE_FILE
        `error "FPGA mode needs SNN_POST_NEUR_STATE_FILE; see user/src/snn_ff/sram/README.md"
`endif
        initial $readmemh(`SNN_POST_NEUR_STATE_FILE, SRAM);
`endif

        always @(posedge CK) begin
            Qr <= CS ? SRAM[A] : Qr;
            if (CS & WE) SRAM[A] <= D;
        end
        assign Q = Qr;


endmodule
