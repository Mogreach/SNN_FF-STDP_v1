#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$script_dir"
mkdir -p build_axi_test

iverilog -g2012 -Wall \
  -s tb_axi4_rw_test_v1_0 \
  -f axi_snn_filelist.f \
  -o build_axi_test/tb_axi4_rw_test_v1_0_M_AXI.vvp

vvp build_axi_test/tb_axi4_rw_test_v1_0_M_AXI.vvp \
  | tee build_axi_test/tb_axi4_rw_test_v1_0_M_AXI.log
