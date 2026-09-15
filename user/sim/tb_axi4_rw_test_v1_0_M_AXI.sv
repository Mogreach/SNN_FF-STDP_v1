`timescale 1ns / 1ps

module tb_axi4_rw_test_v1_0;

    // Parameters
    parameter TIME_TOTAL_STEP = 8;
    parameter DATA_SIZE = 784;
    parameter OUTPUT_NEURON = 256;
    // Smoke-test defaults: process two training samples only. Override these
    // parameters when a batch or full-dataset regression is actually needed.
    parameter TOTAL_TRAIN_SIZE = 3;
    parameter TOTAL_TEST_SIZE = 0;
    parameter STOP_AFTER_FIRST_PROCESS_DONE = 1'b0;
    parameter VCD_FILE = "build_axi_test/tb_axi4_rw_test_v1_0_M_AXI.vcd";
    parameter integer SIM_TIMEOUT_NS = 20_000_000;
    // Vivado/xsim commonly launches from a generated run directory. Set this
    // to an absolute path on the machine running the simulation.
    parameter SPIKE_DATA_FILE = "/home/mogreach/WorkSpace/Work-Local-Server/SNN_FFSTDP_version_1/Gen_out/MNIST/all_spikes.bin";
    parameter WEIGHT_DATA_FILE = "/home/mogreach/WorkSpace/Work-Local-Server/SNN_FFSTDP_version_1/Gen_out/MNIST/weights_weight.txt";
    parameter POST_NEURON_STATE_FILE = "/home/mogreach/WorkSpace/Work-Local-Server/SNN_FFSTDP_version_1/Gen_out/MNIST/post_neuron_state.txt";
    parameter PRE_NEURON_STATE_FILE = "/home/mogreach/WorkSpace/Work-Local-Server/SNN_FFSTDP_version_1/Gen_out/MNIST/pre_neuron_state.txt";
    parameter C_M_TARGET_SLAVE_WRITE_ADDR = 32'h01900000;
    parameter C_M_TARGET_SLAVE_READ_ADDR = 32'h00010000;
    parameter integer C_M_AXI_READ_BURST_LEN = 4;
    parameter integer C_M_AXI_WRITE_BURST_LEN = 1;
    parameter integer C_M_AXI_ID_WIDTH = 1;
    parameter integer C_M_AXI_ADDR_WIDTH = 32;
    parameter integer C_M_AXI_DATA_WIDTH = 32;
    parameter integer C_M_AXI_AWUSER_WIDTH = 0;
    parameter integer C_M_AXI_ARUSER_WIDTH = 0;
    parameter integer C_M_AXI_WUSER_WIDTH = 0;
    parameter integer C_M_AXI_RUSER_WIDTH = 0;
    parameter integer C_M_AXI_BUSER_WIDTH = 0;

    // Inputs (reg 类型)
    wire PROCESS_DONE;
    wire [31:0] GOODNESS;
    reg SNN_CLK;
    wire AER_IN_ACK;
    reg m_axi_init_axi_txn;
    reg train_enable_txn;
    reg m_axi_aclk;
    reg m_axi_aresetn;
    reg m_axi_awready;
    reg m_axi_wready;
    reg [C_M_AXI_ID_WIDTH-1:0] m_axi_bid;
    reg [1:0] m_axi_bresp;
    reg [C_M_AXI_BUSER_WIDTH-1:0] m_axi_buser;
    reg m_axi_bvalid;
    reg m_axi_arready;
    reg [C_M_AXI_ID_WIDTH-1:0] m_axi_rid;
    reg [C_M_AXI_DATA_WIDTH-1:0] m_axi_rdata;
    reg [1:0] m_axi_rresp;
    reg m_axi_rlast;
    reg [C_M_AXI_RUSER_WIDTH-1:0] m_axi_ruser;
    reg m_axi_rvalid;

    // Outputs (wire 类型)
    logic AER_IN_REQ;
    logic [11:0] AER_IN_ADDR;
    wire IS_POS;
    wire IS_TRAIN;
    wire [2:0] STATE;
    wire m_axi_txn_done;
    wire m_axi_error;
    wire [C_M_AXI_ID_WIDTH-1:0] m_axi_awid;
    wire [C_M_AXI_ADDR_WIDTH-1:0] m_axi_awaddr;
    wire [7:0] m_axi_awlen;
    wire [2:0] m_axi_awsize;
    wire [1:0] m_axi_awburst;
    wire m_axi_awlock;
    wire [3:0] m_axi_awcache;
    wire [2:0] m_axi_awprot;
    wire [3:0] m_axi_awqos;
    wire [C_M_AXI_AWUSER_WIDTH-1:0] m_axi_awuser;
    wire m_axi_awvalid;
    wire [C_M_AXI_DATA_WIDTH-1:0] m_axi_wdata;
    wire [C_M_AXI_DATA_WIDTH/8-1:0] m_axi_wstrb;
    wire m_axi_wlast;
    wire [C_M_AXI_WUSER_WIDTH-1:0] m_axi_wuser;
    wire m_axi_wvalid;
    wire m_axi_bready;
    wire [C_M_AXI_ID_WIDTH-1:0] m_axi_arid;
    wire [C_M_AXI_ADDR_WIDTH-1:0] m_axi_araddr;
    wire [7:0] m_axi_arlen;
    wire [2:0] m_axi_arsize;
    wire [1:0] m_axi_arburst;
    wire m_axi_arlock;
    wire [3:0] m_axi_arcache;
    wire [2:0] m_axi_arprot;
    wire [3:0] m_axi_arqos;
    wire [C_M_AXI_ARUSER_WIDTH-1:0] m_axi_aruser;
    wire m_axi_arvalid;
    wire m_axi_rready;
axi4_rw_test_v1_0#(
   .TIME_TOTAL_STEP(TIME_TOTAL_STEP),
   .DATA_SIZE(DATA_SIZE),
   .TOTAL_TRAIN_SIZE(TOTAL_TRAIN_SIZE),
   .TOTAL_TEST_SIZE(TOTAL_TEST_SIZE),
   .C_M_TARGET_SLAVE_WRITE_ADDR(C_M_TARGET_SLAVE_WRITE_ADDR),
   .C_M_TARGET_SLAVE_READ_ADDR(C_M_TARGET_SLAVE_READ_ADDR)
)
 u_axi4_rw_test_v1_0(
// Users to add parameters here
// User parameters ends
// Do not modify the parameters beyond this line
// Parameters of Axi Master Bus Interface M_AXI
// Users to add ports here
    .PROCESS_DONE                       (PROCESS_DONE              ),
    .GOODNESS                           (GOODNESS                  ),
    .SNN_CLK                            (SNN_CLK                   ),
    .AER_IN_ACK                         (AER_IN_ACK                ),
    .AER_IN_REQ                         (AER_IN_REQ                ),
    .AER_IN_ADDR                        (AER_IN_ADDR               ),
    .IS_POS                             (IS_POS                    ),
    .IS_TRAIN                           (IS_TRAIN                  ),
// Debug
    .STATE                              (STATE                     ),
// User ports ends
// Do not modify the ports beyond this line
// Ports of Axi Master Bus Interface M_AXI
    .m_axi_init_axi_txn                 (m_axi_init_axi_txn        ),
    .train_enable_txn                   (train_enable_txn          ),
    .TRAIN_ENABLE_FLAG                  (m_axi_txn_done            ),
    .TRAIN_FINISH_FLAG                  (m_axi_error               ),
    .m_axi_aclk                         (m_axi_aclk                ),
    .m_axi_aresetn                      (m_axi_aresetn             ),
    .m_axi_awid                         (m_axi_awid                ),
    .m_axi_awaddr                       (m_axi_awaddr              ),
    .m_axi_awlen                        (m_axi_awlen               ),
    .m_axi_awsize                       (m_axi_awsize              ),
    .m_axi_awburst                      (m_axi_awburst             ),
    .m_axi_awlock                       (m_axi_awlock              ),
    .m_axi_awcache                      (m_axi_awcache             ),
    .m_axi_awprot                       (m_axi_awprot              ),
    .m_axi_awqos                        (m_axi_awqos               ),
    .m_axi_awuser                       (m_axi_awuser              ),
    .m_axi_awvalid                      (m_axi_awvalid             ),
    .m_axi_awready                      (m_axi_awready             ),
    .m_axi_wdata                        (m_axi_wdata               ),
    .m_axi_wstrb                        (m_axi_wstrb               ),
    .m_axi_wlast                        (m_axi_wlast               ),
    .m_axi_wuser                        (m_axi_wuser               ),
    .m_axi_wvalid                       (m_axi_wvalid              ),
    .m_axi_wready                       (m_axi_wready              ),
    .m_axi_bid                          (m_axi_bid                 ),
    .m_axi_bresp                        (m_axi_bresp               ),
    .m_axi_buser                        (m_axi_buser               ),
    .m_axi_bvalid                       (m_axi_bvalid              ),
    .m_axi_bready                       (m_axi_bready              ),
    .m_axi_arid                         (m_axi_arid                ),
    .m_axi_araddr                       (m_axi_araddr              ),
    .m_axi_arlen                        (m_axi_arlen               ),
    .m_axi_arsize                       (m_axi_arsize              ),
    .m_axi_arburst                      (m_axi_arburst             ),
    .m_axi_arlock                       (m_axi_arlock              ),
    .m_axi_arcache                      (m_axi_arcache             ),
    .m_axi_arprot                       (m_axi_arprot              ),
    .m_axi_arqos                        (m_axi_arqos               ),
    .m_axi_aruser                       (m_axi_aruser              ),
    .m_axi_arvalid                      (m_axi_arvalid             ),
    .m_axi_arready                      (m_axi_arready             ),
    .m_axi_rid                          (m_axi_rid                 ),
    .m_axi_rdata                        (m_axi_rdata               ),
    .m_axi_rresp                        (m_axi_rresp               ),
    .m_axi_rlast                        (m_axi_rlast               ),
    .m_axi_ruser                        (m_axi_ruser               ),
    .m_axi_rvalid                       (m_axi_rvalid              ),
    .m_axi_rready                       (m_axi_rready              )
);

Top_test #(
    .TIME_STEP(TIME_TOTAL_STEP),
    .INPUT_NEURON(DATA_SIZE),
    .OUTPUT_NEURON(OUTPUT_NEURON)
) u_Top_test(
    .CLK                                (SNN_CLK                       ),
    .RST                                (!m_axi_aresetn                   ),
    .AERIN_ADDR                         (AER_IN_ADDR                ),
    .AERIN_REQ                          (AER_IN_REQ                 ),
    .IS_POS                             (IS_POS                    ),
    .IS_TRAIN                           (IS_TRAIN                ),
    .AERIN_ACK                          (AER_IN_ACK                 ),
    .GOODNESS                           (GOODNESS                  ),
    .PROCESS_DONE                       (PROCESS_DONE              )
);


    // 时钟产生
    always #5 m_axi_aclk = ~m_axi_aclk;
    
localparam int TOTAL_SAMPLE_COUNT = TOTAL_TRAIN_SIZE + TOTAL_TEST_SIZE;
localparam int RAM_DEPTH_BYTES =
    (TOTAL_SAMPLE_COUNT * TIME_TOTAL_STEP * DATA_SIZE) / 8;
integer file;
integer bytes_read;
bit [7:0] ram [0:RAM_DEPTH_BYTES-1];
bit [31:0] rd_burst_data [0:3];
integer i, block_index = 0;
integer aer_event_count = 0;
integer tstep_event_count = 0;
integer completed_sample_count = 0;
integer pre_ram_init_index;
integer post_ram_init_index;

    initial begin
        $dumpfile(VCD_FILE);
        // Keep the VCD focused: top-level AXI/AER signals plus the two control
        // FSMs. Dumping every SRAM word makes a full-size run unnecessarily huge.
        $dumpvars(0,
            m_axi_aclk, SNN_CLK, m_axi_aresetn, m_axi_init_axi_txn,
            train_enable_txn, STATE, IS_POS, IS_TRAIN,
            AER_IN_ADDR, AER_IN_REQ, AER_IN_ACK,
            PROCESS_DONE, GOODNESS,
            m_axi_araddr, m_axi_arlen, m_axi_arvalid, m_axi_arready,
            m_axi_rdata, m_axi_rvalid, m_axi_rready, m_axi_rlast,
            m_axi_awaddr, m_axi_awvalid, m_axi_awready,
            m_axi_wdata, m_axi_wvalid, m_axi_wready, m_axi_wlast,
            m_axi_bvalid, m_axi_bready,
            aer_event_count, tstep_event_count, completed_sample_count);
        $dumpvars(0,
            u_axi4_rw_test_v1_0.axi4_rw_test_v1_0_M_AXI_inst.mst_exec_state,
            u_axi4_rw_test_v1_0.axi4_rw_test_v1_0_M_AXI_inst.sample_count,
            u_axi4_rw_test_v1_0.axi4_rw_test_v1_0_M_AXI_inst.read_burst_counter,
            u_axi4_rw_test_v1_0.axi4_rw_test_v1_0_M_AXI_inst.write_burst_counter,
            u_axi4_rw_test_v1_0.axi4_rw_test_v1_0_M_AXI_inst.input_fifo_full,
            u_axi4_rw_test_v1_0.axi4_rw_test_v1_0_M_AXI_inst.input_fifo_empty,
            u_axi4_rw_test_v1_0.axi4_rw_test_v1_0_M_AXI_inst.input_fifo_rd_en,
            u_axi4_rw_test_v1_0.axi4_rw_test_v1_0_M_AXI_inst.spike_data_vaild,
            u_axi4_rw_test_v1_0.axi4_rw_test_v1_0_M_AXI_inst.u_parallel_to_serial.cnt,
            u_axi4_rw_test_v1_0.axi4_rw_test_v1_0_M_AXI_inst.u_parallel_to_serial.tstep_cnt,
            u_axi4_rw_test_v1_0.axi4_rw_test_v1_0_M_AXI_inst.u_parallel_to_serial.tstep_valid,
            u_Top_test.u_ODIN_ffstdp.controller_inst.state,
            u_Top_test.u_ODIN_ffstdp.controller_inst.T_step_cnt,
            u_Top_test.u_ODIN_ffstdp.controller_inst.post_neur_cnt,
            u_Top_test.u_ODIN_ffstdp.controller_inst.pre_neur_cnt,
            u_Top_test.u_ODIN_ffstdp.controller_inst.pre_neur_cnt_inc,
            u_Top_test.u_ODIN_ffstdp.controller_inst.CTRL_NEUR_EVENT,
            u_Top_test.u_ODIN_ffstdp.controller_inst.CTRL_TSTEP_EVENT,
            u_Top_test.u_ODIN_ffstdp.controller_inst.CTRL_TREF_EVENT,
            u_Top_test.u_ODIN_ffstdp.controller_inst.tref_finish,
            u_Top_test.AEROUT_ADDR, u_Top_test.AEROUT_REQ,
            u_Top_test.AEROUT_ACK,
            u_Top_test.u_ODIN_ffstdp.AEROUT_CTRL_FINISH,
            u_Top_test.u_ODIN_ffstdp.u_aer_out.fifo_empty,
            u_Top_test.u_ODIN_ffstdp.u_aer_out.fifo_full,
            u_Top_test.u_ODIN_ffstdp.u_aer_out.fifo_rd_en,
            u_Top_test.u_ODIN_ffstdp.u_aer_out.fifo_wr_en,
            u_Top_test.u_ODIN_ffstdp.u_aer_out.aer_out_start,
            u_Top_test.u_ODIN_ffstdp.u_aer_out.aer_out_fifo_dout,
            u_Top_test.u_ODIN_ffstdp.u_aer_out.AEROUT_ACK_sync,
            u_Top_test.u_ODIN_ffstdp.u_aer_out.AEROUT_ACK_sync_del,
            u_Top_test.u_ODIN_ffstdp.u_aer_out.aer_out_trans,
            u_Top_test.u_ODIN_ffstdp.u_aer_out.syncFIFO_diffWidth_u0.wdata_empty,
            u_Top_test.u_ODIN_ffstdp.u_aer_out.syncFIFO_diffWidth_u0.rdata_full,
            u_Top_test.u_ODIN_ffstdp.u_aer_out.syncFIFO_diffWidth_u0.rdata_wr_en,
            u_Top_test.u_ODIN_ffstdp.u_aer_out.syncFIFO_diffWidth_u0.wdata_rd_en);
    end

    initial begin
        #(SIM_TIMEOUT_NS);
        $fatal(1,
            "Simulation timeout: completed=%0d AXI_STATE=%03b AER_REQ=%b AER_ACK=%b",
            completed_sample_count, STATE, AER_IN_REQ, AER_IN_ACK);
    end

    always @(posedge SNN_CLK) begin
        // Empty FIFO data is intentionally clamped to zero by scheduler.v.
        // Once non-empty, every entry must have been written by a valid AER
        // event before the controller may consume it.
        if (m_axi_aresetn &&
            !u_Top_test.u_ODIN_ffstdp.SCHED_EMPTY &&
            $isunknown(u_Top_test.u_ODIN_ffstdp.SCHED_DATA_OUT)) begin
            $fatal(1, "Unknown scheduler FIFO output: empty=%b read_ptr=%0d write_ptr=%0d data=%h at %0t",
                u_Top_test.u_ODIN_ffstdp.SCHED_EMPTY,
                u_Top_test.u_ODIN_ffstdp.scheduler_inst.fifo_spike_0.read_ptr,
                u_Top_test.u_ODIN_ffstdp.scheduler_inst.fifo_spike_0.write_ptr,
                u_Top_test.u_ODIN_ffstdp.SCHED_DATA_OUT, $time);
        end
        if (m_axi_aresetn &&
            u_Top_test.u_ODIN_ffstdp.controller_inst.CTRL_PRE_NEUR_WE &&
            ($isunknown(u_Top_test.u_ODIN_ffstdp.controller_inst.CTRL_PRE_NEURON_ADDRESS) ||
             $isunknown(u_Top_test.u_ODIN_ffstdp.neuron_core_inst.pre_neuron_sram_in))) begin
            $fatal(1, "Unknown pre-neuron write: ctrl_state=%b addr=%0d pre_q=%h pre_d=%h event=%b tref=%b at %0t",
                u_Top_test.u_ODIN_ffstdp.controller_inst.state,
                u_Top_test.u_ODIN_ffstdp.controller_inst.CTRL_PRE_NEURON_ADDRESS,
                u_Top_test.u_ODIN_ffstdp.neuron_core_inst.pre_neuron_sram_out,
                u_Top_test.u_ODIN_ffstdp.neuron_core_inst.pre_neuron_sram_in,
                u_Top_test.u_ODIN_ffstdp.CTRL_NEUR_EVENT,
                u_Top_test.u_ODIN_ffstdp.CTRL_TREF_EVENT, $time);
        end
        if (m_axi_aresetn &&
            u_Top_test.u_ODIN_ffstdp.controller_inst.CTRL_POST_NEUR_WE &&
            $isunknown(u_Top_test.u_ODIN_ffstdp.neuron_core_inst.post_neuron_sram_in)) begin
            $fatal(1, "Unknown post-neuron write: ctrl_state=%b addr=%0d post_q=%h post_d=%h syn_q=%h at %0t",
                u_Top_test.u_ODIN_ffstdp.controller_inst.state,
                u_Top_test.u_ODIN_ffstdp.controller_inst.CTRL_POST_NEURON_ADDRESS,
                u_Top_test.u_ODIN_ffstdp.neuron_core_inst.post_neuron_sram_out,
                u_Top_test.u_ODIN_ffstdp.neuron_core_inst.post_neuron_sram_in,
                u_Top_test.u_ODIN_ffstdp.SYNARRAY_RDATA, $time);
        end
        if (m_axi_aresetn &&
            u_Top_test.u_ODIN_ffstdp.u_aer_out.fifo_wr_en &&
            $isunknown(u_Top_test.u_ODIN_ffstdp.u_aer_out.aer_out_fifo_din)) begin
            $fatal(1, "Unknown AER FIFO input: addr=%0d events=%b post_q=%h post_d=%h syn_q=%h at %0t",
                u_Top_test.u_ODIN_ffstdp.controller_inst.CTRL_POST_NEURON_ADDRESS,
                u_Top_test.u_ODIN_ffstdp.NEUR_EVENT_OUT,
                u_Top_test.u_ODIN_ffstdp.neuron_core_inst.post_neuron_sram_out,
                u_Top_test.u_ODIN_ffstdp.neuron_core_inst.post_neuron_sram_in,
                u_Top_test.u_ODIN_ffstdp.SYNARRAY_RDATA, $time);
        end
        if (AER_IN_REQ && AER_IN_ACK) begin
            aer_event_count <= aer_event_count + 1;
            if (AER_IN_ADDR[11:10] == 2'b01) begin
                tstep_event_count <= tstep_event_count + 1;
                $display("Accepted timestep event %0d/%0d at %0t",
                         tstep_event_count + 1, TIME_TOTAL_STEP, $time);
            end
        end
        if (PROCESS_DONE) begin
            completed_sample_count <= completed_sample_count + 1;
            $display("SNN sample %0d complete: events=%0d timesteps=%0d goodness=%0d at %0t",
                     completed_sample_count + 1, aer_event_count,
                     tstep_event_count, GOODNESS, $time);
            aer_event_count <= 0;
            tstep_event_count <= 0;
            if (STOP_AFTER_FIRST_PROCESS_DONE) begin
                $display("PASS: observed the first PROCESS_DONE; ending smoke test.");
                $finish;
            end
        end
    end

    initial begin
        file = $fopen(SPIKE_DATA_FILE, "rb");
        if (file == 0)
            $fatal(1, "Cannot open spike data file: %s", SPIKE_DATA_FILE);
        bytes_read = $fread(ram, file);
        $fclose(file);
        if (bytes_read < RAM_DEPTH_BYTES)
            $fatal(1, "Spike data is too short: got %0d bytes, need %0d bytes",
                   bytes_read, RAM_DEPTH_BYTES);

        // 打印部分数据用于�?�?
        for (i = 0; i < 16; i = i + 1) begin
            $display("RAM[%0d] = %h", i, ram[i]);
        end

        $display("Loaded %0d spike bytes from %s", bytes_read, SPIKE_DATA_FILE);
    end

    // Neuron RAM is self-written in both modes. The weight model exposes its
    // internal SRAM array only in SNN_RAM_SIM; FPGA mode uses the IP COE file.
    initial begin
        #1;
`ifdef SNN_RAM_SIM
        $readmemb(WEIGHT_DATA_FILE,
            u_Top_test.u_ODIN_ffstdp.u_synaptic_core.u_sram_synaptic.SRAM,
            0, DATA_SIZE * OUTPUT_NEURON / u_Top_test.POST_NEUR_PARALLEL - 1);
`endif
        $readmemh(POST_NEURON_STATE_FILE,
            u_Top_test.u_ODIN_ffstdp.neuron_core_inst.neurarray_post.SRAM,
            0, OUTPUT_NEURON / u_Top_test.POST_NEUR_PARALLEL - 1);
        $readmemh(PRE_NEURON_STATE_FILE,
            u_Top_test.u_ODIN_ffstdp.neuron_core_inst.neurarray_pre.SRAM,
            0, DATA_SIZE - 1);

        // Check the storage arrays themselves.  Do not check Qr/Q here: both
        // neuron RAMs have synchronous read ports, so Qr legitimately remains
        // X until the first clock edge with CS asserted.
        for (pre_ram_init_index = 0;
             pre_ram_init_index < DATA_SIZE;
             pre_ram_init_index = pre_ram_init_index + 1) begin
            if ($isunknown(u_Top_test.u_ODIN_ffstdp.neuron_core_inst
                           .neurarray_pre.SRAM[pre_ram_init_index]))
                $fatal(1, "Pre-neuron RAM initialization failed: file=%s addr=%0d value=%h",
                       PRE_NEURON_STATE_FILE, pre_ram_init_index,
                       u_Top_test.u_ODIN_ffstdp.neuron_core_inst
                       .neurarray_pre.SRAM[pre_ram_init_index]);
        end
        for (post_ram_init_index = 0;
             post_ram_init_index < OUTPUT_NEURON / u_Top_test.POST_NEUR_PARALLEL;
             post_ram_init_index = post_ram_init_index + 1) begin
            if ($isunknown(u_Top_test.u_ODIN_ffstdp.neuron_core_inst
                           .neurarray_post.SRAM[post_ram_init_index]))
                $fatal(1, "Post-neuron RAM initialization failed: file=%s addr=%0d value=%h",
                       POST_NEURON_STATE_FILE, post_ram_init_index,
                       u_Top_test.u_ODIN_ffstdp.neuron_core_inst
                       .neurarray_post.SRAM[post_ram_init_index]);
        end
        $display("Loaded neuron state files.");
    end

  
    // always@(posedge m_axi_aclk) begin
    //     if (cnt == 'd784)
    //         cnt <= 0;
    //     else if(AER_IN_REQ && AER_IN_ACK)
    //         cnt <= cnt + 1;
    //     else
    //         cnt <= cnt;
    // end

    // 声明数据存储
    // logic [C_M_AXI_DATA_WIDTH-1:0] write_data[4] = '{32'hDEADBEEF, 32'h12345678, 32'h87654321, 32'hCAFEBABE};
    // logic [C_M_AXI_DATA_WIDTH-1:0] read_data[4];

    // // 写入 AXI（地�? 0x1000，突发长�? 4�?
    // axi_write_task(32'h00001000, write_data, 4);

    // // 读取 AXI（地�? 0x1000，突发长�? 4�?
    // axi_read_task(32'h00001000, 4, read_data);
    initial begin
    //   SNN_CLK = 0;
    //   #2;
      SNN_CLK = 1;
      forever
        #5 SNN_CLK = ~SNN_CLK;
    end
    always @(posedge m_axi_aclk) begin
        if(m_axi_wvalid && m_axi_wready && m_axi_wlast) begin
            m_axi_bvalid <= 1;
            m_axi_bresp  <= 2'b00;
        end
        else if(m_axi_bready)begin
            m_axi_bvalid <= 0;
        end
        else begin
            m_axi_bvalid <= m_axi_bvalid;
        end
    end
    // 测试过程
    initial begin
        // 初始化信�?
        m_axi_aclk = 1;
        m_axi_init_axi_txn = 0;
        train_enable_txn = 0;
        m_axi_aresetn = 0;
        m_axi_awready = 1;
        m_axi_wready = 1;
        m_axi_bid = 0;
        m_axi_bresp = 0;
        m_axi_buser = 0;
        m_axi_bvalid = 0;
        m_axi_arready = 1;
        m_axi_rid = 0;
        m_axi_rdata = 0;
        m_axi_rresp = 0;
        m_axi_rlast = 0;
        m_axi_ruser = 0;
        m_axi_rvalid = 0;
        // 复位
        #10 m_axi_aresetn = 1;
        // 生成写事�?

        // 生成读事�?
        // fork
        //     axi_slave_read_response();
        // join_none

        // Enable online learning, then start the AXI transfer FSM.
        #50 train_enable_txn = 1;
        #10 train_enable_txn = 0;
        #140 m_axi_init_axi_txn = 1;
        #10 m_axi_init_axi_txn = 0;

        // 进行AXI读写操作测试
        // #50 m_axi_awready = 1;
        // #50 m_axi_wready = 1;
        // #50 m_axi_bvalid = 1;
        // #50 m_axi_arready = 1;
        // #50 m_axi_rvalid = 1; m_axi_rdata = 32'h12345678;
        
        wait (STATE != 3'b000);
        while(STATE != 3'b000) begin
          while(STATE != 3'b011) begin
                if ((block_index * 16 + 15) >= RAM_DEPTH_BYTES)
                    $fatal(1, "AXI model read past spike buffer at block %0d", block_index);
                for (i = 0; i < 4; i = i + 1) begin
                // 按大端模式拼�? 32 位数�?
                rd_burst_data[i] = {ram[block_index * 16 + i * 4+3], 
                               ram[block_index * 16 + i * 4 + 2], 
                               ram[block_index * 16 + i * 4 + 1], 
                               ram[block_index * 16 + i * 4]};
                end
                block_index++;
                axi_slave_read_response();
                @(posedge m_axi_aclk);
                #1; // sample STATE after DUT nonblocking assignments settle
           end
            // Do not spin in zero simulation time while the SNN processes the
            // sample. The write response is handled by the clocked model above.
            wait (STATE != 3'b011);
            wait ((STATE == 3'b001) || (STATE == 3'b000));
        end


        #100;
        $display("PASS: completed %0d samples and their AXI write responses.",
                 completed_sample_count);
        $finish;
    end
// ---------------- AXI 从机（Slave�? 写响�? TASK ----------------
// task axi_slave_write_response();
//     int i;
    
//     // 1. 等待写地�?有效
//     wait (m_axi_awvalid);
//     @(posedge m_axi_aclk) m_axi_awready <= 1; // 发�?�写地址握手信号
//     @(posedge m_axi_aclk) m_axi_awready <= 0; // 释放握手信号

//     // 2. 等待写数�?
//     for (i = 0; i < m_axi_awlen + 1; i++) begin  // `awlen` �? 0-based 计数
//         wait (m_axi_wvalid);
//         @(posedge m_axi_aclk) m_axi_wready <= 1; // 允许写数�?
//         @(posedge m_axi_aclk) m_axi_wready <= 0;
//     end

//     // 3. 发�?�写响应
//     @(posedge m_axi_aclk) 
//     begin
//         m_axi_bvalid <= 1;
//         m_axi_bresp  <= 2'b00; // OKAY
//     end
//     // 等待主机 `bready` 信号
//     wait (m_axi_bready);
//     @(posedge m_axi_aclk) m_axi_bvalid <= 0; // 清除 `bvalid`
// endtask


// ---------------- AXI 从机（Slave�? 读响�? TASK ----------------
task axi_slave_read_response;
    int i;
    
    // 1. 等待主机发�?�读地址
    wait (m_axi_arvalid);
    @(posedge m_axi_aclk);
    #1;
    // m_axi_arready = 1;
    // @(posedge m_axi_aclk);
    // m_axi_arready = 0;

    // 2. 发�?�读数据
    for (i = 0; i <= m_axi_arlen; i++) begin
        // @(posedge m_axi_aclk);
        m_axi_rvalid = 1;
        m_axi_rdata  = rd_burst_data[i];
        m_axi_rlast  = (i == m_axi_arlen) ? 1 : 0;
        wait (m_axi_rready);
        @(posedge m_axi_aclk);
        #1;
        m_axi_rvalid = 0;
        m_axi_rlast = 0;
    end
endtask
task wait_ns;
  input   tics_ns;
  integer tics_ns;
  #tics_ns;
endtask
endmodule
