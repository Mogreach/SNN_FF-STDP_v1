`timescale 1ns / 1ps

// Direct SNN-core regression: no AXI master or input FIFO is involved.
// Two MNIST samples are injected through the AER input handshake while
// online learning is disabled (IS_TRAIN=0).
module tb_core_test;
    parameter integer CLK_PERIOD_NS = 4;
    parameter integer SAMPLE_COUNT = 2;
    parameter integer TIME_STEPS = 8;
    parameter integer INPUT_NEURONS = 784;
    parameter integer OUTPUT_NEURONS = 256;
    parameter integer SIM_TIMEOUT_NS = 5_000_000;

    // These absolute paths must be changed when the repository is moved.
    parameter SPIKE_DATA_FILE = "/home/mogreach/WorkSpace/Work-Local-Server/SNN_FFSTDP_version_1/Gen_out/MNIST/all_spikes.bin";
    parameter WEIGHT_DATA_FILE = "/home/mogreach/WorkSpace/Work-Local-Server/SNN_FFSTDP_version_1/Gen_out/MNIST/weights_weight.txt";
    parameter POST_NEURON_STATE_FILE = "/home/mogreach/WorkSpace/Work-Local-Server/SNN_FFSTDP_version_1/Gen_out/MNIST/post_neuron_state.txt";
    parameter PRE_NEURON_STATE_FILE = "/home/mogreach/WorkSpace/Work-Local-Server/SNN_FFSTDP_version_1/Gen_out/MNIST/pre_neuron_state.txt";
    parameter VCD_FILE = "build_core_test/tb_core_test.vcd";

    localparam integer SPIKE_BYTES_PER_SAMPLE = TIME_STEPS * INPUT_NEURONS / 8;
    localparam integer SPIKE_BYTE_COUNT = SAMPLE_COUNT * SPIKE_BYTES_PER_SAMPLE;

    logic CLK;
    logic RST;
    logic IS_POS;
    logic IS_TRAIN;
    logic [11:0] AERIN_ADDR;
    logic AERIN_REQ;
    wire AERIN_ACK;
    wire [31:0] GOODNESS;
    wire PROCESS_DONE;

    // Top_test internally acknowledges its AER output. These aliases are
    // observation-only signals for waveforms and counters.
    wire [11:0] AEROUT_ADDR = dut.AEROUT_ADDR;
    wire AEROUT_REQ = dut.AEROUT_REQ;
    wire AEROUT_ACK = dut.AEROUT_ACK;

    bit [7:0] spike_bytes [0:SPIKE_BYTE_COUNT-1];
    integer spike_file;
    integer bytes_read;
    integer completed_samples;
    integer input_events_this_sample;
    integer output_spikes_this_sample;
    integer accepted_tsteps_this_sample;
    logic AEROUT_REQ_d;

    Top_test #(
        .TIME_STEP    (TIME_STEPS),
        .INPUT_NEURON (INPUT_NEURONS),
        .OUTPUT_NEURON(OUTPUT_NEURONS)
    ) dut (
        .CLK         (CLK),
        .RST         (RST),
        .AERIN_ADDR  (AERIN_ADDR),
        .AERIN_REQ   (AERIN_REQ),
        .IS_POS      (IS_POS),
        .IS_TRAIN    (IS_TRAIN),
        .AERIN_ACK   (AERIN_ACK),
        .GOODNESS    (GOODNESS),
        .PROCESS_DONE(PROCESS_DONE)
    );

    initial begin
        CLK = 1'b0;
        forever #(CLK_PERIOD_NS / 2) CLK = ~CLK;
    end

    // Dump the complete testbench/DUT hierarchy for debugging, including the
    // controller, neuron/synapse cores, FIFOs, and behavioral SRAM contents.
    initial begin
        $dumpfile(VCD_FILE);
        $dumpvars(0, tb_core_test);
    end

    initial begin
        #(SIM_TIMEOUT_NS);
        $fatal(1,
            "Simulation timeout: completed=%0d AERIN_REQ=%b AERIN_ACK=%b controller_state=%b",
            completed_samples, AERIN_REQ, AERIN_ACK,
            dut.u_ODIN_ffstdp.controller_inst.state);
    end

    // Load only the two requested samples. Pixel zero is stored in bit 7 of
    // each source byte, matching the layout used by the original core TB.
    initial begin
        spike_file = $fopen(SPIKE_DATA_FILE, "rb");
        if (spike_file == 0)
            $fatal(1, "Cannot open spike file: %s", SPIKE_DATA_FILE);
        bytes_read = $fread(spike_bytes, spike_file);
        $fclose(spike_file);
        if (bytes_read < SPIKE_BYTE_COUNT)
            $fatal(1, "Spike file too short: got %0d bytes, need %0d",
                   bytes_read, SPIKE_BYTE_COUNT);
        $display("Loaded %0d spike bytes for %0d samples.",
                 bytes_read, SAMPLE_COUNT);
    end

    // Replace the behavioral SRAM models' random power-up values with the
    // generated MNIST initialization files after their initial blocks finish.
    initial begin
        #1;
        $readmemb(WEIGHT_DATA_FILE,
            dut.u_ODIN_ffstdp.u_synaptic_core.u_sram_synaptic.SRAM,
            0, INPUT_NEURONS * OUTPUT_NEURONS / dut.POST_NEUR_PARALLEL - 1);
        $readmemh(POST_NEURON_STATE_FILE,
            dut.u_ODIN_ffstdp.neuron_core_inst.neurarray_post.SRAM,
            0, OUTPUT_NEURONS / dut.POST_NEUR_PARALLEL - 1);
        $readmemh(PRE_NEURON_STATE_FILE,
            dut.u_ODIN_ffstdp.neuron_core_inst.neurarray_pre.SRAM,
            0, INPUT_NEURONS - 1);
        $display("Loaded SNN weights and neuron states.");
    end

    always @(posedge CLK) begin
        if (!RST && AERIN_REQ && AERIN_ACK) begin
            if (AERIN_ADDR[11:10] == 2'b01)
                accepted_tsteps_this_sample <= accepted_tsteps_this_sample + 1;
            else if (AERIN_ADDR[11:10] == 2'b00)
                input_events_this_sample <= input_events_this_sample + 1;
        end

        AEROUT_REQ_d <= AEROUT_REQ;
        if (!RST && AEROUT_REQ && !AEROUT_REQ_d && AEROUT_ADDR[11:10] == 2'b00)
            output_spikes_this_sample <= output_spikes_this_sample + 1;

        if (!RST && PROCESS_DONE) begin
            completed_samples <= completed_samples + 1;
            $display(
                "SNN sample %0d complete: input_events=%0d timesteps=%0d output_spikes=%0d goodness=%0d at %0t",
                completed_samples + 1, input_events_this_sample,
                accepted_tsteps_this_sample, output_spikes_this_sample,
                GOODNESS, $time);
            input_events_this_sample <= 0;
            accepted_tsteps_this_sample <= 0;
            output_spikes_this_sample <= 0;
        end

        if (!RST && dut.u_ODIN_ffstdp.controller_inst.CTRL_POST_NEUR_WE &&
            $isunknown(dut.u_ODIN_ffstdp.neuron_core_inst.post_neuron_sram_in))
            $fatal(1, "Unknown value in post-neuron write at %0t", $time);

        if (!RST && dut.u_ODIN_ffstdp.u_aer_out.fifo_wr_en &&
            $isunknown(dut.u_ODIN_ffstdp.u_aer_out.aer_out_fifo_din))
            $fatal(1, "Unknown value in AER output FIFO write at %0t", $time);
    end

    initial begin : stimulus
        integer sample_index;
        integer time_index;
        integer pixel_index;
        integer flat_bit_index;
        integer byte_index;
        integer bit_in_byte;

        RST = 1'b1;
        IS_POS = 1'b1;
        IS_TRAIN = 1'b0;
        AERIN_ADDR = 12'd0;
        AERIN_REQ = 1'b0;
        completed_samples = 0;
        input_events_this_sample = 0;
        accepted_tsteps_this_sample = 0;
        output_spikes_this_sample = 0;
        AEROUT_REQ_d = 1'b0;
        // Top_test keeps the original SPI block internally. It is unused in
        // this direct-AER regression, so hold its pins at known idle values.
        dut.SCK = 1'b0;
        dut.MOSI = 1'b0;

        repeat (5) @(posedge CLK);
        @(negedge CLK);
        RST = 1'b0;

        for (sample_index = 0; sample_index < SAMPLE_COUNT; sample_index = sample_index + 1) begin
            for (time_index = 0; time_index < TIME_STEPS; time_index = time_index + 1) begin
                for (pixel_index = 0; pixel_index < INPUT_NEURONS; pixel_index = pixel_index + 1) begin
                    flat_bit_index = (sample_index * TIME_STEPS + time_index)
                                   * INPUT_NEURONS + pixel_index;
                    byte_index = flat_bit_index / 8;
                    bit_in_byte = 7 - (flat_bit_index % 8);
                    if (spike_bytes[byte_index][bit_in_byte])
                        send_aer_event({2'b00, pixel_index[9:0]});
                end
                send_aer_event({2'b01, 10'd0});
            end

            wait (completed_samples == sample_index + 1);
            $display("Sample %0d PROCESS_DONE observed; starting next sample.",
                     sample_index + 1);
        end

        repeat (10) @(posedge CLK);
        if (completed_samples != SAMPLE_COUNT)
            $fatal(1, "Expected %0d completed samples, got %0d",
                   SAMPLE_COUNT, completed_samples);
        $display("PASS: inference mode completed %0d samples with IS_TRAIN=%b.",
                 completed_samples, IS_TRAIN);
        $finish;
    end

    task automatic send_aer_event(input logic [11:0] event_addr);
        begin
            while (AERIN_ACK) @(posedge CLK);
            @(negedge CLK);
            AERIN_ADDR = event_addr;
            AERIN_REQ = 1'b1;
            while (!AERIN_ACK) @(posedge CLK);
            @(negedge CLK);
            AERIN_REQ = 1'b0;
            while (AERIN_ACK) @(posedge CLK);
        end
    endtask
endmodule
