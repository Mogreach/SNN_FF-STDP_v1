`timescale 1ns / 1ps

// Icarus-only behavioral replacement for the Vivado FIFO Generator instance:
//   input  32 bit x 512 words
//   output  4 bit x 4096 words
// The checked-in XCI selects Common_Clock, which matches the current BD and TB.
module axi_input_fifo (
    input  wire        rst,
    input  wire        wr_clk,
    input  wire        rd_clk,
    input  wire [31:0] din,
    input  wire        wr_en,
    input  wire        rd_en,
    output reg  [3:0]  dout,
    output wire        full,
    output wire        empty,
    output wire        wr_rst_busy,
    output wire        rd_rst_busy
);
    localparam integer OUTPUT_DEPTH = 4096;

    reg [3:0] memory [0:OUTPUT_DEPTH-1];
    reg [11:0] write_pointer;
    reg [11:0] read_pointer;
    reg [12:0] stored_nibbles;
    integer lane;

    wire write_accepted = wr_en && !full;
    wire read_accepted = rd_en && !empty;

    assign full = (stored_nibbles > OUTPUT_DEPTH-8);
    assign empty = (stored_nibbles == 0);
    assign wr_rst_busy = 1'b0;
    assign rd_rst_busy = 1'b0;

    // rd_clk and wr_clk are the same clock in this project's BD and testbench.
    // The least-significant nibble is emitted first, matching FIFO Generator's
    // asymmetric-width ordering used by parallel_to_serial.
    always @(posedge wr_clk or posedge rst) begin
        if (rst) begin
            write_pointer <= 0;
            read_pointer <= 0;
            stored_nibbles <= 0;
            dout <= 0;
        end else begin
            if (write_accepted) begin
                for (lane = 0; lane < 8; lane = lane + 1)
                    memory[write_pointer + lane] <= din[lane*4 +: 4];
                write_pointer <= write_pointer + 8;
            end

            if (read_accepted) begin
                dout <= memory[read_pointer];
                read_pointer <= read_pointer + 1'b1;
            end

            case ({write_accepted, read_accepted})
                2'b10: stored_nibbles <= stored_nibbles + 8;
                2'b01: stored_nibbles <= stored_nibbles - 1'b1;
                2'b11: stored_nibbles <= stored_nibbles + 7;
                default: stored_nibbles <= stored_nibbles;
            endcase
        end
    end

    // Reference the second clock so lint does not treat it as an accidental
    // unused port; functional behavior intentionally follows common-clock mode.
    wire unused_rd_clk = rd_clk;
endmodule
