#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$script_dir"
mkdir -p build_core_test

iverilog -g2012 -Wall \
  -s tb_core_test \
  -f core_test_filelist.f \
  -o build_core_test/tb_core_test.vvp

vvp build_core_test/tb_core_test.vvp \
  | tee build_core_test/tb_core_test.log
