
 module scheduler #(
    parameter TIME_STEP = 8,
    parameter INPUT_NEURON = 784,
    parameter OUTPUT_NEURON = 256,
    parameter AER_WIDTH = 12,

    parameter PRE_NEUR_ADDR_WIDTH = 10,
    parameter PRE_NEUR_WORD_ADDR_WIDTH= 10,
    parameter PRE_NEUR_BYTE_ADDR_WIDTH = 0,

    parameter POST_NEUR_ADDR_WIDTH = 10,
    parameter POST_NEUR_WORD_ADDR_WIDTH= 8,
    parameter POST_NEUR_BYTE_ADDR_WIDTH = 2,
    parameter POST_NEUR_PARALLEL = 4,
    
    parameter PRE_NEUR_DATA_WIDTH = 8,
    parameter POST_NEUR_DATA_WIDTH = 32,
    parameter POST_NEUR_MEM_WIDTH = 12,
    parameter POST_NEUR_SPIKE_CNT_WIDTH = 7,
    parameter SYN_ARRAY_DATA_WIDTH = 32,
    parameter SYN_ARRAY_ADDR_WIDTH = 16,
    parameter WEIGHT_WIDTH = 8
)( 

    // Global inputs ------------------------------------------
    input  wire                 CLK,
    input  wire                 RSTN,
    
    // Inputs from controller ---------------------------------
    input  wire                 CTRL_SCHED_POP_N,
    input  wire [          1:0] CTRL_SCHED_VIRTS,
    input  wire [PRE_NEUR_ADDR_WIDTH-1:0] CTRL_SCHED_ADDR,
    input  wire                 CTRL_SCHED_EVENT_IN,
    
    // Outputs ------------------------------------------------
    output wire                 SCHED_EMPTY,
    output wire                 SCHED_FULL,
    output wire [AER_WIDTH-1:0] SCHED_DATA_OUT
);

    wire                   push_req_n;

    wire                   empty_main;
    wire                   full_main;
    wire [AER_WIDTH-1:0] data_out_main;


    // FIFO instances

    fifo #(
        .width(AER_WIDTH),
        .depth(128),
        .depth_addr(7)
    ) fifo_spike_0 (
        .clk(CLK),
        .rst_n(RSTN),
        .push_req_n(full_main | push_req_n),
        .pop_req_n(empty_main | CTRL_SCHED_POP_N),
        .data_in({CTRL_SCHED_VIRTS,CTRL_SCHED_ADDR}),// 外部神经元事件 or 
        .empty(empty_main),
        .full(full_main),
        .data_out(data_out_main)
    );

    assign push_req_n = ~(CTRL_SCHED_EVENT_IN);


    // Output definition

    assign SCHED_DATA_OUT = data_out_main;
    assign SCHED_EMPTY    = empty_main;
    assign SCHED_FULL     = full_main;



endmodule
